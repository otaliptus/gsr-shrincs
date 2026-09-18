"""Audit current follow-up inputs, builds, schedules, and recorded outcomes."""
import gzip
import hashlib
import json
import math
import statistics

from runner.checks import require
from runner.evaluator import is_budget_error
from runner.evidence import CORPUS, COSTS, COUNTS, NATIVE, PROFILE, PROBE, PARSER, sha, value_sha, verify_provenance
from scripts.profile_build import hashes, overlay_inputs
from scripts.parse_benchmark import schedule_for
from scripts.multi_compare import programs, request_for, OUTPUT_COUNTS, LIMIT


def named(rows, expected):
    require(len(rows) == len(expected), "follow-up row inventory changed")
    result = {row["name"]: row for row in rows}
    require(set(result) == set(expected), "follow-up names changed or duplicated")
    return result


def samples(values, median, repeats):
    require(type(repeats) is int and repeats > 0, "invalid follow-up repeat count")
    require(len(values) == repeats and all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values),
            "invalid follow-up timing samples")
    require(statistics.median(values) == median, "follow-up timing median changed")


def validate_parsing(counts, benchmark, spends, costs):
    names = [row["name"] for row in spends]
    recorded = named(counts["rows"], names)
    timed = named(benchmark["rows"], names)
    measured = named(costs["transactions"], names)
    require(benchmark["passes"] == 16, "parser pass count changed")
    for spend in spends:
        name = spend["name"]
        row, timing, cost = recorded[name], timed[name], measured[name]
        result = row["result"]
        require(result["classification"] == "accept", ("parsing observation rejected", name))
        require((result["consumed"], result["allowance"], result["weight"]) ==
                (cost["varops_consumed"], cost["varops_allowed"], cost["weight"]),
                ("parsing accounting differs from current costs", name))
        counter = row["counts"]
        require(set(counter) == {"parsed_bytes", "parsed_instructions", "skipped_bytes", "skipped_instructions", "skipped_push_bytes"},
                "parsing counter inventory changed")
        require(all(type(x) is int and x >= 0 for x in counter.values()), "invalid parsing counter")
        require(counter["skipped_instructions"] <= counter["parsed_instructions"] <= counter["parsed_bytes"], "invalid instruction counts")
        require(counter["skipped_push_bytes"] <= counter["skipped_bytes"] <= counter["parsed_bytes"], "invalid byte counts")
        require(timing["counts"] == counter, ("parser counts differ", name))
        schedule = schedule_for(spend, cost)
        require(timing["schedule_sha256"] == value_sha(schedule), ("stale parser schedule", name))
        require(sum(len(bytes.fromhex(item["script"])) * item["calls"] for item in schedule) == counter["parsed_bytes"],
                ("parser schedule byte count differs", name))
        variants = {"with_payload_copy", "without_payload_copy"}
        require(set(timing["samples_ns"]) == set(timing["median_ns"]) == variants, "parser timing variants changed")
        for variant in variants:
            samples(timing["samples_ns"][variant], timing["median_ns"][variant], benchmark["repeats"])


def multi_corpus(codes):
    return {name: {str(count): dict(valid=request_for(code, count), wrong_sum=request_for(code, count, 1),
                                  over_limit=request_for(code, LIMIT + 1), empty=request_for(code, 0))
                   for count in OUTPUT_COUNTS} for name, code in codes.items()}


def validate_multi(data):
    codes = programs()
    require(data["programs"] == {name: code.hex() for name, code in codes.items()}, "OP_MULTI programs changed")
    require(data["corpus_sha256"] == value_sha(multi_corpus(codes)), "OP_MULTI transaction corpus changed")
    pairs = {(name, count) for name in codes for count in OUTPUT_COUNTS}
    require(len(data["rows"]) == len(pairs) and
            {(r["construction"], r["output_count"]) for r in data["rows"]} == pairs, "OP_MULTI row inventory changed")
    for row in data["rows"]:
        code = codes[row["construction"]]
        require(row["script_bytes"] == len(code) and row["script_sha256"] == hashlib.sha256(code).hexdigest(), "OP_MULTI program size/hash changed")
        require(row["result"]["classification"] == "accept" and
                0 <= row["result"]["consumed"] <= row["result"]["allowance"], "OP_MULTI positive result changed")
        require(set(row["negative_results"]) == {"wrong_sum", "over_limit", "empty"}, "OP_MULTI rejection inventory changed")
        for result in row["negative_results"].values():
            require(result["classification"] == "reject" and not any(is_budget_error(e) for e in result["errors"]),
                    "OP_MULTI negative case did not reject semantically")
        samples(row["times_ns"], row["median_ns"], data["repeats"])


def validate_multi_scenario(root, data):
    from generator import multi
    from generator.transaction import compile_policy
    from reference.oracle import PUBLIC_SEED, scheme

    expected = {f"{name}-{mode}" for name in ("full", "catfix", "multi") for mode in ("stateful", "stateless")}
    rows = data["transactions"]
    require(set(rows) == expected, "OP_MULTI scenario row inventory changed")
    require(type(data["agreement_cases"]) is int and data["agreement_cases"] > 0, "OP_MULTI scenario agreement missing")
    _, pk = scheme.shrincs_keygen(PUBLIC_SEED, b"\x01\x08")
    for key, row in rows.items():
        name, mode = row["variant"], row["mode"]
        code = compile_policy(pk, mode=mode, profile="full").code if name == "full" else multi.compile_policy(name, pk, mode=mode).code
        require(row["program_bytes"] == len(code) and row["program_sha256"] == hashlib.sha256(code).hexdigest(),
                ("OP_MULTI scenario program changed", key))
        require(0 < row["varops_consumed"] <= row["varops_allowed"] and row["varops_allowed"] == 10000 * row["weight"],
                ("OP_MULTI scenario accounting invalid", key))
        require(bool(row["multi_uses"]) == (name == "multi"), ("OP_MULTI use inventory wrong", key))
        samples(row["times_ns"], row["median_interpreter_ms"] * 1e6, data["repeats"])
    for mode in ("stateful", "stateless"):
        require(rows[f"full-{mode}"]["program_bytes"] > rows[f"catfix-{mode}"]["program_bytes"] > rows[f"multi-{mode}"]["program_bytes"],
                "OP_MULTI scenario size ordering changed")


def check_overlay(source, target):
    allowed = {"src/script/interpreter.cpp", "src/bitcoin-util.cpp", "src/gsr_profile.hpp"}
    require(set(target) == set(source) | {"src/gsr_profile.hpp"}, "unexpected follow-up source files")
    require(all(target[name] == digest for name, digest in source.items() if name not in allowed),
            "follow-up overlay modified unrelated source")


def audit_followups(root, environment, *, check_builds=True):
    load = lambda name: json.loads((root / name).read_text())
    counts = load(COUNTS)
    benchmark = load("reports/parser-benchmark.json")
    multi = load("reports/multi-comparison.json")
    verify_provenance(root, counts["provenance"], [CORPUS, COSTS], [PROFILE, PROBE], environment, check_binaries=check_builds)
    verify_provenance(root, benchmark["provenance"], [CORPUS, COSTS, COUNTS], [PARSER], environment, check_binaries=check_builds)
    verify_provenance(root, multi["provenance"], [], [PROFILE], environment, check_binaries=check_builds)
    scenario = load("reports/multi-scenario.json")
    verify_provenance(root, scenario["provenance"], ["fixtures/vectors.json"], [NATIVE, PROFILE], environment, check_binaries=check_builds)
    for report in (benchmark, multi, scenario, load(COSTS)):
        require({key: report["environment"][key] for key in ("platform", "machine", "python")} ==
                {key: environment[key] for key in ("platform", "machine", "python")}, "measurement environment label differs")
    require(counts["corpus_sha256"] == sha(root / CORPUS), "stale parsing corpus")
    require(counts["reference_binary_sha256"] == environment["binaries"][PROFILE], "stale parsing reference binary")
    for report, binary in ((counts, PROBE), (benchmark, PARSER), (multi, PROFILE)):
        require(report["binary_sha256"] == environment["binaries"][binary], "stale follow-up executable")
    if check_builds:
        for report, directory in ((counts, "parsing-probe"), (benchmark, "parser-benchmark")):
            require(report["build_cache_sha256"] == sha(root / "build" / directory / "build/CMakeCache.txt"),
                    "follow-up build configuration changed")
    raw = gzip.decompress((root / "reports/parsing-source-manifest.json.gz").read_bytes())
    require(hashlib.sha256(raw).hexdigest() == counts["source_manifest_sha256"], "stale parsing source manifest")
    if check_builds:
        require(raw == (root / "build/parsing-probe/parsing-source-manifest.json").read_bytes(), "different local parsing manifest")
    manifest = json.loads(raw)
    source = hashes(root / "vendor/bitcoin")
    require(manifest["source_files"] == source, "parsing source revision changed")
    if check_builds:
        require(manifest["target_files"] == hashes(root / "build/parsing-probe/source"), "parsing observation source changed")
    require(manifest["driver_sha256"] == sha(root / "scripts/parsing_probe.py") and manifest["base_overlay"] == overlay_inputs(),
            "parsing overlay code changed")
    check_overlay(source, manifest["target_files"])
    if check_builds:
        require(benchmark["source_files"] == hashes(root / "build/parser-benchmark/source"), "parser benchmark source changed")
    check_overlay(source, benchmark["source_files"])
    require(benchmark["driver_files"] == {name: sha(root / name) for name in
            ("scripts/parse_benchmark.py", "scripts/parsing_probe.py", "runner/parsebench.inc")}, "parser benchmark drivers changed")
    require(multi["source_sha256"] == sha(root / "scripts/multi_compare.py"), "OP_MULTI driver changed")
    spends = json.loads(gzip.decompress((root / CORPUS).read_bytes()))["spends"]
    validate_parsing(counts, benchmark, spends, load(COSTS))
    validate_multi(multi)
    validate_multi_scenario(root, scenario)
