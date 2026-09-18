#!/usr/bin/env python3
"""Export a fixed workload, or recompile it in an isolated harness checkout."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))


def load_json(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def transaction_cases(root, committed=False):
    sys.path.insert(0, str(root / "vendor/bitcoin/test/functional"))
    from test_framework.messages import tx_from_hex
    if committed:
        raw = subprocess.check_output(["git", "-C", str(root), "show", "HEAD:reports/regtest-details.json.gz"])
        records = json.loads(gzip.decompress(raw))
    else:
        records = load_json(root / "reports/regtest-details.json.gz")
    cases = []
    for group, expected in (("spends", True), ("rejections", False)):
        for row in records[group]:
            tx = tx_from_hex(row["raw_transaction"])
            witness = [item.scriptWitness.stack for item in tx.wit.vtxinwit]
            # The fixed workload contains Taproot script spends. An annex is last.
            witness = [items[:-1] if len(items) >= 2 and items[-1].startswith(b"\x50") else items for items in witness]
            cases.append(dict(
                id=f"{group}/{row['name']}", command="measuretx", expected=expected,
                request=dict(transaction=row["raw_transaction"], spent_outputs=row["spent_outputs"]),
                artifacts=dict(program_bytes=sum(len(items[-2]) for items in witness),
                               signature_bytes=sum(len(items[0]) for items in witness),
                               control_block_bytes=sum(len(items[-1]) for items in witness),
                               weight=tx.get_weight(), vsize=tx.get_vsize()),
            ))
    if len(records["spends"]) != 14 or len(records["rejections"]) != 128:
        raise ValueError("expected the fixed fourteen spends and 128 negative transactions")
    return cases


def export(root, frozen=None):
    # The selected checkout supplies the compiler and reference, not this script's parent.
    sys.path.insert(0, str(root))
    from generator.verifier import compile_verifier
    from reference.oracle import decode, synthetic_stateful, verify

    programs, contracts, cases = {}, {}, []

    def program(profile, mode, context):
        contract = f"{profile}/{mode}/{context.hex()}"
        if contract not in contracts:
            compiled = compile_verifier(profile, mode, context)
            compiled.audit()
            code = compiled.code
            if frozen is None:
                recorded = root / "generated" / f"{profile}-{mode}.bin"
                if recorded.read_bytes() != code:
                    raise ValueError("baseline compiler output differs from its committed program")
            sha = digest(code)
            programs[sha] = code.hex()
            contracts[contract] = dict(profile=profile, mode=mode, context=context.hex(), sha256=sha)
        return contract

    def standalone(name, profile, mode, vector, values=None, expected=True):
        args = decode(vector) if values is None else values
        contract = program(profile, mode, bytes.fromhex(vector["context"]))
        cases.append(dict(
            id=name, command="evalscript", expected=expected, contract=contract,
            request=dict(protocol=1, sigversion="tapscript_v2", stack=[x.hex() for x in args],
                         varops_budget=1_000_000_000),
        ))

    if frozen is None:
        vectors = json.loads((root / "fixtures/vectors.json").read_text())["vectors"]
        for vector in vectors:
            mode = "stateless" if bytes.fromhex(vector["signature"])[0] == 255 else "stateful"
            for profile in ("baseline", "bytes", "full"):
                for leaf in ("unified", mode):
                    name = f"vectors/{profile}/{leaf}/{vector['name']}"
                    standalone(name, profile, leaf, vector)
                    sig, pk, msg = decode(vector)
                    for suffix, args in (
                        ("message", (sig, pk, bytes([msg[0] ^ 1]) + msg[1:])),
                        ("length", (sig[:-1], pk, msg)),
                        ("path", (sig[:-1] + bytes([sig[-1] ^ 1]), pk, msg)),
                    ):
                        accepted = verify(args[2], args[0], args[1], bytes.fromhex(vector["context"]))
                        standalone(name + "/" + suffix, profile, leaf, vector, args, accepted)
        for depth in range(1, 256):
            for index in (0, 2 ** min(depth, 64) - 1):
                vector = synthetic_stateful(depth, index)
                for profile in ("baseline", "bytes", "full"):
                    standalone(f"boundary/{profile}/{depth}/{index}", profile, "unified", vector)
    else:
        for contract, info in frozen["contracts"].items():
            actual = program(info["profile"], info["mode"], bytes.fromhex(info["context"]))
            if actual != contract:
                raise ValueError("changed compiler contract")
        cases = [row for row in frozen["cases"] if row["command"] == "evalscript"]
    cases.extend(transaction_cases(root, committed=frozen is None))
    ids = [row["id"] for row in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate workload case")
    if frozen is not None and ids != [row["id"] for row in frozen["cases"]]:
        raise ValueError("recompiled workload changed the case inventory")
    sources = {name: digest((root / name).read_bytes()) for name in (
        "fixtures/vectors.json", "reports/regtest-details.json.gz", "spec/ACCEPTANCE.md",
        "spec/TRANSCRIPT.md", "vendor/shrincs-spec/impl/shrincs.py")}
    if frozen is None:
        sources["reports/regtest-details.json.gz"] = digest(subprocess.check_output(
            ["git", "-C", str(root), "show", "HEAD:reports/regtest-details.json.gz"]))
    return dict(schema=1, programs=programs, contracts=contracts, cases=cases, source_files=sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frozen", type=Path)
    args = parser.parse_args()
    frozen = load_json(args.frozen) if args.frozen else None
    result = export(args.root.resolve(), frozen)
    write_json(args.output, result)
    print(f"Exported {len(result['cases'])} cases and {len(result['programs'])} programs", flush=True)


if __name__ == "__main__":
    main()
