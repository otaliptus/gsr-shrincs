**GSR SHRINCS verifier: implementation plan and related Script research**

Prepared 18 September 2026. This is a proposed work plan, informed by source inspection. No GSR build, verifier execution, cryptographic proof validation, or performance measurement was performed for this document.

**Decision to make**

Can a faithful implementation of the pinned SHRINCS verification algorithm run directly in restored Bitcoin Script at a useful cost, and can we bind that check to a complete spending policy?

The first deliverable is a reproducible verifier and cost report. Its result may be that a native verifier is materially better. A measured limit is a useful result; changing the scheme or granting an arbitrary resource allowance to obtain a passing demonstration would not answer the question.

The scope is verification. Fixture generation may use the upstream reference signer with public test seeds. Production signing, hardware state management, public-network funding, activation, and a complete wallet are later projects.

**1. Freeze the experiment**

These heads were checked directly through GitHub on the date above:

| Project | Pinned revision | Role |
|---|---|---|
| jmoik/bitcoin, gsr-full | `d2799052604eb138c5a79acf88514a0c8b07f4ef` | Experimental C++ execution target |
| SHRINCS/shrincs-bip | `4cd63a6497a0ba7c5e99699b94d33973546d9e37` | Algorithm and executable reference |
| BitVM/BitVM | `7d1ca3660cac08aab62e76f3aa4daec0d7403ecc` | Script generation, checked hints, and chunking reference |
| remix7531/libshrincs | `911c583cc9c4e5e54a91695a1c6d2a114968715c` | WOTS+C component and proof research; not full SHRINCS |

Record downloaded-file hashes, compiler versions, build flags, CPU, operating system, and generated script hashes with every result. Upstream changes should trigger an explicit comparison and a new result set.

Use three feature profiles:

| Profile | Allowed features | Question |
|---|---|---|
| Restoration baseline | BIPs 440/441 operations and limits | What does the published restoration surface buy us? |
| Full branch | Baseline plus the branch's extra function and byte operations | How much does the supplied experimental package improve code size and execution? |
| Transaction integration | Full branch plus its OP_TX implementation and a transaction-aware checker | Can the computed signature check authorize exactly the intended spend? |

The branch's opcode table includes OP_DEFINE, OP_INVOKE, OP_MULTI, OP_BYTEREV, OP_TX, CSFS, and TWEAKADD. These must not silently become assumptions of a BIP-441-only result. Function calls in this implementation reject active recursion and have an executed-body allowance; they do not introduce unrestricted computation. The older companion-draft PR is useful design history, but is not an exact specification of every feature in the pinned branch. [Pinned opcode table](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/script/script.h), [interpreter](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/script/interpreter.cpp), [draft history](https://github.com/rustyrussell/bips/pull/1).

**2. Specify exactly what the verifier accepts**

Start with a transaction-oriented profile: a 32-byte message, one fixed and documented laboratory context, and the exact 48-byte public-key representation. This is a restricted input profile, not a claim to implement every variable-length-message use of the upstream API.

The standalone interface accepts a public key, signature, message, and context and returns accept/reject. The transaction wrapper must commit the public key and context in the spending policy and derive the message from authenticated transaction data. Merely accepting all four values from the spender proves no authorization.

Both modes are required before calling the result a complete SHRINCS verifier: the stateful FXMSS route and the stateless fallback. The current encoding has a mode indicator, a randomizer, a variable-width leaf index on the stateful route, and precisely sized component data. Preserve cross-binding to the other component's root and context. Reaching a Merkle root alone is not the whole verification algorithm. [Pinned executable specification](https://github.com/SHRINCS/shrincs-bip/blob/4cd63a6497a0ba7c5e99699b94d33973546d9e37/impl/shrincs.py).

Write a short acceptance specification before coding: byte lengths, permitted indices, integer widths, endianness, domain-separation bytes, context framing, final stack behavior, and reject behavior. Keep a table identifying each requirement's upstream function and generated Script component.

The verifier is stateless. It can check a leaf index's encoding and path, but cannot establish that a device never signed a different message with that leaf. That remains a signer obligation. [State-management guidance](https://github.com/SHRINCS/shrincs-bip/blob/4cd63a6497a0ba7c5e99699b94d33973546d9e37/docs/state.md).

**3. Build the smallest useful toolchain**

Use Python for fixtures, the upstream oracle, report generation, and orchestration. Use a small Rust Script builder for named values, byte strings, unsigned values, stack effects, and profile-specific emission. Evaluate whether the BitVM/Fairgate builder can supply this structure, but adapt its numeric serialization explicitly for GSR. Do not import the bridge workspace or build a general compiler.

The C++ evaluator is the execution target, not a second implementation of the SHRINCS algorithm. Agreement between a reference verifier and the generated program tests translation into this VM; it does not prove either upstream specification or VM correct. A third component implementation provides useful evidence only where versions, parameters, and independence are established.

Every generated component should have named inputs, output widths, consumed values, preserved values, peak live values, source mapping, and a local cost measurement. The builder should detect missing values and inconsistent branch stack shapes before execution.

Proposed future layout:

```text
gsr-shrincs/
  versions.json
  spec/                  acceptance rules, transcript, feature profiles
  reference/             pinned-source adapters and provenance
  fixtures/              public test vectors and intermediate values
  generator/             typed values, stack tracking, Script components
  runner/                evaluator adapter and transaction-test adapter
  tests/                 component and end-to-end agreement checks
  reports/               generated JSON, CSV, and readable results
```

Keep this research package separate from the public reader's asset bundle. A browser visualization can later consume report JSON; it should not become the consensus test runner.

**4. Work in stages with explicit completion conditions**

| Stage | Work | Required result before continuing |
|---|---|---|
| A: execution preflight | Build the pinned fork; run its relevant existing tests; exercise the standalone request/response contract; record numeric and byte semantics | Reproducible executable and a feature manifest; no unexplained VM behavior |
| B: reference corpus | Generate public-seed fixtures for each mode and capture intermediate values | Fixture provenance plus exact agreement between specification and adapter |
| C: hash and byte components | Implement bounded slicing, concatenation, integer conversion, ADRS construction, tweaked hashes, and required message-hash functions | Byte-for-byte intermediate agreement, with boundary cases |
| D: WOTS+C and stateful verification | Validate the supplied grinding counter, derive digits, finish hash chains, compress endpoints, and authenticate through FXMSS | First valid stateful signature accepted; wrong message/key/context rejected; exact parser coverage grows to all supported depths |
| E: stateless verification | Implement FORS recovery, WOTS-TW, XMSS paths, the hypertree, and the top-level wrapper | Both SHRINCS modes supported under the declared message profile |
| F: cost and code size | Measure the baseline, then add full-branch optimizations one at a time | Auditable comparison with identical accepted-input rules |
| G: transaction binding | Use transaction-aware execution, define a transcript, integrate a regtest spend | Covered transaction changes invalidate the original signature; real budget is enforced |
| H: reviewable release | Reproduce results, package fixtures and reports, review acceptance equivalence and limitations | Another developer can rerun the result from pinned inputs |

The first vertical slice is A–D for one deliberately narrow stateful fixture. It is not completion of D's full parser coverage, E, or a Bitcoin spending system. Expand only after the small slice produces understandable costs.

For C, focus on byte handling before long signature paths. GSR arithmetic is unsigned and little-endian; the cryptographic serialization includes fixed-width big-endian fields. Numeric equality must not replace byte equality. A high bit or a trailing zero is data when handling a hash.

For D, the signer performs the WOTS+C grinding search; the verifier checks the supplied counter and the resulting digit constraint. Do not accidentally compile the signing search into verification. Start with one chain, then all chains, then one path level, then the bounded complete path.

For E, stream the calculation where possible: finish a chain or subtree, combine its result, and discard values that are no longer needed. Distinguish scratch memory from the original signature remaining on the stack. Repeatedly copying a whole signature to extract a small slice can dominate cost even when hashing is fast.

For F, compare repeated inline code against OP_DEFINE/OP_INVOKE helpers. Also compare a unified two-mode program against two committed mode-specific leaves. The latter changes script placement and control-block overhead, not the underlying SHRINCS signature; preserve both roots and the same context bindings. Count function-body storage and invocation costs. No recursion is needed.

**5. Test claims, not only examples**

Use tests whose expected result is defined by the scheme or the chosen transaction policy:

- Positive vectors across both modes, representative keys, contexts, and supported tree depths. Include synthetic boundary vectors where generating an enormous signer tree is impractical; label these separately from signing round trips.
- Alter the message, context, public seed, either root, path order, index, and mode independently. Check the expected rejection and compare intermediate values to locate disagreements.
- Check exact lengths, omitted bytes, appended data, index-width boundaries, and out-of-range encodings. Do not require every random byte change to be invalid: transformations can sometimes preserve the same decoded value. The reference acceptance rule decides.
- Exercise all bounded hash-chain step counts and tree-direction choices. Use property tests on the local components to supplement the curated corpus.
- For any auxiliary witness value, test that it is bound to the computation it claims to replace. A supplied digest is not trustworthy merely because it has the right length.
- Confirm the generated program reaches its intended final comparison and succeeds with clean-stack semantics. Reject unknown or success-reserved operations in the emitted program and its defined function bodies. An evaluator's success flag can otherwise be weaker than the intended signature check.
- Separate process errors, timeouts, malformed evaluator JSON, VM rejection, and cryptographic rejection. Never count a failed test process as a successfully rejected signature.
- Compare costs near the measured budget boundary in our local harness, including the final-result check. The pinned checker consumes the final stack value, so a successful response need not retain a visible `01` item.

For formal review, separate three questions: does the Script implement the accepted byte-level relation; is that relation a secure signature scheme under stated assumptions; and does the complete transaction enforce it? A component theorem does not answer all three. The `libshrincs` repository currently presents a WOTS+C proof-of-concept with explicit assumptions and compiler scope. Treat it as a component reference to reproduce and assess, not proof that our GSR program or full SHRINCS is verified. [Pinned libshrincs](https://github.com/remix7531/libshrincs/tree/911c583cc9c4e5e54a91695a1c6d2a114968715c).

**6. Report complete costs**

For each mode, implementation profile, and input class, record:

| Quantity | Why it matters |
|---|---|
| Signature, public-key, script, and control-block bytes separately | A short signature can hide a large verification program |
| Complete serialized transaction weight and virtual size | Includes framing, outputs, witness lengths, and all inputs |
| Varops consumed and allowance | Establishes whether the actual transaction pays for execution |
| Peak stack entries and bytes; maximum element size | Establishes memory-limit compliance |
| Function-body bytes and executed-body count/size | Exposes costs hidden by code reuse |
| SHA-256 calls/compressions, where measurable | Explains hashing cost without substituting it for VM cost |
| Runtime distribution and environment | Separates measured timing from specification accounting |
| Rejected-input costs and failure stage | Avoids reporting only the inexpensive happy path |
| Process startup and instrumentation overhead | Keeps CLI timing separate from interpreter timing |

Under BIP 440, the allowance is B = 10,000W, where W is transaction weight. Record C/B, where C is measured consumed varops. A successful run with a hand-selected huge B is only a functional experiment. [BIP 440](https://bips.dev/440/).

Report several-input transactions too: the budget is transaction-wide. Report an honest serialization first; any extra bytes added only to purchase more execution allowance must be shown separately. Compression of the program can reduce both witness weight and the allowance, so fewer bytes do not automatically mean more budget headroom.

Separate consensus limits, this branch's relay policy, and an application target. Do not use a block-sized experiment as evidence of a practical everyday payment. Choose practical targets after the first measured path. A parameterized fee table should use vbytes × sat/vbyte, not a predicted future fee market.

Pause for design review if correct verification requires an output policy we cannot specify, depends on an unverified host digest, exceeds the honest transaction budget, or only fits after dropping part of SHRINCS. Failure of the direct route is a reason to document alternatives, not silently replace it with an optimistic protocol.

**7. Bind the verified message to a transaction**

The standalone evaluator uses a base signature checker without transaction context. The later stage needs the fork's transaction-aware path; valid OP_TX data cannot be supplied by inventing equivalent witness bytes. [Evaluator source](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/bitcoin-util.cpp).

Begin with one input, a fixed policy, and an all-inputs/all-outputs commitment. Document a versioned laboratory transcript covering outpoints, spent-output amounts and scripts, input sequences, outputs, locktime, transaction version, current input, and the executing policy. Specify ordering and lengths. Either reproduce a precise established sighash or name the result as a distinct experimental transcript; do not call an arbitrary field concatenation BIP-341 SIGHASH_ALL.

Use OP_TX fields only where the pinned implementation actually supplies authenticated values. Its selection and serialization rules need their own agreement tests. Exclude the signature and witness-dependent quantities from the initial signed transcript to avoid circular signing dependencies. Initially reject unsupported annex and code-separator cases, or bind their semantics explicitly. Later relax restrictions one at a time. [OP_TX implementation](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/script/op_tx.cpp).

Then test output destination and amount changes, input substitutions, ordering, sequences, locktime, and cross-policy replay against the stated coverage. Fee changes are consequences of input/output amounts, not a separately serialized fee field. Fee sponsorship needs a deliberately more flexible policy; it should not appear accidentally through omitted fields.

A PQ leaf inside ordinary Taproot does not remove the quantum-vulnerable key path. The same concern applies to a NUMS internal key. Use a separately specified output rule that actually removes or secures that route before making an end-to-end PQ claim. A regtest-only key-path restriction must be labeled as an additional consensus assumption; it is not supplied by GSR automatically. P2MR is one proposal to evaluate. [BIP 360](https://bips.dev/360/), [BIP 347's explicit key-path discussion](https://bips.dev/347/).

**8. What BitVM and related projects teach us**

BitVM2's main trick is to move a large computation off-chain, commit to intermediate results, and permit a challenger to establish a wrong step on-chain during a dispute period. It carries protocol assumptions about setup, monitoring, time, and transaction inclusion. Direct signature verification instead executes its check as part of the spend. These are different acceptance models. [BitVM2 paper](https://bitvm.org/bitvm_bridge.pdf).

| Technique | Evidence examined | What to use here |
|---|---|---|
| Generate Script from a host language | Rust Script macro library | Reusable components and deterministic bytecode; adapt GSR encoding |
| Track moving stack values | Fairgate StackTracker | Named values and stack-effect checks instead of manual OP_PICK bookkeeping |
| Supply a cheap-to-check intermediate value | BitVM's verifier design notes and multiplication components | Consider only when every hint is checked and total cost improves |
| Partition a large verifier into chunks | BitVM chunk API and workflow | Use component boundaries for testing; avoid importing its dispute protocol into v1 |
| Commit to intermediate states using Winternitz | BitVM signature and chunk modules | Learn binding discipline; do not substitute its scheme for WOTS+C |
| Verify optimized implementations against a specification | Synthesis-aided lifting research | Explore equivalence checks after a small correct baseline exists |

Concrete checked-hint example: a witness may provide an inverse y for nonzero x modulo a prime p. The program checks the domain, range, and xy mod p = 1. The witness saves an expensive search; it does not get to assert the answer without a check. In a hash chain there is no corresponding general shortcut: supplying the alleged final hash does not establish the omitted chain steps. [BitVM verifier design notes](https://bitvm.org/snark.html).

The inspected BitVM Winternitz module uses 20-byte HASH160-based values. SHRINCS's addressed, truncated-SHA-256 WOTS+C construction is different. Its component formats, domain separation, and verification conditions must come from the pinned SHRINCS spec. [Pinned BitVM Winternitz source](https://github.com/BitVM/BitVM/blob/7d1ca3660cac08aab62e76f3aa4daec0d7403ecc/bitvm/src/signatures/winternitz.rs).

The Rust execution library is a development aid and explicitly disclaims consensus use. We should not use its success result as authority for a different VM. [Script builder](https://github.com/BitVM/rust-bitcoin-script), [StackTracker](https://github.com/FairgateLabs/rust-bitcoin-script-stack), [development interpreter](https://github.com/BitVM/rust-bitcoin-scriptexec).

The chunk API separates compile-time preparation from runtime assertions and disproval. That separation is useful: keep our compiler, fixture generator, executor, and result interpretation independent. The complete transaction graph and bridge machinery are not needed for our direct verifier. [Pinned chunk workflow](https://github.com/BitVM/BitVM/blob/7d1ca3660cac08aab62e76f3aa4daec0d7403ecc/docs/chunk_instructions.md), [API](https://github.com/BitVM/BitVM/blob/7d1ca3660cac08aab62e76f3aa4daec0d7403ecc/bitvm/src/chunk/api.rs).

Other comparisons worth keeping:

- **GreatRSI:** a close WOTS+ Script experiment, but its partial interpreter lacks varops accounting and its scheme differs. [Repository](https://github.com/jonasnick/GreatRSI).
- **Simplicity SHRINCS:** a useful verifier decomposition in another execution environment. Check revision and parameter compatibility before comparing outputs or costs. [Repository](https://github.com/BlockstreamResearch/shrincs-simplicity-verifier).
- **BitVMX:** a CPU-execution dispute approach. Useful for traces and debugging; unnecessary machinery for a fixed signature algorithm unless direct verification proves unsuitable. [Paper](https://arxiv.org/abs/2405.06842).
- **BitVM3:** uses garbled-circuit evaluation off-chain to enable a compact dispute. Interesting for very large computations; a distinct protocol, not a free compression pass for our verifier. [Paper](https://bitvm.org/bitvm3.pdf).
- **Synthesis-aided lifting:** explores lifting low-level Bitcoin programs into forms suitable for verification. Its applicability to GSR's changed arithmetic needs assessment. [Research paper](https://eprint.iacr.org/2024/1768).

A Groth16/BN254 wrapper does not preserve a post-quantum claim merely because the computation inside verifies SHRINCS. The complete construction would acquire quantum-vulnerable algebraic assumptions. A hash-based proof system could avoid that particular issue, but its own proof size, quantum analysis, verifier cost, and transaction policy would become new work.

**9. Other GSR applications: a dependency map**

These are engineering possibilities, not statements of activation or established practicality. Many conditions can already be expressed in restricted or expensive forms; restoration changes their cost and composability. “Core” below means the restored computation surface; a useful spending application may still need transaction binding.

| Application | Concrete example | Needed surface | Remaining problem |
|---|---|---|---|
| Custom Merkle proofs | Prove a key belongs to a committed allowlist | Core hash/byte operations | Bind the leaf to the intended authorization |
| Other hash-based signatures | Compare WOTS, XMSS, LMS, or a selected SLH-DSA profile | Core; measured cost | Correct parameters, parsing, and signer state where applicable |
| PQ multisignature policies | Require two of three independent SHRINCS signatures | Verifiers plus transaction binding | Cost scales with checks; this is not signature aggregation |
| Classical-plus-PQ policies | Require both signatures on the same statement | Both verifiers; safe output | Cover all alternate paths and avoid ambiguous OR semantics |
| Signed attestations | Allow an action after a named key signs a statement | Core verifier or CSFS companion | The signer is an oracle; Script cannot know whether the external fact is true |
| Fixed transaction templates | Commit to a payout's destinations and amounts | OP_TX or another sound binding construction | Flexibility, fees, change, and replay scope |
| Recovery vaults | Delayed hot withdrawal with a constrained cold recovery route | OP_TX, existing timelocks, correct state/output design | Recovery availability and complete path constraints |
| Fee-sponsored spends | Preserve protected value while another input pays fees | OP_TX; selected input/output constraints | Prove sponsor-controlled outputs cannot receive protected value |
| Spending budgets | Limit an authorized withdrawal and retain the remainder | OP_TX and a continuing covenant | Time epochs, state continuity, and termination |
| UTXO state machines | Update a committed counter or application state | Core proof checks plus OP_TX | Enforce the next output; prevent reset and duplicate-state routes |
| Batched payout trees | Recipients expand committed claims as needed | Templates/introspection and Merkle commitments | Exit fees, dust, coordination, and availability |
| Shared-UTXO protocols | Explore payment pools or channel factories | Covenants, signatures, timeouts | Complete exit and fee protocol; not automatic scalability |
| More efficient fraud-proof steps | Check a VM or arithmetic step with native byte/large-int operations | Core; surrounding dispute protocol | Trace commitments, challenges, inclusion, and economic assumptions |
| Direct proof verifiers | Study a STARK or another proof verifier in Script | Core; potentially additional primitives | Proof-system-specific soundness and measured cost; feasibility unknown |
| Selective-disclosure conditions | Prove an attribute without revealing all source data | Appropriate proof verifier and commitment | Privacy leakage, proof availability, and input provenance |
| Header and inclusion proofs | Verify supplied headers and transaction membership | Core arithmetic/hashes; possible covenant state | Correct chain anchor, difficulty, freshness, and reorg model |
| Bridge exit predicates | Check evidence for release of a locked output | Proof/header verification plus covenants | Foreign consensus, availability, monitoring, liquidity, and safe exits |
| Noninteractive offer conditions | Constrain what outputs an accepted offer creates | OP_TX and a precise exchange protocol | Asset model, front-running, settlement, and cancellation |
| Smaller repeated programs | Define a hash helper once and invoke it repeatedly | OP_DEFINE/OP_INVOKE companion | Invocation cost and executed-body limits still apply |
| Taproot policy construction | Compute tweaked keys for committed policies | TWEAKADD companion | Elliptic-curve operation; not itself PQ protection |

The supplied branch already has a particularly useful example: two vault designs, one based on a fixed template and another constraining an indexed output. Its test contrasts their behavior under fee sponsorship. This is the best next transaction exercise after the SHRINCS work because it makes introspection and policy tradeoffs concrete. The tests were inspected, not executed here. [Pinned vault example](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/test/functional/feature_tapscript_v2_op_tx_vaults.py).

For this map, use the actual OP_TX source as evidence of available transaction fields, BIP 441 for the restored computational primitives, and BIP 449 for the separate tweak operation. These primitives support the possibilities above; they do not establish a finished protocol or adequate performance. [OP_TX source](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/script/op_tx.cpp), [BIP 441](https://bips.dev/441/), [BIP 449](https://bips.dev/449/).

GSR does not supply live Internet access, an authenticated view of every external chain, automatic global mutable state, free repeated computation, or a quantum-safe output wrapper. A script checks a bounded computation over the data it can authenticate. A useful system must specify where that data comes from and what happens next.

**10. Recommended work order**

Start with the pinned runner, public vector corpus, and a single WOTS+C component. Finish one complete stateful verification path and publish its cost breakdown internally. Then add the stateless path, compare the two feature profiles, and build a transaction-aware regtest wrapper. Obtain external review of the byte-level equivalence and transaction policy before hardware integration.

The first review package should contain the exact source revisions, accepted input format, deterministic fixtures, readable generated Script, evaluator results, resource table, and an explicit list of unimplemented coverage. This is small enough to inspect and strong enough to decide whether the direct route deserves the next stage.
