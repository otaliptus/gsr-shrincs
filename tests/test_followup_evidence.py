"""Stale inputs and misleading follow-up results must fail the audit."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runner.evidence import provenance, verify_provenance, value_sha
from runner.followup import validate_parsing, validate_multi, multi_corpus
from scripts.multi_compare import programs, OUTPUT_COUNTS


class FollowupEvidence(unittest.TestCase):
    def test_input_binary_driver_and_environment_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ("reports/input.json", "build/tool", "runner/driver.py")
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("original")
            record = provenance(root, [names[0]], [names[1]])
            environment = dict(record["environment"], binaries=dict(record["binaries"]))
            verify_provenance(root, record, [names[0]], [names[1]], environment)
            for name in names:
                with self.subTest(file=name):
                    (root / name).write_text("changed")
                    with self.assertRaises(ValueError):
                        verify_provenance(root, record, [names[0]], [names[1]], environment)
                    (root / name).write_text("original")
            incomplete = copy.deepcopy(record)
            incomplete["inputs"].clear()
            with self.assertRaisesRegex(ValueError, "inventory"):
                verify_provenance(root, incomplete, [names[0]], [names[1]], environment)
            environment["binaries"][names[1]] = "different"
            with self.assertRaisesRegex(ValueError, "environment"):
                verify_provenance(root, record, [names[0]], [names[1]], environment)
            environment["binaries"] = dict(record["binaries"])
            (root / names[1]).unlink()
            verify_provenance(root, record, [names[0]], [names[1]], environment, check_binaries=False)
            with patch("runner.evidence.host_environment", return_value=dict(platform="another OS", machine="another CPU", python="another Python")):
                verify_provenance(root, record, [names[0]], [names[1]], environment, check_binaries=False)
            with self.assertRaises(FileNotFoundError):
                verify_provenance(root, record, [names[0]], [names[1]], environment)
            (root / names[0]).write_text("stale input")
            with self.assertRaisesRegex(ValueError, "inputs"):
                verify_provenance(root, record, [names[0]], [names[1]], environment, check_binaries=False)

    def test_parsing_accounting_schedule_and_samples(self):
        counters = dict(parsed_bytes=1, parsed_instructions=1, skipped_bytes=0, skipped_instructions=0, skipped_push_bytes=0)
        schedule = [dict(script="51", calls=1)]
        counts = dict(rows=[dict(name="one", counts=counters, result=dict(classification="accept", consumed=5, allowance=10, weight=1))])
        benchmark = dict(passes=16, repeats=1, rows=[dict(name="one", counts=counters,
            schedule_sha256=value_sha(schedule), samples_ns={v: [1] for v in ("with_payload_copy", "without_payload_copy")},
            median_ns={v: 1 for v in ("with_payload_copy", "without_payload_copy")})])
        costs = dict(transactions=[dict(name="one", varops_consumed=5, varops_allowed=10, weight=1)])
        spends = [dict(name="one")]
        with patch("runner.followup.schedule_for", return_value=schedule):
            validate_parsing(counts, benchmark, spends, costs)
            changed = copy.deepcopy(costs)
            changed["transactions"][0]["varops_consumed"] = 6
            with self.assertRaisesRegex(ValueError, "accounting"):
                validate_parsing(counts, benchmark, spends, changed)
            changed = copy.deepcopy(benchmark)
            changed["rows"][0]["schedule_sha256"] = "old"
            with self.assertRaisesRegex(ValueError, "schedule"):
                validate_parsing(counts, changed, spends, costs)
            changed = copy.deepcopy(benchmark)
            changed["rows"][0]["median_ns"]["with_payload_copy"] = 2
            with self.assertRaisesRegex(ValueError, "median"):
                validate_parsing(counts, changed, spends, costs)
            with self.assertRaisesRegex(ValueError, "inventory"):
                validate_parsing(dict(rows=[]), benchmark, spends, costs)

    def test_multi_corpus_and_negative_outcomes(self):
        codes = programs()
        data = dict(programs={name: code.hex() for name, code in codes.items()},
                    corpus_sha256=value_sha(multi_corpus(codes)), repeats=1, rows=[])
        for name, code in codes.items():
            for count in OUTPUT_COUNTS:
                data["rows"].append(dict(construction=name, output_count=count, script_bytes=len(code),
                    script_sha256=hashlib.sha256(code).hexdigest(), result=dict(classification="accept", consumed=1, allowance=2),
                    negative_results={case: dict(classification="reject", errors=["Script failed"])
                                      for case in ("wrong_sum", "over_limit", "empty")}, times_ns=[1], median_ns=1))
        validate_multi(data)
        changed = copy.deepcopy(data)
        changed["corpus_sha256"] = "old"
        with self.assertRaisesRegex(ValueError, "corpus"):
            validate_multi(changed)
        for classification, errors in (("accept", []), ("budget", ["Varops budget exceeded"]),
                                       ("reject", ["Varops budget exceeded"])):
            changed = copy.deepcopy(data)
            changed["rows"][0]["negative_results"]["wrong_sum"] = dict(classification=classification, errors=errors)
            with self.subTest(classification=classification), self.assertRaisesRegex(ValueError, "semantically"):
                validate_multi(changed)


if __name__ == "__main__":
    unittest.main()
