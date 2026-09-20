#!/usr/bin/env python3
"""Reproduce the isolated experiment; do not regenerate the baseline reports."""
import argparse
import copy
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import reference as ref
import gsr
from runner.evaluator import evaluate, DEFAULT_BINARY
from runner.profile import run_profile, BINARY as PROFILE

WORK = ROOT / "build/simplicity-version-comparison"
UPSTREAM = ROOT / "build/simplicity-upstream"
BINARY = ROOT / "build/simplicityhl/target/release/simplicity-comparison-runner"
PROFILES = ("baseline", "bytes", "full", "catfix")
MODES = ("stateful", "stateless")
TYPES = {
    "stateful": "(u256, (u128, u128), ((u256, u32, [u128; 64]), List<u128, 512>, u32), u128)",
    "stateless": "(u256, (u128, u128), ((u256, ([(u128, [u128; 22]); 4], [(u128, [u128; 22]); 1])), [((u256, u32, [u128; 64]), [u128; 12]); 2]), u128)",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(path.read_bytes())


def value_sha(data):
    return sha(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())


def command(args, **kwargs):
    return subprocess.check_output(args, text=True, cwd=ROOT, **kwargs).strip()


def check(ok, message):
    if not ok:
        raise ValueError(message)


def prepare():
    WORK.mkdir(parents=True, exist_ok=True)
    check(command(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"]) == ref.PIN, "upstream revision changed")
    check(not command(["git", "-C", str(UPSTREAM), "status", "--porcelain", "--untracked-files=no"]), "upstream source changed")
    source = command(["clang", "-E", "-P", "-x", "c", "-Wno-invalid-pp-token",
                      str(UPSTREAM / "examples/shrincs/shrincs_main.simf")])
    body, entry = source.rsplit("fn main()", 1)
    check("shrincs_verify(witness::PROOF)" in entry, "upstream entry changed")
    for mode, tag, typ in (("stateful", "Left", "UXMSSSignature"), ("stateless", "Right", "SPHINCSSignature")):
        wrapper = f'''fn main() {{
    let (message, pk, signature, unused): (u256, SPHINCSPK, {typ}, u128) = witness::PROOF;
    shrincs_verify((message, pk, {tag}(signature), unused));
}}
'''
        (WORK / f"{mode}.simf").write_text('simc "0.7.2";\n' + body + wrapper)
    return {str(p.relative_to(UPSTREAM)): file_sha(p) for p in sorted(UPSTREAM.rglob("*.simf"))}


def cases(proof):
    """Deterministic mutations of public fixtures, including accepted ignored fields."""
    yield "upstream", copy.deepcopy(proof)
    paths = [[0], [1, 0], [1, 1], [3]]
    if ref.mode_of(proof) == "stateful":
        prefix = [2, "Left"]
        paths += [prefix + [0, 0], prefix + [0, 1], prefix + [2]]
        paths += [prefix + [0, 2, i] for i in range(64)]
        paths += [prefix + [1, i] for i in range(len(proof[2]["Left"][1]))]
    else:
        prefix = [2, "Right"]
        paths += [prefix + [0, 0]]
        for group, count in ((0, 4), (1, 1)):
            for i in range(count):
                base = prefix + [0, 1, group, i]
                paths += [base + [0]] + [base + [1, h] for h in range(22)]
        for layer in range(2):
            base = prefix + [1, layer]
            # The first field in these WOTS tuples is unused upstream.
            paths += [base + [0, 0], base + [0, 1]]
            paths += [base + [0, 2, i] for i in range(64)]
            paths += [base + [1, i] for i in range(12)]
    for path in paths:
        for bit in (0, 7):
            mutated = copy.deepcopy(proof)
            target = mutated
            for index in path[:-1]:
                target = target[index]
            target[path[-1]] ^= 1 << bit
            yield "flip/" + "/".join(map(str, path)) + f"/bit{bit}", mutated


def run_simplicity(mode, inputs, repeats):
    requests = [dict(witness=ref.witness_json(proof, TYPES[mode], specialized=True),
                     repeats=repeats if name == "upstream" else 1) for name, proof in inputs]
    proc = subprocess.run([str(BINARY), str(WORK / f"{mode}.simf")],
                          input="".join(json.dumps(x) + "\n" for x in requests),
                          capture_output=True, text=True, timeout=900, cwd=ROOT)
    check(proc.returncode == 0, f"Simplicity runner failed: {proc.stderr[-3000:]}")
    results = [json.loads(x) for x in proc.stdout.splitlines()]
    check(len(results) == len(inputs), "missing Simplicity results")
    return results


def source_hashes():
    paths = [p for p in HERE.iterdir() if p.name != "build_page.py" and p.suffix in (".py", ".rs", ".toml", ".lock", ".sh")]
    paths += [ROOT / p for p in ("generator/script.py", "generator/verifier.py", "runner/evaluator.py", "runner/profile.py", "runner/profile.hpp", "scripts/profile_build.py")]
    return {str(p.relative_to(ROOT)): file_sha(p) for p in sorted(paths)}


def measure(repeats):
    upstream_sources = prepare()
    result = dict(schema=1, name="simplicity-version-comparison", scope="standalone mode-specific verification",
                  upstream_revision=ref.PIN, compiler_revision="f3fa882e77c221e96e10acde9f0e46e68e69930f",
                  gsr_revision=command(["git", "-C", "vendor/bitcoin", "rev-parse", "HEAD"]),
                  host=dict(platform=platform.platform(), machine=platform.machine(), python=sys.version,
                            rustc=command(["rustc", "--version"]), clang=command(["clang", "--version"])),
                  sources=source_hashes(), upstream_sources=upstream_sources,
                  binaries={str(p.relative_to(ROOT)): file_sha(p) for p in (DEFAULT_BINARY, PROFILE, BINARY)},
                  modes={}, repeats=repeats)
    for mode in MODES:
        fixture = HERE / f"fixtures/{mode}.wit"
        proof = ref.load_fixture(fixture)
        check(fixture.read_bytes() == (UPSTREAM / f"examples/shrincs/shrincs_main_{mode}.wit").read_bytes(), "fixture differs from upstream")
        inputs = list(cases(proof))
        programs = {profile: gsr.compile_verifier(mode, profile) for profile in PROFILES}
        print(f"{mode}: evaluating {len(inputs)} public fixture cases in Simplicity", flush=True)
        observed = run_simplicity(mode, inputs, repeats)
        print(f"{mode}: checking the same cases in four GSR profiles", flush=True)
        inventory = []
        for (name, vector), simp in zip(inputs, observed):
            expected = ref.verify(vector)
            check(simp["success"] == expected, f"Simplicity/reference disagreement: {mode} {name}")
            for profile, program in programs.items():
                res = evaluate(program.code, ref.stack(vector))
                check(res.classification != "budget", f"budget exhaustion: {mode} {profile} {name}")
                check(res.success == expected, f"GSR disagreement: {mode} {profile} {name}")
                if res.success:
                    check(not res.stack, "unexpected evaluator remainder")
            inventory.append(dict(name=name, proof_sha256=value_sha(vector), accepted=expected))
        simp = observed[0]
        check(simp["success"] and int(simp["cost_bound"]) == simp["c_cost_bound"], "Simplicity native cost disagreement")
        normalized = ref.stack(proof)
        row = dict(fixture_sha256=file_sha(fixture), proof_sha256=value_sha(proof),
                   source_sha256=file_sha(WORK / f"{mode}.simf"),
                   logical_input_bytes=sum(map(len, normalized)),
                   cases=inventory, simplicity=simp, gsr={})
        for profile, program in programs.items():
            req = dict(protocol=1, sigversion="tapscript_v2", script=program.code.hex(),
                       stack=[x.hex() for x in normalized], varops_budget=1_000_000_000, profile=True)
            profiled = run_profile("evalscript", req)
            native = evaluate(program.code, normalized)
            check(profiled["success"] and native.success and native.remaining == profiled["varops-budget-remaining"], "profiling disagreement")
            times = []
            for _ in range(repeats):
                timed = run_profile("evalscript", dict(req, profile=False))
                check(timed["success"] and timed["varops-budget-remaining"] == native.remaining, "timing disagreement")
                times.append(timed["profile"]["interpreter_ns"])
            row["gsr"][profile] = dict(program_bytes=len(program.code), program_sha256=sha(program.code),
                                       varops=native.consumed, interpreter_ns=times, metrics=profiled["profile"])
        result["modes"][mode] = row
        print(f"{mode}: {len(inputs)} cases agree across Python, Simplicity, and four GSR profiles", flush=True)
    (HERE / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def audit(execute=False):
    report = json.loads((HERE / "results.json").read_text())
    check(report["sources"] == source_hashes(), "experiment source changed; regenerate evidence")
    check(report["upstream_revision"] == ref.PIN, "wrong upstream pin")
    for mode in MODES:
        row = report["modes"][mode]
        fixture = HERE / f"fixtures/{mode}.wit"
        proof = ref.load_fixture(fixture)
        check(row["fixture_sha256"] == file_sha(fixture), "fixture changed")
        check(row["proof_sha256"] == value_sha(proof), "proof changed")
        check(row["logical_input_bytes"] == sum(map(len, ref.stack(proof))), "input size changed")
        expected = [dict(name=n, proof_sha256=value_sha(p), accepted=ref.verify(p)) for n, p in cases(proof)]
        check(row["cases"] == expected, "case inventory or outcomes changed")
        s = row["simplicity"]
        check(s["success"] is True and int(s["cost_bound"]) == s["c_cost_bound"], "invalid Simplicity result")
        for name in ("program", "witness"):
            check(len(bytes.fromhex(s[f"{name}_hex"])) == s[f"{name}_bytes"], "Simplicity encoded size changed")
        for profile in PROFILES:
            p = gsr.compile_verifier(mode, profile)
            measured = row["gsr"][profile]
            check(sha(p.code) == measured["program_sha256"] and len(p.code) == measured["program_bytes"], "GSR compile changed")
            check(len(measured["interpreter_ns"]) == report["repeats"], "missing timing samples")
    if execute:
        check(prepare() == report["upstream_sources"], "upstream files changed")
        for path, expected in report["binaries"].items():
            check(file_sha(ROOT / path) == expected, f"binary changed: {path}")
        for mode in MODES:
            row = report["modes"][mode]
            check(file_sha(WORK / f"{mode}.simf") == row["source_sha256"], "preprocessed source changed")
            inputs = list(cases(ref.load_fixture(HERE / f"fixtures/{mode}.wit")))
            observed = run_simplicity(mode, inputs, 1)
            for (name, proof), simp in zip(inputs, observed):
                check(simp["success"] == ref.verify(proof), f"Simplicity replay changed: {name}")
            for key in ("program_hex", "witness_hex", "cmr", "cost_bound", "c_cost_bound", "jets", "extra_cells_bound", "extra_frames_bound", "unpruned_program_bytes"):
                check(observed[0][key] == row["simplicity"][key], f"Simplicity replay changed: {key}")
            for profile in PROFILES:
                program = gsr.compile_verifier(mode, profile)
                for name, proof in inputs:
                    res = evaluate(program.code, ref.stack(proof))
                    check(res.classification != "budget" and res.success == ref.verify(proof), f"GSR replay changed: {name}")
                    if name == "upstream":
                        check(res.consumed == row["gsr"][profile]["varops"], "GSR charge changed")
    print("Experiment evidence verified" + (" with local execution" if execute else " (portable checks; no VM execution)"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "measure", "audit"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--repeats", type=int, default=11)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100:
        parser.error("repeats must be between 1 and 100")
    if args.action == "prepare": prepare()
    elif args.action == "measure": measure(args.repeats)
    else: audit(args.execute)
