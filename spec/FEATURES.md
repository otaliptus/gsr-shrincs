# Execution profiles and compiler design

Authoritative execution target: jmoik/bitcoin at
`d2799052604eb138c5a79acf88514a0c8b07f4ef`. Scheme: SHRINCS/shrincs-bip at
`4cd63a6497a0ba7c5e99699b94d33973546d9e37`.

1. **baseline**: the BIP 440/441 restoration surface as represented by the pinned
   fork. Uses CAT, SUBSTR, LEFT, unsigned arithmetic/shifts, hashes, conditionals,
   and ordinary stack operations. Byte reversal is expanded into exact slices;
   all bounded computation is inlined. No function opcodes or OP_TX.
2. **full**: baseline plus BYTEREV and DEFINE/INVOKE. Hash-chain, WOTS, FORS,
   stateful/stateless recovery, and Merkle-pair bodies are shared nonrecursive
   functions. No MULTI, TWEAKADD, or CHECKSIGFROMSTACK is needed.
3. **transaction**: either verifier placement plus authenticated OP_TX. This is
   always an additional fork extension; a baseline verifier inside this wrapper
   does not make the complete spending policy BIP-441-only.

Pinned limits from `src/script/script.h`, `interpreter.cpp`, and `varops.h`:
32,768 combined stack entries including function definitions; 4,000,000 bytes
per item; 8,000,000 total stack/altstack/function-body bytes; 4,000,000 cumulative
invoked function-body bytes per evaluation. Transaction-wide varops allowance is
10,000 times weight. Active recursion and function-local code separators reject.
Consensus ceilings, mempool standardness, and everyday-payment practicality are
separate. No padding is added to purchase execution budget.

The handoff proposed a Rust generator; this implementation deliberately uses a
small Python generator instead. That removes a second build/tool dependency and
lets one deterministic stack-checked compiler cover all fixed scheme components.
There is no Python consensus VM. Only the pinned C++ execution result establishes
Script behavior. The reference module remains an independent upstream oracle.

Expressions leave one stack item. Named values track stack depth; missing values
and different branch stack shapes fail generation. Function inputs and outputs
have explicit contracts; each consumes its own arguments/locals and returns one
item. Input/hash widths are checked or derived from validated slices. All loops
are bounded at generation time. Reference addresses are copied before mutable
upstream calls. Original signature storage and scratch copying are included in
measured peak memory.

The separate profiling build applies the reviewable `scripts/profile_build.py`
observation overlay to a disposable copy under build/. The original vendor tree
and the node used for regtest remain unchanged. Observation counters do not alter
branches, budgets, limits, or comparison results. Instrumented/uninstrumented
acceptance and varops must agree. Offline transaction measurements use recorded
UTXOs; they are not an independent source of authenticated chain data.
