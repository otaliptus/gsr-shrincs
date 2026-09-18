"""Observation adapter; an error is never a cryptographic rejection."""

import json
import subprocess
import time
from .evaluator import ROOT, HarnessError
from .checks import require

BINARY = ROOT / "build/profile/bin/bitcoin-util"


def run_profile(command, request):
    if command not in ("evalscript", "measuretx"):
        raise ValueError("unknown profiling command")
    start = time.perf_counter_ns()
    try:
        p = subprocess.run(
            [str(BINARY), command],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HarnessError(str(e)) from e
    wall = time.perf_counter_ns() - start
    if p.returncode:
        raise HarnessError(p.stderr)
    try:
        r = json.loads(p.stdout)
        require(type(r["protocol"]) is int and r["protocol"] == 1)
        require(type(r["success"]) is bool)
        metrics = r["profile"]
        require(type(metrics["observations_enabled"]) is bool)
        for key in (
            "interpreter_ns",
            "peak_stack_entries",
            "peak_stack_bytes",
            "peak_total_entries",
            "peak_total_bytes",
            "max_item_bytes",
            "function_storage_bytes",
            "executed_function_body_bytes",
            "invocations",
            "sha256_calls",
            "sha256_compressions",
        ):
            require(type(metrics[key]) is int and metrics[key] >= 0)
        for key in ("opcodes", "function_calls", "function_body_varops_inclusive", "multi_operations"):
            require(type(metrics[key]) is dict)
            require(
                all(
                    k.isdecimal() and 0 <= int(k) <= 255 and type(v) is int and v >= 0
                    for k, v in metrics[key].items()
                )
            )
        if command == "evalscript":
            require(r["context"] == "standalone" and r["sigversion"] == "tapscript_v2")
            require(r["error"] is None if r["success"] else isinstance(r["error"], str))
            remaining = r["varops-budget-remaining"]
            require(
                type(remaining) is int and 0 <= remaining <= request["varops_budget"]
            )
            require(type(r["stack-after"]) is list)
            for item in r["stack-after"]:
                bytes.fromhex(item)
        else:
            require(r["context"] == "offline-transaction-script-check")
            for key in ("weight", "varops_allowed", "varops_consumed"):
                require(type(r[key]) is int and r[key] >= 0)
            require(r["varops_allowed"] == 10000 * r["weight"])
            require(r["varops_consumed"] <= r["varops_allowed"])
            require(type(r["inputs"]) is list and bool(r["inputs"]))
            require(len(r["inputs"]) <= len(request["spent_outputs"]))
            require(not r["success"] or len(r["inputs"]) == len(request["spent_outputs"]))
            require(all(row["success"] is True for row in r["inputs"][:-1]))
            for i, row in enumerate(r["inputs"]):
                require(type(row["input"]) is int and row["input"] == i)
                require(type(row["success"]) is bool)
                require(type(row["consumed"]) is int and row["consumed"] >= 0)
                require(row["success"] or isinstance(row["error"], str))
            require(r["success"] == all(row["success"] for row in r["inputs"]))
            require(r["varops_consumed"] == sum(row["consumed"] for row in r["inputs"]))
    except (ValueError, KeyError, AssertionError, TypeError) as e:
        raise HarnessError(p.stdout[:1000]) from e
    r["wall_ns"] = wall
    r["process_and_protocol_overhead_ns"] = wall - r["profile"]["interpreter_ns"]
    return r
