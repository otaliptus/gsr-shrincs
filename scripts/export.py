#!/usr/bin/env python3
"""Deterministic bytecode, disassembly, source maps, and source/environment manifest."""
from pathlib import Path
import hashlib
import json
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.checks import require
from generator.verifier import compile_verifier
from generator.script import OPS


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args):
    return subprocess.check_output(
        args, cwd=ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def disassemble(code):
    inverse = {v: k for k, v in OPS.items()}
    pos = 0
    rows = []
    while pos < len(code):
        offset = pos
        opcode = code[pos]
        pos += 1
        n = None
        if opcode <= 75:
            n = opcode
        elif opcode in (76, 77, 78):
            width = 1 << (opcode - 76)
            n = int.from_bytes(code[pos : pos + width], "little")
            pos += width
        if n is not None:
            data = code[pos : pos + n]
            pos += n
            # Full pushed data is in the binary; avoid duplicating large function bodies.
            description = "PUSH " + (
                (data.hex() or "<empty>")
                if n <= 64
                else f"{n} bytes sha256={hashlib.sha256(data).hexdigest()}"
            )
        elif 81 <= opcode <= 96:
            description = str(opcode - 80)
        else:
            description = "OP_" + inverse[opcode]
        rows.append(f"{offset:07d} {description}")
    return "\n".join(rows) + "\n"


def program_artifacts(program, name):
    maps = dict(main=program.source_map, functions={})
    for fn, (fid, code, source_map) in program.functions.items():
        maps["functions"][fn] = dict(
            id=fid,
            bytes=len(code),
            sha256=hashlib.sha256(code).hexdigest(),
            source_map=source_map,
            assembly=disassemble(code),
        )
    return {
        name + ".bin": program.code,
        name + ".asm": disassemble(program.code).encode(),
        name + ".map.json": (json.dumps(maps, indent=2) + "\n").encode(),
    }


def main():
    destination = ROOT / "generated"
    destination.mkdir(exist_ok=True)
    manifest = {}
    for profile in ("baseline", "bytes", "full"):
        for mode in ("unified", "stateful", "stateless"):
            p = compile_verifier(profile, mode)
            name = f"{profile}-{mode}"
            for filename, contents in program_artifacts(p, name).items():
                (destination / filename).write_bytes(contents)
            manifest[name] = dict(
                bytes=len(p.code),
                sha256=hashlib.sha256(p.code).hexdigest(),
                function_body_bytes=sum(len(v[1]) for v in p.functions.values()),
            )
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    from scripts.profile_build import verify_build

    verify_build()
    versions = json.loads((ROOT / "versions.json").read_text())
    for key, path in (
        ("bitcoin", "vendor/bitcoin"),
        ("shrincs", "vendor/shrincs-spec"),
    ):
        require(
            command("git", "-C", path, "rev-parse", "HEAD") == versions[key]["commit"]
        )
        require(
            not command("git", "-C", path, "status", "--porcelain"),
            f"modified pinned source: {path}",
        )
    sources = {
        str(p.relative_to(ROOT)): digest(p)
        for directory in (
            "generator",
            "runner",
            "reference",
            "tests",
            "scripts",
            "spec",
        )
        for p in sorted((ROOT / directory).rglob("*"))
        if p.is_file() and "__pycache__" not in str(p)
    }
    metadata = dict(
        versions=versions,
        platform=platform.platform(),
        machine=platform.machine(),
        python=sys.version,
        compiler=command("c++", "--version").splitlines()[0],
        cmake=command("cmake", "--version").splitlines()[0],
        ninja=command("ninja", "--version"),
        sources_sha256=sources,
        fixtures_sha256=digest(ROOT / "fixtures/vectors.json"),
        binaries={
            str(p.relative_to(ROOT)): digest(p)
            for p in (
                ROOT / "build/bitcoin/bin/bitcoin-util",
                ROOT / "build/bitcoin/bin/bitcoind",
                ROOT / "build/profile/bin/bitcoin-util",
                ROOT / "build/parsing-probe/build/bin/bitcoin-util",
                ROOT / "build/parser-benchmark/build/bin/bitcoin-util",
            )
        },
        dependencies={p.name: digest(p) for p in (ROOT / "build/deps").glob("*.deb")},
    )
    metadata["profiling_build_manifest_sha256"] = digest(
        ROOT / "build/profile-build-manifest.json"
    )
    metadata["profiling_source_manifest_sha256"] = digest(
        ROOT / "build/profile-source-manifest.json"
    )
    metadata["cpu"] = (
        next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            "unknown",
        )
        if Path("/proc/cpuinfo").exists()
        else platform.processor()
    )
    for name, directory in (("bitcoin", "bitcoin"), ("profile", "profile"),
                            ("parsing_probe", "parsing-probe/build"), ("parser_benchmark", "parser-benchmark/build")):
        cache = ROOT / "build" / directory / "CMakeCache.txt"
        if cache.exists():
            metadata[f"{name}_build_flags"] = [
                line
                for line in cache.read_text().splitlines()
                if line.startswith(
                    (
                        "CMAKE_CXX_FLAGS",
                        "CMAKE_BUILD_TYPE",
                        "ENABLE_IPC:",
                        "ENABLE_WALLET:",
                        "WITH_CCACHE:",
                        "BUILD_GUI:",
                    )
                )
            ]
    (ROOT / "reports/environment.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    print("Exported nine programs and source/environment manifest")


if __name__ == "__main__":
    main()
