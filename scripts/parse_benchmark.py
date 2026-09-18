#!/usr/bin/env python3
"""Replay parser work from valid SHRINCS spends; do not synthesize stress scripts."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from generator.transaction import compile_policy
from runner.bitcoin import NUMS_XONLY  # Loads the pinned transaction decoding module.
from scripts.parsing_probe import prepare, build_probe
from scripts.profile_build import replace_once, hashes
from runner.evidence import CORPUS, COSTS, COUNTS, provenance, verify_provenance, host_environment, value_sha, sha
from test_framework.messages import tx_from_hex


def schedule_for(row, measurements):
    tx = tx_from_hex(row["raw_transaction"])
    program = compile_policy(bytes.fromhex(row["public_key"]),
                             profile=row.get("profile", "full"), mode=row.get("mode", "unified"),
                             max_inputs=row.get("max_inputs", 4 if len(tx.vin) > 1 else 1))
    schedule = []
    for item in tx.wit.vtxinwit:
        code = item.scriptWitness.stack[-2]
        if code != program.code:
            raise ValueError("recorded policy differs from reconstructed program")
        schedule.append(dict(script=code.hex(), calls=1))
    bodies = {str(fid): code for fid, code, _ in program.functions.values()}
    for fid, count in measurements["metrics"]["function_calls"].items():
        schedule.append(dict(script=bodies[fid].hex(), calls=count))
    return schedule


def run(binary, schedule, copy_data, passes=16):
    request = dict(schedule=schedule, copy_data=copy_data, passes=passes)
    process = subprocess.run([str(binary), "parsebench"], input=json.dumps(request), text=True,
                             capture_output=True, check=True, timeout=30)
    result = json.loads(process.stdout)
    if result.get("protocol") != 1 or result.get("context") != "isolated-parser-benchmark":
        raise ValueError("bad parser-benchmark response")
    if result["passes"] != passes or result["copy_data"] is not copy_data:
        raise ValueError("wrong parser-benchmark configuration")
    expected_bytes = sum(len(bytes.fromhex(row["script"])) * row["calls"] for row in schedule)
    if result["bytes_per_pass"] != expected_bytes:
        raise ValueError("wrong parser schedule")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-root", type=Path, default=ROOT / "build/parser-benchmark")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/parser-benchmark.json")
    parser.add_argument("--repeats", type=int, default=21)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.repeats < 1 or args.jobs < 1:
        parser.error("repeats and jobs must be positive")
    probe = args.probe_root.resolve()
    if probe == ROOT or ROOT.is_relative_to(probe) or probe == ROOT / "build/parsing-probe":
        parser.error("benchmark needs its own build directory")
    probe.mkdir(parents=True, exist_ok=True)
    source = prepare(ROOT / "vendor/bitcoin", probe)
    util = source / "src/bitcoin-util.cpp"
    text = util.read_text()
    text = replace_once(text, "MAIN_FUNCTION\n{", (ROOT / "runner/parsebench.inc").read_text() + "\nMAIN_FUNCTION\n{")
    needle = '    argsman.AddCommand("measuretx", "Measure recorded transaction Script validation");'
    text = replace_once(text, needle, needle + '\n    argsman.AddCommand("parsebench", "Measure parsing of recorded valid programs");')
    needle = '        } else if (cmd->command == "measuretx") {'
    text = replace_once(text, needle, '        } else if (cmd->command == "parsebench") {\n            ret = ParseBenchCommand(cmd->args, strPrint);\n' + needle)
    util.write_text(text)
    source_hashes = hashes(source)
    binary = build_probe(source, probe, args.jobs)
    binary_names = [str(binary.relative_to(ROOT))]
    proof = provenance(ROOT, [CORPUS, COSTS, COUNTS], binary_names)
    records = json.loads(gzip.decompress((ROOT / "reports/regtest-details.json.gz").read_bytes()))
    costs = {r["name"]: r for r in json.loads((ROOT / "reports/costs.json").read_text())["transactions"]}
    counts = {r["name"]: r for r in json.loads((ROOT / "reports/parsing-counts.json").read_text())["rows"]}
    rows = []
    for row in records["spends"]:
        schedule = schedule_for(row, costs[row["name"]])
        expected = counts[row["name"]]["counts"]
        samples = {"with_payload_copy": [], "without_payload_copy": []}
        checksums = set()
        for repeat in range(args.repeats + 1):
            for copy_data in ((True, False) if repeat % 2 == 0 else (False, True)):
                result = run(binary, schedule, copy_data)
                if result["bytes_per_pass"] != expected["parsed_bytes"] or result["instructions"] != 16 * expected["parsed_instructions"]:
                    raise ValueError("isolated parser schedule differs from the measured interpreter work")
                checksums.add(result["checksum"])
                if repeat:
                    samples["with_payload_copy" if copy_data else "without_payload_copy"].append(result["elapsed_ns"] / 16)
        if len(checksums) != 1:
            raise ValueError("parser variants decoded different instructions")
        rows.append(dict(name=row["name"], schedule_sha256=value_sha(schedule),
                         counts=expected, samples_ns=samples,
                         median_ns={name: statistics.median(values) for name, values in samples.items()}))
    verify_provenance(ROOT, proof, [CORPUS, COSTS, COUNTS], binary_names)
    data = dict(rows=rows, provenance=proof, repeats=args.repeats, passes=16,
                build_cache_sha256=sha(probe / "build/CMakeCache.txt"),
                environment=dict(**host_environment(), host_load="not controlled"),
                binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(), source_files=source_hashes,
                driver_files={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
                    "scripts/parse_benchmark.py", "scripts/parsing_probe.py", "runner/parsebench.inc")},
                scope="Isolated parsing, not an interpreter optimization. No branch state, stack work, or signature verification. Reuses a payload buffer within a body; allocation behavior differs from execution. The no-copy pass approximates the separate success scan's decoding, without its success checks.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    for row in rows:
        print(row["name"], row["median_ns"])


if __name__ == "__main__":
    main()
