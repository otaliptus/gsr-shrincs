# Execution profiles and compiler design

The execution target is `jmoik/bitcoin` at this revision:

```text
d2799052604eb138c5a79acf88514a0c8b07f4ef
```

The signature reference is `SHRINCS/shrincs-bip` at this revision:

```text
4cd63a6497a0ba7c5e99699b94d33973546d9e37
```

## Profiles

The `baseline` profile uses the BIP 440/441 restoration operations present in the pinned fork.
These include CAT, SUBSTR, LEFT, unsigned arithmetic, shifts, hashes, conditionals,
and ordinary stack operations.
Exact slices implement byte reversal.
The compiler expands all bounded computation inline.
This standalone profile uses no function opcodes or `OP_TX`.

The `bytes` profile adds BYTEREV to the baseline operations.
It retains inline execution for comparison with shared functions.

The `full` profile also adds DEFINE and INVOKE.
It shares functions for hash chains, WOTS, FORS, root recovery, and Merkle pairs.
The functions do not use recursion.
No profile needs MULTI, TWEAKADD, or CHECKSIGFROMSTACK.

A transaction policy adds authenticated `OP_TX` access to the selected verifier.
This is an additional fork extension in every case.
A baseline verifier within this policy does not make the complete policy BIP-441-only.

## Resource limits

The following limits come from `src/script/script.h`, `interpreter.cpp`, and `varops.h`
in the pinned fork.

| Resource | Limit |
|---|---:|
| Combined stack entries, including function definitions | 32,768 |
| Bytes per item | 4,000,000 |
| Total stack, altstack, and function-body bytes | 8,000,000 |
| Cumulative invoked function-body bytes per evaluation | 4,000,000 |
| Transaction-wide varops allowance | 10,000 × transaction weight |

The VM rejects active recursion and function-local code separators.
The experiments add no padding to obtain a larger budget.
Consensus limits, relay policy, and payment costs are separate constraints.
Meeting a consensus limit does not establish practical payment costs.

## Compiler

The handoff proposed Rust for the generator.
This implementation uses Python to avoid another build dependency.
One deterministic compiler covers all fixed components of the scheme.
Python does not implement the consensus VM.
Only execution in the pinned C++ fork establishes Script behavior.

The reference module remains an independent upstream implementation.
The generator copies address objects before upstream calls that can change them.

Each expression leaves one stack item.
Named values track stack depth.
Generation fails if a value is missing or branches have different stack shapes.
Function contracts specify their inputs and outputs.
Each function consumes its arguments and local values and returns one item.

The compiler checks input and hash widths or derives them from validated slices.
All generated repetition has a fixed bound.
Measured peak memory includes the original signature and temporary copies.

## Measurements

`scripts/profile_build.py` applies measurement changes to a separate source copy under `build/`.
The original upstream source and regtest node remain unchanged.
Measurement counters do not change branches, budgets, limits, or comparison results.
Instrumented and uninstrumented execution must agree on acceptance and varops.

Offline transaction measurements use recorded UTXOs.
These records are not an independent source of authenticated chain data.
