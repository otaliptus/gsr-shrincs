"""Independent translation of the pinned Simplicity verification relation.

This is a verifier for public research fixtures, not a signer or wallet.
Integers in the upstream typed witness have big-endian byte representations.
"""
import ast
import hashlib
import json
from pathlib import Path

PIN = "d13165d3d21bac73e8794eede21f0f1527f3b837"


def number(x, n):
    return x.to_bytes(n, "big")


def digest(x):
    return hashlib.sha256(x).digest()


def address(layer=0, tree=0, kind=0, key=0, height=0, index=0):
    return number(layer, 4) + number(tree, 12) + number(kind, 4) + number(key, 4) + number(height, 4) + number(index, 4)


def parse_value(value):
    """Parse the limited upstream witness grammar without executing Python."""
    node = ast.parse(value.replace("list![", "["), mode="eval").body

    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) is int and n.value >= 0:
            return n.value
        if isinstance(n, (ast.Tuple, ast.List)):
            return [walk(x) for x in n.elts]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("Left", "Right") and len(n.args) == 1 and not n.keywords:
            return {n.func.id: walk(n.args[0])}
        raise ValueError("unsupported witness expression")

    return walk(node)


def load_fixture(path):
    document = json.loads(Path(path).read_text())
    return parse_value(document["PROOF"]["value"])


def mode_of(proof):
    return "stateful" if "Left" in proof[2] else "stateless"


def wots(mapped, values, pad, layer, tree, key, kind):
    digits = [(x >> shift) & 3 for x in mapped for shift in (6, 4, 2, 0)]
    if sum(digits) != 140 or len(values) != 64:
        raise ValueError("WOTS digit sum")
    tips = []
    for i, (value, digit) in enumerate(zip(values, digits)):
        node = number(value, 16)
        for j in range(digit, 3):
            node = digest(pad + address(layer, tree, kind, key, i, j) + node)[:16]
        tips.append(node)
    return digest(pad + address(layer, tree, kind + 1, key) + b"".join(tips))[:16]


def recover(proof):
    message, (seed, expected), signature, unused = proof
    seed, expected, message = number(seed, 16), number(expected, 16), number(message, 32)
    pad = seed + bytes(48)
    if "Left" in signature:
        (r, counter, chains), path, key = signature["Left"]
        if len(path) >= 512 or not 0 <= key < 2**32:
            raise ValueError("stateful bounds")
        msg = digest(address(kind=4) + number(r, 32) + seed + expected + message)[:16]
        mapped = digest(address(kind=3, key=key) + seed + msg + number(counter, 4))[:16]
        root = wots(mapped, chains, pad, 0, 0, key, 0)
        height = 1 if key == 207 else (207 - key) % 2**32
        right = key == 207
        for sibling in path:
            sibling = number(sibling, 16)
            children = sibling + root if right else root + sibling
            root = digest(pad + address(kind=2, height=height) + children)[:16]
            right, height = True, (height + 1) % 2**32
        roots = root + number(unused, 16)
    else:
        (r, (parts4, parts1)), layers = signature["Right"]
        if len(parts4) != 4 or len(parts1) != 1 or len(layers) != 2:
            raise ValueError("stateless shape")
        msg = digest(address(kind=14) + number(r, 32) + seed + expected + message)
        msg_int = int.from_bytes(msg, "big")
        if (msg_int >> 124) & ((1 << 22) - 1):
            raise ValueError("FORS grinding bits")
        idx = (int.from_bytes(msg[16:20], "big") >> 4) & 0xFFFFFF
        roots = []
        for i, (secret, path) in enumerate(parts4 + parts1):
            if len(path) != 22:
                raise ValueError("FORS path")
            index = (msg_int >> (234 - 22 * i)) & ((1 << 22) - 1)
            node = digest(pad + address(tree=idx, kind=6, key=i, index=index) + number(secret, 16))[:16]
            for height, sibling in enumerate(path, 1):
                sibling = number(sibling, 16)
                children = sibling + node if index & 1 else node + sibling
                index >>= 1
                node = digest(pad + address(tree=idx, kind=7, key=i, height=height, index=index) + children)[:16]
            roots.append(node)
        root = digest(pad + address(tree=idx, kind=8) + b"".join(roots))[:16]
        key, tree = idx & 4095, idx >> 12
        for layer, ((_, counter, chains), path) in enumerate(layers):
            if len(path) != 12:
                raise ValueError("XMSS path")
            mapped = digest(address(layer, tree, 13, key) + seed + root + number(counter, 4))[:16]
            root = wots(mapped, chains, pad, layer, tree, key, 10)
            index = key
            for height, sibling in enumerate(path, 1):
                sibling = number(sibling, 16)
                children = sibling + root if index & 1 else root + sibling
                index >>= 1
                root = digest(pad + address(layer, tree, 12, height=height, index=index) + children)[:16]
            key, tree = tree, tree >> 12
        roots = number(unused, 16) + root
    return digest(pad + address(kind=16) + roots)[:16]


def verify(proof):
    try:
        return recover(proof) == number(proof[1][1], 16)
    except (ValueError, OverflowError, IndexError, TypeError):
        return False


def stack(proof):
    """Lossless logical fields; this is not a standardized signature encoding."""
    message, (seed, expected), signature, unused = proof

    def wt(w):
        r, counter, chains = w
        return number(r, 32) + number(counter, 4) + b"".join(number(x, 16) for x in chains)

    if "Left" in signature:
        w, path, key = signature["Left"]
        sig = wt(w) + b"".join(number(x, 16) for x in path) + number(key, 4)
    else:
        (r, groups), layers = signature["Right"]
        sig = number(r, 32)
        for secret, path in groups[0] + groups[1]:
            sig += number(secret, 16) + b"".join(number(x, 16) for x in path)
        for w, path in layers:
            sig += wt(w) + b"".join(number(x, 16) for x in path)
    return [sig, number(seed, 16) + number(expected, 16), number(message, 32), number(unused, 16)]


def witness_json(proof, type_string, *, specialized=False):
    def render(x):
        if type(x) is int:
            return str(x)
        if isinstance(x, dict):
            tag, val = next(iter(x.items()))
            if tag == "Left":
                w, path, key = val
                inner = f"({wtuple(w)}, list![{', '.join(map(str, path))}], {key})"
                return inner if specialized else f"Left({inner})"
            (r, (p4, p1)), layers = val
            part = lambda p: f"({p[0]}, [{', '.join(map(str, p[1]))}])"
            layer = lambda p: f"({wtuple(p[0])}, [{', '.join(map(str, p[1]))}])"
            inner = f"(({r}, ([{', '.join(map(part, p4))}], [{', '.join(map(part, p1))}])), [{', '.join(map(layer, layers))}])"
            return inner if specialized else f"Right({inner})"
        return "(" + ", ".join(map(render, x)) + ")"

    def wtuple(w):
        return f"({w[0]}, {w[1]}, [{', '.join(map(str, w[2]))}])"

    return {"PROOF": {"type": type_string, "value": render(proof)}}
