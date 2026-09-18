#!/usr/bin/env python3
"""Fail closed if packaged evidence is missing, stale, or inconsistent."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.checks import require
from runner.evaluator import is_budget_error
from generator.verifier import compile_verifier, CONTEXT
from generator.transaction import compile_policy
from reference.oracle import verify, decode
from runner.bitcoin import message
from test_framework.messages import tx_from_hex, CTxOut
import io
from scripts.export import program_artifacts
from scripts.profile_build import verify_build
from scripts.record_tests import validate_results


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    env = json.loads((ROOT / "reports/environment.json").read_text())
    for file, expected in env["sources_sha256"].items():
        require(sha(ROOT / file) == expected, ("stale source", file))
    for file, expected in env["binaries"].items():
        require(sha(ROOT / file) == expected, ("stale binary", file))
    require(sha(ROOT / "fixtures/vectors.json") == env["fixtures_sha256"])
    for key, path in (
        ("bitcoin", "vendor/bitcoin"),
        ("shrincs", "vendor/shrincs-spec"),
    ):
        pin = subprocess.check_output(
            ["git", "-C", str(ROOT / path), "rev-parse", "HEAD"], text=True
        ).strip()
        require(pin == env["versions"][key]["commit"])
        require(
            not subprocess.check_output(
                ["git", "-C", str(ROOT / path), "status", "--porcelain"], text=True
            )
        )
    verify_build()
    require(
        sha(ROOT / "build/profile-build-manifest.json")
        == env["profiling_build_manifest_sha256"]
    )
    require(
        sha(ROOT / "build/profile-source-manifest.json")
        == env["profiling_source_manifest_sha256"]
    )
    programs = json.loads((ROOT / "generated/manifest.json").read_text())
    for profile in ("baseline", "bytes", "full"):
        for mode in ("unified", "stateful", "stateless"):
            name = f"{profile}-{mode}"
            p = compile_verifier(profile, mode)
            require((ROOT / f"generated/{name}.bin").read_bytes() == p.code, name)
            require(hashlib.sha256(p.code).hexdigest() == programs[name]["sha256"])
            for filename, expected in program_artifacts(p, name).items():
                require(
                    (ROOT / "generated" / filename).read_bytes() == expected,
                    ("stale review artifact", filename),
                )
            p.audit()
    vectors = json.loads((ROOT / "fixtures/vectors.json").read_text())["vectors"]
    for v in vectors:
        sig, pk, msg = decode(v)
        require(verify(msg, sig, pk, bytes.fromhex(v["context"])), v["name"])
    data = json.loads(
        gzip.decompress((ROOT / "reports/regtest-details.json.gz").read_bytes())
    )
    costs = json.loads((ROOT / "reports/costs.json").read_text())
    require(
        costs["recorded_transactions_sha256"]
        == sha(ROOT / "reports/regtest-details.json.gz")
    )
    require(len(data["spends"]) == len(costs["transactions"]))
    required_spends = {
        f"{profile}-{mode}"
        for profile in ("full", "baseline")
        for mode in ("unified", "stateful", "stateless")
    }
    required_spends |= {
        "full-unified-sl",
        "baseline-unified-sl",
        "full-2-input-mixed",
        "full-4-input-mixed",
    }
    required_spends |= {f"full-cap{cap}-boundary" for cap in range(1, 5)}
    require({row["name"] for row in data["spends"]} == required_spends)
    require(len(data["rejections"]) == len(costs["rejected_transactions"]) >= 128)
    for row, measured in zip(data["spends"], costs["transactions"]):
        require(row["name"] == measured["name"])
        tx = tx_from_hex(row["raw_transaction"])
        pk = bytes.fromhex(row["public_key"])
        require(tx.get_weight() == measured["weight"])
        require(measured["varops_allowed"] == 10000 * tx.get_weight())
        require(measured["varops_consumed"] <= measured["varops_allowed"])
        spent = []
        for serialized in row["spent_outputs"]:
            item = CTxOut()
            item.deserialize(io.BytesIO(bytes.fromhex(serialized)))
            spent.append(item)
        for i, witness in enumerate(tx.wit.vtxinwit):
            sig, script, control = witness.scriptWitness.stack
            policy = compile_policy(
                pk,
                mode=row.get("mode", "unified"),
                profile=row.get("profile", "full"),
                max_inputs=row.get("max_inputs", 4 if len(tx.vin) > 1 else 1),
            )
            require(script == policy.code, (row["name"], "stale transaction program"))
            digest = message(tx, spent, i, script)
            require(verify(digest, sig, pk), row["name"])
            if "message" in row:
                require(digest.hex() == row["message"])
            require(control[0] & 0xFE == 0xC2)
        metrics = measured["metrics"]
        require(metrics["peak_total_entries"] <= 32768)
        require(metrics["peak_total_bytes"] <= 8_000_000)
        require(metrics["max_item_bytes"] <= 4_000_000)
        require(metrics["executed_function_body_bytes"] <= 4_000_000)
    cap_cases = [row for row in data["rejections"] if "max_inputs" in row]
    require({row["max_inputs"] for row in cap_cases} == {1, 2, 3, 4})
    for row in cap_cases:
        tx = tx_from_hex(row["raw_transaction"])
        pk = bytes.fromhex(row["public_key"])
        cap = row["max_inputs"]
        require(len(tx.vin) == cap + 1)
        spent = []
        for serialized in row["spent_outputs"]:
            item = CTxOut()
            item.deserialize(io.BytesIO(bytes.fromhex(serialized)))
            spent.append(item)
        policy = compile_policy(pk, mode="stateful", max_inputs=cap).code
        for i, witness in enumerate(tx.wit.vtxinwit):
            sig, script, control = witness.scriptWitness.stack
            require(script == policy)
            require(
                verify(message(tx, spent, i, script), sig, pk),
                ("invalid cap-test signature", cap, i),
            )
    for row in costs["rejected_transactions"]:
        require(not row["node_result"]["allowed"])
        require(any(not x["success"] for x in row["failure"]))
        require(not any(is_budget_error(x.get("error")) for x in row["failure"]))
    components = json.loads((ROOT / "reports/components.json").read_text())
    require(
        components["cases"] == 384 and all(x["accepted"] for x in components["rows"])
    )
    require(
        components["evaluator_sha256"] == sha(ROOT / "build/bitcoin/bin/bitcoin-util")
    )
    boundaries = json.loads((ROOT / "reports/boundary-costs.json").read_text())
    require(boundaries["rows"] == 1530 and boundaries["depths"] == 255)
    require(
        boundaries["details_sha256"] == sha(ROOT / "reports/boundary-costs.json.gz")
    )
    boundary_rows = json.loads(
        gzip.decompress((ROOT / "reports/boundary-costs.json.gz").read_bytes())
    )
    require(len(boundary_rows) == 1530)
    for profile in ("baseline", "bytes", "full"):
        subset = [x for x in boundary_rows if x["profile"] == profile]
        require(len(subset) == 510)
        require(
            {(x["depth"], x["index"]) for x in subset}
            == {(d, i) for d in range(1, 256) for i in (0, 2 ** min(d, 64) - 1)}
        )
        for row in subset:
            require(row["script_sha256"] == programs[f"{profile}-unified"]["sha256"])
            require(row["metrics"]["peak_total_bytes"] <= 8_000_000)
            require(row["metrics"]["peak_total_entries"] <= 32768)
            require(row["metrics"]["max_item_bytes"] <= 4_000_000)
            require(row["metrics"]["executed_function_body_bytes"] <= 4_000_000)
    for kind in ("native", "profiled", "optimized"):
        validate_results(kind)
        provenance = json.loads(
            (ROOT / f"reports/tests-{kind}-provenance.json").read_text()
        )
        for file, expected in provenance.items():
            require(sha(ROOT / file) == expected, ("stale tested artifact", kind, file))
    require("No errors detected" in (ROOT / "reports/upstream-unit.log").read_text())
    log = (ROOT / "reports/upstream-functional.log").read_text()
    for name in (
        "feature_tapscript_v2.py",
        "feature_tapscript_v2_taproot.py",
        "feature_tapscript_v2_op_tx_vaults.py",
        "tool_utils.py",
    ):
        require(
            any(name in line and "passed" in line for line in log.splitlines()), name
        )
    require("Tests successful" in (ROOT / "reports/regtest.log").read_text())
    output = dict(
        status="pass",
        source_pins_clean=True,
        generated_programs=9,
        reference_fixtures=len(vectors),
        stateful_depths_tested=255,
        accepted_mined_transactions=len(data["spends"]),
        rejected_transactions=len(data["rejections"]),
        scope="Laboratory verifier/transaction package M0-M7; no external review, production signer, or quantum-safe output wrapper",
        evidence_hashes={
            str(p.relative_to(ROOT)): sha(p)
            for p in sorted((ROOT / "reports").iterdir())
            if p.is_file() and p.name not in ("audit.json", "AUDIT.md", "check.log")
        },
    )
    (ROOT / "reports/audit.json").write_text(json.dumps(output, indent=2) + "\n")
    print("Completion evidence audit passed")


if __name__ == "__main__":
    main()
