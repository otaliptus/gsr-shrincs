#!/usr/bin/env python3
"""Measure the OP_MULTI extension against the audited profiles.

Checks that the extended programs accept and reject exactly what the reference
does on the public vectors, their standard mutations, and a sample of stateful
depths. Then measures two things for the audited ``baseline``, ``bytes`` and
``full`` profiles and the ``catfix``, ``multi`` and ``multisel`` variants:

- Matched-input standalone runs: one public fixture per signature type,
  evaluated by every program. These isolate the program's effect, because the
  signature bytes are identical across programs.
- Complete transactions: one input, two outputs, a two-leaf tree, one freshly
  signed transaction per program. These give real spend sizes. Their charged
  costs are not directly comparable across programs, because the script is part
  of the signed message and a different message changes the hash-chain work.

The report records the raw transactions so the follow-up audit can re-derive
sizes, re-verify signatures, and re-execute the measurements.
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
AUDITED = ("baseline", "bytes", "full")
EXTENDED = ("catfix", "multi", "multisel")
VARIANTS = AUDITED + EXTENDED
FIXTURES = "fixtures/vectors.json"
ARG_VARIANTS = 5
STANDALONE_BUDGET = 1_000_000_000


def verifier(name, mode):
    return audited_verifier(name, mode) if name in AUDITED else multi.compile_verifier(name, mode)


def policy(name, pk, mode):
    return audited_policy(pk, mode=mode, profile=name) if name in AUDITED else multi.compile_policy(name, pk, mode=mode)


def fixed_charge(metrics):
    """Sum of fixed prices: ordinary opcodes by count, OP_MULTI by its logical operations."""
    total = 0
    for opcode, count in metrics["opcodes"].items():
        if int(opcode) == OPS["MULTI"]:
            continue
        total += count * FIXED.get(INV.get(int(opcode), ""), 1250)
    for target, operations in metrics["multi_operations"].items():
        total += operations * FIXED.get(INV.get(int(target), ""), 1250)
    return total


def metrics_row(metrics):
    return dict(opcodes=sum(metrics["opcodes"].values()), multi_operations=sum(metrics["multi_operations"].values()),
                fixed_charge=fixed_charge(metrics), sha256_calls=metrics["sha256_calls"],
                sha256_compressions=metrics["sha256_compressions"], invocations=metrics["invocations"],
                peak_total_bytes=metrics["peak_total_bytes"], max_item_bytes=metrics["max_item_bytes"],
                executed_function_body_bytes=metrics["executed_function_body_bytes"])


def agreement_inventory(vectors, depths):
    return dict(vectors=len(vectors), leaf_forms=2, argument_variants=ARG_VARIANTS, variants=list(EXTENDED),
                sample_depths=list(depths), index_extremes=2,
                expected_cases=len(vectors) * 2 * ARG_VARIANTS + len(depths) * 2)


def check_agreement(vectors, depths):
    cases = 0
    for mode in ("unified", "stateful", "stateless"):
        progs = {name: verifier(name, mode) for name in ("full",) + EXTENDED}
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
    progs = {name: verifier(name, "unified") for name in ("full",) + EXTENDED}
    for depth in depths:
        for index in (0, 2 ** min(depth, 64) - 1):
            args = decode(synthetic_stateful(depth, index))
            for name, program in progs.items():
                result = evaluate(program.code, args)
                if not result.success or result.stack:
                    raise SystemExit(f"boundary rejected: {name} depth {depth} index {index}")
            cases += 1
    return cases


def standalone_rows(vectors):
    rows = {}
    for mode in ("stateful", "stateless"):
        vector = next(v for v in vectors if (bytes.fromhex(v["signature"])[0] == 255) == (mode == "stateless"))
        args = decode(vector)
        for name in VARIANTS:
            program = verifier(name, mode)
            native = evaluate(program.code, args, STANDALONE_BUDGET)
            request = dict(protocol=1, sigversion="tapscript_v2", script=program.code.hex(),
                           stack=[x.hex() for x in args], varops_budget=STANDALONE_BUDGET, profile=True)
            observed = run_profile("evalscript", request)
            if not (native.success and observed["success"]):
                raise SystemExit(f"standalone rejected: {name} {mode}")
            if native.remaining != observed["varops-budget-remaining"]:
                raise SystemExit("native and profiling accounting disagree")
            rows[f"{name}-{mode}"] = dict(
                variant=name, mode=mode, fixture=vector["name"], program_bytes=len(program.code),
                program_sha256=hashlib.sha256(program.code).hexdigest(),
                input_sha256=hashlib.sha256(b"".join(args)).hexdigest(), varops_consumed=native.consumed,
                metrics=metrics_row(observed["profile"]),
                multi_uses=multi.multi_uses(program.code, [v[1] for v in program.functions.values()]))
    return rows


def transaction_rows(repeats):
    key, pk = scheme.shrincs_keygen(PUBLIC_SEED, b"\x01\x08")
    dest = CScript(bytes.fromhex("0014") + bytes(20))
    rows = {}
    for mode, state in (("stateful", 0), ("stateless", None)):
        other_mode = "stateless" if mode == "stateful" else "stateful"
        for name in VARIANTS:
            code = policy(name, pk, mode).code
            other = policy(name, pk, other_mode).code
            bodies = verifier(name, mode).functions
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
                variant=name, mode=mode, public_key=pk.hex(), raw_transaction=request["transaction"],
                spent_outputs=request["spent_outputs"], signature_bytes=len(sig), program_bytes=len(code),
                program_sha256=hashlib.sha256(code).hexdigest(),
                function_body_bytes=sum(len(v[1]) for v in bodies.values()),
                control_block_bytes=len(control_block(tap, "verify")), transaction_bytes=len(tx.serialize()),
                weight=tx.get_weight(), vbytes=tx.get_vsize(), varops_consumed=observed["varops_consumed"],
                varops_allowed=observed["varops_allowed"],
                budget_fraction=observed["varops_consumed"] / observed["varops_allowed"],
                times_ns=times, median_interpreter_ms=statistics.median(times) / 1e6,
                metrics=metrics_row(observed["profile"]),
                multi_uses=multi.multi_uses(code, [v[1] for v in bodies.values()]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/multi-scenario.json")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--depths", default="1,64,255")
    args = parser.parse_args()
    depths = [int(x) for x in args.depths.split(",")]
    vectors = json.loads((ROOT / FIXTURES).read_text())["vectors"]
    inventory = agreement_inventory(vectors, depths)
    cases = check_agreement(vectors, depths)
    if cases != inventory["expected_cases"]:
        raise SystemExit(f"agreement inventory mismatch: {cases} != {inventory['expected_cases']}")
    print(f"agreement: {cases} cases", flush=True)
    standalone = standalone_rows(vectors)
    transactions = transaction_rows(args.repeats)
    proof = provenance(ROOT, [FIXTURES], [NATIVE, PROFILE])
    verify_provenance(ROOT, proof, [FIXTURES], [NATIVE, PROFILE])
    data = dict(
        scope="Laboratory extension of the audited profiles; the audited programs are unchanged",
        provenance=proof, environment=host_environment(), repeats=args.repeats, standalone_budget=STANDALONE_BUDGET,
        agreement=inventory, agreement_cases=cases, variants=list(VARIANTS), audited=list(AUDITED),
        standalone=standalone, transactions=transactions)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    for key, row in standalone.items():
        print(f"standalone  {key:20} program={row['program_bytes']:>7,} varops={row['varops_consumed']:>12,} "
              f"sha={row['metrics']['sha256_calls']:>5} multi={row['multi_uses']}")
    for key, row in transactions.items():
        print(f"transaction {key:20} vbytes={row['vbytes']:>6,} varops={row['varops_consumed']:>12,} {row['budget_fraction']:6.1%} "
              f"{row['median_interpreter_ms']:.2f}ms")


if __name__ == "__main__":
    main()
