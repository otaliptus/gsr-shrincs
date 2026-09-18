#!/usr/bin/env python3
"""Compare three equivalent bounded transaction-output sum predicates."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from generator.script import push
from runner.bitcoin import NUMS_XONLY, control_block
from runner.comparison import sample
from runner.evidence import provenance, verify_provenance, value_sha, host_environment
from test_framework.messages import CTransaction, CTxIn, COutPoint, CTxOut, CTxInWitness
from test_framework.script import CScript, taproot_construct, LEAF_VERSION_TAPSCRIPT_V2

COUNT = bytes.fromhex("004000000000")
TOTAL = bytes.fromhex("008000000000")
AMOUNTS = bytes.fromhex("000000020001")
LIMIT = 32
EXPECTED = 1_000_000
OUTPUT_COUNTS = (1, 2, 4, 8, 16, 32)


def programs():
    # Require the same domain for each construction: 1 <= output count <= LIMIT.
    common = push(COUNT) + b"\xbd\x76" + push(0) + b"\xa0\x69\x76" + push(LIMIT) + b"\xa1\x69"
    multi = b"\x6b" + push(AMOUNTS) + b"\xbd\x6c\xbf\x93"
    selector = b"\x75" + push(TOTAL) + b"\xbd"
    unroll = b"\x6b" + push(AMOUNTS) + b"\xbd"
    for index in range(1, LIMIT):
        unroll += b"\x6c\x76\x6b" + push(index) + b"\xa0\x63\x93\x68"
    unroll += b"\x6c\x75"
    return {name: common + middle + push(EXPECTED) + b"\x9c"
            for name, middle in (("multi", multi), ("selector", selector), ("unroll", unroll))}


def request_for(code, count, delta=0):
    tap = taproot_construct(NUMS_XONLY, [("sum", CScript(code), LEAF_VERSION_TAPSCRIPT_V2)])
    tx = CTransaction()
    tx.version = 2
    tx.vin = [CTxIn(COutPoint(1, 0), CScript(), 0xFFFFFFFE)]
    tx.vout = [CTxOut(EXPECTED // count, CScript(b"\x51")) for _ in range(count)]
    if count:
        tx.vout[-1].nValue += EXPECTED % count + delta
    tx.wit.vtxinwit = [CTxInWitness()]
    tx.wit.vtxinwit[0].scriptWitness.stack = [code, control_block(tap, "sum")]
    spent = CTxOut(EXPECTED + 100_000, tap.scriptPubKey)
    return dict(transaction=tx.serialize().hex(), spent_outputs=[spent.serialize().hex()])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=31)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    codes = programs()
    binary_names = [str(args.binary.resolve().relative_to(ROOT))]
    proof = provenance(ROOT, [], binary_names)
    corpus = {name: {str(count): dict(valid=request_for(code, count), wrong_sum=request_for(code, count, 1),
                                     over_limit=request_for(code, LIMIT + 1), empty=request_for(code, 0))
                     for count in OUTPUT_COUNTS} for name, code in codes.items()}
    rows = []
    for count in OUTPUT_COUNTS:
        requests = {name: request_for(code, count) for name, code in codes.items()}
        records = {}
        for name, request in requests.items():
            result, response = sample(args.binary, "measuretx", request, True)
            if result["classification"] != "accept":
                raise RuntimeError((name, count, result))
            bad, _ = sample(args.binary, "measuretx", request_for(codes[name], count, 1), True)
            if bad["classification"] != "reject":
                raise RuntimeError(("incorrect sum did not reject", name, count, bad))
            over, _ = sample(args.binary, "measuretx", request_for(codes[name], LIMIT + 1), True)
            if over["classification"] != "reject":
                raise RuntimeError(("count limit did not reject", name, over))
            empty, _ = sample(args.binary, "measuretx", request_for(codes[name], 0), True)
            if empty["classification"] != "reject":
                raise RuntimeError(("empty output list did not reject", name, empty))
            records[name] = dict(construction=name, output_count=count, script_bytes=len(codes[name]),
                                 script_sha256=hashlib.sha256(codes[name]).hexdigest(), result=result,
                                 negative_results=dict(wrong_sum=bad, over_limit=over, empty=empty),
                                 metrics=response["profile"], times_ns=[])
        for iteration in range(args.repeats + 1):
            names = list(codes)
            names = names[iteration % 3:] + names[:iteration % 3]
            for name in names:
                result, response = sample(args.binary, "measuretx", requests[name], False)
                if result != records[name]["result"]:
                    raise RuntimeError("measurement changed result")
                if iteration:
                    records[name]["times_ns"].append(response["profile"]["interpreter_ns"])
        for row in records.values():
            row["median_ns"] = statistics.median(row["times_ns"])
            rows.append(row)
    verify_provenance(ROOT, proof, [], binary_names)
    data = dict(provenance=proof, corpus_sha256=value_sha(corpus), repeats=args.repeats,
                binary_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest(),
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                environment=dict(**host_environment(),
                                 timing="Counters disabled, profiling hooks present; host load is not controlled"),
                scope="Offline Script predicates; not funded transactions or a complete authorization policy",
                rule="1 <= output count <= 32 and sum of all output amounts equals 1000000 satoshis",
                programs={name: code.hex() for name, code in codes.items()}, rows=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    for row in rows:
        print(row["construction"], row["output_count"], row["script_bytes"], row["result"]["consumed"], row["median_ns"])


if __name__ == "__main__":
    main()
