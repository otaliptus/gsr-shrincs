"""Exact local provenance for the follow-up measurements."""
import hashlib
import json
import platform
import sys

from runner.checks import require


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def host_environment():
    return dict(platform=platform.platform(), machine=platform.machine(), python=sys.version)


def drivers(root):
    return {str(p.relative_to(root)): sha(p)
            for directory in ("generator", "runner", "reference", "scripts")
            for p in sorted((root / directory).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def provenance(root, inputs, binaries):
    return dict(schema=1, inputs={name: sha(root / name) for name in inputs},
                binaries={name: sha(root / name) for name in binaries},
                drivers=drivers(root), environment=host_environment())


def verify_provenance(root, recorded, inputs, binaries, environment=None, *, check_binaries=True):
    require(recorded.get("schema") == 1, "unsupported follow-up provenance")
    require(set(recorded["inputs"]) == set(inputs), "follow-up input inventory changed")
    require(set(recorded["binaries"]) == set(binaries), "follow-up binary inventory changed")
    for category in ("inputs", "binaries"):
        if category == "binaries" and not check_binaries:
            continue
        for name, expected in recorded[category].items():
            require(sha(root / name) == expected, ("stale follow-up " + category, name))
    require(recorded["drivers"] == drivers(root), "stale follow-up measurement code")
    if environment is not None:
        for name, expected in recorded["binaries"].items():
            require(environment["binaries"].get(name) == expected,
                    ("follow-up binary differs from environment", name))
        require(recorded["environment"] == {k: environment[k] for k in host_environment()},
                "follow-up measurement environment differs")


CORPUS = "reports/regtest-details.json.gz"
COSTS = "reports/costs.json"
COUNTS = "reports/parsing-counts.json"
NATIVE = "build/bitcoin/bin/bitcoin-util"
PROFILE = "build/profile/bin/bitcoin-util"
PROBE = "build/parsing-probe/build/bin/bitcoin-util"
PARSER = "build/parser-benchmark/build/bin/bitcoin-util"
