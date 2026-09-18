"""Authenticated OP_TX wrapper: GSR-SHRINCS laboratory transcript v1."""

from runner.checks import require
from .script import Builder, Ref, op, cat, sha
from .verifier import compile_verifier, CONTEXT, Program

DOMAIN = b"GSR-SHRINCS/transaction/v1\x00"
TRANSCRIPT_SELECTOR = bytes.fromhex("00578b222f03")
COUNT_SELECTOR = bytes.fromhex("001000000000")
ANNEX_SELECTOR = bytes.fromhex("000002000000")
CODESEP_SELECTOR = bytes.fromhex("000080000000")
SELECTORS = (TRANSCRIPT_SELECTOR, COUNT_SELECTOR, ANNEX_SELECTOR, CODESEP_SELECTOR)


def compile_policy(
    public_key, context=CONTEXT, mode="unified", max_inputs=1, profile="full"
):
    if len(public_key) != 48 or not 1 <= max_inputs <= 4:
        raise ValueError("48-byte key and 1..4 inputs required")
    # OP_TX is an explicitly separate extension even when the verifier is baseline.
    b = Builder(("sig",), "full")
    b.emit("DEPTH")
    b.stack.append(None)
    b.literal(1)
    b.emit("NUMEQUAL")
    b.stack.pop()
    b.emit("VERIFY")
    b.stack.pop()
    count = op("TX", COUNT_SELECTOR)
    b.require(op("LESSTHAN", 0, count))
    b.require(op("LESSTHANOREQUAL", count, max_inputs))
    b.require(op("EQUAL", op("TX", ANNEX_SELECTOR), b""))
    b.require(op("EQUAL", op("TX", CODESEP_SELECTOR), b"\xff" * 4))
    b.let("pk", public_key)
    b.let("msg", sha(cat(DOMAIN, op("TX", TRANSCRIPT_SELECTOR))))
    require(b.stack == ["sig", "pk", "msg"])
    verifier = compile_verifier(profile, mode, context)
    program = Program(
        bytes(b.code) + verifier.code,
        "full",
        mode,
        [dict(offset=0, component="authenticated_transaction_transcript")]
        + [
            dict(row, offset=row["offset"] + len(b.code)) for row in verifier.source_map
        ],
        verifier.functions,
    )
    program.audit()
    return program
