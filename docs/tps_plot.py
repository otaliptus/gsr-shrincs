#!/usr/bin/env python3
"""Draw docs/tps.png: throughput against witness bytes per input.

The layout and the first six points follow Jonas Nick's size-optimized plot,
https://gist.github.com/jonasnick/0e7a3c4a41063e39afe8a16f70662fd3, and use
his assumptions: 4,000,000 weight units per block, one block every 600 s, an
average transaction with 2.27 inputs and 2.64 outputs. Under those assumptions
this script reproduces his P2TR figure of 6.55 transactions per second.

The remaining points come from this repository's measured witness sizes
(reports/regtest-details.json.gz, tag baseline-2026-09-18). Bytes per input
are signature plus checker program plus control block. The native-opcode point
is hypothetical: the same 660-byte signature with nothing else in the witness.

Requires matplotlib, which is not a dependency of the repository:
    python3 -m venv /tmp/plot && /tmp/plot/bin/pip install matplotlib
    /tmp/plot/bin/python docs/tps_plot.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

BLOCK_WEIGHT = 4_000_000
BLOCK_INTERVAL = 600
INPUTS = 2.27
OUTPUTS = 2.64


def compact_size(n):
    return 1 if n < 253 else 3 if n < 65536 else 5


def throughput(witness_items):
    """Transactions per second if every input carried these witness items."""
    base_weight = (10 + INPUTS * 41 + OUTPUTS * 43) * 4 + 2
    witness = 1 + sum(compact_size(n) + n for n in witness_items)
    weight = base_weight + INPUTS * witness
    per_block = BLOCK_WEIGHT / weight
    return per_block / BLOCK_INTERVAL, witness


# Jonas Nick's rows, copied from his table: name, bytes, TPS, UTXOs per block.
THEIRS = [
    ("P2TR keyspend only", 64, 6.55, 8918, "D", "#1f77b4", (14, -6)),
    ("SHRINCS only", 324, 4.13, 5630, "s", "#2ca02c", (14, 6)),
    ("Mixed (60/30/10)", 1367, 1.67, 2281, "p", "#9467bd", (-150, 18)),
    ("SHRIMPS only", 2564, 1.00, 1356, "^", "#ff7f0e", (-135, 20)),
    ("Opt. SPHINCS+ only", 4036, 0.66, 904, "o", "#d62728", (-195, -14)),
    ("SLH-DSA only", 7872, 0.36, 484, "v", "#8c564b", (16, 16)),
]

# This experiment: name, witness items per input, marker, color, label offset.
MEASURED = [
    ("Native opcode (hypothetical)", [660], "D", "#17becf", (14, -20)),
    ("Script, stateful", [660, 4476, 65], "*", "#e377c2", (10, 22)),
    ("Script, stateless", [5777, 14091, 65], "*", "#bcbd22", (14, -3)),
    ("Script, stateful, inline", [660, 95350, 65], "X", "#7f7f7f", (-130, 34)),
    ("Script, stateless, inline", [5777, 133452, 65], "X", "#000000", (-90, 62)),
]

FOOTER = (
    "Each point assumes all block spends use that scheme. 4 MWU blocks, 600 s interval, average tx 2.27 inputs and 2.64 outputs.\n"
    "Upper six points and their table rows: Jonas Nick, size-optimized parameters. There the output commits directly to the PQ key,\n"
    "so bytes per input equals signature size. Shaded rows: this experiment on the GSR fork, measured on regtest, pinned SHRINCS spec\n"
    "(660-byte stateful, 5,777-byte stateless signature). Bytes per input include the checker program and control block.\n"
    "Native opcode row is hypothetical: the same signature and no program. Inline: the checker without shared functions."
)


def main():
    check, _ = throughput([64])
    if abs(check - 6.55) > 0.01:
        raise SystemExit(f"P2TR reference does not reproduce: {check:.3f}")
    ours = []
    for name, items, marker, color, offset in MEASURED:
        tps, _ = throughput(items)
        # Plot and tabulate the bare item bytes, matching the signature-size axis
        # of the reference points. Length prefixes only enter the weight model.
        ours.append((name, sum(items), tps, round(tps * BLOCK_INTERVAL * INPUTS), marker, color, offset))

    fig, ax = plt.subplots(figsize=(12.2, 9.6), dpi=180)
    fig.suptitle("Bitcoin Post-Quantum Throughput: Size-Optimized, with SHRINCS in Script",
                 fontsize=17, fontweight="bold", y=0.965)
    ax.set_xscale("log")
    ax.set_xlim(45, 400000)
    ax.set_ylim(0, 6.9)
    ax.grid(True, which="major", color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Witness bytes per input", fontsize=15)
    ax.set_ylabel("Transactions per second", fontsize=15)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.tick_params(labelsize=13)
    for name, x, y, _, marker, color, (dx, dy) in THEIRS + ours:
        ax.plot(x, y, marker=marker, ms=18 if marker == "*" else 15, mec="black", mfc=color, ls="none", zorder=3)
        ax.annotate(name, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=12.5,
                    fontweight="bold", color=color,
                    arrowprops=dict(arrowstyle="-", color=color, lw=0.8, alpha=0.7))
    ax2 = ax.twinx()
    ax2.set_ylim(0, 6.9 * BLOCK_INTERVAL * INPUTS)
    ax2.set_ylabel("UTXOs spent per block", fontsize=15, color="#666666")
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax2.tick_params(labelsize=13, colors="#666666")
    ax2.set_yticks([0, 2000, 4000, 6000, 8000])
    rows = [[n, f"{x:,}", f"{y:.2f}", f"{u:,}"] for n, x, y, u, *_ in THEIRS + ours]
    table = ax.table(cellText=rows, colLabels=["Scheme", "Bytes/input", "TPS", "UTXOs/blk"],
                     colWidths=[0.50, 0.19, 0.13, 0.18], cellLoc="right", loc="upper right",
                     bbox=[0.475, 0.47, 0.515, 0.51], zorder=5)
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#cccccc")
        cell.set_facecolor("white")
        if c == 0:
            cell.set_text_props(ha="left")
        if r == 0:
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#f2f2f2")
        if r > len(THEIRS):
            cell.set_facecolor("#eef4ff")
    fig.text(0.5, 0.035, FOOTER, ha="center", fontsize=10.5, color="#333333")
    fig.subplots_adjust(top=0.92, bottom=0.19, left=0.075, right=0.91)
    out = Path(__file__).with_name("tps.png")
    fig.savefig(out)
    print(out)


if __name__ == "__main__":
    main()
