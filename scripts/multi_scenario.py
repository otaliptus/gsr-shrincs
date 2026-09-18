#!/usr/bin/env python3
"""Measure the OP_MULTI scenario against the audited full profile.

Checks that the extended programs accept and reject exactly what the reference
does on the public vectors, their standard mutations, and a sample of stateful
depths. Then measures standalone and offline-transaction costs for the audited
``full`` profile, the ``catfix`` variant, and the ``multi`` variant, with one
signature and one transaction shape per signature type.
"""
import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from generator import multi
from generator.script import OPS
from generator.transaction import compile_policy as audited_policy
from generator.verifier import compile_verifier as audited_verifier
from reference.oracle import CONTEXT, PUBLIC_SEED, decode, scheme, synthetic_stateful, verify
from runner.bitcoin import NUMS_XONLY, control_block, message
from runner.evaluator import evaluate
from runner.evidence import NATIVE, PROFILE, host_environment, provenance, verify_provenance
from runner.profile import run_profile
from test_framework.messages import COutPoint, CTransaction, CTxIn, CTxInWitness, CTxOut
from test_framework.script import LEAF_VERSION_TAPSCRIPT_V2, CScript, taproot_construct

INV = {v: k for k, v in OPS.items()}
FIXED = {"INVOKE": 4000, "MUL": 3000, "DIV": 3000, "MOD": 3000, "NUMEQUAL": 3000, "LESSTHAN": 3000,
         "LESSTHANOREQUAL": 3000, "LSHIFT": 3000, "RSHIFT": 3000}
VARIANTS = ("full", "catfix", "multi")
FIXTURES = "fixtures/vectors.json"


def programs(mode):
    out = {"full": audited_verifier("full", mode)}
    for name in ("catfix", "multi"):
        out[name] = multi.compile_verifier(name, mode)
    return out


def check_agreement(sample_depths):
    vectors = json.loads((ROOT / "fixtures/vectors.json").read_text())["vectors"]
    cases = 0
    for mode in ("unified", "stateful", "stateless"):
        progs = programs(mode)
        for vector in vectors:
            sig, pk, msg = decode(vector)
            stateless = sig[0] == 255
            if mode != "unified" and (mode == "stateless") != stateless:
                continue
            context = bytes.fromhex(vector["context"])
            for args in ((sig, pk, msg), (sig, pk, bytes([msg[0] ^ 1]) + msg[1:]), (sig[:-1], pk, msg),
                         (sig[:-1] + bytes([sig[-1] ^ 1]), pk, msg), (sig, bytes([pk[0] ^ 1]) + pk[1:], msg)):
                expected = verify(args[2], args[0], args[1], context)
                for name, program in progs.items():
                    result = evaluate(program.code, args)
                    if result.classification == "budget" or result.success != expected or (result.success and result.stack):
                        raise SystemExit(f"disagreement: {mode} {name} {vector['name']}")
                cases += 1
    progs = programs("unified")
    for depth in sample_depths:
        for index in (0, 2 ** min(depth, 64) - 1):
            args = decode(synthetic_stateful(depth, index))
            for name, program in progs.items():
                result = evaluate(program.code, args)
                if not result.success or result.stack:
                    raise SystemExit(f"boundary rejected: {name} depth {depth} index {index}")
            cases += 1
    return cases


def metrics_row(response):
    m = response["profile"]
    ops = sum(m["opcodes"].values())
    fixed = sum(v * FIXED.get(INV.get(int(k), ""), 1250) for k, v in m["opcodes"].items())
    return dict(opcodes=ops, fixed_charge=fixed, sha256_calls=m["sha256_calls"], invocations=m["invocations"],
                peak_total_bytes=m["peak_total_bytes"], max_item_bytes=m["max_item_bytes"],
                executed_function_body_bytes=m["executed_function_body_bytes"])


def measure_transactions(repeats):
    key, pk = scheme.shrincs_keygen(PUBLIC_SEED, b"\x01\x08")
    dest = CScript(bytes.fromhex("0014") + bytes(20))
    rows = {}
    for mode, state in (("stateful", 0), ("stateless", None)):
        other_mode = "stateless" if mode == "stateful" else "stateful"
        for name in VARIANTS:
            if name == "full":
                code = audited_policy(pk, mode=mode, profile="full").code
                other = audited_policy(pk, mode=other_mode, profile="full").code
                bodies = audited_verifier("full", mode).functions
            else:
                code = multi.compile_policy(name, pk, mode=mode).code
                other = multi.compile_policy(name, pk, mode=other_mode).code
                bodies = multi.compile_verifier(name, mode).functions
            tap = taproot_construct(NUMS_XONLY, [("verify", CScript(code), LEAF_VERSION_TAPSCRIPT_V2),
                                                 ("other", CScript(other), LEAF_VERSION_TAPSCRIPT_V2)])
            tx = CTransaction()
            tx.version = 2
            tx.vin = [CTxIn(COutPoint(1, 0), CScript(), 0xFFFFFFFE)]
            tx.vout = [CTxOut(48_900_000, dest), CTxOut(100_000, dest)]
            spent = [CTxOut(50_000_000, tap.scriptPubKey)]
            sig = scheme.shrincs_sign(message(tx, spent, 0, code), CONTEXT, key, state, None)
            tx.wit.vtxinwit = [CTxInWitness()]
            tx.wit.vtxinwit[0].scriptWitness.stack = [sig, code, control_block(tap, "verify")]
            request = dict(transaction=tx.serialize().hex(), spent_outputs=[s.serialize().hex() for s in spent])
            observed = run_profile("measuretx", dict(request, profile=True))
            if not observed["success"]:
                raise SystemExit(f"transaction rejected: {name} {mode} {observed}")
            times = []
            for _ in range(repeats):
                plain = run_profile("measuretx", dict(request, profile=False))
                if plain["varops_consumed"] != observed["varops_consumed"]:
                    raise SystemExit("instrumentation changed accounting")
                times.append(plain["profile"]["interpreter_ns"])
            rows[f"{name}-{mode}"] = dict(
                variant=name, mode=mode, signature_bytes=len(sig), program_bytes=len(code), times_ns=times,
                function_body_bytes=sum(len(v[1]) for v in bodies.values()),
                control_block_bytes=len(control_block(tap, "verify")), transaction_bytes=len(tx.serialize()),
                weight=tx.get_weight(), vbytes=tx.get_vsize(), varops_consumed=observed["varops_consumed"],
                varops_allowed=observed["varops_allowed"],
                budget_fraction=observed["varops_consumed"] / observed["varops_allowed"],
                median_interpreter_ms=statistics.median(times) / 1e6, metrics=metrics_row(observed),
                multi_uses=multi.multi_uses(code, [v[1] for v in bodies.values()]),
                program_sha256=hashlib.sha256(code).hexdigest())
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/multi-scenario.json")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--depths", default="1,64,255")
    args = parser.parse_args()
    depths = [int(x) for x in args.depths.split(",")]
    cases = check_agreement(depths)
    print(f"agreement: {cases} cases across three variants", flush=True)
    rows = measure_transactions(args.repeats)
    sizes = {f"{name}-{mode}": len(p.code) for mode in ("unified", "stateful", "stateless")
             for name, p in programs(mode).items()}
    proof = provenance(ROOT, [FIXTURES], [NATIVE, PROFILE])
    verify_provenance(ROOT, proof, [FIXTURES], [NATIVE, PROFILE])
    data = dict(
        scope="Laboratory extension of the audited full profile; the audited programs are unchanged",
        provenance=proof, environment=host_environment(), repeats=args.repeats,
        agreement_cases=cases, sample_depths=depths, standalone_program_bytes=sizes, transactions=rows)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    for key, row in rows.items():
        print(f"{key:20} program={row['program_bytes']:>7,} vbytes={row['vbytes']:>6,} varops={row['varops_consumed']:>12,} "
              f"{row['budget_fraction']:6.1%} ops={row['metrics']['opcodes']:>7,} multi={row['multi_uses']} {row['median_interpreter_ms']:.2f}ms")


if __name__ == "__main__":
    main()
