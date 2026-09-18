#!/usr/bin/env python3
"""Run the discovered suite and persist structured coverage, including failures."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


def discover():
    return unittest.defaultTestLoader.discover(
        str(ROOT / "tests"), top_level_dir=str(ROOT)
    )


def main():
    kind = sys.argv[1]
    if kind not in ("native", "profiled", "optimized"):
        raise SystemExit("expected native, profiled, or optimized")
    suite = discover()
    ids = sorted(test_ids(suite))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = dict(
        test_ids=ids,
        tests_run=result.testsRun,
        success=result.wasSuccessful() and not result.skipped,
        skipped=[test.id() for test, _ in result.skipped],
        failures=[test.id() for test, _ in result.failures],
        errors=[test.id() for test, _ in result.errors],
        optimization=sys.flags.optimize,
    )
    (ROOT / f"reports/tests-{kind}-results.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    if not record["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
