"""Run separately from the frozen baseline test inventory."""
import copy
import json
import unittest
from unittest.mock import patch

import run


class ComparisonTests(unittest.TestCase):
    def test_preprocessor_selection(self):
        with patch.dict(run.os.environ, {"CPP": "clang-18 -DPORTABLE=1"}), patch.object(run.shutil, "which", return_value="/usr/bin/clang-18"):
            self.assertEqual(run.preprocessor(), ["clang-18", "-DPORTABLE=1"])
        for available in ("clang-18", "cc", "cpp"):
            with patch.dict(run.os.environ, {"CPP": ""}), patch.object(run.shutil, "which", side_effect=lambda name: name if name == available else None):
                self.assertEqual(run.preprocessor(), [available])
        with patch.dict(run.os.environ, {"CPP": "missing-compiler"}), patch.object(run.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "CPP executable"):
                run.preprocessor()

    def test_multi_cost_and_compiler_isolation(self):
        from generator import multi, script
        for mode in run.MODES:
            proof = run.ref.load_fixture(run.HERE / f"fixtures/{mode}.wit")
            plain = run.gsr.compile_verifier(mode, "catfix")
            old_builder, old_widths = script.Builder, multi.KNOWN_WIDTHS.copy()
            costs = {}
            for profile in ("catfix", "multi", "multisel"):
                program = run.gsr.compile_verifier(mode, profile)
                result = run.evaluate(program.code, run.ref.stack(proof))
                self.assertTrue(result.success)
                costs[profile] = result.consumed
                if profile != "catfix":
                    uses = multi.multi_uses(program.code, [v[1] for v in program.functions.values()])
                    self.assertGreater(uses.get("SHA256", 0), 0)
                    if profile == "multisel":
                        self.assertEqual(set(uses), {"SHA256"})
                self.assertIs(script.Builder, old_builder)
                self.assertEqual(multi.KNOWN_WIDTHS, old_widths)
            self.assertLess(costs["multisel"], costs["catfix"])
            self.assertEqual(run.gsr.compile_verifier(mode, "catfix").code, plain.code)

    def test_original_fixtures_and_witness_round_trip(self):
        for mode in run.MODES:
            fixture = run.HERE / f"fixtures/{mode}.wit"
            document = json.loads(fixture.read_text())
            proof = run.ref.load_fixture(fixture)
            self.assertTrue(run.ref.verify(proof))
            encoded = run.ref.witness_json(proof, document["PROOF"]["type"])
            self.assertEqual(proof, run.ref.parse_value(encoded["PROOF"]["value"]))

    def test_unused_stateless_randomizers_stay_unused(self):
        proof = run.ref.load_fixture(run.HERE / "fixtures/stateless.wit")
        for layer in range(2):
            changed = copy.deepcopy(proof)
            changed[2]["Right"][1][layer][0][0] ^= 2**255
            self.assertTrue(run.ref.verify(changed))
            for profile in run.PROFILES:
                program = run.gsr.compile_verifier("stateless", profile)
                self.assertTrue(run.evaluate(program.code, run.ref.stack(changed)).success)

    def test_gsr_rejects_malformed_field_lengths(self):
        for mode in run.MODES:
            proof = run.ref.load_fixture(run.HERE / f"fixtures/{mode}.wit")
            fields = run.ref.stack(proof)
            for profile in run.PROFILES:
                program = run.gsr.compile_verifier(mode, profile)
                for field in range(4):
                    for delta in (-1, 1):
                        changed = fields.copy()
                        changed[field] = fields[field][:-1] if delta == -1 else fields[field] + b"\0"
                        result = run.evaluate(program.code, changed)
                        self.assertEqual(result.classification, "reject", (mode, profile, field, delta))

    def test_case_names_and_mutations_are_distinct(self):
        for mode in run.MODES:
            proof = run.ref.load_fixture(run.HERE / f"fixtures/{mode}.wit")
            inputs = list(run.cases(proof))
            self.assertEqual(len(inputs), len({name for name, _ in inputs}))
            self.assertEqual(len(inputs), len({run.value_sha(p) for _, p in inputs}))
            self.assertGreater(len(inputs), 100)


if __name__ == "__main__":
    unittest.main()
