"""The comparison must expose drift and must not turn tool errors into rejection."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from runner.comparison import sha, validate_corpus, request_for, run_pair, summarize, outcome
from runner.evaluator import HarnessError, Result
from scripts.compare_forks import checkout, resolve
from scripts.comparison_corpus import transaction_cases


def corpus(expected=True):
    digest = sha(b"\x51")
    return dict(schema=1, programs={digest: "51"}, contracts={"full": dict(sha256=digest)}, cases=[
        dict(id="small", command="evalscript", expected=expected, contract="full",
             request=dict(protocol=1, sigversion="tapscript_v2", stack=[], varops_budget=10000))])


def fake_sample(binary, command, request, observe):
    consumed = 12 if binary == "new" else 10
    return (dict(classification="accept", consumed=consumed, allowance=10000,
                 errors=[], stack=[], program_bytes=1),
            dict(profile=dict(interpreter_ns=100 if observe else 50)))


def fake_native(script, stack, budget, *, binary):
    consumed = 12 if binary == "new" else 10
    return Result(True, None, [], budget - consumed, consumed, 0.1)


class ComparisonContracts(unittest.TestCase):
    def test_extra_witness_keeps_original_signature_size(self):
        rows = {row["id"]: row for row in transaction_cases(
            Path(__file__).resolve().parents[1], committed=True)}
        checked = 0
        for name, row in rows.items():
            if not name.endswith("/extra-witness"):
                continue
            spend = "spends/" + name.removeprefix("rejections/").removesuffix("/extra-witness")
            self.assertEqual(row["artifacts"]["signature_bytes"],
                             rows[spend]["artifacts"]["signature_bytes"])
            self.assertGreater(row["artifacts"]["weight"], rows[spend]["artifacts"]["weight"])
            checked += 1
        self.assertEqual(checked, 8)

    def test_bytes_and_inventory_are_checked(self):
        original = corpus()
        self.assertEqual(validate_corpus(original), {"small"})
        self.assertEqual(request_for(original, original["cases"][0])["script"], "51")
        changed = copy.deepcopy(original)
        changed["programs"][sha(b"\x51")] = "00"
        with self.assertRaisesRegex(ValueError, "digest"):
            validate_corpus(changed)
        changed = copy.deepcopy(original)
        changed["cases"].append(changed["cases"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_corpus(changed)
        changed = copy.deepcopy(original)
        changed["cases"][0]["id"] = "replacement"
        with self.assertRaisesRegex(ValueError, "inventory"):
            run_pair({}, {}, original, changed)

    def test_accounting_changes_are_separate_from_acceptance(self):
        with patch("runner.comparison.sample", side_effect=fake_sample), patch(
            "runner.comparison.evaluate", side_effect=fake_native
        ):
            rows = run_pair(dict(profile="old", native="old"), dict(profile="new", native="new"), corpus(), corpus())
        self.assertEqual(rows[0]["accounting_delta"], 2)
        self.assertEqual(summarize(rows)["accounting_changes"], 1)
        self.assertEqual(summarize(rows)["acceptance_changes"], 0)
        self.assertEqual(summarize(rows)["candidate_unexpected"], 0)
        self.assertEqual(rows[0]["timing_ratio"], 1)

    def test_unexpected_acceptance_does_not_pass_negative_case(self):
        with patch("runner.comparison.sample", side_effect=fake_sample), patch(
            "runner.comparison.evaluate", side_effect=fake_native
        ):
            rows = run_pair(dict(profile="old", native="old"), dict(profile="old", native="old"), corpus(False), corpus(False))
        self.assertEqual(summarize(rows)["baseline_unexpected"], 1)
        self.assertEqual(summarize(rows)["candidate_unexpected"], 1)

    def test_budget_exhaustion_is_not_an_expected_rejection(self):
        for error, expected in (("Varops budget exceeded", "budget"),
                                ("unrelated budget message", "reject")):
            with self.subTest(error=error):
                native_result = Result(False, error, [], 0, 10000, 0.1)
                self.assertEqual(native_result.classification, expected)
                standalone = outcome("evalscript", {"varops_budget": 10000, "script": "51"},
                    {"success": False, "error": error, "varops-budget-remaining": 0, "stack-after": []})
                transaction = outcome("measuretx", {"transaction": "00"},
                    {"success": False, "inputs": [{"success": False, "error": error}],
                     "varops_consumed": 10000, "varops_allowed": 10000, "weight": 1})
                self.assertEqual(standalone["classification"], expected)
                self.assertEqual(transaction["classification"], expected)

        def exhausted(*args):
            result, response = fake_sample(*args)
            result.update(classification="budget", errors=["Varops budget exceeded"], consumed=10000)
            return result, response
        native = Result(False, "Varops budget exceeded", [], 0, 10000, 0.1)
        with patch("runner.comparison.sample", side_effect=exhausted), patch(
            "runner.comparison.evaluate", return_value=native
        ):
            rows = run_pair(dict(profile="old", native="old"), dict(profile="old", native="old"), corpus(False), corpus(False))
        self.assertEqual(summarize(rows)["candidate_unexpected"], 1)

    def test_process_failure_remains_failure(self):
        with patch("runner.comparison.sample", side_effect=HarnessError("process failed")):
            with self.assertRaises(HarnessError):
                run_pair(dict(profile="old"), dict(profile="new"), corpus(False), corpus(False))

    def test_native_disagreement_is_not_a_measurement(self):
        with patch("runner.comparison.sample", side_effect=fake_sample), patch(
            "runner.comparison.evaluate", return_value=Result(True, None, [], 9991, 9, 0)
        ):
            with self.assertRaisesRegex(HarnessError, "disagreement"):
                run_pair(dict(profile="old", native="old"), dict(profile="new", native="new"), corpus(), corpus())

    def test_checkout_accepts_empty_gitlink_directory_and_pins_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / "source", root / "target"
            source.mkdir()
            subprocess.run(["git", "init", "-q", source], check=True)
            (source / "marker").write_text("first")
            subprocess.run(["git", "-C", source, "add", "marker"], check=True)
            subprocess.run(["git", "-C", source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "fixture"], check=True)
            revision = resolve(source, "HEAD")
            target.mkdir()
            checkout(source, revision, target, root / "log")
            self.assertEqual(resolve(target, "HEAD"), revision)
            self.assertEqual((target / "marker").read_text(), "first")
            with patch("scripts.compare_forks.subprocess.check_output", wraps=subprocess.check_output) as check:
                self.assertEqual(resolve(source, "HEAD"), revision)
                self.assertIn("--end-of-options", check.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
