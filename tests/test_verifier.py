import json
import unittest
from generator.script import Builder, Library, Ref, audit, cat, cut, op
from generator.verifier import (
    compile_verifier,
    chain_body,
    be,
    from_be,
    hash16,
    CONTEXT,
)
from reference.oracle import (
    scheme,
    decode,
    deterministic,
    synthetic_stateful,
    verify,
    ROOT,
)
from runner.evaluator import evaluate


def component(inputs, build, values, expected, profile):
    lib = Library()
    b = Builder(inputs, profile, lib)
    result = build(b)
    b.finish(op("EQUAL", result, expected))
    prefix = lib.prefix() if profile == "full" else b""
    code = prefix + bytes(b.code)
    audit(code, profile, [v[1] for v in lib.functions.values()])
    r = evaluate(code, values)
    if not r.success:
        raise AssertionError((r.error, r.stack))
    return r


class Components(unittest.TestCase):
    def test_fixed_width_bytes(self):
        for profile in ("full", "baseline"):
            for width in (1, 2, 4, 8, 17):
                for n in (0, 1, 127, 128, 129, 255, 2 ** (8 * width) - 1):
                    raw = n.to_bytes(width, "big")
                    component(
                        ("x",),
                        lambda b: be(b, Ref("x"), width),
                        [n.to_bytes(width, "little")],
                        raw,
                        profile,
                    )
                    component(
                        ("x",),
                        lambda b: from_be(b, Ref("x"), width),
                        [raw],
                        raw[::-1],
                        profile,
                    )
            for raw in (b"\0\x80\0", b"\xff\0\xff", bytes(range(32))):
                component(
                    ("x",),
                    lambda b: cut(Ref("x"), 1, len(raw) - 2),
                    [raw],
                    raw[1:-1],
                    profile,
                )

        # Both pinned transaction serialization and OP_TX expose uint32 version bits.
        from runner.bitcoin import transcript, DOMAIN
        from test_framework.messages import CTransaction

        for version in (0, 1, 2, 2**31, 2**32 - 1):
            tx = CTransaction()
            tx.version = version
            actual = transcript(tx, [], 0, b"")[len(DOMAIN) : len(DOMAIN) + 4]
            self.assertEqual(actual, tx.serialize_without_witness()[:4])

    def test_addressed_hashes(self):
        for profile in ("full", "baseline"):
            for kind in (0, 1, 2, 3, 4, 16, 17, 18, 22):
                seed = deterministic(f"seed/{kind}", 16)
                ad = bytearray(deterministic(f"addr/{kind}", 22))
                ad[9] = kind
                for size in (16, 32, 160, 512, 560):
                    data = deterministic(f"input/{size}", size)
                    expected = scheme.F(seed, bytearray(ad), data)
                    component(
                        ("data",),
                        lambda b: hash16(seed + bytes(48), bytes(ad), Ref("data")),
                        [data],
                        expected,
                        profile,
                    )

    def test_every_chain_step(self):
        for profile in ("full", "baseline"):
            for kind in (0, 16):
                seed = deterministic("chain-seed", 16)
                prefix = bytearray(deterministic("chain-address", 18))
                prefix[9] = kind
                node = deterministic("chain-node", 16)
                for start in range(16):
                    fn = (
                        scheme.wots_c_chain_iter
                        if kind == 16
                        else scheme.wots_tw_chain_iter
                    )
                    expected = fn(
                        node, start, 15 - start, seed, bytearray(prefix + bytes(4))
                    )

                    def build(b):
                        return b.call(
                            "chain",
                            ("node", "digit", "prefix", "pad"),
                            chain_body,
                            (Ref("x"), start, bytes(prefix), seed + bytes(48)),
                            "out",
                        )

                    component(("x",), build, [node], expected, profile)

    def test_compiler_rejects_bad_programs(self):
        with self.assertRaises(ValueError):
            audit(b"\x50")
        with self.assertRaises(ValueError):
            audit(b"\x4f")
        with self.assertRaises(ValueError):
            audit(b"\xab")
        with self.assertRaises(ValueError):
            audit(b"\x4d\xff")
        with self.assertRaises(ValueError):
            audit(b"\xcf", "baseline")
        with self.assertRaises(ValueError):
            audit(b"\x51", function_bodies=[b"\x50"])
        with self.assertRaises(ValueError):
            Builder().expr(Ref("missing"))
        with self.assertRaises(ValueError):
            Builder().branch(1, lambda b: b.let("a", 1))


class FullVerifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads((ROOT / "fixtures/vectors.json").read_text())[
            "vectors"
        ]
        cls.programs = {p: compile_verifier(p) for p in ("full", "baseline", "bytes")}

    def check(self, vector, expected=None):
        args = decode(vector)
        oracle = verify(args[2], args[0], args[1], bytes.fromhex(vector["context"]))
        if expected is not None:
            self.assertEqual(oracle, expected, vector["name"])
        for profile, p in self.programs.items():
            r = evaluate(p.code, args)
            self.assertEqual(r.success, oracle, (profile, vector["name"], r.error))
            self.assertNotEqual(r.classification, "budget")
            if r.success:
                self.assertEqual(r.stack, [])

    def test_reference_roundtrips_and_boundaries(self):
        for v in self.vectors:
            self.check(v, True)

    def test_all_stateful_depths_and_index_extremes(self):
        for depth in range(1, 256):
            for index in (0, 2 ** min(depth, 64) - 1):
                self.check(synthetic_stateful(depth, index), True)

    def test_rejection_matches_oracle(self):
        for vector in self.vectors:
            sig, pk, msg = decode(vector)
            mutations = [
                ("message", 0),
                ("public_key", 0),
                ("public_key", 16),
                ("public_key", 32),
                ("signature", 0),
                ("signature", 1),
                ("signature", len(sig) - 1),
            ]
            if sig[0] != 255:
                width = (min(255 - sig[0], 64) + 7) // 8
                mutations += [
                    ("signature", 17),
                    ("signature", 17 + width),
                    ("signature", 19 + width),
                ]
            else:
                mutations += [
                    ("signature", 17),
                    ("signature", 2257),
                    ("signature", 2961),
                ]
            for field, offset in mutations:
                value = bytearray.fromhex(vector[field])
                value[offset] ^= 1
                self.check(dict(vector, **{field: value.hex()}))
            for malformed in (b"", sig[:-1], sig + b"\0", sig[:17], sig[:100]):
                self.check(dict(vector, signature=malformed.hex()), False)
            for malformed in (pk[:-1], pk + b"\0"):
                self.check(dict(vector, public_key=malformed.hex()), False)
            for malformed in (msg[:-1], msg + b"\0"):
                self.check(dict(vector, message=malformed.hex()), False)

    def test_context_binding_and_mode_leaves(self):
        for mode, vector in (
            ("stateful", self.vectors[0]),
            ("stateless", self.vectors[4]),
        ):
            args = decode(vector)
            for profile in ("full", "baseline"):
                self.assertTrue(
                    evaluate(compile_verifier(profile, mode).code, args).success
                )
                other = "stateful" if mode == "stateless" else "stateless"
                self.assertFalse(
                    evaluate(compile_verifier(profile, other).code, args).success
                )
                wrong = compile_verifier(profile, mode, CONTEXT + b"!")
                self.assertFalse(evaluate(wrong.code, args).success)

    def test_invalid_index_encoding(self):
        for depth in (d for d in range(1, 64) if d % 8):
            v = synthetic_stateful(depth, 0)
            sig = bytearray.fromhex(v["signature"])
            sig[17] |= 0x80
            self.check(dict(v, signature=sig.hex()), False)

    def test_budget_boundary_and_clean_stack(self):
        for profile, p in self.programs.items():
            for v in (self.vectors[0], self.vectors[4], self.vectors[-1]):
                args = decode(v)
                r = evaluate(p.code, args)
                self.assertTrue(evaluate(p.code, args, r.consumed).success)
                self.assertEqual(
                    evaluate(p.code, args, r.consumed - 1).classification, "budget"
                )
                self.assertFalse(evaluate(p.code, (b"extra", *args)).success)


class HashAndWotsAgreement(unittest.TestCase):
    def test_message_hashes_and_grinding(self):
        from generator.verifier import h_msg_sf, h_msg_sl, h_grind

        for profile in ("full", "baseline"):
            for label in ("zeros", "highbits", "ordinary"):
                seed = (
                    bytes(16)
                    if label == "zeros"
                    else deterministic(label + "/seed", 16)
                )
                root = deterministic(label + "/root", 16)
                randomizer = deterministic(label + "/R", 16)
                address = bytearray(deterministic(label + "/address", 22))
                bound = (
                    b"\0"
                    + bytes([len(CONTEXT)])
                    + CONTEXT
                    + root
                    + deterministic(label + "/M", 32)
                )
                sf = scheme.H_msg_sf(randomizer, seed, root, bytearray(address), bound)
                sl = scheme.H_msg_sl(randomizer, seed, root, bound)
                component(
                    ("m",),
                    lambda b: h_msg_sf(
                        randomizer, seed, root, bytes(address[:9]), Ref("m")
                    ),
                    [bound],
                    sf,
                    profile,
                )
                component(
                    ("m",),
                    lambda b: h_msg_sl(randomizer, seed, root, Ref("m")),
                    [bound],
                    sl,
                    profile,
                )
                address[9] = 22
                for counter in (0, 1, 255, 256, 32768, 65535):
                    expected = scheme.H_grind(seed, bytearray(address), sf, counter)
                    component(
                        ("m",),
                        lambda b: h_grind(
                            seed + bytes(48),
                            bytes(address[:9]),
                            Ref("m"),
                            counter.to_bytes(2, "big"),
                        ),
                        [sf],
                        expected,
                        profile,
                    )

    def test_wots_intermediate_keys_and_counter_extremes(self):
        from generator.verifier import wots_body, WOTS_ARGS

        seed = deterministic("wots/seed", 16)
        sk = deterministic("wots/public-secret", 16)
        address = bytearray(deterministic("wots/address", 22))
        address[10:22] = bytes(12)
        for counter in (0, 1, 255, 256, 32768, 65535):
            address[9] = 22
            for n in range(10000):
                digest = deterministic(f"wots/msg/{counter}/{n}", 32)
                digits = scheme.wots_c_map_digest(
                    seed, digest, bytearray(address), counter
                )
                if digits is not None:
                    break
            self.assertIsNotNone(digits)
            sig = counter.to_bytes(2, "big")
            for i, digit in enumerate(digits):
                ad = bytearray(address)
                ad[9] = 21
                ad[14:18] = i.to_bytes(4, "big")
                ad[18:22] = bytes(4)
                node = scheme.PRF(seed, sk, ad)
                sig += scheme.wots_c_chain_iter(node, 0, digit, seed, ad)
            expected = scheme.wots_c_pubkey_from_sig(
                sig, digest, seed, bytearray(address)
            )
            self.assertIsNotNone(expected)
            for profile in ("full", "baseline"):

                def build(b):
                    return b.call(
                        "wots_c",
                        WOTS_ARGS,
                        lambda c: wots_body(c, True),
                        (
                            Ref("sig"),
                            digest,
                            seed + bytes(48),
                            bytes(address[:9]),
                            bytes(4),
                        ),
                        "out",
                    )

                component(("sig",), build, [sig], expected, profile)
                for badsig in (sig[:-1], sig + b"\0"):
                    lib = Library()
                    b = Builder(("sig",), profile, lib)
                    r = build(b)
                    b.finish(op("EQUAL", r, expected))
                    code = (lib.prefix() if profile == "full" else b"") + bytes(b.code)
                    self.assertFalse(evaluate(code, [badsig]).success)


class StatelessComponents(unittest.TestCase):
    def test_fors_digest_extremes_and_unused_bits(self):
        from generator.verifier import fors_body

        seed = deterministic("fors/seed", 16)
        sig = deterministic("fors/signature", 2240)
        location = b"\0" + (2**36 - 1).to_bytes(8, "big")
        keypair = (511).to_bytes(4, "big")
        for digest in (
            bytes(17),
            b"\xff" * 17,
            b"\x80" + bytes(16),
            bytes(16) + b"\x3f",
        ):
            address = bytearray(location + b"\x03" + keypair + bytes(8))
            expected = scheme.fors_pubkey_from_sig(sig, digest, seed, address)
            for profile in ("full", "baseline"):

                def build(b):
                    return b.call(
                        "fors",
                        ("sig", "digest", "pad", "location", "keypair"),
                        fors_body,
                        (Ref("sig"), digest, seed + bytes(48), location, keypair),
                        "out",
                    )

                component(("sig",), build, [sig], expected, profile)
        address = bytearray(location + b"\x03" + keypair + bytes(8))
        self.assertEqual(
            scheme.fors_pubkey_from_sig(sig, bytes(17), seed, bytearray(address)),
            scheme.fors_pubkey_from_sig(
                sig, bytes(16) + b"\x3f", seed, bytearray(address)
            ),
        )

    def test_wots_tw_checksum_boundaries(self):
        from generator.verifier import wots_body, WOTS_ARGS

        seed = deterministic("tw/seed", 16)
        sig = deterministic("tw/signature", 560)
        for layer, tree, leaf in ((0, 0, 0), (4, 2**36 - 1, 511)):
            location = bytes([layer]) + tree.to_bytes(8, "big")
            keypair = leaf.to_bytes(4, "big")
            for msg in (bytes(16), b"\xff" * 16, b"\x0f" * 16, b"\xf0" * 16):
                address = bytearray(location + b"\0" + keypair + bytes(8))
                expected = scheme.wots_tw_pubkey_from_sig(sig, msg, seed, address)
                for profile in ("full", "baseline"):

                    def build(b):
                        return b.call(
                            "wots_tw",
                            WOTS_ARGS,
                            lambda c: wots_body(c, False),
                            (Ref("sig"), msg, seed + bytes(48), location, keypair),
                            "out",
                        )

                    component(("sig",), build, [sig], expected, profile)
