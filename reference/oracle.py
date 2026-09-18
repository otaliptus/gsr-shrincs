"""Load only the pinned executable spec; all seeds in this module are PUBLIC TEST DATA."""

from runner.checks import require
import importlib.util
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "vendor/shrincs-spec/impl/shrincs.py"
spec = importlib.util.spec_from_file_location("shrincs_pinned", path)
scheme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheme)
CONTEXT = b"after-quantum/gsr-lab/v1"
PUBLIC_SEED = bytes(range(48))


def deterministic(label, length):
    return hashlib.shake_256(("PUBLIC GSR SHRINCS TEST ONLY:" + label).encode()).digest(
        length
    )


def verify(message, signature, public_key, context=CONTEXT):
    if len(message) != 32 or len(context) > 255:
        return False
    return scheme.shrincs_verify(message, signature, context, public_key)


def fixture(name, message, signature, public_key, provenance, context=CONTEXT):
    require(verify(message, signature, public_key, context), name)
    return dict(
        name=name,
        message=message.hex(),
        signature=signature.hex(),
        public_key=public_key.hex(),
        context=context.hex(),
        provenance=provenance,
    )


def decode(vector):
    return tuple(
        bytes.fromhex(vector[k]) for k in ("signature", "public_key", "message")
    )


def synthetic_stateful(depth, index, label="boundary", message=None):
    """Genuine WOTS signing + synthetic authentication siblings, NOT a full-tree signer.

    First compute the actual WOTS public key and path root, then bind that root
    into H_msg_sf and sign. This preserves the circular-looking root binding.
    """
    if not 1 <= depth <= 255 or not 0 <= index < 2 ** min(depth, 64):
        raise ValueError("invalid stateful location")
    height = 255 - depth
    seed = deterministic(label + "/seed", 16)
    sk = deterministic(label + "/public-secret", 16)
    sl = deterministic(label + "/sl", 16)
    if message is None:
        message = deterministic(label + f"/msg/{depth}/{index}", 32)
    randomizer = deterministic(label + "/R", 16)
    address = bytearray(bytes([height]) + index.to_bytes(8, "big") + bytes(13))
    node = scheme.wots_c_pubkey_gen(sk, seed, bytearray(address))
    siblings = deterministic(label + f"/path/{depth}/{index}", 16 * depth)
    for k in range(depth):
        sibling = siblings[16 * k : 16 * (k + 1)]
        ad = bytearray(
            bytes([height + k + 1])
            + (index >> (k + 1)).to_bytes(8, "big")
            + b"\x12"
            + bytes(12)
        )
        node = scheme.H(
            seed, ad, sibling + node if (index >> k) & 1 else node + sibling
        )
    sf = node
    bound = b"\0" + bytes([len(CONTEXT)]) + CONTEXT + sl + message
    digest = scheme.H_msg_sf(randomizer, seed, sf, bytearray(address), bound)
    wots = scheme.wots_c_sign(digest, sk, seed, bytearray(address))
    require(wots is not None)
    sig = (
        bytes([height])
        + randomizer
        + index.to_bytes((min(depth, 64) + 7) // 8, "big")
        + wots
        + siblings
    )
    return fixture(
        f"synthetic-depth-{depth}-index-{index}",
        message,
        sig,
        seed + sl + sf,
        dict(
            kind="synthetic-authentication-path",
            public_seed_label=label,
            depth=depth,
            index=index,
            full_tree_generated=False,
        ),
    )


def real_vectors():
    key, pk = scheme.shrincs_keygen(PUBLIC_SEED, b"\x01\x04")
    result = []
    for state in (0, 1, 7, 15, None):
        message = deterministic(f"genuine/{state}", 32)
        signature = scheme.shrincs_sign(message, CONTEXT, key, state, None)
        result.append(
            fixture(
                f"genuine-{state}",
                message,
                signature,
                pk,
                dict(
                    kind="reference-keygen-sign-verify",
                    public_seed=PUBLIC_SEED.hex(),
                    structure="0104",
                    state_counter=state,
                ),
            )
        )
    # A second public seed and genuinely unbalanced tree exercise variable path
    # lengths independently of synthetic boundary construction.
    second = PUBLIC_SEED[::-1]
    key, pk = scheme.shrincs_keygen(second, b"\x00\x04")
    for state in (0, 1, 3, 4, None):
        message = deterministic(f"unbalanced/{state}", 32)
        signature = scheme.shrincs_sign(message, CONTEXT, key, state, None)
        result.append(
            fixture(
                f"genuine-unbalanced-{state}",
                message,
                signature,
                pk,
                dict(
                    kind="reference-keygen-sign-verify",
                    public_seed=second.hex(),
                    structure="0004",
                    state_counter=state,
                ),
            )
        )
    return result
