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
from runner.evaluator import evaluate, is_budget_error
from runner.evidence import host_environment
from runner.profile import run_profile


CAVEATS = [
    "Interpreter timing excludes process startup and JSON parsing.",
    "Timing with counters disabled uses the profiling executable. Conditional measurement hooks remain active. Their overhead is not subtracted.",
    "CLI overhead includes launch, initialization, JSON input and output, and teardown. It does not measure process startup alone.",
    "Each function cost includes its nested calls. Adding these costs would count some work more than once.",
    "Executed function-body bytes give the maximum for one input evaluation. The limit applies per evaluation. Invocation counts and varops sum across inputs.",
    "Peak memory measures logical VM bytes. It excludes allocator capacity and process resident memory.",
    "Peaks for rejected inputs include completed opcode states. Temporary values before a failing operation can be larger.",
]


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
        environment=host_environment(),
        standalone=[],
        transactions=[],
        rejected_transactions=[],
        caveats=list(CAVEATS),
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
            not any(is_budget_error(x.get("error")) for x in result["inputs"]),
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
    (ROOT / "reports/RESULTS.md").write_text(render_results(data))
    print(
        f"Measured {len(data['standalone'])} standalone classes, {len(data['transactions'])} spends and {len(data['rejected_transactions'])} rejected transactions"
    )


def render_results(data):
    """Format recorded measurements without executing the verifier again."""
    lines = [
        "# Measured results",
        "",
        f"Timing environment: **{data['environment']['platform']}**, {data['environment']['machine']}, Python {data['environment']['python'].split()[0]}.",
        "These timings apply to this machine and method. Do not infer performance regressions from timings across different environments.",
        "The [environment manifest](environment.json) records build and executable details. The baseline tag retains the earlier Linux measurements.",
        "",
        "These measurements use the pinned fork and SHRINCS parameters. The unmodified local regtest node accepted and mined every listed spend. The transactions contain no budget padding.",
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
        f"The stateful spend uses {compact['vsize']:,} vbytes. The same transaction shape used 6,879 vbytes at commit `6e1e807`. This is a reduction of {1-compact['vsize']/6879:.1%}. The Script uses shared authentication functions with a fixed execution bound and no call cycle. Each child receives only its required path portion.\n\nThe inline profiles retain their expanded authentication code for comparison. The signature remains 660 bytes. The transaction and control-block shapes remain unchanged. Newly signed transactions can have different hash-chain digits, which affect varops comparisons.",
        "",
        "Each policy contains a 48-byte public key. Original single-input rows use a 65-byte control block for two committed leaves. Mixed-input and cap-boundary rows use a 33-byte control block per input.\n\nMixed-input policies permit a maximum of four inputs. Cap-boundary policies test each limit from one through four. A mode-specific tree pairs its leaf with the opposite mode. A combined leaf has an additional mode-specific sibling for replay tests under another policy.",
        "",
        "A smaller program reduces witness weight. In this fork, lower weight also reduces the execution allowance. The full stateless leaf therefore has less unused allowance than the larger combined leaf. Both perform the same signature computation.",
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
        f"All {len(data['rejected_transactions'])} recorded negative transactions also fail the offline Script checker with transaction data. These include annex and large two-input cases that relay policy rejects before Script executes.\n\nFour over-limit cases have fresh, independently valid signatures for every input. The input-count limits cause these rejections. The node accepts and mines each corresponding transaction at its permitted limit. The older append-input cases check transcript binding. The checks distinguish cryptographic and policy rejection from process failure and insufficient budget.",
        "",
        "`costs.json` records accepted and rejected execution costs, function calls, hash operations, stack entries, timing distributions, and script and input hashes. It also compares the byte-helper profile. Function costs include nested calls. The records distinguish early parser and message failures from later authentication-path failures.\n\n`components.json` contains 384 component measurements. `boundary-costs.json.gz` covers all 1,530 stateful boundary executions. `environment.json` records source and executable hashes, platform details, and compiler flags. `regtest-details.json.gz` contains complete transactions, transcripts, and authenticated spent-output records.",
        "",
        "The measured programs fit the pinned consensus limits. These limits permit 32,768 entries, including definitions, and 4,000,000 bytes per item. Total stack, altstack, and function storage cannot exceed 8,000,000 bytes. Cumulative invoked function-body bytes cannot exceed 4,000,000 per evaluation.\n\nThese results do not establish low payment costs or production readiness. The fee at a selected rate is `vbytes × sat/vbyte`.",
        "",
        "Ordinary Taproot retains its key path, which remains vulnerable to quantum attacks. These measurements concern SHRINCS leaf verification. They do not establish complete post-quantum protection for the output. The implementation has no independent cryptographic audit or formal proof.",
        "",
        "## Measurement boundaries",
        "",
    ] + ["- " + x for x in data["caveats"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
