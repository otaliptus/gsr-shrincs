#!/usr/bin/env python3
"""Bind structured successful test results to sources, fixtures and executable."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.checks import require
from scripts.run_tests import discover, test_ids


def validate_results(kind):
    results = ROOT / f"reports/tests-{kind}-results.json"
    record = json.loads(results.read_text())
    expected = sorted(test_ids(discover()))
    require(bool(expected) and record["test_ids"] == expected, "test coverage changed")
    require(
        record["success"] is True and record["tests_run"] == len(expected),
        "incomplete test run",
    )
    require(
        not any(record[key] for key in ("skipped", "failures", "errors")),
        "unsuccessful test run",
    )
    require(
        record["optimization"] == (1 if kind == "optimized" else 0),
        "wrong optimization mode",
    )
    return results


def main():
    kind = sys.argv[1]
    require(kind in ("native", "profiled", "optimized"), "unknown test run")
    results = validate_results(kind)
    log = ROOT / (
        "reports/tests.log" if kind == "native" else f"reports/tests-{kind}.log"
    )
    binary = ROOT / (
        "build/profile/bin/bitcoin-util"
        if kind == "profiled"
        else "build/bitcoin/bin/bitcoin-util"
    )
    files = [
        p
        for d in ("generator", "runner", "reference", "tests", "scripts")
        for p in (ROOT / d).rglob("*")
        if p.is_file() and "__pycache__" not in str(p)
    ]
    files += [ROOT / "fixtures/vectors.json", binary, log, results]
    record = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(files)
    }
    (ROOT / f"reports/tests-{kind}-provenance.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
