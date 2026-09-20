#!/usr/bin/env python3
"""Generate the separate comparison page from its own checked evidence."""
from html import escape
import json
import statistics
import run
from docs.build_page import ADDED_OPCODES, experiment_nav, instruction_names

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
                        'content="SHRINCS verification in GSR Script and Simplicity: program sizes, execution charges, test results, and limits."')
    extra_css = '''
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
    .size-note { border-top:1px solid var(--grid); border-bottom:1px solid var(--grid); padding:18px 0; margin:28px 0; }
    .size-note h2 { margin:0 0 8px; }
    .size-note p:last-child { margin-bottom:0; }
    .size-note table { max-width:580px; }
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
{experiment_nav("simplicity")}
<h1>SHRINCS in Script and Simplicity</h1>
<p class="lead comparison-intro">We translated Blockstream Research’s Simplicity verifier into GSR Bitcoin Script. Both implementations check the same public keys, messages, and signature fields.</p>
<p>The <a href="/">original Script experiment</a> uses different SHRINCS parameters. This page measures the Simplicity verification rules in both languages.</p>
<div class="evidence-strip"><strong>{fmt(total)} test cases.</strong> Python, Simplicity, and all four Script variants accept {fmt(accepted)} cases and reject {fmt(total-accepted)} cases.
<p class="note">The tests start from two public signatures, one per mode. They change individual fields. Four changes affect unused fields and remain valid.</p></div>
<h2>Program size</h2>
<p>These bars show encoded instructions, without input data or transaction overhead. The Script programs use shared functions and optimized CAT joins.</p>
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
    page += '''</div><p class="note">Simplicity removes unused branches before encoding. This operation is called pruning. Script keeps its conditional branches.</p>
<section class="size-note" id="50kb" aria-labelledby="50kb-title">
<h2 id="50kb-title">What about the 50 kB claim?</h2>
<p>We previously cited an approximate 50 kB verifier size. We have not verified its program revision, compiler, or size definition.</p>
<p>Our current Simplicity build gives these sizes. One kB equals 1,000 bytes.</p>
<table><thead><tr><th>Program bytes</th><th class="n">Stateful</th><th class="n">Stateless</th></tr></thead><tbody>'''
    for label, key in (("Before pruning", "unpruned_program_bytes"), ("After pruning", "program_bytes")):
        page += f'<tr><td>{label}</td><td class="n">{fmt(report["modes"]["stateful"]["simplicity"][key])}</td><td class="n">{fmt(report["modes"]["stateless"]["simplicity"][key])}</td></tr>'
    page += '''</tbody></table>
<p>Pruning alone cannot explain 50 kB: these programs are already below 5 kB before pruning.</p>
<p>These are separate stateful and stateless programs, compiled with SimplicityHL 0.7.2. They exclude transaction data and execution-budget padding.</p>
<p>The <a href="https://github.com/BlockstreamResearch/shrincs-simplicity-verifier/blob/d13165d3d21bac73e8794eede21f0f1527f3b837/docs/shrincs_liquid_benchmarks/performance_report.md">upstream Liquid report</a> measures transaction witness size and includes padding. It does not establish the source of the 50 kB figure.</p>
<p>We need the original program and build settings to explain the difference. Until then, 50 kB is an unverified reference.</p>
</section>
<h2>Measurements</h2>
<p>Each language encodes its input fields differently. Simplicity calls its encoded input data the witness.</p>'''
    for mode, row in report["modes"].items():
        page += f'<h3>{mode.capitalize()}</h3><div class="comparison-table"><table><thead><tr><th>Implementation</th><th class="n">Program bytes</th><th class="n">Input bytes</th><th class="n">Execution charge or bound</th></tr></thead><tbody>'
        for profile, g in row["gsr"].items():
            label = f'<button type="button" class="opcode-label" data-opcodes="{mode}-{profile}" aria-expanded="false" aria-controls="opcode-panel">{LABELS[profile]}</button>'
            page += f'<tr><td>{label}</td><td class="n">{fmt(g["program_bytes"])}</td><td class="n">{fmt(row["logical_input_bytes"])}</td><td class="n">{fmt(g["varops"])} varops</td></tr>'
        s = row["simplicity"]
        page += f'<tr class="featured"><td>Simplicity · pruned</td><td class="n">{fmt(s["program_bytes"])}</td><td class="n">{fmt(s["witness_bytes"])}</td><td class="n">{fmt(int(s["cost_bound"]))} milliweight</td></tr></tbody></table></div>'
        page += f'<p class="note">Simplicity before pruning: {fmt(s["unpruned_program_bytes"])} program bytes. C and Rust agree on its cost bound.</p>'
    page += '''<p>GSR charges execution in varops. Simplicity gives an upper limit in milliweight. These units do not give a common performance scale.</p>
<p class="note">Script input sizes exclude the length prefixes for stack items. Simplicity input sizes include witness encoding. Pruning can remove unused fields.</p>
<h2>Verification steps</h2>
<div class="comparison-table"><table><thead><tr><th>Step</th><th>Script restoration</th><th>Simplicity</th></tr></thead><tbody>
<tr><td>Read the input</td><td>Check byte lengths and extract fields.</td><td>Decode the witness according to its data types.</td></tr>
<tr><td>Recover the signature root</td><td>Run hash chains and authentication paths with Script instructions.</td><td>Run the same hash rules with typed functions and SHA-256 jets.</td></tr>
<tr><td>Check the public key</td><td>Combine the recovered root with the supplied unused root. Compare the resulting hash.</td><td>Apply the same root-combination rule.</td></tr>
<tr><td>Remove unused code</td><td>Keep conditional branches in the Script.</td><td>Remove branches that this input does not use.</td></tr>
</tbody></table></div>
<p>A jet runs a specified Simplicity operation through native code. This verifier uses general hash and arithmetic jets. It has no dedicated SHRINCS jet.</p>
<details><summary>Jets used by these programs</summary><ul class="jets">'''
    jets = sorted(set(j for row in report["modes"].values() for j in row["simplicity"]["jets"]))
    page += ''.join(f'<li><code>{escape(j)}</code></li>' for j in jets) + '</ul></details>'
    page += f'''<h2>Execution time</h2>
<p>The table shows the median of {report["repeats"]} runs on one machine. The timers exclude compilation and process startup.</p>
<div class="comparison-table"><table><thead><tr><th>Timed operation</th><th class="n">Stateful, ms</th><th class="n">Stateless, ms</th></tr></thead><tbody>'''
    sf, sl = (report["modes"][m] for m in run.MODES)
    for label, values in (
        ("GSR interpreter · functions + CAT joins", [x["gsr"]["catfix"]["interpreter_ns"] for x in (sf, sl)]),
        ("Simplicity C · evaluation and bounds checks", [x["simplicity"]["c_execution_ns"] for x in (sf, sl)]),
        ("Simplicity C · decode, check, and evaluate", [x["simplicity"]["c_validation_ns"] for x in (sf, sl)]),
        ("Simplicity Rust · Bit Machine execution", [x["simplicity"]["execution_ns"] for x in (sf, sl)])):
        page += f'<tr><td>{label}</td><td class="n">{ms(values[0])}</td><td class="n">{ms(values[1])}</td></tr>'
    page += '''</tbody></table></div><p class="note">The timers cover different work. Do not use these values to calculate a speed ratio between the languages. The experiment notes define each timer.</p>
<h2>Limits</h2>
<ul>
<li>These tests do not prove equivalence for every input. We measured one original signature per mode, without testing all stateful path depths.</li>
<li>These programs receive the public key and message as inputs. A spending policy must commit to the key and calculate the transaction message.</li>
<li>We have not measured complete transaction sizes or fees. A smaller program does not guarantee a cheaper transaction.</li>
<li>Compiler choices affect program size. We have not established the smallest possible program in either language.</li>
</ul>
<h2>Source and data</h2>
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
