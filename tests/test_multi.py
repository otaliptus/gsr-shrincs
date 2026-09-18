"""The OP_MULTI extension must agree with the audited verifier and leave it untouched."""
import json
import unittest

from generator import multi
from generator.script import OPS, push
from generator.verifier import compile_verifier
from reference.oracle import ROOT, decode, verify
from runner.evaluator import evaluate


class MultiExtension(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads((ROOT / "fixtures/vectors.json").read_text())["vectors"]
        cls.audited = compile_verifier("full").code

    def test_variants_agree_and_use_multi_only_when_asked(self):
        selected = [self.vectors[0], next(v for v in self.vectors if bytes.fromhex(v["signature"])[0] == 255)]
        for name in ("catfix", "multi", "multisel"):
            program = multi.compile_verifier(name)
            uses = multi.multi_uses(program.code, [v[1] for v in program.functions.values()])
            self.assertEqual(bool(uses), name != "catfix", name)
            if name == "multisel":
                self.assertEqual(set(uses), {"SHA256"})
            self.assertLess(len(program.code), len(self.audited), name)
            for vector in selected:
                sig, pk, msg = decode(vector)
                context = bytes.fromhex(vector["context"])
                for args in ((sig, pk, msg), (sig, pk, bytes([msg[0] ^ 1]) + msg[1:]), (sig[:-1], pk, msg)):
                    expected = verify(args[2], args[0], args[1], context)
                    result = evaluate(program.code, args)
                    self.assertNotEqual(result.classification, "budget")
                    self.assertEqual(result.success, expected, (name, vector["name"]))
                    if result.success:
                        self.assertEqual(result.stack, [])

    def test_extension_leaves_audited_compiler_unchanged(self):
        multi.compile_verifier("multi")
        self.assertEqual(compile_verifier("full").code, self.audited)


class SelectionRule(unittest.TestCase):
    def test_rule_matches_evaluator_on_both_sides_of_the_line(self):
        def chained(sizes):
            code = b"".join(push(bytes(n)) for n in sizes) + bytes([OPS["CAT"]]) * (len(sizes) - 1) + bytes([OPS["SHA256"]])
            return evaluate(code + bytes([OPS["DROP"]]) + b"\x51").consumed

        def multi_hash(sizes):
            code = b"".join(push(bytes(n)) for n in sizes) + push(len(sizes)) + bytes([OPS["MULTI"], OPS["SHA256"]])
            return evaluate(code + bytes([OPS["DROP"]]) + b"\x51").consumed

        for sizes in ((83, 84, 83), (86, 86, 86), (100, 100, 100, 100), (16,) * 17, (16, 16, 16), (64, 22, 512)):
            intermediate = sum(sum(sizes[:k + 1]) for k in range(1, len(sizes)))
            predicted = multi.multi_sha_is_cheaper(intermediate, len(sizes))
            self.assertEqual(predicted, multi_hash(sizes) < chained(sizes), sizes)
