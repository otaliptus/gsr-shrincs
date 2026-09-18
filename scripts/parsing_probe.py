#!/usr/bin/env python3
"""Observe parsing on recorded spends without changing consensus charges."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import profile_build
from runner.comparison import sample
from runner.evidence import CORPUS, COSTS, provenance, verify_provenance, sha


def prepare(source, output):
    # First construct and validate the original observation-only overlay.
    old_source, old_target = profile_build.SOURCE, profile_build.TARGET
    try:
        profile_build.SOURCE = source
        profile_build.TARGET = output / "source"
        profile_build.prepare()
    finally:
        profile_build.SOURCE, profile_build.TARGET = old_source, old_target
    target = output / "source"
    header_path = target / "src/gsr_profile.hpp"
    header = header_path.read_text()
    header = profile_build.replace_once(header, "    bool enabled{true};", """    bool enabled{true};
    uint64_t parsed_bytes{}, parsed_instructions{}, skipped_bytes{}, skipped_instructions{}, skipped_push_bytes{};
""")
    header = profile_build.replace_once(header, '        r.pushKV("observations_enabled",enabled);', """        r.pushKV("observations_enabled",enabled);
        r.pushKV("parsed_bytes",parsed_bytes); r.pushKV("parsed_instructions",parsed_instructions);
        r.pushKV("skipped_bytes",skipped_bytes); r.pushKV("skipped_instructions",skipped_instructions);
        r.pushKV("skipped_push_bytes",skipped_push_bytes);
""")
    header_path.write_text(header)
    path = target / "src/script/interpreter.cpp"
    text = path.read_text()
    start = text.index("static bool EvalTapscriptV2Impl(")
    before, body = text[:start], text[start:]
    needle = "            if (!script.GetOp(pc, opcode, vchPushValue))"
    body = profile_build.replace_once(body, needle, "            const auto parsed_begin = pc;\n" + needle)
    needle = "            const bool executes_opcode{fExec || (OP_IF <= opcode && opcode <= OP_ENDIF)};"
    body = profile_build.replace_once(body, needle, needle + """
            if (gsr_profile.enabled) {
                const uint64_t parsed_size = pc - parsed_begin;
                gsr_profile.parsed_bytes += parsed_size;
                ++gsr_profile.parsed_instructions;
                if (!executes_opcode) {
                    gsr_profile.skipped_bytes += parsed_size;
                    ++gsr_profile.skipped_instructions;
                    if (opcode <= OP_PUSHDATA4) gsr_profile.skipped_push_bytes += vchPushValue.size();
                }
            }
""")
    path.write_text(before + body)
    allowed = {"src/script/interpreter.cpp", "src/bitcoin-util.cpp", "src/gsr_profile.hpp"}
    source_hashes, target_hashes = profile_build.hashes(source), profile_build.hashes(target)
    if set(target_hashes) != set(source_hashes) | {"src/gsr_profile.hpp"}:
        raise RuntimeError("unexpected parsing overlay files")
    if any(target_hashes[name] != value for name, value in source_hashes.items() if name not in allowed):
        raise RuntimeError("parsing overlay modified an unrelated source")
    manifest = dict(source_files=source_hashes, target_files=target_hashes,
                    driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    base_overlay=profile_build.overlay_inputs())
    (output / "parsing-source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return target


def build_probe(source, output, jobs):
    build = output / "build"
    configure = ["cmake", "-S", source, "-B", build, "-G", "Ninja",
                 "-DCMAKE_BUILD_TYPE=Release", "-DENABLE_IPC=OFF", "-DENABLE_WALLET=OFF",
                 "-DBUILD_GUI=OFF", "-DWITH_CCACHE=OFF", "-DBUILD_TESTS=OFF", "-DBUILD_UTIL=ON"]
    local = ROOT / "build/deps/usr"
    if local.exists():
        configure.append("-DCMAKE_PREFIX_PATH=" + str(local))
    with (output / "build.log").open("w") as log:
        subprocess.run(configure, stdout=log, stderr=subprocess.STDOUT, check=True)
        subprocess.run(["cmake", "--build", build, "--target", "bitcoin-util", "-j", str(jobs)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    return build / "bin/bitcoin-util"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "vendor/bitcoin")
    parser.add_argument("--reference-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/parsing-probe")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/parsing-counts.json")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("jobs must be positive")
    output = args.output.resolve()
    if output == ROOT or ROOT.is_relative_to(output):
        parser.error("output must not contain the active repository")
    output.mkdir(parents=True, exist_ok=True)
    source = prepare(args.source.resolve(), output)
    binary = build_probe(source, output, args.jobs)
    binary_names = [str(path.resolve().relative_to(ROOT)) for path in (args.reference_binary, binary)]
    proof = provenance(ROOT, [CORPUS, COSTS], binary_names)
    records = json.loads(gzip.decompress((ROOT / "reports/regtest-details.json.gz").read_bytes()))
    rows = []
    for row in records["spends"]:
        request = dict(transaction=row["raw_transaction"], spent_outputs=row["spent_outputs"])
        original, _ = sample(args.reference_binary, "measuretx", request, True)
        result, response = sample(binary, "measuretx", request, True)
        if result != original or result["classification"] != "accept":
            raise RuntimeError("parsing observation changed acceptance or accounting")
        metrics = response["profile"]
        rows.append(dict(name=row["name"], result=result,
                         counts={name: metrics[name] for name in ("parsed_bytes", "parsed_instructions", "skipped_bytes", "skipped_instructions", "skipped_push_bytes")}))
    manifest = (output / "parsing-source-manifest.json").read_bytes()
    report = dict(rows=rows, provenance=proof, source_manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                  build_cache_sha256=sha(output / "build/CMakeCache.txt"),
                  binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  reference_binary_sha256=hashlib.sha256(args.reference_binary.read_bytes()).hexdigest(),
                  corpus_sha256=hashlib.sha256((ROOT / "reports/regtest-details.json.gz").read_bytes()).hexdigest(),
                  scope="Counts inside EvalTapscriptV2Impl, including invoked bodies. Does not count the separate success-opcode scan or decode OP_MULTI's second opcode separately. No causal timing claim.")
    verify_provenance(ROOT, proof, [CORPUS, COSTS], binary_names)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    args.report.with_name("parsing-source-manifest.json.gz").write_bytes(gzip.compress(manifest, mtime=0))
    print(args.report, flush=True)


if __name__ == "__main__":
    main()
