#!/usr/bin/env python3
"""Persist local component costs from the existing independent agreement tests.

The contract harness includes expected-output comparison and clean-stack cleanup;
these are not isolated intrinsic opcode prices or full-policy estimates.
"""
from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from runner.checks import require
import test_verifier as suite
from runner.evaluator import evaluate, DEFAULT_BINARY


def main():
    rows = []
    active = {}
    test_name = ""
    old_component = suite.component

    def component(inputs, build, values, expected, profile):
        active.update(
            profile=profile, inputs=list(inputs), expected_width=len(expected)
        )
        try:
            return old_component(inputs, build, values, expected, profile)
        finally:
            active.clear()

    def observed(code, stack=(), budget=1_000_000_000, **kwargs):
        result = evaluate(code, stack, budget, **kwargs)
        if active:
            rows.append(
                dict(
                    active,
                    test=test_name,
                    script_bytes=len(code),
                    script_sha256=hashlib.sha256(code).hexdigest(),
                    input_bytes=[len(x) for x in stack],
                    input_sha256=hashlib.sha256(b"".join(stack)).hexdigest(),
                    accepted=result.success,
                    varops_consumed=result.consumed,
                    cli_seconds=result.elapsed_seconds,
                )
            )
        return result

    class Result(unittest.TextTestResult):
        def startTest(self, test):
            nonlocal test_name
            test_name = test.id()
            super().startTest(test)

    suite.component = component
    suite.evaluate = observed
    tests = unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (
            suite.Components,
            suite.HashAndWotsAgreement,
            suite.StatelessComponents,
        )
    )
    result = unittest.TextTestRunner(resultclass=Result, verbosity=1).run(tests)
    if not result.wasSuccessful():
        raise SystemExit(1)
    require(rows and all(row["accepted"] for row in rows))
    data = dict(
        measurement_scope="Component agreement harness including expected-output comparison and cleanup",
        evaluator_sha256=hashlib.sha256(DEFAULT_BINARY.read_bytes()).hexdigest(),
        cases=len(rows),
        rows=rows,
    )
    (ROOT / "reports/components.json").write_text(json.dumps(data, indent=2) + "\n")
    print(f"Recorded {len(rows)} component cost measurements")


if __name__ == "__main__":
    main()
