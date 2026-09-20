"""Run separately from the frozen baseline test inventory."""
import copy
import json
import unittest

import run


class ComparisonTests(unittest.TestCase):
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
