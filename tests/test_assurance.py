"""Regression coverage for the review's tooling and compiler-contract findings."""

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from generator.script import Builder, Library, Ref, op
from runner.evaluator import evaluate, HarnessError, ROOT
from runner.profile import run_profile
from scripts import profile_build


class CompilerContracts(unittest.TestCase):
    def test_conflicting_definitions_and_recovery(self):
        library = Library()

        def increment(amount):
            return lambda b: b.finish(op("ADD", Ref("x"), amount))

        fid = library.define("increment", ("x",), increment(1))
        self.assertEqual(fid, library.define("increment", ("x",), increment(1)))
        original = library.functions.copy()
        for inputs, body in ((("x",), increment(2)), (("x", "unused"), increment(1))):
            with self.assertRaisesRegex(ValueError, "conflicting definition"):
                library.define("increment", inputs, body)
            self.assertEqual(original, library.functions)
            self.assertEqual(set(), library.active)
        with self.assertRaisesRegex(ValueError, "one result"):
            library.define("unfinished", ("x",), lambda b: None)
        self.assertNotIn("unfinished", library.functions)
        self.assertEqual(1, library.define("constant", (), lambda b: b.finish(1)))

        def recursive(b):
            library.define("recursive", (), recursive)

        with self.assertRaisesRegex(ValueError, "recursive"):
            library.define("recursive", (), recursive)
        self.assertEqual(set(), library.active)

    def test_arity_and_zero_argument_stack_preservation(self):
        for profile, inline in (("full", False), ("full", True), ("baseline", False)):
            library = Library(inline=inline)
            builder = Builder(("outer",), profile, library)
            for args in ((), (1, 2)):
                with self.assertRaisesRegex(ValueError, "expected 1 arguments"):
                    builder.call(
                        "identity", ("x",), lambda b: b.finish(Ref("x")), args, "out"
                    )
                self.assertEqual(builder.stack, ["outer"])
                self.assertEqual(builder.code, b"")
                self.assertEqual(library.functions, {})
            value = builder.call("constant", (), lambda b: b.finish(7), (), "out")
            builder.finish(op("EQUAL", op("ADD", Ref("outer"), value), 10))
            prefix = library.prefix() if profile == "full" and not inline else b""
            self.assertTrue(evaluate(prefix + bytes(builder.code), [b"\x03"]).success)
            with self.assertRaisesRegex(ValueError, "one result"):
                Builder((), profile, library).call("bad", (), lambda b: None, (), "out")

    def test_expression_contracts(self):
        for expr in (op("ADD", 1), op("SHA256", 1, 2), op("DROP", 1), op("DUP", 1)):
            builder = Builder()
            with self.assertRaisesRegex(ValueError, "expression contract"):
                builder.expr(expr)
            self.assertEqual(builder.code, b"")


class EvidenceContracts(unittest.TestCase):
    def test_script_entrypoint_imports(self):
        # An installed/importable package can mask a broken direct-script path.
        # Isolate Python's search path and import each entry point without main().
        with tempfile.TemporaryDirectory() as directory:
            for script in sorted((ROOT / "scripts").glob("*.py")):
                flags = ["-I"] + (["-O"] if sys.flags.optimize else [])
                result = subprocess.run(
                    [
                        sys.executable,
                        *flags,
                        "-c",
                        "import runpy,sys; runpy.run_path(sys.argv[1], run_name='preflight')",
                        str(script),
                    ],
                    cwd=directory,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, (script.name, result.stderr))

    def test_overlay_refresh_removal_tampering_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "vendor", root / "build/profile-source"
            for name in ("src/script/interpreter.cpp", "src/bitcoin-util.cpp"):
                destination = source / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(profile_build.SOURCE / name, destination)
            for name in (
                "scripts/profile_build.py",
                "runner/profile.hpp",
                "runner/measuretx.inc",
            ):
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, destination)
            (source / "marker").write_text("revision A")
            with patch.multiple(profile_build, ROOT=root, SOURCE=source, TARGET=target):
                profile_build.prepare()
                (source / "marker").write_text("revision B")
                (source / "added").write_text("new file")
                (target / "unexpected").write_text("stale cache file")
                profile_build.prepare()
                self.assertEqual((target / "marker").read_text(), "revision B")
                self.assertEqual((target / "added").read_text(), "new file")
                self.assertFalse((target / "unexpected").exists())
                (source / "added").unlink()
                profile_build.prepare()
                self.assertFalse((target / "added").exists())
                timestamps = {
                    name: p.stat().st_mtime_ns
                    for name, p in profile_build.source_files(target).items()
                }
                profile_build.prepare()
                self.assertEqual(
                    timestamps,
                    {
                        name: p.stat().st_mtime_ns
                        for name, p in profile_build.source_files(target).items()
                    },
                )
                (target / "marker").write_text("tampered")
                with self.assertRaisesRegex(RuntimeError, "modified profiling"):
                    profile_build.verify_overlay()
                profile_build.prepare()
                profile_build.verify_overlay()

    def test_audit_rejects_stale_evidence_under_optimization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reports").mkdir()
            (root / "marker").write_text("new")
            (root / "reports/environment.json").write_text(
                json.dumps({"sources_sha256": {"marker": "old"}})
            )
            code = "from pathlib import Path; from scripts import audit; import sys; audit.ROOT=Path(sys.argv[1]); audit.main()"
            result = subprocess.run(
                [sys.executable, "-O", "-c", code, directory],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stale source", result.stderr)
            self.assertFalse((root / "reports/audit.json").exists())

    def test_profile_response_contracts(self):
        request = dict(
            protocol=1,
            sigversion="tapscript_v2",
            script="51",
            stack=[],
            varops_budget=1000000,
            profile=True,
        )
        valid = run_profile("evalscript", request)
        for field, value in (
            ("protocol", True),
            ("success", 1),
            ("context", "wrong"),
            ("varops-budget-remaining", -1),
            ("stack-after", [False]),
        ):
            response = copy.deepcopy(valid)
            response[field] = value
            process = subprocess.CompletedProcess([], 0, json.dumps(response), "")
            with patch("runner.profile.subprocess.run", return_value=process):
                with self.assertRaises(HarnessError):
                    run_profile("evalscript", request)
        for value in (True, -1, "10"):
            response = copy.deepcopy(valid)
            response["profile"]["interpreter_ns"] = value
            with patch(
                "runner.profile.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    [], 0, json.dumps(response), ""
                ),
            ):
                with self.assertRaises(HarnessError):
                    run_profile("evalscript", request)


class AdditionalRelationCoverage(unittest.TestCase):
    def test_interior_indices(self):
        from generator.verifier import compile_verifier
        from reference.oracle import synthetic_stateful, decode

        programs = [
            compile_verifier(profile).code for profile in ("baseline", "bytes", "full")
        ]
        for depth in (7, 8, 9, 31, 32, 63, 64, 65, 255):
            index = 0xA53C19E70B824D6F & (2 ** min(depth, 64) - 1)
            args = decode(synthetic_stateful(depth, index))
            for program in programs:
                self.assertTrue(evaluate(program, args).success)

    def test_valid_contexts(self):
        from generator.verifier import compile_verifier
        from reference.oracle import scheme, PUBLIC_SEED, deterministic

        key, pk = scheme.shrincs_keygen(PUBLIC_SEED, b"\x01\x04")
        for state, context in enumerate((b"", b"\x00\x80\xff", bytes(range(255)))):
            message = deterministic(f"context/{state}", 32)
            for mode, counter in (("stateful", state), ("stateless", None)):
                signature = scheme.shrincs_sign(message, context, key, counter, None)
                self.assertTrue(scheme.shrincs_verify(message, signature, context, pk))
                for profile in ("baseline", "bytes", "full"):
                    for leaf in (mode, "unified"):
                        code = compile_verifier(profile, leaf, context).code
                        self.assertTrue(
                            evaluate(code, (signature, pk, message)).success
                        )

    def test_compact_stateful_transaction_budgets(self):
        from generator.transaction import compile_policy
        from reference.oracle import synthetic_stateful, decode
        from runner.bitcoin import NUMS_XONLY, control_block, message
        from test_framework.messages import (
            CTransaction,
            COutPoint,
            CTxIn,
            CTxOut,
            CTxInWitness,
        )
        from test_framework.script import (
            CScript,
            taproot_construct,
            LEAF_VERSION_TAPSCRIPT_V2,
        )

        # Actual serialized weight and transaction-aware checking, without padding.
        # Synthetic roots/paths are explicitly used, just as in the depth corpus.
        for depth in (1, 8, 63, 64, 65, 127, 128, 129, 255):
            for index in (0, 2 ** min(depth, 64) - 1):
                _, pk, _ = decode(synthetic_stateful(depth, index))
                code = compile_policy(pk, mode="stateful").code
                tap = taproot_construct(
                    NUMS_XONLY, [("verify", CScript(code), LEAF_VERSION_TAPSCRIPT_V2)]
                )
                tx = CTransaction()
                tx.version = 2
                tx.vin = [CTxIn(COutPoint(1, 0), CScript(), 0xFFFFFFFE)]
                tx.vout = [CTxOut(49000000, CScript(b"\x51"))]
                spent = [CTxOut(50000000, tap.scriptPubKey)]
                signature, new_pk, _ = decode(
                    synthetic_stateful(
                        depth, index, message=message(tx, spent, 0, code)
                    )
                )
                self.assertEqual(pk, new_pk)
                tx.wit.vtxinwit = [CTxInWitness()]
                tx.wit.vtxinwit[0].scriptWitness.stack = [
                    signature,
                    code,
                    control_block(tap, "verify"),
                ]
                result = run_profile(
                    "measuretx",
                    dict(
                        transaction=tx.serialize().hex(),
                        spent_outputs=[item.serialize().hex() for item in spent],
                        profile=True,
                    ),
                )
                self.assertTrue(result["success"], (depth, index, result))
                self.assertEqual(result["varops_allowed"], tx.get_weight() * 10000)
                self.assertLessEqual(
                    result["varops_consumed"], result["varops_allowed"]
                )
