#!/usr/bin/env python3
"""Generate docs/index.html from the committed reports.

Every number on the page comes from reports/multi-scenario.json, reports/costs.json,
and generated/manifest.json. The page stamps the hashes of the reports it was built from. Static prose lives in docs/_static_parts.json and in this file.

    python3 docs/build_page.py
"""
from html import escape
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from generator import multi
from generator.script import OPS
from generator.transaction import compile_policy
from generator.verifier import compile_verifier

INV = {v: k for k, v in OPS.items()}
FIXED = {"INVOKE": 4000, "MUL": 3000, "DIV": 3000, "MOD": 3000, "NUMEQUAL": 3000, "LESSTHAN": 3000,
         "LESSTHANOREQUAL": 3000, "LSHIFT": 3000, "RSHIFT": 3000}
INPUTS, OUTPUTS = 2.27, 2.64
LABELS = {"baseline": "Restored opcodes (inline)", "bytes": "OP_BYTEREV (inline)",
          "full": "OP_DEFINE + OP_INVOKE", "catfix": "Functions + optimized CAT joins",
          "multi": "OP_MULTI — all uses", "multisel": "OP_MULTI — selective hashing"}
SHORT = LABELS
ORDER = ("baseline", "bytes", "full", "catfix", "multi", "multisel")


OPCODE_DETAILS = {}
# Disabled byte/arithmetic instructions restored by GSR, plus the fork's extensions.
# Ordinary Bitcoin opcodes and data pushes do not belong in these tooltips.
ADDED_OPCODES = {
    "OP_CAT", "OP_SUBSTR", "OP_LEFT", "OP_RIGHT", "OP_INVERT", "OP_AND", "OP_OR", "OP_XOR",
    "OP_2MUL", "OP_2DIV", "OP_MUL", "OP_DIV", "OP_MOD", "OP_LSHIFT", "OP_RSHIFT",
    "OP_TX", "OP_BYTEREV", "OP_DEFINE", "OP_INVOKE", "OP_MULTI",
}
TECHNIQUES = {
    "baseline": "Restores byte-string and arithmetic instructions. Transaction policies also use OP_TX.",
    "bytes": "Adds OP_BYTEREV to the restored-opcode approach.",
    "full": "Adds OP_DEFINE and OP_INVOKE for shared functions. Keeps OP_BYTEREV and the restored instructions.",
    "catfix": "No additional opcode over shared functions. The compiler removes unnecessary instructions from CAT joins.",
    "multi": "Adds OP_MULTI for hashing, concatenation, and cleanup. Keeps shared functions and optimized CAT joins.",
    "multisel": "Uses the same added opcodes as the all-uses variant. The compiler selects OP_MULTI only for cheaper hash joins.",
}


def instruction_names(program):
    """Read instructions, never pushed data; inspect declared function bodies separately."""
    names, pushes = set(), set()
    for code in (program.code, *(body[1] for body in program.functions.values())):
        pos = 0
        while pos < len(code):
            opcode = code[pos]
            pos += 1
            if 1 <= opcode <= 75:
                pushes.add(opcode)
                pos += opcode
            elif opcode in (76, 77, 78):
                width = 1 << (opcode - 76)
                names.add({76: "OP_PUSHDATA1", 77: "OP_PUSHDATA2", 78: "OP_PUSHDATA4"}[opcode])
                size = int.from_bytes(code[pos:pos + width], "little")
                pos += width + size
            else:
                names.add(opcode_name(opcode))
            if pos > len(code):
                raise ValueError("Truncated instruction in opcode inventory")
    return names, pushes


def prepare_opcode_details(report):
    OPCODE_DETAILS.clear()
    for scope, rows in (("transactions", report["transactions"]), ("standalone", report["standalone"])):
        for name in ORDER:
            union_names = set()
            for mode in ("stateful", "stateless"):
                row = rows[f"{name}-{mode}"]
                if scope == "transactions":
                    pk = bytes.fromhex(row["public_key"])
                    program = (compile_policy(pk, mode=mode, profile=name) if name not in multi.VARIANTS
                               else multi.compile_policy(name, pk, mode=mode))
                else:
                    program = (compile_verifier(name, mode) if name not in multi.VARIANTS
                               else multi.compile_verifier(name, mode))
                if hashlib.sha256(program.code).hexdigest() != row["program_sha256"]:
                    raise ValueError(f"Opcode inventory differs from report: {scope}/{name}-{mode}")
                names, _ = instruction_names(program)
                names &= ADDED_OPCODES
                union_names.update(names)
                OPCODE_DETAILS[f"{scope}-{name}-{mode}"] = dict(
                    title=LABELS[name], note=f"{mode.capitalize()} {'transaction policy and verifier' if scope == 'transactions' else 'standalone verifier'}. "
                    + TECHNIQUES[name], opcodes=sorted(names))
            OPCODE_DETAILS[f"{scope}-{name}-both"] = dict(
                title=LABELS[name], note=TECHNIQUES[name], opcodes=sorted(union_names))
    OPCODE_DETAILS["p2tr"] = dict(title="Today: P2TR key spend", note="No added opcodes. Bitcoin already verifies Taproot key-path Schnorr signatures natively.", opcodes=[])
    OPCODE_DETAILS["native"] = dict(title="Native SHRINCS opcode (hypothetical)", note="Would add one native SHRINCS verification instruction. It is hypothetical; this experiment assigns no opcode name or byte value.", opcodes=[])


def tip_key(label, mode="both", scope="transactions"):
    if label.startswith("Today: P2TR"):
        return "p2tr"
    if label.startswith("Native SHRINCS"):
        return "native"
    name = next(name for name in ORDER if label == LABELS[name])
    return f"{scope}-{name}-{mode}"


def opcode_label(label, mode="both", scope="transactions", key=None):
    key = key or tip_key(label, mode, scope)
    return f'<button type="button" class="opcode-label" data-opcodes="{key}" aria-expanded="false" aria-controls="opcode-panel">{escape(label)}</button>'


def f(n):
    return f"{n:,}"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_size(n):
    return 1 if n < 253 else 3 if n < 65536 else 5


def tps(items):
    base = (10 + INPUTS * 41 + OUTPUTS * 43) * 4 + 2
    witness = 1 + sum(compact_size(n) + n for n in items)
    return 4_000_000 / (base + INPUTS * witness) / 600


def shape(items):
    """Bytes, weight and vbytes of our one-input two-output shape: 113 non-witness bytes,
    the two SegWit marker and flag bytes, and the witness."""
    witness = 1 + sum(compact_size(n) + n for n in items)
    weight = 113 * 4 + 2 + witness
    return 113 + 2 + witness, weight, -(-weight // 4)


def opcode_name(o):
    o = int(o)
    if o == 0:
        return "OP_0"
    if 1 <= o <= 75:
        return "push 1 to 75 bytes"
    if o in (76, 77, 78):
        return "OP_PUSHDATA"
    if 81 <= o <= 96:
        return f"OP_{o - 80}"
    return "OP_" + INV.get(o, f"0x{o:02x}")


def fixed_price(o):
    return FIXED.get(INV.get(int(o), ""), 1250)


def size_rows(tx, mode):
    sig = tx[f"full-{mode}"]["signature_bytes"]
    rows = [("Today: P2TR key spend", 64, 0, 0, *shape([64]), "dim")]
    for name in ORDER:
        r = tx[f"{name}-{mode}"]
        rows.append((LABELS[name], r["signature_bytes"], r["program_bytes"], r["control_block_bytes"],
                     r["transaction_bytes"], r["weight"], r["vbytes"], "s1"))
    rows.append(("Native SHRINCS opcode (hypothetical)", sig, 0, 0, *shape([sig]), "dim"))
    return rows


def size_chart(rows, mode):
    mx = max(r[6] for r in rows)
    W, x0 = 300, 300
    out = [f'<div class="plot"><svg viewBox="0 0 640 {10 + len(rows) * 30}" role="img" aria-label="Transaction size in vbytes per scenario, {mode}">',
           f'<line x1="{x0}" y1="6" x2="{x0}" y2="{4 + len(rows) * 30}" stroke="var(--axis)" stroke-width="1"/>']
    for i, (label, *_, vb, col) in enumerate(rows):
        y = 10 + i * 30
        w = max(round(vb / mx * W, 1), 2)
        short = label.replace(" (hypothetical)", "")
        for k, v in SHORT.items():
            short = short.replace(LABELS[k], v)
        out.append(f'<g class="opcode-label" role="button" tabindex="0" data-opcodes="{tip_key(label, mode)}" aria-label="{escape(label)}: {f(vb)} vbytes. Show opcodes" aria-expanded="false" aria-controls="opcode-panel"><title>{label}: {f(vb)} vbytes</title><text x="0" y="{y + 14}">{short}</text>'
                   f'<rect x="{x0}" y="{y}" width="{w}" height="18" rx="4" fill="var(--{col})"/>'
                   f'<text class="val" x="{x0 + w + 8}" y="{y + 14}">{f(vb)}</text></g>')
    out.append("</svg></div>")
    return "\n".join(out)


def size_table(rows, mode):
    out = ['<table><tr><th>Implementation</th><th class="n">Signature</th><th class="n">Program</th><th class="n">Control block</th>'
           '<th class="n">Whole tx, bytes</th><th class="n">Weight</th><th class="n">vbytes</th><th class="n">Fee at 1 sat/vB</th><th class="n">Fee at 10 sat/vB</th></tr>']
    for label, sg, pg, cb, b, w, vb, _ in rows:
        out.append(f'<tr><td>{opcode_label(label, mode)}</td><td class="n">{f(sg)}</td><td class="n">{f(pg) if pg else "none"}</td><td class="n">{f(cb) if cb else "none"}</td>'
                   f'<td class="n">{f(b)}</td><td class="n">{f(w)}</td><td class="n">{f(vb)}</td><td class="n">{f(vb)} sat</td><td class="n">{f(vb * 10)} sat</td></tr>')
    return "\n".join(out) + "</table>"


def cost_table(tx, mode):
    out = ['<table><tr><th>Implementation</th><th class="n">Charged units</th><th class="n">Allowance</th><th class="n">Share used</th>'
           '<th class="n">Interpreter time</th><th class="n">Opcodes executed</th><th class="n">SHA256 calls</th><th class="n">Function calls</th>'
           '<th class="n">Peak memory</th><th class="n">Largest item</th></tr>']
    for name in ORDER:
        r = tx[f"{name}-{mode}"]
        m = r["metrics"]
        out.append(f'<tr><td>{opcode_label(LABELS[name], mode)}</td><td class="n">{f(r["varops_consumed"])}</td><td class="n">{f(r["varops_allowed"])}</td>'
                   f'<td class="n">{r["budget_fraction"]:.1%}</td><td class="n">{r["median_interpreter_ms"]:.2f} ms</td><td class="n">{f(m["opcodes"])}</td>'
                   f'<td class="n">{f(m["sha256_calls"])}</td><td class="n">{f(m["invocations"])}</td><td class="n">{f(m["peak_total_bytes"])} B</td>'
                   f'<td class="n">{f(m["max_item_bytes"])} B</td></tr>')
    return "\n".join(out) + "</table>"


def standalone_table(st, mode):
    base = st[f"full-{mode}"]["varops_consumed"]
    out = ['<table><tr><th>Program</th><th class="n">Program bytes</th><th class="n">Charged units</th><th class="n">Change from shared functions</th>'
           '<th class="n">Fixed charge</th><th class="n">SHA256 calls</th><th class="n">OP_MULTI uses</th></tr>']
    for name in ORDER:
        r = st[f"{name}-{mode}"]
        m = r["metrics"]
        change = "" if name == "full" else f'{(r["varops_consumed"] - base) / base:+.1%}'
        out.append(f'<tr><td>{opcode_label(LABELS[name], mode, "standalone")}</td><td class="n">{f(r["program_bytes"])}</td><td class="n">{f(r["varops_consumed"])}</td>'
                   f'<td class="n">{change}</td><td class="n">{f(m["fixed_charge"])}</td><td class="n">{f(m["sha256_calls"])}</td>'
                   f'<td class="n">{f(sum(r["multi_uses"].values()))}</td></tr>')
    return "\n".join(out) + "</table>"


def tps_table(tx):
    out = ['<table><tr><th>Implementation</th><th class="n">Witness bytes per input</th><th class="n">Tx per second</th><th class="n">Tx per block</th></tr>',
           f'<tr><td>{opcode_label("Today: P2TR key spend")}</td><td class="n">64</td><td class="n">{tps([64]):.2f}</td><td class="n">{f(round(tps([64]) * 600))}</td></tr>']
    for mode in ("stateful", "stateless"):
        for name in ORDER:
            r = tx[f"{name}-{mode}"]
            items = [r["signature_bytes"], r["program_bytes"], r["control_block_bytes"]]
            t = tps(items)
            out.append(f'<tr><td>{opcode_label(LABELS[name], mode)}, {mode}</td><td class="n">{f(sum(items))}</td><td class="n">{t:.2f}</td><td class="n">{f(round(t * 600))}</td></tr>')
        sig = tx[f"full-{mode}"]["signature_bytes"]
        t = tps([sig])
        out.append(f'<tr><td>{opcode_label("Native SHRINCS opcode (hypothetical)")}, {mode}</td><td class="n">{f(sig)}</td><td class="n">{t:.2f}</td><td class="n">{f(round(t * 600))}</td></tr>')
    return "\n".join(out) + "</table>"


def mined_tables(costs, manifest):
    rows = {r["name"]: r for r in costs["transactions"]}
    out = ['<div class="wide"><table><tr><th>Program</th><th class="n">Script bytes</th><th class="n">Of which function bodies</th><th class="n">Executed opcodes</th>'
           '<th class="n">Function calls</th><th class="n">SHA256 calls</th><th class="n">Fixed charge</th><th class="n">Charged units</th><th class="n">Fixed share</th><th class="n">Budget used</th></tr>']
    for name, label in (("full-stateful", "Stateful, shared"), ("baseline-stateful", "Stateful, inline"), ("full-stateless", "Stateless, shared"),
                        ("baseline-stateless", "Stateless, inline"), ("full-unified", "Unified, shared"), ("baseline-unified", "Unified, inline")):
        r = rows[name]
        program = compile_policy(bytes.fromhex(r["public_key"]), mode=r["mode"], profile=r["profile"])
        if len(program.code) != r["program_bytes"]:
            raise ValueError(f"Mined opcode inventory size mismatch: {name}")
        names, _ = instruction_names(program)
        OPCODE_DETAILS[f"mined-{name}"] = dict(title=label,
            note=TECHNIQUES[r["profile"]], opcodes=sorted(names & ADDED_OPCODES))
        m = r["metrics"]
        ops = sum(m["opcodes"].values())
        fixed = sum(v * fixed_price(k) for k, v in m["opcodes"].items())
        body = manifest[name]["function_body_bytes"]
        out.append(f'<tr><td>{opcode_label(label, key="mined-" + name)}</td><td class="n">{f(r["program_bytes"])}</td><td class="n">{f(body)}</td><td class="n">{f(ops)}</td><td class="n">{f(m["invocations"])}</td>'
                   f'<td class="n">{f(m["sha256_calls"])}</td><td class="n">{f(fixed)}</td><td class="n">{f(r["varops_consumed"])}</td><td class="n">{fixed / r["varops_consumed"]:.0%}</td>'
                   f'<td class="n">{r["budget_fraction"]:.1%}</td></tr>')
    out.append("</table></div>")
    a, b = rows["full-stateful"]["metrics"]["opcodes"], rows["baseline-stateful"]["metrics"]["opcodes"]
    agg = {}
    for k in set(a) | set(b):
        nm = opcode_name(k)
        agg.setdefault(nm, [0, 0, fixed_price(k)])
        agg[nm][0] += a.get(k, 0)
        agg[nm][1] += b.get(k, 0)
    op = ['<table><tr><th>Opcode</th><th class="n">Count, with functions</th><th class="n">Count, without</th><th class="n">Fixed price</th><th class="n">Fixed charge, with</th><th class="n">Fixed charge, without</th></tr>']
    for nm, (x, y, price) in sorted(agg.items(), key=lambda kv: (-(kv[1][0] + kv[1][1]), kv[0])):
        op.append(f'<tr><td>{nm}</td><td class="n">{f(x)}</td><td class="n">{f(y)}</td><td class="n">{f(price)}</td><td class="n">{f(x * price)}</td><td class="n">{f(y * price)}</td></tr>')
    ta, tb = sum(a.values()), sum(b.values())
    fa, fb = sum(v * fixed_price(k) for k, v in a.items()), sum(v * fixed_price(k) for k, v in b.items())
    op.append(f'<tr><th>Total</th><th class="n">{f(ta)}</th><th class="n">{f(tb)}</th><th></th><th class="n">{f(fa)}</th><th class="n">{f(fb)}</th></tr></table>')
    full = rows["full-stateful"]
    fixed_pct = sum(v * fixed_price(k) for k, v in full["metrics"]["opcodes"].items()) / full["varops_consumed"] * 100
    body_pct = full["metrics"]["executed_function_body_bytes"] * 3 / full["varops_consumed"] * 100
    return "\n".join(out), "\n".join(op), len(agg), fixed_pct, body_pct


def main():
    parts = json.loads((ROOT / "docs/_static_parts.json").read_text())
    report = json.loads((ROOT / "reports/multi-scenario.json").read_text())
    costs = json.loads((ROOT / "reports/costs.json").read_text())
    manifest = json.loads((ROOT / "generated/manifest.json").read_text())
    tx, st = report["transactions"], report["standalone"]
    prepare_opcode_details(report)
    # Identify the inputs by content, not by commit: the reports may not be committed yet
    # when the page is built, and CI regenerates the page from the committed reports to
    # check that the committed page matches them.
    stamp = (f'reports/multi-scenario.json <code>{sha(ROOT / "reports/multi-scenario.json")[:16]}</code>, '
             f'reports/costs.json <code>{sha(ROOT / "reports/costs.json")[:16]}</code>')
    mined, opcodes, n_opcodes, fixed_pct, body_pct = mined_tables(costs, manifest)
    data_pct = 100 - fixed_pct - body_pct
    avail = 596
    w1, w2, w3 = round(avail * fixed_pct / 100, 1), round(avail * data_pct / 100, 1), max(round(avail * body_pct / 100, 1), 2)
    sf, sl = tx["full-stateful"], tx["full-stateless"]
    cf, cl = st["catfix-stateful"], st["catfix-stateless"]
    ff, fl = st["full-stateful"], st["full-stateless"]
    mf, ml = st["multi-stateful"], st["multi-stateless"]
    ef, el = st["multisel-stateful"], st["multisel-stateless"]
    size_sf, size_sl = size_rows(tx, "stateful"), size_rows(tx, "stateless")
    d_sf, d_sl = size_sf[-1][6], size_sl[-1][6]

    page = parts["head"] + f'''

<h1>Checking post-quantum signatures in Bitcoin Script</h1>
<p class="lead">What a SHRINCS spend costs under different sets of Script opcodes, measured on an experimental fork's private test network. Not production software. It does not make any coins quantum-safe.</p>

{parts["summary"]}



<h2>Transaction size and fee</h2>
<p>One input, two outputs, one signature. Fees are paid per vbyte, and witness bytes count for a quarter, so the whole-transaction byte count and the vbyte count differ. The fee columns assume the shown rates and nothing else.</p>

<h3>Stateful signature, {f(sf["signature_bytes"])} bytes</h3>
<figure><figcaption>Transaction size in vbytes. Lower is better.</figcaption>
{size_chart(size_sf, "stateful")}
<ul class="legend"><li style="--sw: var(--s1)">Measured</li><li style="--sw: var(--dim)">Reference or hypothetical</li></ul>
<details><summary>Show as table</summary><div class="wide">{size_table(size_sf, "stateful")}</div></details></figure>

<h3>Stateless signature, {f(sl["signature_bytes"])} bytes</h3>
<figure><figcaption>Transaction size in vbytes. Lower is better.</figcaption>
{size_chart(size_sl, "stateless")}
<ul class="legend"><li style="--sw: var(--s1)">Measured</li><li style="--sw: var(--dim)">Reference or hypothetical</li></ul>
<details><summary>Show as table</summary><div class="wide">{size_table(size_sl, "stateless")}</div></details></figure>

<p>Reading the two charts: with restored opcodes alone, the checker program is {f(tx["baseline-stateful"]["program_bytes"])} bytes and the spend costs {f(tx["baseline-stateful"]["vbytes"])} vbytes, about {round(tx["baseline-stateful"]["vbytes"] / 130)} ordinary payments. Byte reversal alone cuts the program almost in half. Functions cut it by a further factor of twelve, to {f(sf["vbytes"])} vbytes, about {round(sf["vbytes"] / 130)} ordinary payments. The join fix takes {f(sf["vbytes"] - tx["catfix-stateful"]["vbytes"])} vbytes more off. A native opcode would bring it to {f(d_sf)} vbytes, about twice an ordinary payment. For the stateless type the signature itself is {f(sl["signature_bytes"])} bytes, so even a native opcode leaves the spend at {f(d_sl)} vbytes.</p>

<h2>Execution cost</h2>
<p>The fork gives every transaction an execution allowance of 10,000 units per weight unit and charges each opcode a fixed price plus data-dependent extras. A spend that exceeds its allowance is invalid. Interpreter time is the median of {report["repeats"]} runs on one machine with counters off; it is indicative, not a benchmark.</p>
<p>One caution for reading across rows. Each program signs its own transaction, because the script is part of the signed message, and a different message changes how much hash-chain work the signature needs. So the charged units in these two tables include signature-to-signature variation of a few percent. The matched-input tables further down remove that variation.</p>
<h3>Stateful</h3>
<div class="wide">{cost_table(tx, "stateful")}</div>
<h3>Stateless</h3>
<div class="wide">{cost_table(tx, "stateless")}</div>
<p>Three things stand out. Restored opcodes, OP_BYTEREV, and shared functions have similar charged costs. Byte reversal and functions mainly reduce program size. The share of the allowance rises from {tx["baseline-stateful"]["budget_fraction"]:.1%} to {sf["budget_fraction"]:.1%} for the stateful spend because a smaller transaction gets a smaller allowance. And the stateless spend with shared functions uses {sl["budget_fraction"]:.0%} of its allowance, which leaves little room for anything else in the same transaction.</p>

<figure>
  <figcaption>Where the charged units go: mined stateful spend with OP_DEFINE + OP_INVOKE.</figcaption>
  <div class="plot"><svg viewBox="0 0 640 60" role="img" aria-label="Fixed per-instruction charge {fixed_pct:.0f} percent, data-dependent charges {data_pct:.0f} percent, function body copying {body_pct:.1f} percent">
    <g><title>Fixed charge per instruction: {fixed_pct:.1f}%</title><rect x="0" y="14" width="{w1}" height="24" rx="4" fill="var(--s1)"/><text class="in" x="12" y="31">{fixed_pct:.0f}% fixed charge per instruction</text></g>
    <g><title>Data-dependent charges: {data_pct:.1f}%</title><rect x="{w1 + 2}" y="14" width="{w2}" height="24" fill="var(--s2)"/></g>
    <g><title>Function body copying: {body_pct:.1f}%</title><rect x="{w1 + 2 + w2 + 2}" y="14" width="{w3}" height="24" rx="4" fill="var(--s3)"/></g>
  </svg></div>
  <ul class="legend"><li style="--sw: var(--s1)">Fixed charge per instruction, {fixed_pct:.0f}%</li><li style="--sw: var(--s2)">Data-dependent: hashing, copying, arithmetic, {data_pct:.0f}%</li><li style="--sw: var(--s3)">Function body copying, {body_pct:.1f}%</li></ul>
</figure>
<p>Nine tenths of the charge is the fixed price of instructions, most of them stack shuffling: PICK, CAT, DROP, small pushes, IF and ENDIF. The SHA256 hashing is under a tenth. The cost model prices this checker as bookkeeping, not cryptography. Programs with much skipped code, such as the restored-opcode verifier, also run slower per charged unit than the model predicts, because parsing skipped code is not charged. Both points bear on any recalibration of the fork's prices.</p>

{parts["scenarios"]}
<p>The same checker was compiled six ways. The restored-opcode and shared-function variants were also mined on the test network. The native SHRINCS estimate uses the signature size alone. "Stateful" and "stateless" are the two SHRINCS signature types: the small one a wallet normally uses, and the large fallback for when signing state is lost.</p>

<h2>What OP_MULTI changes</h2>
<p>OP_MULTI applies one operation to a run-time number of stack items: push the items, push the count, then <code>OP_MULTI OP_SHA256</code> hashes them all as one message. The checker builds every hash input by joining parts, so this is where the opcode would help if it helped anywhere.</p>
<p>The OP_MULTI comparison exposed a compiler issue. The audited compiler starts every join from an empty push, which costs two extra opcodes per join. The optimized CAT joins remove these instructions without a new opcode. The all-uses variant then adds OP_MULTI wherever supported. The selective-hashing variant uses OP_MULTI only where hashing costs less.</p>
<p>These tables use one public test signature per signature type and run every program on it, so the signature bytes are identical across rows and only the program differs. That is the fair comparison; the transaction tables above cannot give it, because each program there signs a different message.</p>
<h3>Matched input, stateful</h3>
<div class="wide">{standalone_table(st, "stateful")}</div>
<h3>Matched input, stateless</h3>
<div class="wide">{standalone_table(st, "stateless")}</div>
<p>The join fix removes {(ff["program_bytes"] - cf["program_bytes"]) / ff["program_bytes"]:.1%} of the stateful program bytes and {(ff["varops_consumed"] - cf["varops_consumed"]) / ff["varops_consumed"]:.1%} of its charged cost; {(fl["program_bytes"] - cl["program_bytes"]) / fl["program_bytes"]:.1%} and {(fl["varops_consumed"] - cl["varops_consumed"]) / fl["varops_consumed"]:.1%} for the stateless type. OP_MULTI everywhere then removes a further {(cf["program_bytes"] - mf["program_bytes"]) / cf["program_bytes"]:.1%} of bytes but adds {(mf["varops_consumed"] - cf["varops_consumed"]) / cf["varops_consumed"]:.1%} to the charged cost, {(ml["varops_consumed"] - cl["varops_consumed"]) / cl["varops_consumed"]:.1%} for the stateless type. OP_MULTI where it is cheaper changes the charged cost by {f(ef["varops_consumed"] - cf["varops_consumed"])} and {f(el["varops_consumed"] - cl["varops_consumed"])} units, from {sum(ef["multi_uses"].values())} and {sum(el["multi_uses"].values())} uses.</p>
<p>The reason is in the cost table. The OP_MULTI byte itself is free, but its count is an ordinary push and pays the fixed 1,250, and the opcode then charges the target's fixed price once per logical operation. Against that, a chain of CATs pays 3 units per byte of every intermediate result. So hashing with OP_MULTI wins once the intermediate bytes of a join exceed about 422, after the count's own push and decoding: three 200-byte parts already cross that line, at 40,630 units against 42,364 on the pinned evaluator. The 16-byte hashes that dominate this checker do not come close, and the few large joins it has, {sum(el["multi_uses"].values())} in the stateless program, are too few to matter. OP_MULTI applied to joins that are not hashed, or to cleanups, always pays the count push for nothing under this table.</p>
<p>So the result is specific: a hash-based signature verifier, whose joins are short, does not gain from OP_MULTI. A program that hashes long lists of large items would. All extended programs pass the same {f(report["agreement_cases"])} acceptance and rejection checks as the shared-function verifier.</p>

<h2>Throughput</h2>
<p>If every transaction on the network used one scenario, how many would fit per second? Same method and assumptions as <a href="https://x.com/n1ckler/status/2039338319603999036">Jonas Nick's chart</a>: 4,000,000 weight units per block, one block per 600 seconds, an average transaction with 2.27 inputs and 2.64 outputs. The P2TR row reproduces his figure. These are capacity estimates from size, not measured network throughput.</p>
<figure><figcaption>His plot, with restored opcodes, shared functions, and the native SHRINCS estimate added. The other scenarios are in the table; they sit within a few percent of their neighbours.</figcaption>
<a href="tps.png"><img src="tps.png" alt="Scatter plot of transactions per second against witness bytes per input, with reference schemes and this experiment's scenarios" style="width:100%;height:auto;display:block;border-radius:4px"></a>
<details><summary>Show as table</summary><div class="wide">{tps_table(tx)}</div></details></figure>
<p>His SHRINCS point sits at 4.13 because it uses a 324-byte signature from a different parameter set. Ours is {f(sf["signature_bytes"])} bytes from the pinned specification. The gap between shared functions and a native SHRINCS opcode, about five times, is the cost of checking in Script instead of in the node. The gap between restored opcodes alone and shared functions, about seventeen times, is what the fork's two extra opcode groups buy.</p>

<h2>Feasibility</h2>
<div class="prose feasibility"><table>
  <tr><th>Question</th><th>Restored opcodes (inline)</th><th>OP_BYTEREV (inline)</th><th>OP_DEFINE + OP_INVOKE</th><th>OP_MULTI — all uses</th><th>Native SHRINCS opcode</th></tr>
  <tr><td>Fits the fork's consensus limits? (4 MB per item, 8 MB stack, 4 MB of executed function bodies, execution allowance)</td><td>Yes, all types</td><td>Yes, all types</td><td>Yes, all types</td><td>Yes, all types</td><td>Not applicable</td></tr>
  <tr><td>Standard under the fork's relay policy? (400,000 weight units; leaf 0xc2 has no witness-item size limit)</td><td>Yes, mined on regtest</td><td>Yes by the same limits, not spent on a node</td><td>Yes, mined on regtest</td><td>Yes by the same limits, not spent on a node</td><td>Not applicable</td></tr>
  <tr><td>Standard under Bitcoin Core's policy today?</td><td colspan="4">No. Core limits tapscript witness items to 80 bytes. Every signature here is larger. The fork exempts its new leaf version from that rule.</td><td>Would need its own rule</td></tr>
  <tr><td>Share of execution allowance, stateful / stateless</td><td>{tx["baseline-stateful"]["budget_fraction"]:.0%} / {tx["baseline-stateless"]["budget_fraction"]:.0%}</td><td>{tx["bytes-stateful"]["budget_fraction"]:.0%} / {tx["bytes-stateless"]["budget_fraction"]:.0%}</td><td>{sf["budget_fraction"]:.0%} / {sl["budget_fraction"]:.0%}</td><td>{tx["multi-stateful"]["budget_fraction"]:.0%} / {tx["multi-stateless"]["budget_fraction"]:.0%}</td><td>None</td></tr>
  <tr><td>Fee at 10 sat/vB, stateful / stateless</td><td>{f(tx["baseline-stateful"]["vbytes"] * 10)} / {f(tx["baseline-stateless"]["vbytes"] * 10)} sat</td><td>{f(tx["bytes-stateful"]["vbytes"] * 10)} / {f(tx["bytes-stateless"]["vbytes"] * 10)} sat</td><td>{f(sf["vbytes"] * 10)} / {f(sl["vbytes"] * 10)} sat</td><td>{f(tx["multi-stateful"]["vbytes"] * 10)} / {f(tx["multi-stateless"]["vbytes"] * 10)} sat</td><td>{f(d_sf * 10)} / {f(d_sl * 10)} sat</td></tr>
  <tr><td>Specification status</td><td>Draft BIPs</td><td>2024 draft text</td><td>None. Code only.</td><td>2024 draft text; inclusion questioned in review</td><td>None</td></tr>
  <tr><td>Open problems</td><td>Program size. Cost model undercharges skipped code.</td><td>Skipped code remains uncharged. Program size is reduced.</td><td>Function bodies can come from the witness. A reserved opcode inside a body makes the spend succeed. No call frames. See the <a href="https://github.com/otaliptus/gsr-shrincs/blob/main/spec/FUNCTION-DESIGN.md">design note</a>.</td><td>Same function-safety issues. Raises charged cost here; saves under 2% of bytes.</td><td>Consensus change per scheme</td></tr>
</table></div>
<p>Three things apply to every scenario. The output is ordinary Taproot, so its key path remains vulnerable to a quantum computer; a SHRINCS leaf alone does not protect the coins. There is no wallet, no signer state management, and no security proof; the scheme's own specification lists its proof as unfinished. And the numbers come from one experimental fork whose cost table is being recalibrated, so the execution costs will move; the sizes will not.</p>

<h2>What was not done</h2>
{parts["notdone"]}

<details>
  <summary>The numbers behind the charts</summary>
  <p>One row per program in the mined transactions, from {stamp}. "Shared" uses OP_BYTEREV, OP_DEFINE, and OP_INVOKE. "Inline" uses restored opcodes without these additions. Executed opcodes and calls are for one spend. The fixed charge is the sum of each executed opcode's fixed price.</p>
  {mined}
  <p>Every opcode executed by the mined stateful spend, with and without shared functions, sorted by how often it runs. The last two columns multiply the count by the opcode's fixed price.</p>
  <details><summary>Show all {n_opcodes} opcodes</summary><div class="wide">{opcodes}</div></details>
</details>

<h2>Check it yourself</h2>
<p>Everything is in the <a href="https://github.com/otaliptus/gsr-shrincs">repository</a>, which is private for now. Its README has a reading guide. The code, the test inputs, the mined transactions, and the measurements are all there, and a clean build on GitHub reproduces the programs and test results byte for byte. This page is generated from the committed reports by <code>docs/build_page.py</code>; the scenario tables come from <code>reports/multi-scenario.json</code>, which the follow-up audit re-derives and re-executes.</p>
<p class="note">Built from {stamp}. Sources: <a href="https://github.com/SHRINCS/shrincs-bip/blob/4cd63a6497a0ba7c5e99699b94d33973546d9e37/SHRINCS.md">SHRINCS specification</a>, <a href="https://github.com/jmoik/bitcoin/tree/d2799052604eb138c5a79acf88514a0c8b07f4ef">the fork</a>, <a href="https://bips.dev/440/">BIP 440</a>, <a href="https://bips.dev/441/">BIP 441</a>, <a href="https://github.com/rustyrussell/bips/pull/1">Rusty Russell's 2024 draft</a>, <a href="https://gist.github.com/jonasnick/0e7a3c4a41063e39afe8a16f70662fd3">Jonas Nick's throughput script</a>.</p>

<footer>
  Written 18 September 2026. Fork revision <code>d279905</code>. SHRINCS specification revision <code>4cd63a6</code>.
</footer>

</main>
</body>
</html>
'''
    # Static overview and feasibility labels use the union of both signature types.
    for label in (*LABELS.values(), "Today: P2TR key spend", "Native SHRINCS opcode"):
        for tag in ("td", "th"):
            page = page.replace(f"<{tag}>{label}</{tag}>", f"<{tag}>{opcode_label(label)}</{tag}>")
    payload = json.dumps(OPCODE_DETAILS, ensure_ascii=False).replace("<", "\\u003c")
    panel = '<aside id="opcode-panel" class="opcode-panel" aria-label="Added opcodes" hidden></aside>'
    page = page.replace("</body>", panel + '<script id="opcode-data" type="application/json">' + payload + '</script><script src="opcode-tooltips.js"></script></body>')
    (ROOT / "docs/index.html").write_text(page)
    print("docs/index.html", len(page))


if __name__ == "__main__":
    main()
