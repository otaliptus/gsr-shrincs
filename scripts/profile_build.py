#!/usr/bin/env python3
"""Build an observation-only source overlay; never edit the pinned submodule."""
from pathlib import Path
import shutil
import subprocess
import sys
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "vendor/bitcoin"
TARGET = ROOT / "build/profile-source"
OVERLAY_FILES = {
    "src/script/interpreter.cpp",
    "src/bitcoin-util.cpp",
    "src/gsr_profile.hpp",
}


def source_files(directory):
    return {
        p.relative_to(directory).as_posix(): p
        for p in directory.rglob("*")
        if p.is_file()
        and not {".git", "__pycache__"} & set(p.relative_to(directory).parts)
    }


def hashes(directory):
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(source_files(directory).items())
    }


def overlay_inputs():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "scripts/profile_build.py",
            "runner/profile.hpp",
            "runner/measuretx.inc",
        )
    }


def verify_overlay():
    manifest = json.loads((TARGET.parent / "profile-source-manifest.json").read_text())
    source, target = hashes(SOURCE), hashes(TARGET)
    if source != manifest["source_files"] or target != manifest["target_files"]:
        raise RuntimeError("stale or modified profiling source tree")
    if overlay_inputs() != manifest["overlay_inputs"]:
        raise RuntimeError("stale profiling overlay inputs")
    if set(target) != set(source) | {"src/gsr_profile.hpp"}:
        raise RuntimeError("unexpected profiling source files")
    if any(
        target[name] != digest
        for name, digest in source.items()
        if name not in OVERLAY_FILES
    ):
        raise RuntimeError("profiling diff exceeds the permitted overlay")
    return manifest


def verify_build():
    verify_overlay()
    build = json.loads((TARGET.parent / "profile-build-manifest.json").read_text())
    for name, expected in build.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"stale profiling build: {name}")
    required = {"build/profile-source-manifest.json", "build/profile/bin/bitcoin-util"}
    if set(build) != required:
        raise RuntimeError("incomplete profiling build manifest")


def replace_once(text, needle, replacement):
    if text.count(needle) != 1:
        raise RuntimeError(f"overlay source mismatch: {needle[:70]}")
    return text.replace(needle, replacement)


def write_changed(path, text):
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def prepare():
    # Synchronize every file, including removals, while preserving unchanged
    # mtimes so repeat builds remain incremental. Never trust the cache marker.
    sources = source_files(SOURCE)
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, path in source_files(TARGET).items():
        if name not in sources and name not in OVERLAY_FILES:
            path.unlink()
    for name, source in sources.items():
        if name in OVERLAY_FILES:
            continue
        destination = TARGET / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_bytes() != source.read_bytes():
            shutil.copy2(source, destination)
    (TARGET / "src/script").mkdir(parents=True, exist_ok=True)
    write_changed(
        TARGET / "src/gsr_profile.hpp", (ROOT / "runner/profile.hpp").read_text()
    )
    text = (SOURCE / "src/script/interpreter.cpp").read_text()
    text = "#include <gsr_profile.hpp>\n" + text
    needle = "    ValtypeStack& altstack{shared_altstack ? *shared_altstack : local_altstack};"
    observe = """
    const auto gsr_observe = [&]() {
        if (!gsr_profile.enabled) return;
        const uint64_t entries=stack.size()+altstack.size();
        const uint64_t bytes=stack.GetTotalSize()+altstack.GetTotalSize();
        gsr_profile.stack_entries=std::max(gsr_profile.stack_entries,entries);
        gsr_profile.stack_bytes=std::max(gsr_profile.stack_bytes,bytes);
        gsr_profile.total_entries=std::max(gsr_profile.total_entries,entries+function_state.definition_count);
        gsr_profile.total_bytes=std::max(gsr_profile.total_bytes,bytes+function_state.stored_body_bytes);
        gsr_profile.max_item=std::max<uint64_t>(gsr_profile.max_item,std::max(stack.GetMaxElementSize(),altstack.GetMaxElementSize()));
        gsr_profile.function_storage=std::max<uint64_t>(gsr_profile.function_storage,function_state.stored_body_bytes);
        gsr_profile.executed_bodies=std::max<uint64_t>(gsr_profile.executed_bodies,function_state.invoked_body_bytes);
    };
    gsr_observe();
"""
    text = replace_once(text, needle, needle + observe)
    needle = "            const bool executes_opcode{fExec || (OP_IF <= opcode && opcode <= OP_ENDIF)};"
    text = replace_once(
        text,
        needle,
        needle
        + """
            if (gsr_profile.enabled && executes_opcode) ++gsr_profile.opcodes[static_cast<uint8_t>(opcode)];
            if (gsr_profile.enabled && fExec && opcode == OP_SHA256 && stack.size()) {
                ++gsr_profile.sha_calls;
                gsr_profile.sha_compressions += (stack.back().size()+9+63)/64;
            }
""",
    )
    needle = "                    function_state.active[id] = true;"
    text = replace_once(
        text,
        needle,
        "                    GsrFunctionSample gsr_sample{id,varops_budget};\n"
        + needle,
    )
    needle = "            // Size limits\n            const size_t stack_entries{stack.size() + altstack.size()};"
    text = replace_once(text, needle, "            gsr_observe();\n" + needle)
    write_changed(TARGET / "src/script/interpreter.cpp", text)
    text = (SOURCE / "src/bitcoin-util.cpp").read_text()
    text = (
        "#include <gsr_profile.hpp>\n#include <consensus/validation.h>\n#include <policy/policy.h>\n#include <primitives/transaction.h>\n"
        + text
    )
    needle = '    argsman.AddCommand("evalscript", "Evaluate a standalone Tapscript v2 script from a JSON request on standard input");'
    text = replace_once(
        text,
        needle,
        needle
        + '\n    argsman.AddCommand("measuretx", "Measure recorded transaction Script validation");',
    )
    needle = "    const std::optional<bool> op_success{\n        CheckTapscriptOpSuccess(script, SCRIPT_VERIFY_NONE, SigVersion::TAPSCRIPT_V2, &error)};"
    text = replace_once(
        text,
        needle,
        """    gsr_profile={};
    if(request.exists("profile")) gsr_profile.enabled=request["profile"].get_bool();
    const auto gsr_start=std::chrono::steady_clock::now();
"""
        + needle,
    )
    needle = '    UniValue result{UniValue::VOBJ};\n    result.pushKV("protocol", 1);'
    text = replace_once(
        text,
        needle,
        """    const uint64_t gsr_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-gsr_start).count();
"""
        + needle
        + '\n    result.pushKV("profile", gsr_profile.Json(gsr_ns));',
    )
    text = replace_once(
        text,
        "MAIN_FUNCTION\n{",
        (ROOT / "runner/measuretx.inc").read_text() + "\nMAIN_FUNCTION\n{",
    )
    needle = '        } else if (cmd->command == "evalscript") {'
    text = replace_once(
        text,
        needle,
        """        } else if (cmd->command == "measuretx") {
            ret = MeasureTransactionCommand(cmd->args, strPrint);
"""
        + needle,
    )
    write_changed(TARGET / "src/bitcoin-util.cpp", text)
    manifest = dict(
        source_files=hashes(SOURCE),
        target_files=hashes(TARGET),
        overlay_inputs=overlay_inputs(),
    )
    (TARGET.parent / "profile-source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    verify_overlay()


def main():
    prepare()
    configure = [
        "cmake",
        "-S",
        str(TARGET),
        "-B",
        str(ROOT / "build/profile"),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DENABLE_IPC=OFF",
        "-DENABLE_WALLET=OFF",
        "-DBUILD_GUI=OFF",
        "-DWITH_CCACHE=OFF",
        "-DBUILD_TESTS=OFF",
        "-DBUILD_DAEMON=OFF",
        "-DBUILD_CLI=OFF",
        "-DBUILD_TX=OFF",
        "-DBUILD_UTIL=ON",
    ]
    local = ROOT / "build/deps/usr"
    if local.exists():
        configure += ["-DCMAKE_PREFIX_PATH=" + str(local)]
    subprocess.run(configure, check=True)
    subprocess.run(
        [
            "cmake",
            "--build",
            str(ROOT / "build/profile"),
            "--target",
            "bitcoin-util",
            "-j",
            sys.argv[1] if len(sys.argv) > 1 else "4",
        ],
        check=True,
    )
    build = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "build/profile-source-manifest.json",
            "build/profile/bin/bitcoin-util",
        )
    }
    (ROOT / "build/profile-build-manifest.json").write_text(
        json.dumps(build, indent=2) + "\n"
    )
    verify_build()


if __name__ == "__main__":
    main()
