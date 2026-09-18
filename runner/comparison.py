"""Compare fixed workloads. Acceptance, accounting, and timing remain separate."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import statistics

from runner import profile
from runner.evaluator import HarnessError, evaluate


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_corpus(corpus):
    if corpus.get("schema") != 1:
        raise ValueError("unsupported corpus schema")
    ids = set()
    for digest, code in corpus["programs"].items():
        if sha(bytes.fromhex(code)) != digest:
            raise ValueError("program digest mismatch")
    for name, contract in corpus["contracts"].items():
        if contract["sha256"] not in corpus["programs"]:
            raise ValueError(f"missing program for {name}")
    for row in corpus["cases"]:
        if not isinstance(row["id"], str) or row["id"] in ids or type(row["expected"]) is not bool:
            raise ValueError("invalid or duplicate case")
        ids.add(row["id"])
        if row["command"] not in ("evalscript", "measuretx"):
            raise ValueError("unsupported command")
        if row["command"] == "evalscript" and row["contract"] not in corpus["contracts"]:
            raise ValueError("missing contract")
    return ids


def request_for(corpus, row):
    request = dict(row["request"])
    if row["command"] == "evalscript":
        contract = corpus["contracts"][row["contract"]]
        request["script"] = corpus["programs"][contract["sha256"]]
    return request


@contextmanager
def profile_binary(binary):
    previous = profile.BINARY
    try:
        profile.BINARY = Path(binary)
        yield
    finally:
        profile.BINARY = previous


def outcome(command, request, response):
    if command == "evalscript":
        errors = [response["error"]] if response["error"] else []
        consumed = request["varops_budget"] - response["varops-budget-remaining"]
        result = dict(stack=response["stack-after"], errors=errors, consumed=consumed,
                      allowance=request["varops_budget"], program_bytes=len(bytes.fromhex(request["script"])))
    else:
        errors = [r["error"] for r in response["inputs"] if not r["success"]]
        result = dict(errors=errors, consumed=response["varops_consumed"],
                      allowance=response["varops_allowed"], weight=response["weight"],
                      transaction_bytes=len(bytes.fromhex(request["transaction"])), inputs=response["inputs"])
    result["classification"] = (
        "accept" if response["success"] else
        "budget" if any("budget" in e.lower() for e in errors) else "reject"
    )
    return result


def sample(binary, command, request, observe):
    with profile_binary(binary):
        response = profile.run_profile(command, dict(request, profile=observe))
    return outcome(command, request, response), response


def run_pair(left, right, left_corpus, right_corpus, *, repeats=11, emit=None):
    if repeats < 1:
        raise ValueError("at least one timing sample is required")
    left_ids, right_ids = validate_corpus(left_corpus), validate_corpus(right_corpus)
    if left_ids != right_ids:
        raise ValueError("case inventory changed")
    right_cases = {r["id"]: r for r in right_corpus["cases"]}
    rows = []
    for ordinal, lcase in enumerate(left_corpus["cases"]):
        rcase = right_cases[lcase["id"]]
        if (lcase["command"], lcase["expected"]) != (rcase["command"], rcase["expected"]):
            raise ValueError("case meaning changed")
        requests = [request_for(left_corpus, lcase), request_for(right_corpus, rcase)]
        command = lcase["command"]
        measurements = []
        for side, request, case in zip((left, right), requests, (lcase, rcase)):
            result, observed = sample(side["profile"], command, request, True)
            if command == "evalscript":
                native = evaluate(bytes.fromhex(request["script"]),
                                  [bytes.fromhex(x) for x in request["stack"]],
                                  request["varops_budget"], binary=side["native"])
                if (native.classification, native.consumed, [x.hex() for x in native.stack]) != (
                    result["classification"], result["consumed"], result["stack"]
                ):
                    raise HarnessError("native/profiling acceptance or accounting disagreement")
            if command == "measuretx" and case["artifacts"]["weight"] != result["weight"]:
                raise HarnessError("Python/C++ transaction weight disagreement")
            measurements.append(dict(result=result, metrics=observed["profile"], artifacts=case.get("artifacts", {}),
                                     request_sha256=sha(canonical(request)), times_ns=[]))
        # Warm up both binaries, then alternate their order to reduce drift bias.
        samples = repeats if command == "measuretx" and lcase["expected"] else 1
        for iteration in range(samples + 1):
            for index in ((0, 1) if (iteration + ordinal) % 2 == 0 else (1, 0)):
                binary = (left, right)[index]["profile"]
                result, response = sample(binary, command, requests[index], False)
                if result != measurements[index]["result"]:
                    raise HarnessError("instrumentation or repetition changed execution outcome")
                if iteration:
                    measurements[index]["times_ns"].append(response["profile"]["interpreter_ns"])
        for measurement in measurements:
            measurement["median_ns"] = statistics.median(measurement["times_ns"])
        a, b = measurements
        row = dict(id=lcase["id"], expected=lcase["expected"], baseline=a, candidate=b,
                   acceptance_changed=a["result"]["classification"] != b["result"]["classification"],
                   errors_changed=a["result"]["errors"] != b["result"]["errors"],
                   stack_changed=a["result"].get("stack") != b["result"].get("stack"),
                   accounting_delta=b["result"]["consumed"] - a["result"]["consumed"],
                   timing_ratio=b["median_ns"] / a["median_ns"] if a["median_ns"] else None,
                   input_changed=a["request_sha256"] != b["request_sha256"],
                   baseline_matches_expected=a["result"]["classification"] == ("accept" if lcase["expected"] else "reject"),
                   candidate_matches_expected=b["result"]["classification"] == ("accept" if lcase["expected"] else "reject"))
        rows.append(row)
        if emit:
            emit(row)
    return rows


def summarize(rows):
    return dict(cases=len(rows), acceptance_changes=sum(r["acceptance_changed"] for r in rows),
                baseline_unexpected=sum(not r["baseline_matches_expected"] for r in rows),
                candidate_unexpected=sum(not r["candidate_matches_expected"] for r in rows),
                accounting_changes=sum(r["accounting_delta"] != 0 for r in rows),
                error_changes=sum(r["errors_changed"] for r in rows),
                stack_changes=sum(r["stack_changed"] for r in rows),
                changed_inputs=sum(r["input_changed"] for r in rows))


def render_report(data):
    lines = ["# Fork comparison", "", f"Status: {data['status']}.", "",
             "The replay uses fixed programs and input bytes. The recompile uses newly generated policies and signatures.",
             "Transaction results are offline Script checks against recorded spent outputs. They are not new node validation.",
             "Fresh node acceptance is recorded separately for the recompile mode.", "",
             "Timing includes profiling hooks with counters disabled. Timing changes are observations, not acceptance failures.",
             "Boundary and negative cases have one recorded timing sample. Positive transactions have repeated samples.", ""]
    for mode, result in data.get("comparisons", {}).items():
        lines += [f"## {mode}", "", "```json", json.dumps(result["summary"], indent=2), "```", "",
                  "| Spend | Script bytes, before → after | Signature bytes, before → after | Weight, before → after | Varops change | Time ratio | Inputs changed |",
                  "|---|---:|---:|---:|---:|---:|---|"]
        for row in result["rows"]:
            if not row["id"].startswith("spends/"):
                continue
            a, b = row["baseline"], row["candidate"]
            ratio = row["timing_ratio"]
            dimensions = " | ".join(f"{a['artifacts'][key]} → {b['artifacts'][key]}" for key in ("program_bytes", "signature_bytes", "weight"))
            lines.append(f"| {row['id'][7:]} | {dimensions} | {row['accounting_delta']:+,} | {ratio:.3f} | {row['input_changed']} |")
        lines += ["", "Changed signatures can change hash-chain work. Recompile timings do not isolate compiler effects.", ""]
    if data.get("error"):
        lines += ["## Incomplete execution", "", data["error"], ""]
    return "\n".join(lines)
