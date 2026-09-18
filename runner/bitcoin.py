"""Pinned transaction serialization utilities, shared with the upstream test framework."""

from pathlib import Path
import sys
import hashlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/bitcoin/test/functional"))
from test_framework.messages import ser_string
from test_framework.key import TaggedHash
from generator.transaction import DOMAIN

NUMS_XONLY = bytes.fromhex(
    "50929b74c1a04954b78b4b6035e97a5e078a5a0f28ec96d547bfee9ace803ac0"
)


def control_block(tap, name):
    leaf = tap.leaves[name]
    return bytes([leaf.version | tap.negflag]) + tap.internal_pubkey + leaf.merklebranch


def transcript(tx, spent_outputs, input_index, script, annex=b"", codesep=0xFFFFFFFF):
    if len(spent_outputs) != len(tx.vin):
        raise ValueError("missing spent outputs")
    data = tx.version.to_bytes(4, "little") + tx.nLockTime.to_bytes(4, "little")
    data += len(tx.vin).to_bytes(4, "little")
    for txin, spent in zip(tx.vin, spent_outputs):
        data += txin.prevout.serialize() + spent.nValue.to_bytes(8, "little")
        data += ser_string(spent.scriptPubKey) + txin.nSequence.to_bytes(4, "little")
    data += len(tx.vout).to_bytes(4, "little")
    data += b"".join(x.serialize() for x in tx.vout)
    data += input_index.to_bytes(4, "little") + ser_string(annex)
    data += TaggedHash("TapLeaf", b"\xc2" + ser_string(script))
    data += codesep.to_bytes(4, "little")
    return DOMAIN + data


def message(tx, spent_outputs, input_index, script, **kwargs):
    return hashlib.sha256(
        transcript(tx, spent_outputs, input_index, script, **kwargs)
    ).digest()
