#!/usr/bin/env python3
"""Generate the separate comparison page from its own checked evidence."""
from html import escape
import json
import statistics
import run
from docs.build_page import ADDED_OPCODES, instruction_names

LABELS = {"baseline": "Restored opcodes · inline", "bytes": "OP_BYTEREV · inline",
          "full": "OP_DEFINE + OP_INVOKE", "catfix": "Functions + optimized CAT joins"}


def fmt(n): return f"{n:,}"
def ms(samples): return f"{statistics.median(samples) / 1e6:.3f}"


def main():
    run.audit()
    report = json.loads((run.HERE / "results.json").read_text())
    parts = json.loads((run.ROOT / "docs/_static_parts.json").read_text())
    head = parts["head"].replace("<title>SHRINCS in Bitcoin Script</title>", "<title>Simplicity version comparison · SHRINCS</title>")
    head = head.replace('content="A plain summary of an experiment: checking SHRINCS post-quantum signatures with general-purpose Bitcoin Script on an experimental fork."',
                        'content="The same SHRINCS verification rules measured in GSR Script and Simplicity. Separate, reproducible research experiment."')
    extra_css = '''
    .comparison-nav { display:flex; flex-wrap:wrap; gap:8px 24px; padding-bottom:14px; margin-bottom:28px; border-bottom:1px solid var(--grid); font-size:14px; }
    .comparison-nav a { text-decoration:none; }
    .comparison-nav [aria-current] { color:var(--ink); font-weight:600; }
    .comparison-intro { max-width:740px; }
    .comparison-figures { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
    .comparison-figures figure { margin:0; padding:18px; }
    .bar-row { margin:14px 0; }
    .bar-label { display:flex; justify-content:space-between; gap:12px; font-size:14px; }
    .bar-track { background:var(--grid); margin-top:6px; height:10px; }
    .bar-fill { height:10px; background:var(--s1); }
    .bar-fill.simplicity { background:var(--s3); }
    .evidence-strip { border-left:3px solid var(--s3); padding-left:16px; margin:24px 0; }
    .comparison-table { overflow-x:auto; }
    .comparison-table table { min-width:630px; }
    .comparison-table th, .comparison-table td { padding:10px 12px 10px 0; }
    .comparison-table tr.featured { background:var(--surface); }
    .hash { overflow-wrap:anywhere; }
    .jets { columns:2; font-size:13px; }
    @media(max-width:650px) { .comparison-figures { grid-template-columns:1fr; } .jets { columns:1; } }
    '''
    head = head.replace("</style>", extra_css + "</style>")
    total = sum(len(x["cases"]) for x in report["modes"].values())
    accepted = sum(sum(c["accepted"] for c in x["cases"]) for x in report["modes"].values())
    tips = {}
    for mode in run.MODES:
        for profile in run.PROFILES:
            names, _ = instruction_names(run.gsr.compile_verifier(mode, profile))
            tips[f"{mode}-{profile}"] = dict(title=LABELS[profile],
                note=f"{mode.capitalize()} standalone verifier. Restored instructions and fork extensions used by this program.",
                opcodes=sorted(names & ADDED_OPCODES))
    page = head + f'''
<nav class="comparison-nav" aria-label="Experiments"><a href="/">Script restoration</a><a href="/simplicity-version-comparison/" aria-current="page">Simplicity version comparison</a></nav>
<p class="note">Separate experiment · same verification rules</p>
<h1>SHRINCS, using the Simplicity construction</h1>
<p class="lead comparison-intro">One set of signatures. Two execution languages. This experiment translates Blockstream Research’s Simplicity verifier into GSR Bitcoin Script.</p>
<div class="evidence-strip"><strong>{fmt(total)} cases agree.</strong> Python, Simplicity, and all four Script variants agree on {fmt(accepted)} accepted cases and {fmt(total-accepted)} rejected cases.
<p class="note">The corpus starts from two public signatures, one per mode. It changes their fields one at a time. This is testing, not a proof of equivalence.</p></div>
<p>Our <a href="/">original experiment</a> follows a different SHRINCS specification. Its measurements remain separate. The results below follow the Simplicity construction on both sides.</p>
<h2>Encoded program size</h2>
<p>These bars compare the Script variant with shared functions and optimized CAT joins against the pruned Simplicity program.</p>
<div class="comparison-figures">
'''
    for mode, row in report["modes"].items():
        values = [("Script · functions + CAT joins", row["gsr"]["catfix"]["program_bytes"], ""),
                  ("Simplicity · pruned", row["simplicity"]["program_bytes"], "simplicity")]
        maximum = max(v for _, v, _ in values)
        page += f'<figure><figcaption><strong>{mode.capitalize()}</strong> · program bytes</figcaption>'
        for label, value, kind in values:
            page += f'<div class="bar-row"><div class="bar-label"><span>{label}</span><strong>{fmt(value)}</strong></div><div class="bar-track" aria-hidden="true"><div class="bar-fill {kind}" style="width:{100*value/maximum:.3f}%"></div></div></div>'
        page += '</figure>'
    page += '''</div><p class="note">Program bytes exclude input data and transaction overhead. Simplicity removes unexecuted branches before encoding. Script retains its conditional branches.</p>
<h2>All measured implementations</h2>
<p>The signatures contain the same logical values. Each language uses its own input encoding.</p>'''
    for mode, row in report["modes"].items():
        page += f'<h3>{mode.capitalize()}</h3><div class="comparison-table"><table><thead><tr><th>Implementation</th><th class="n">Program bytes</th><th class="n">Input bytes</th><th class="n">Execution charge or bound</th></tr></thead><tbody>'
        for profile, g in row["gsr"].items():
            label = f'<button type="button" class="opcode-label" data-opcodes="{mode}-{profile}" aria-expanded="false" aria-controls="opcode-panel">{LABELS[profile]}</button>'
            page += f'<tr><td>{label}</td><td class="n">{fmt(g["program_bytes"])}</td><td class="n">{fmt(row["logical_input_bytes"])}</td><td class="n">{fmt(g["varops"])} varops</td></tr>'
        s = row["simplicity"]
        page += f'<tr class="featured"><td>Simplicity · pruned</td><td class="n">{fmt(s["program_bytes"])}</td><td class="n">{fmt(s["witness_bytes"])}</td><td class="n">{fmt(int(s["cost_bound"]))} milliweight</td></tr></tbody></table></div>'
        page += f'<p class="note">Simplicity before pruning: {fmt(s["unpruned_program_bytes"])} program bytes. C and Rust agree on its cost bound.</p>'
    page += '''<p><strong>Varops and milliweight are different units.</strong> Do not divide one by the other to compare performance.</p>
<p class="note">Script input bytes count the fixed-width fields placed on its initial stack. They exclude stack-item length prefixes. Simplicity input bytes count its encoded witness. Pruning can remove unused fields.</p>
<h2>What the two languages do</h2>
<div class="comparison-table"><table><thead><tr><th>Step</th><th>Script restoration</th><th>Simplicity</th></tr></thead><tbody>
<tr><td>Read the proof</td><td>Check byte lengths and extract fields.</td><td>Decode a typed witness.</td></tr>
<tr><td>Recover the signature root</td><td>Run hash chains and authentication paths with Script instructions.</td><td>Run the same hash rules with typed functions and SHA-256 jets.</td></tr>
<tr><td>Check the public key</td><td>Combine the recovered root with the supplied unused root. Compare the resulting hash.</td><td>Apply the same root-combination rule.</td></tr>
<tr><td>Remove unused code</td><td>Keep conditional branches in the Script.</td><td>Prune branches that this witness does not execute.</td></tr>
</tbody></table></div>
<p>A jet is a native implementation of a specified Simplicity operation. This verifier uses general hashing and arithmetic jets; it has no dedicated SHRINCS jet.</p>
<details><summary>Jets present in the measured, pruned programs</summary><ul class="jets">'''
    jets = sorted(set(j for row in report["modes"].values() for j in row["simplicity"]["jets"]))
    page += ''.join(f'<li><code>{escape(j)}</code></li>' for j in jets) + '</ul></details>'
    page += f'''<h2>Timing, with the boundaries shown</h2>
<p>These samples use the same machine and {report["repeats"]} repetitions. The table shows medians. Compilation and process startup are excluded.</p>
<div class="comparison-table"><table><thead><tr><th>Timed operation</th><th class="n">Stateful, ms</th><th class="n">Stateless, ms</th></tr></thead><tbody>'''
    sf, sl = (report["modes"][m] for m in run.MODES)
    for label, values in (
        ("GSR interpreter · functions + CAT joins", [x["gsr"]["catfix"]["interpreter_ns"] for x in (sf, sl)]),
        ("Simplicity C · evaluation and bounds checks", [x["simplicity"]["c_execution_ns"] for x in (sf, sl)]),
        ("Simplicity C · decode, check, and evaluate", [x["simplicity"]["c_validation_ns"] for x in (sf, sl)]),
        ("Simplicity Rust · Bit Machine execution", [x["simplicity"]["execution_ns"] for x in (sf, sl)])):
        page += f'<tr><td>{label}</td><td class="n">{ms(values[0])}</td><td class="n">{ms(values[1])}</td></tr>'
    page += '''</tbody></table></div><p class="note">The timed boundaries differ. These figures do not establish a VM speed ratio. The C adapter is documented in the experiment notes.</p>
<h2>What this establishes</h2>
<p>Both languages execute this construction on the same public fixtures. The recorded sizes include the effects of their actual compilers and encodings.</p>
<p>The comparison does not establish a complete Bitcoin spend cost. Both standalone programs receive the public key and message as inputs.</p>
<p>A spending policy must commit to the expected key and derive the message from the transaction. That work remains separate.</p>
<p>A smaller program does not guarantee a cheaper spend. The <a href="https://github.com/BlockstreamResearch/shrincs-simplicity-verifier/blob/d13165d3d21bac73e8794eede21f0f1527f3b837/docs/shrincs_liquid_benchmarks/performance_report.md">published Liquid transactions</a> include padding to meet their execution budget.</p>
<p>We have not proved equivalence for every input, measured all stateful depths, or established that either compiler produces optimal code.</p>
<h2>Reproduce and inspect</h2>
<ul>
<li><a href="results.json">Recorded measurements and case inventory</a></li>
<li><a href="README.md">Method, exact pins, commands, and limits</a></li>
<li><a href="https://github.com/BlockstreamResearch/shrincs-simplicity-verifier/tree/d13165d3d21bac73e8794eede21f0f1527f3b837">Pinned upstream verifier</a></li>
<li><a href="https://github.com/otaliptus/gsr-shrincs/tree/main/experiments/simplicity-version-comparison">Experiment source in our private repository</a></li>
</ul>'''
    page += f'<p class="note">Recorded host: {escape(report["host"]["platform"])} · {escape(report["host"]["machine"])}</p>'
    page += f'<footer><p>Research experiment. No production wallet or mainnet activation is claimed.</p><p class="hash">Evidence SHA-256: {run.file_sha(run.HERE / "results.json")}</p><a href="/">Return to the original Script experiment</a></footer></main></body></html>'
    payload = json.dumps(tips, ensure_ascii=False).replace("<", "\\u003c")
    page = page.replace('</body>', '<aside id="opcode-panel" class="opcode-panel" aria-label="Added opcodes" hidden></aside>'
                        + '<script id="opcode-data" type="application/json">' + payload + '</script>'
                        + '<script src="/opcode-tooltips.js"></script></body>')
    output = run.ROOT / "docs/simplicity-version-comparison"
    output.mkdir(exist_ok=True)
    (output / "index.html").write_text(page)
    for name in ("README.md", "results.json"):
        (output / name).write_bytes((run.HERE / name).read_bytes())
    print(f"Generated {output.relative_to(run.ROOT)}/index.html")


if __name__ == "__main__":
    main()
