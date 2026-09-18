#!/usr/bin/env python3
"""Build two pinned forks and compare fixed and recompiled SHRINCS workloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.comparison import run_pair, summarize, render_report
from scripts.comparison_corpus import load_json, write_json

BASELINE = "937e05811e45b1b61f505201ac8f06c05abf2253"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def resolve(repo, ref):
    # --end-of-options prevents refs from becoming Git options.
    return git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")


def blob(repo, ref, path):
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{ref}:{path}"])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log, cwd=None, env=None):
    with log.open("a") as stream:
        stream.write("\nCOMMAND " + json.dumps([str(x) for x in command]) + "\n")
        stream.flush()
        subprocess.run([str(x) for x in command], cwd=cwd, stdout=stream,
                       stderr=subprocess.STDOUT, check=True, env=env)


def checkout(repo, ref, destination, log):
    if not (destination / ".git").exists():
        run(["git", "clone", "--shared", "--no-checkout", repo, destination], log)
        run(["git", "-C", destination, "checkout", "--detach", ref], log)
    if git(destination, "rev-parse", "HEAD") != ref:
        raise ValueError(f"checkout revision mismatch: {destination}")


def prepare_side(name, harness_ref, fork_ref, args, output, log):
    root = (args.build_cache or output) / name
    checkout(ROOT, harness_ref, root, log)
    versions = json.loads(blob(ROOT, harness_ref, "versions.json"))
    checkout(args.fork_repository, fork_ref, root / "vendor/bitcoin", log)
    checkout(ROOT / "vendor/shrincs-spec", versions["shrincs"]["commit"], root / "vendor/shrincs-spec", log)
    # The candidate submodule intentionally differs from its original gitlink.
    # Reports may change after a fresh regtest. Executable source must stay clean.
    changed = git(root, "status", "--porcelain", "--", "generator", "reference", "runner", "scripts", "spec", "tests", "fixtures")
    if changed:
        raise ValueError(f"modified snapshot source: {changed}")
    for sub in ("bitcoin", "shrincs-spec"):
        if git(root / "vendor" / sub, "status", "--porcelain"):
            raise ValueError(f"modified upstream source: {sub}")
    build = root / "build/bitcoin"
    print(f"Building {name}: fork {fork_ref[:12]}, harness {harness_ref[:12]}", flush=True)
    configure = ["cmake", "-S", root / "vendor/bitcoin", "-B", build, "-G", "Ninja",
                 "-DCMAKE_BUILD_TYPE=Release", "-DENABLE_IPC=OFF", "-DENABLE_WALLET=OFF",
                 "-DBUILD_GUI=OFF", "-DWITH_CCACHE=OFF"]
    if args.cmake_prefix:
        configure.append("-DCMAKE_PREFIX_PATH=" + str(args.cmake_prefix))
    run(configure, log)
    targets = ["bitcoin-util"]
    if args.mode in ("recompile", "both"):
        targets += ["bitcoind", "bitcoin-cli", "bitcoin-tx"]
    run(["cmake", "--build", build, "--target", *targets, "-j", str(args.jobs)], log)
    # The pinned overlay fails closed if its expected interpreter interface moved.
    # Porting the overlay requires a new, recorded harness revision.
    env = dict(os.environ)
    if args.cmake_prefix:
        env["CMAKE_PREFIX_PATH"] = str(args.cmake_prefix.resolve())
    run([sys.executable, root / "scripts/profile_build.py", str(args.jobs)], log, root, env)
    binary = root / "build/profile/bin/bitcoin-util"
    native = build / "bin/bitcoin-util"
    info = dict(root=str(root), harness_ref=harness_ref, fork_ref=fork_ref,
                native=str(native), profile=str(binary), native_sha256=sha(native),
                profile_sha256=sha(binary),
                profile_manifest_sha256=sha(root / "build/profile-source-manifest.json"),
                cache_sha256=sha(build / "CMakeCache.txt"))
    return info


def save(output, data):
    write_json(output / "results.json.gz", data)
    (output / "RESULTS.md").write_text(render_report(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-fork-ref", required=True)
    parser.add_argument("--baseline-harness-ref", default=BASELINE)
    parser.add_argument("--baseline-fork-ref")
    parser.add_argument("--candidate-harness-ref", default="HEAD")
    parser.add_argument("--fork-repository", type=Path, default=ROOT / "vendor/bitcoin")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("replay", "recompile", "both"), default="both")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=11)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cmake-prefix", type=Path)
    parser.add_argument("--build-cache", type=Path, help="reuse isolated checkouts with the same exact revisions")
    args = parser.parse_args()
    if args.jobs < 1 or args.repeats < 1:
        parser.error("jobs and repeats must be positive")
    args.fork_repository = args.fork_repository.resolve()
    if args.build_cache:
        args.build_cache = args.build_cache.resolve()
        if args.build_cache == ROOT or ROOT.is_relative_to(args.build_cache):
            parser.error("build cache must not contain the active repository")
    output = args.output.resolve()
    if output == ROOT or ROOT.is_relative_to(output):
        parser.error("output must not contain the active repository")
    baseline_harness = resolve(ROOT, args.baseline_harness_ref)
    candidate_harness = resolve(ROOT, args.candidate_harness_ref)
    baseline_versions = json.loads(blob(ROOT, baseline_harness, "versions.json"))
    baseline_fork = resolve(args.fork_repository, args.baseline_fork_ref or baseline_versions["bitcoin"]["commit"])
    candidate_fork = resolve(args.fork_repository, args.candidate_fork_ref)
    config = dict(schema=1, mode=args.mode, baseline_harness=baseline_harness,
                  candidate_harness=candidate_harness, baseline_fork=baseline_fork,
                  candidate_fork=candidate_fork, repeats=args.repeats, jobs=args.jobs,
                  fork_repository=str(args.fork_repository), cmake_prefix=str(args.cmake_prefix),
                  build_cache=str(args.build_cache),
                  driver_sha256={str(p.relative_to(ROOT)): sha(p) for p in (
                      Path(__file__), ROOT / "scripts/comparison_corpus.py", ROOT / "runner/comparison.py",
                      ROOT / "runner/profile.py", ROOT / "runner/evaluator.py")})
    if output.exists():
        if not args.resume or json.loads((output / "config.json").read_text()) != config:
            parser.error("output exists; resume requires identical resolved revisions and driver files")
    else:
        output.mkdir(parents=True)
        (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    data = dict(status="incomplete", config=config, comparisons={},
                environment=dict(platform=platform.platform(), machine=platform.machine(),
                                 python=sys.version, started_at=time.time()))
    log = output / "build.log"
    corpus_script = ROOT / "scripts/comparison_corpus.py"
    save(output, data)
    try:
        left = prepare_side("baseline", baseline_harness, baseline_fork, args, output, log)
        right = prepare_side("candidate", candidate_harness, candidate_fork, args, output, log)
        data["builds"] = dict(baseline=left, candidate=right)
        save(output, data)
        fixed_path = output / "fixed-corpus.json.gz"
        check_path = output / "fixed-corpus-check.json.gz"
        run([sys.executable, corpus_script, "--root", left["root"], "--output", check_path], log)
        if fixed_path.exists() and fixed_path.read_bytes() != check_path.read_bytes():
            raise ValueError("fixed corpus changed; start a new experiment")
        check_path.replace(fixed_path)
        fixed = load_json(fixed_path)
        data["fixed_corpus_sha256"] = sha(fixed_path)
        # Freeze the exact input relation before doing any execution comparison.
        baseline_check = json.loads(blob(ROOT, baseline_harness, "versions.json"))
        candidate_check = json.loads(blob(ROOT, candidate_harness, "versions.json"))
        if baseline_check["shrincs"] != candidate_check["shrincs"]:
            raise ValueError("SHRINCS specification changed; use a separate experiment")
        for name in ("spec/ACCEPTANCE.md", "spec/TRANSCRIPT.md"):
            if blob(ROOT, baseline_harness, name) != blob(ROOT, candidate_harness, name):
                raise ValueError(f"acceptance contract changed: {name}; review before comparison")

        def compare(mode, a, b):
            print(f"Running {mode}: {len(a['cases'])} cases", flush=True)
            with (output / f"{mode}.jsonl").open("w") as journal:
                def emit(row):
                    journal.write(json.dumps(row, sort_keys=True) + "\n")
                    journal.flush()
                rows = run_pair(left, right, a, b, repeats=args.repeats, emit=emit)
            data["comparisons"][mode] = dict(summary=summarize(rows), rows=rows)
            save(output, data)

        if args.mode in ("replay", "both"):
            compare("replay", fixed, fixed)
        if args.mode in ("recompile", "both"):
            regenerated = []
            for name, side in (("baseline", left), ("candidate", right)):
                root = Path(side["root"])
                print(f"Running fresh {name} regtest spends", flush=True)
                run([sys.executable, root / "tests/regtest.py",
                     "--configfile=" + str(root / "build/bitcoin/test/config.ini")], output / f"{name}-regtest.log", root)
                corpus_path = output / f"{name}-recompiled.json.gz"
                run([sys.executable, corpus_script, "--root", root, "--frozen", fixed_path,
                     "--output", corpus_path], log)
                regenerated.append(load_json(corpus_path))
                data.setdefault("regenerated", {})[name] = dict(corpus_sha256=sha(corpus_path),
                    node_regtest_completed=True, log_sha256=sha(output / f"{name}-regtest.log"))
            compare("recompile", *regenerated)
        failed = any(v["summary"]["baseline_unexpected"] or v["summary"]["candidate_unexpected"]
                     for v in data["comparisons"].values())
        data["status"] = "acceptance-change" if failed else "complete"
        for name, expected in config["driver_sha256"].items():
            if sha(ROOT / name) != expected:
                raise ValueError(f"comparison driver changed during execution: {name}")
        save(output, data)
        print(output / "RESULTS.md", flush=True)
        return 1 if failed else 0
    except Exception as exc:
        data["status"] = "incomplete"
        data["error"] = f"{type(exc).__name__}: {exc}. Inspect the build log and partial case journal."
        save(output, data)
        print(data["error"], file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
