#!/usr/bin/env python3
"""Measured costs and timing, with equality gates against the unmodified evaluator."""
from pathlib import Path
import gzip
import hashlib
import json
import math
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.checks import require
from generator.verifier import compile_verifier
from reference.oracle import decode
from runner.evaluator import evaluate
from runner.profile import run_profile


def distribution(values):
    ordered = sorted(values)
    return dict(
        n=len(values),
        min=min(values),
        median=statistics.median(values),
        p95=ordered[math.ceil(0.95 * len(values)) - 1],
        max=max(values),
    )


def evaluate_request(code, values, profile=True, budget=1_000_000_000):
    return dict(
        protocol=1,
        sigversion="tapscript_v2",
        script=code.hex(),
        stack=[v.hex() for v in values],
        varops_budget=budget,
        profile=profile,
    )


def timing(command, request, repeats=11):
    observations = []
    plain = []
    for _ in range(repeats):
        a = run_profile(command, dict(request, profile=True))
        b = run_profile(command, dict(request, profile=False))
        require(a["success"] == b["success"])
        key = "varops_consumed" if command == "measuretx" else "varops-budget-remaining"
        require(a[key] == b[key])
        observations.append(a)
        plain.append(b)
    return dict(
        observed_interpreter_ns=distribution(
            [x["profile"]["interpreter_ns"] for x in observations]
        ),
        unobserved_interpreter_ns=distribution(
            [x["profile"]["interpreter_ns"] for x in plain]
        ),
        cli_wall_ns=distribution([x["wall_ns"] for x in plain]),
        process_and_protocol_overhead_ns=distribution(
            [x["process_and_protocol_overhead_ns"] for x in plain]
        ),
    )


def main():
    vectors = json.loads((ROOT / "fixtures/vectors.json").read_text())["vectors"]
    data = dict(
        standalone=[],
        transactions=[],
        rejected_transactions=[],
        caveats=[
            "Timing excludes process startup/JSON parsing from interpreter_ns.",
            "Unobserved timings use the same overlay binary with counters disabled; remaining conditional overhead is not subtracted.",
            "CLI overhead includes launch, initialization, JSON IO and teardown; it is not pure process startup.",
            "Function-body costs are inclusive of nested calls and must not be summed.",
            "Executed-function-body bytes is the maximum per input evaluation, matching the per-evaluation limit; invocation counts and varops sum across inputs.",
            "Peak memory is logical VM bytes, not allocator capacity or process RSS.",
            "Rejected-input peaks include completed opcode states; transient values before failing operations can be larger.",
        ],
    )
    selected = [vectors[0], vectors[4], vectors[-1]]
    for profile in ("baseline", "bytes", "full"):
        for mode in ("unified", "stateful", "stateless"):
            program = compile_verifier(profile, mode)
            for v in selected:
                is_sl = bytes.fromhex(v["signature"])[0] == 255
                if mode != "unified" and (mode == "stateless") != is_sl:
                    continue
                values = decode(v)
                request = evaluate_request(program.code, values)
                native = evaluate(program.code, values)
                observed = run_profile("evalscript", request)
                require(native.success and observed["success"])
                require(native.remaining == observed["varops-budget-remaining"])
                require(observed["stack-after"] == [])
                if not is_sl:
                    depth = 255 - values[0][0]
                    require(observed["profile"]["sha256_calls"] == 244 + depth)
                bad = [values[0], values[1], bytes([values[2][0] ^ 1]) + values[2][1:]]
                native_bad = evaluate(program.code, bad)
                observed_bad = run_profile(
                    "evalscript", evaluate_request(program.code, bad)
                )
                require(not native_bad.success and not observed_bad["success"])
                require(native_bad.remaining == observed_bad["varops-budget-remaining"])
                altered_path = values[0][:-1] + bytes([values[0][-1] ^ 1])
                late = evaluate(program.code, [altered_path, *values[1:]])
                late_profile = run_profile(
                    "evalscript",
                    evaluate_request(program.code, [altered_path, *values[1:]]),
                )
                require(not late.success and not late_profile["success"])
                require(late.remaining == late_profile["varops-budget-remaining"])
                malformed = run_profile(
                    "evalscript",
                    evaluate_request(program.code, [values[0][:-1], *values[1:]]),
                )
                require(not malformed["success"])
                data["standalone"].append(
                    dict(
                        profile=profile,
                        mode=mode,
                        fixture=v["name"],
                        script_bytes=len(program.code),
                        script_sha256=hashlib.sha256(program.code).hexdigest(),
                        input_sha256=hashlib.sha256(b"".join(values)).hexdigest(),
                        signature_bytes=len(values[0]),
                        varops_consumed=native.consumed,
                        metrics=observed["profile"],
                        functions={
                            name: fid for name, (fid, _, _) in program.functions.items()
                        },
                        rejected_message_varops=native_bad.consumed,
                        rejected_message_metrics=observed_bad["profile"],
                        rejected_authentication_path_varops=late.consumed,
                        rejected_authentication_path_metrics=late_profile["profile"],
                        malformed_length_varops=1_000_000_000
                        - malformed["varops-budget-remaining"],
                        timing=timing("evalscript", request),
                    )
                )
    records = json.loads(
        gzip.decompress((ROOT / "reports/regtest-details.json.gz").read_bytes())
    )
    for row in records["spends"]:
        request = dict(
            transaction=row["raw_transaction"], spent_outputs=row["spent_outputs"]
        )
        result = run_profile("measuretx", request)
        require(result["success"], (row["name"], result))
        require(
            result["varops_allowed"] == row["varops_allowed"] == 10_000 * row["weight"]
        )
        require(result["weight"] == row["weight"])
        require(
            result["varops_consumed"] == sum(x["consumed"] for x in result["inputs"])
        )
        require(result["varops_consumed"] <= result["varops_allowed"])
        record = {
            k: v
            for k, v in row.items()
            if k not in ("raw_transaction", "spent_outputs", "transcript")
        }
        record.update(
            varops_consumed=result["varops_consumed"],
            budget_fraction=result["varops_consumed"] / result["varops_allowed"],
            metrics=result["profile"],
            inputs=result["inputs"],
            timing=timing("measuretx", request),
            padding_bytes=0,
        )
        data["transactions"].append(record)
    for row in records["rejections"]:
        request = dict(
            transaction=row["raw_transaction"], spent_outputs=row["spent_outputs"]
        )
        result = run_profile("measuretx", request)
        require(not result["success"], row["name"])
        require(
            not any("budget" in x.get("error", "").lower() for x in result["inputs"]),
            row["name"],
        )
        data["rejected_transactions"].append(
            dict(
                name=row["name"],
                node_result=row["result"],
                varops_consumed=result["varops_consumed"],
                varops_allowed=result["varops_allowed"],
                failure=result["inputs"],
                metrics=result["profile"],
            )
        )
    data["empty_program_cli_baseline"] = timing(
        "evalscript", evaluate_request(b"\x51", []), 21
    )
    data["recorded_transactions_sha256"] = hashlib.sha256(
        (ROOT / "reports/regtest-details.json.gz").read_bytes()
    ).hexdigest()
    (ROOT / "reports/costs.json").write_text(json.dumps(data, indent=2) + "\n")
    lines = [
        "# Measured results",
        "",
        "These results use the pinned fork and exact SHRINCS parameters. All listed spends were accepted and mined by the unmodified local regtest node. No budget padding was added.",
        "",
        "| Program / signature mode | Script bytes | Signature bytes | Weight | vbytes | Varops used / allowed | Budget used |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in data["transactions"]:
        lines.append(
            f"| {row['name']} | {row.get('program_bytes','two scripts')} | {row.get('signature_bytes','two signatures')} | {row['weight']:,} | {row['vsize']:,} | {row['varops_consumed']:,} / {row['varops_allowed']:,} | {row['budget_fraction']:.1%} |"
        )
    compact = next(
        row for row in data["transactions"] if row["name"] == "full-stateful"
    )
    lines += [
        "",
        f"The stateful-only spend is now {compact['vsize']:,} vbytes, compared with 6,879 vbytes at the reviewed commit 6e1e807 ({1-compact['vsize']/6879:.1%} smaller). Its Script uses a bounded acyclic tree of shared authentication functions; each child receives only its portion of the path. The inline profiles retain their expanded authentication logic as differential controls. The 660-byte stateful signature and transaction/control-block shape are unchanged. Varops comparisons use newly signed transactions, so their hash-chain digit distributions can differ.",
        "",
        "The public key is 48 bytes, embedded in each policy. Original single-input rows use a 65-byte control block (two committed leaves); the mixed-input and cap-boundary rows use a 33-byte control block per input. Mixed-input policies have a four-input cap; cap-boundary policies exercise each limit from one through four. Mode-specific leaves are paired with their opposite mode in one tree; combined leaves have an extra mode-specific sibling for cross-policy replay tests.",
        "",
        "Program size and execution allowance are distinct: compressed programs reduce witness weight and therefore the budget they purchase. The full mode-specific stateless leaf has substantially less budget headroom than the larger combined leaf, while performing the same signature computation.",
        "",
        "| Program | Peak stack bytes | Stack + functions bytes | Maximum item | Invoked body bytes | Median interpreter ms, counters off |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in data["transactions"]:
        m = row["metrics"]
        t = row["timing"]["unobserved_interpreter_ns"]["median"] / 1e6
        lines.append(
            f"| {row['name']} | {m['peak_stack_bytes']:,} | {m['peak_total_bytes']:,} | {m['max_item_bytes']:,} | {m['executed_function_body_bytes']:,} | {t:.3f} |"
        )
    lines += [
        "",
        f"All {len(data['rejected_transactions'])} recorded negative transactions also fail the offline transaction-aware Script checker, including annex and oversized two-input cases that relay policy rejects first. Four cap+1 cases carry fresh, independently valid signatures for every input; the one-through-four-input caps are the rejecting condition. Each allowed cap boundary is accepted and mined. The older append-input cases remain transcript-binding tests. This distinguishes cryptographic/policy rejection from process failure or insufficient budget.",
        "",
        "Detailed accepted and rejected costs, function calls, inclusive component costs, SHA256 counts/compressions, stack entries, timing distributions, script/input hashes, and byte-helper-only comparisons are in `costs.json`. Early parser/message failures and late authentication-path failures are recorded separately. `components.json` contains 384 local component contract measurements; `boundary-costs.json.gz` covers all 1,530 stateful boundary executions. `environment.json` records source/binary hashes, platform and compiler flags. `regtest-details.json.gz` holds full transactions, transcripts, and authenticated spent-output records from the test.",
        "",
        "Consensus limits: 32,768 entries including definitions, 4,000,000 bytes per item, 8,000,000 stack/altstack/function bytes, and 4,000,000 cumulative invoked body bytes. The measured programs fit. This does not establish everyday-payment economics or production readiness. Fee at any chosen rate is vbytes × sat/vbyte.",
        "",
        "Ordinary Taproot retains its quantum-vulnerable key path. These are direct SHRINCS leaf-verification measurements, not an end-to-end post-quantum Bitcoin output. No independent review or formal proof is claimed.",
        "",
        "## Measurement boundaries",
        "",
    ] + ["- " + x for x in data["caveats"]]
    (ROOT / "reports/RESULTS.md").write_text("\n".join(lines) + "\n")
    print(
        f"Measured {len(data['standalone'])} standalone classes, {len(data['transactions'])} spends and {len(data['rejected_transactions'])} rejected transactions"
    )


if __name__ == "__main__":
    main()
