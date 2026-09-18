#!/usr/bin/env python3
"""Real regtest spends. Public test keys only; no external-network connections."""
import copy
import hashlib
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.checks import require
from runner.bitcoin import NUMS_XONLY, control_block, message, transcript
from reference.oracle import scheme, PUBLIC_SEED, CONTEXT
from generator.transaction import compile_policy
from test_framework.messages import CTransaction, CTxIn, CTxOut, CTxInWitness
from test_framework.script import CScript, taproot_construct, LEAF_VERSION_TAPSCRIPT_V2
from test_framework.wallet import NodeSigner
from feature_tapscript_v2_op_tx_vaults import OpTxVaultsTest


class ShrincsRegtest(OpTxVaultsTest):
    def set_test_params(self):
        super().set_test_params()

    def rejection(self, name, tx):
        result = self.nodes[0].testmempoolaccept([tx.serialize().hex()], 0)[0]
        require(not result["allowed"], name)
        # A policy/consensus script failure is evidence; missing-input/fee failures are not.
        reason = (
            result.get("reject-reason", "") + " " + result.get("reject-details", "")
        )
        require(
            "script-verify-flag" in reason
            or (
                name.endswith("/annex")
                and result["reject-reason"] == "bad-witness-nonstandard"
            )
            or (
                name.endswith("/appended-input-binding")
                and result["reject-reason"] == "tx-size"
            ),
            (name, result),
        )
        self.report["rejections"].append(
            dict(
                name=name,
                result=result,
                raw_transaction=tx.serialize().hex(),
                spent_outputs=[
                    self.prevouts[(x.prevout.hash, x.prevout.n)].serialize().hex()
                    for x in tx.vin
                ],
            )
        )

    def witness(self, tx, tap, leaf, sig, index=0):
        tx.wit.vtxinwit[index].scriptWitness.stack = [
            sig,
            bytes(tap.leaves[leaf].script),
            control_block(tap, leaf),
        ]

    def run_test(self):
        node = self.nodes[0]
        self.nodesigner = NodeSigner(node)
        self.generatetoaddress(
            node, 101, self.nodesigner.getnewaddress(address_type="bech32")[2]
        )
        self.activate_script_restoration()
        key, pk = scheme.shrincs_keygen(PUBLIC_SEED, b"\x01\x08")
        counter = 0

        def sign(msg, stateless=False):
            nonlocal counter
            state = None if stateless else counter
            counter += not stateless
            return scheme.shrincs_sign(msg, CONTEXT, key, state, None)

        self.report = dict(
            public_test_keys=True,
            source="d2799052604eb138c5a79acf88514a0c8b07f4ef",
            transcript="GSR-SHRINCS/transaction/v1",
            spends=[],
            rejections=[],
            padding_bytes=0,
        )
        cases = []
        for profile in ("full", "baseline"):
            for mode in ("unified", "stateful", "stateless"):
                code = compile_policy(pk, mode=mode, profile=profile).code
                other = compile_policy(
                    pk,
                    mode="stateless" if mode == "stateful" else "stateful",
                    profile=profile,
                ).code
                tap = taproot_construct(
                    NUMS_XONLY,
                    [
                        ("verify", CScript(code), LEAF_VERSION_TAPSCRIPT_V2),
                        ("other", CScript(other), LEAF_VERSION_TAPSCRIPT_V2),
                    ],
                )
                cases.append((f"{profile}-{mode}", profile, mode, code, tap))
        for profile in ("full", "baseline"):
            original = next(c for c in cases if c[0] == profile + "-unified")
            _, _, _, code, _ = original
            other = compile_policy(pk, mode="stateless", profile=profile).code
            tap = taproot_construct(
                NUMS_XONLY,
                [
                    ("verify", CScript(code), LEAF_VERSION_TAPSCRIPT_V2),
                    ("other", CScript(other), LEAF_VERSION_TAPSCRIPT_V2),
                ],
            )
            cases.append((profile + "-unified-sl", profile, "unified", code, tap))
        multi = compile_policy(pk, max_inputs=4).code
        multitap = taproot_construct(
            NUMS_XONLY, [("verify", CScript(multi), LEAF_VERSION_TAPSCRIPT_V2)]
        )
        cap_policies = {}
        for cap in range(1, 5):
            policy = compile_policy(pk, mode="stateful", max_inputs=cap).code
            tap = taproot_construct(
                NUMS_XONLY, [("verify", CScript(policy), LEAF_VERSION_TAPSCRIPT_V2)]
            )
            cap_policies[cap] = (policy, tap)
        outputs = [(name, 50_000_000, tap.scriptPubKey) for name, _, _, _, tap in cases]
        outputs += [
            ("index-" + name, 50_000_000, tap.scriptPubKey)
            for name, _, _, _, tap in cases
        ]
        outputs += [(f"multi{i}", 50_000_000, multitap.scriptPubKey) for i in range(6)]
        outputs += [
            (f"cap{cap}-{i}", 50_000_000, tap.scriptPubKey)
            for cap, (_, tap) in cap_policies.items()
            for i in range(cap + 1)
        ]
        funded = self.fund_outputs(outputs)
        alternate = self.fund_outputs(
            [(name, 50_000_000, tap.scriptPubKey) for name, _, _, _, tap in cases]
        )
        self.prevouts = {
            (point.hash, point.n): output
            for point, output in [*funded.values(), *alternate.values()]
        }
        destination = self.nodesigner.getnewaddress(address_type="bech32")[1]
        for name, profile, mode, code, tap in cases:
            stateless = mode == "stateless" or name.endswith("-sl")
            tx = CTransaction()
            tx.version = 2
            tx.vin = [CTxIn(funded[name][0], CScript(), 0xFFFFFFFE)]
            tx.vout = [CTxOut(48_900_000, destination), CTxOut(100_000, destination)]
            tx.wit.vtxinwit = [CTxInWitness()]
            spent = [funded[name][1]]
            digest = message(tx, spent, 0, code)
            sig = sign(digest, stateless)
            require(scheme.shrincs_verify(digest, sig, CONTEXT, pk))
            self.witness(tx, tap, "verify", sig)
            accepted = node.testmempoolaccept([tx.serialize().hex()], 0)[0]
            require(accepted["allowed"], (name, accepted))
            self.log.info(
                "Accepted %s: %d weight, %d signature bytes",
                name,
                tx.get_weight(),
                len(sig),
            )
            for label, mutate in (
                ("version", lambda t: setattr(t, "version", 1)),
                ("locktime", lambda t: setattr(t, "nLockTime", 1)),
                ("sequence", lambda t: setattr(t.vin[0], "nSequence", 0xFFFFFFFD)),
                (
                    "outpoint-txid",
                    lambda t: setattr(t.vin[0], "prevout", alternate[name][0]),
                ),
                (
                    "outpoint-index",
                    lambda t: setattr(t.vin[0], "prevout", funded["index-" + name][0]),
                ),
                ("output-amount", lambda t: setattr(t.vout[0], "nValue", 48_899_999)),
                (
                    "output-script",
                    lambda t: setattr(
                        t.vout[0],
                        "scriptPubKey",
                        CScript(bytes(destination[:-1]) + bytes([destination[-1] ^ 1])),
                    ),
                ),
                ("output-order", lambda t: t.vout.reverse()),
                ("output-count", lambda t: t.vout.append(CTxOut(1000, destination))),
            ):
                changed = copy.deepcopy(tx)
                mutate(changed)
                self.rejection(name + "/" + label, changed)
            replay = copy.deepcopy(tx)
            self.witness(replay, tap, "other", sig)
            self.rejection(name + "/cross-policy", replay)
            annex = copy.deepcopy(tx)
            annex.wit.vtxinwit[0].scriptWitness.stack.append(b"\x50lab")
            self.rejection(name + "/annex", annex)
            extra = copy.deepcopy(tx)
            extra.wit.vtxinwit[0].scriptWitness.stack.insert(0, b"extra")
            self.rejection(name + "/extra-witness", extra)
            for label, change in (
                ("spent-amount", lambda s: setattr(s, "nValue", s.nValue + 1)),
                (
                    "spent-script",
                    lambda s: setattr(s, "scriptPubKey", CScript(b"\x51")),
                ),
            ):
                wrong = copy.deepcopy(spent)
                change(wrong[0])
                badsig = sign(message(tx, wrong, 0, code), stateless)
                altered = copy.deepcopy(tx)
                self.witness(altered, tap, "verify", badsig)
                self.rejection(name + "/" + label, altered)
            # Appending an input invalidates the signed transcript as well as exceeding the cap.
            count = copy.deepcopy(tx)
            count.vin.append(CTxIn(alternate[name][0], CScript(), 0xFFFFFFFE))
            count.wit.vtxinwit.append(copy.deepcopy(count.wit.vtxinwit[0]))
            self.rejection(name + "/appended-input-binding", count)
            txid = node.sendrawtransaction(tx.serialize().hex(), 0)
            block = self.generate(node, 1)[0]
            require(txid in node.getblock(block)["tx"])
            self.report["spends"].append(
                dict(
                    name=name,
                    profile=profile,
                    mode=mode,
                    txid=txid,
                    block=block,
                    weight=tx.get_weight(),
                    vsize=tx.get_vsize(),
                    varops_allowed=tx.get_weight() * 10_000,
                    signature_bytes=len(sig),
                    public_key_bytes=len(pk),
                    program_bytes=len(code),
                    control_block_bytes=len(control_block(tap, "verify")),
                    raw_transaction=tx.serialize().hex(),
                    transcript=transcript(tx, spent, 0, code).hex(),
                    message=digest.hex(),
                    public_key=pk.hex(),
                    spent_outputs=[x.serialize().hex() for x in spent],
                )
            )
        # Inputs share one budget; all fields and the current input index bind.
        for count, offset in ((2, 0), (4, 2)):
            tx = CTransaction()
            tx.version = 2
            tx.vin = [
                CTxIn(funded[f"multi{i+offset}"][0], CScript(), 0xFFFFFFFE)
                for i in range(count)
            ]
            tx.vout = [CTxOut(count * 50_000_000 - 1_000_000, destination)]
            tx.wit.vtxinwit = [CTxInWitness() for _ in range(count)]
            spent = [funded[f"multi{i+offset}"][1] for i in range(count)]
            for i in range(count):
                self.witness(
                    tx,
                    multitap,
                    "verify",
                    sign(message(tx, spent, i, multi), i % 2 == 1),
                    i,
                )
            accepted = node.testmempoolaccept([tx.serialize().hex()], 0)[0]
            require(accepted["allowed"], accepted)
            swapped = copy.deepcopy(tx)
            swapped.wit.vtxinwit.reverse()
            self.rejection(f"multi{count}/current-input-binding", swapped)
            reordered = copy.deepcopy(tx)
            reordered.vin.reverse()
            reordered.wit.vtxinwit.reverse()
            self.rejection(f"multi{count}/input-order", reordered)
            txid = node.sendrawtransaction(tx.serialize().hex(), 0)
            block = self.generate(node, 1)[0]
            require(txid in node.getblock(block)["tx"])
            self.report["spends"].append(
                dict(
                    name=f"full-{count}-input-mixed",
                    weight=tx.get_weight(),
                    vsize=tx.get_vsize(),
                    varops_allowed=tx.get_weight() * 10_000,
                    txid=txid,
                    block=block,
                    raw_transaction=tx.serialize().hex(),
                    spent_outputs=[x.serialize().hex() for x in spent],
                    public_key=pk.hex(),
                    signature_bytes=sum(
                        len(x.scriptWitness.stack[0]) for x in tx.wit.vtxinwit
                    ),
                    program_bytes=count * len(multi),
                    control_block_bytes=count * len(control_block(multitap, "verify")),
                )
            )
        # Fresh signatures cover the complete proposed transaction. All signature
        # relations pass independently; only the authenticated cap rejects cap+1.
        for cap, (code, tap) in cap_policies.items():
            for count in (cap + 1, cap):
                tx = CTransaction()
                tx.version = 2
                tx.vin = [
                    CTxIn(funded[f"cap{cap}-{i}"][0], CScript(), 0xFFFFFFFE)
                    for i in range(count)
                ]
                tx.vout = [CTxOut(count * 50_000_000 - 1_000_000, destination)]
                tx.wit.vtxinwit = [CTxInWitness() for _ in range(count)]
                spent = [funded[f"cap{cap}-{i}"][1] for i in range(count)]
                for i in range(count):
                    digest = message(tx, spent, i, code)
                    signature = sign(digest)
                    require(scheme.shrincs_verify(digest, signature, CONTEXT, pk))
                    self.witness(tx, tap, "verify", signature, i)
                if count > cap:
                    self.rejection(f"cap{cap}/validly-signed-over-limit", tx)
                    self.report["rejections"][-1].update(
                        max_inputs=cap,
                        mode="stateful",
                        profile="full",
                        public_key=pk.hex(),
                    )
                    continue
                result = node.testmempoolaccept([tx.serialize().hex()], 0)[0]
                require(result["allowed"], result)
                txid = node.sendrawtransaction(tx.serialize().hex(), 0)
                block = self.generate(node, 1)[0]
                require(txid in node.getblock(block)["tx"])
                self.report["spends"].append(
                    dict(
                        name=f"full-cap{cap}-boundary",
                        profile="full",
                        mode="stateful",
                        max_inputs=cap,
                        weight=tx.get_weight(),
                        vsize=tx.get_vsize(),
                        varops_allowed=tx.get_weight() * 10000,
                        txid=txid,
                        block=block,
                        raw_transaction=tx.serialize().hex(),
                        spent_outputs=[item.serialize().hex() for item in spent],
                        public_key=pk.hex(),
                        signature_bytes=sum(
                            len(w.scriptWitness.stack[0]) for w in tx.wit.vtxinwit
                        ),
                        program_bytes=count * len(code),
                        control_block_bytes=count * len(control_block(tap, "verify")),
                    )
                )
        details = json.dumps(self.report, sort_keys=True).encode()
        (ROOT / "reports/regtest-details.json.gz").write_bytes(
            gzip.compress(details, mtime=0)
        )
        for row in self.report["spends"] + self.report["rejections"]:
            for field in ("raw_transaction", "spent_outputs", "transcript"):
                row.pop(field, None)
        self.report["details"] = "regtest-details.json.gz"
        (ROOT / "reports/regtest.json").write_text(
            json.dumps(self.report, indent=2) + "\n"
        )


if __name__ == "__main__":
    ShrincsRegtest(__file__).main()
