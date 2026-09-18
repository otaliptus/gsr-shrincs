# Parsing work and varops

The recorded workload supports investigation of skipped-code parsing.
It does not yet establish how much of the timing spread that parsing causes.
No cost constant or consensus rule was changed for this measurement.

## Observed work

The observation build counts instructions and bytes read by `EvalTapscriptV2Impl`.
It includes invoked function bodies. It separates ordinary instructions in untaken branches from instructions that execute.

The observation build preserves acceptance and exact varops for all fourteen recorded spends.

| Recorded spend | Parsed bytes | Bytes in skipped instructions | Parsed instructions | Skipped instructions |
|---|---:|---:|---:|---:|
| Full, stateful | 25,515 | 5,992 | 18,712 | 5,011 |
| Full, stateless | 135,275 | 31,825 | 106,787 | 26,725 |
| Inline, unified, stateful execution | 228,549 | 201,424 | 185,458 | 160,691 |
| Inline, stateful | 95,350 | 76,636 | 69,398 | 53,041 |
| Inline, stateless | 133,452 | 32,545 | 116,129 | 27,325 |

Approximately 88.1% of the parsed bytes in the inline unified stateful case belong to skipped instructions.
The corresponding full stateful figure is approximately 23.5%.
This is a direct work-count difference. It is not a measured CPU-time percentage.

The counters exclude the separate success-opcode scan.
They also exclude the second opcode read internally by OP_MULTI. The recorded SHRINCS programs do not use OP_MULTI.
The counters therefore must not be described as all parser activity in transaction validation.

Evidence: [parsing-counts.json](parsing-counts.json).
The source and executable hashes identify the observation build.

## What the timing spread means

An isolated C++ benchmark replays the observed parsing schedule for all fourteen spends.
It uses the pinned `CScript::GetOp` implementation with and without payload copying.
Every schedule matches the interpreter's recorded byte and instruction counts.

| Recorded spend | Parsing with payload copy, median microseconds | Decoding without payload copy, median microseconds |
|---|---:|---:|
| Full, stateful | 63.1 | 58.8 |
| Full, stateless | 346.9 | 331.7 |
| Inline, unified, stateful execution | 631.4 | 596.3 |
| Inline, stateful | 253.3 | 217.8 |
| Inline, stateless | 374.2 | 373.8 |

Each value uses 21 samples after warm-up. Each sample repeats the recorded schedule sixteen times.
The variants decode the same instruction sequence. No signature or stress program is synthesized for this benchmark.

These figures support the presence of substantial parsing work in the inline unified program.
Payload copying alone does not explain most of its isolated parser time.
The no-copy result excludes the success-opcode checks that accompany the real preliminary scan.

The isolated loop reuses a payload buffer within a body. Its allocation behavior differs from execution.
It also omits branch-state management, stack operations, hashing, and function calls.
Do not subtract these times from interpreter timings to claim an exact CPU-time share.
The machine and concurrent load differ from the historical timing report below.

Evidence: [parser-benchmark.json](parser-benchmark.json). This includes source hashes, executable hashes, counts, and raw samples.

The historical report gives approximately 38,000 varops per microsecond for the full stateless spend.
It gives approximately 13,650 for inline unified stateful execution.
These rates use the earlier report's machine and timing method.

A ratio near 2.8 does not prove incorrect pricing.
The model may intentionally charge different workloads conservatively.
The important requirement is a sufficient bound on validation work under the combined limits.

BIP 440 explicitly treats interpretation overhead as limited by block size.
The current fork also has a fixed execution charge. These are distinct accounting mechanisms.
Source: [BIP 440 assumptions](https://bips.dev/440/).

The hypothesis to test next is narrower:

> A substantial part of the extra time in the inline stateful program comes from parsing its untaken branches.

The isolated benchmark supports this hypothesis but does not prove its share of the full runtime difference.
A controlled interpreter comparison or independent sampling profile must establish that causal share.
Keep acceptance and varops fixed in that comparison.

Do not infer CPU-time shares from opcode counts or inclusive function costs.
Do not add inclusive function costs together; nested work would be counted more than once.

## Correct block extrapolation

The maximum theoretical allowance at four million weight units is forty billion varops under this pinned rule.
Dividing that allowance by the observed rates gives roughly one to three seconds.
That is a budget-saturation extrapolation. It is not a measured block filled with these spends.

For example, the inline unified stateful transaction weighs 229,738 units and uses only about 1.5% of its allowance.
Ignoring block overhead, at most seventeen such transactions fit in four million weight units.
Seventeen times the reported 2.539 ms is approximately 43 ms of summed interpreter time.

Both calculations exclude other block-validation work. Neither establishes a worst-case block-validation bound.
The historical timings retain profiling hooks, even when their counters are disabled.

## Decision

Investigate parsed work before changing the fixed 1,250 charge.
Compare an explicit parsing charge, a parsed-work bound, and implementation improvements only after the timing experiment.
A new charge must specify which passes and repeated function-body parses it counts.
Retain transaction weight, memory limits, and function limits in the analysis.

Reproduce the counts with:

```sh
python3 scripts/parsing_probe.py \
  --reference-binary build/profile/bin/bitcoin-util
```

The command builds a separate observation executable. It does not modify the pinned fork.

After that build, run the isolated parser benchmark:

```sh
python3 scripts/parse_benchmark.py --repeats 21
```

This adds a laboratory command to the separate executable. It does not change Script execution or charging rules.
