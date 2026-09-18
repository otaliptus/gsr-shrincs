# GSR SHRINCS verifier — cross-machine handoff

## Current follow-up: compare fork revisions

The user approved the five-step follow-up after the implementation and review at `937e058`.
Preserve the measured package, build a fork-comparison harness, investigate parsing costs, and write function and OP_MULTI design notes.
Check Simplicity compatibility before starting a full port.

Read `spec/FORK-COMPARISON.md` for the new driver. It has separate replay and recompile modes.
Read `spec/FUNCTION-DESIGN.md`, `spec/OP-MULTI-BENEFIT.md`, `reports/PARSING-ANALYSIS.md`, and `spec/SIMPLICITY-COMPATIBILITY.md` for the follow-up findings.

The original package is tagged `baseline-2026-09-18` at `937e05811e45b1b61f505201ac8f06c05abf2253`.
Verify the tag and CI result remotely. A tag alone does not establish a successful clean build.
Run `35338011287` completed successfully at that exact commit. `reports/baseline-ci.json` records the result.

No function opcode or consensus cost has changed in this follow-up.
The parsing counters establish skipped work, not its causal share of CPU time.
The isolated parser benchmark also matches all fourteen observed parsing schedules. It does not measure the entire interpreter.
The OP_TX total selector wins the tested all-output sum construction on program bytes and varops.
The pinned Simplicity implementation has different parameters and a different top-level key relation.

New comparison outputs live under `build/comparisons/` unless explicitly exported.
Read their status and configuration before treating them as evidence. Partial journals and development runs are not completed experiments.

The completed self-check is archived in `reports/fork-self-check/`.
Both modes passed 2,632 cases. Each checkout also mined fourteen spends and recorded 128 expected node rejections.
Read the archive README for fresh-input cost differences and the subsequent negative-case size-metadata correction.
The implementation at `490242c` passed clean-checkout CI; `reports/follow-up-ci.json` records that run.

Next, select a committed candidate fork revision. Run replay and recompile against that revision.
For function changes, implement the calling convention and compiler adaptation before comparing costs.
The self-check establishes harness consistency, not compatibility with an untested fork change.
Establish parsing's causal share of interpreter time before proposing a new charge.
Defer OP_MULTI on the measured all-output sum case. Require a separate construction for any additional target.
Do not begin a headline Simplicity size comparison until the full verification relation and compiler provenance match.

The subsequent review found stale committed coverage records: 26 recorded methods versus 34 discovered methods.
The complete local pipeline regenerated all reports and provenance. Both normal and optimized evidence audits passed.
CI now checks the three deterministic test-result files against Git.
Read `reports/EVIDENCE-REPAIR.md` for the repair, validation, and design-note qualifications.
After source or build changes, run the complete pipeline before committing evidence. An export alone does not update test provenance.

The next review identified stale follow-up inputs and binaries after main-report regeneration.
The pipeline now regenerates parsing counts, parser timings, and OP_MULTI measurements, then audits their exact dependencies.
The counter and parser benchmark use separate builds. Both binaries appear in the environment manifest.
CI checks committed follow-up provenance before regeneration with `python3 scripts/audit_followups.py --portable`.
This portable check does not require local builds. The full audit still checks the recorded local executables.
The expanded suite has 37 methods. Read `reports/FOLLOWUP-PROVENANCE.md` for validation and timing qualifications.

The original handoff follows. Its pre-implementation status is historical; the later implementation reports supersede it.

> **Implementation update — 18 September 2026:** Milestones M0–M7 are complete.
> [README.md](README.md) gives the build procedure.
> [reports/RESULTS.md](reports/RESULTS.md) gives the measurements.
> [reports/AUDIT.md](reports/AUDIT.md) maps each milestone to its evidence.
> Both upstream submodules remain at their original revisions.
> The text below records the project before implementation.
> Its incomplete-work lists describe that earlier state.
> [report.md](report.md) contains the current Simplicity discussion.

Snapshot: 18 September 2026. Read this file before continuing. This records project context and engineering decisions; it is not a statement that the milestones have been completed.

## 1. User objective and immediate request

The user wants us to implement the full GSR SHRINCS verifier plan, sensibly and autonomously, in a private GitHub repository. Their authorization was:

> go ahead and do it all in a sensible way without asking me, let's go (work in a private github repo)

The latest steering was:

> actually before that dump all context and what to do and milestones into an .md file inside the repo so that I can take over from an another machine and continue working there

This handoff fulfills that immediate request. The implementation objective remains M0–M7 below. Do not redefine completion as a WOTS+C demo, a single stateful fixture, or a green test suite that omits transaction integration.

Use the checked-out files, actual process status, test output, and GitHub state as authoritative. Earlier plans are intentions, not execution evidence. Do not mark the overall project complete until every milestone has the required evidence. If direct verification does not fit the real resource limits, report that measured result honestly; do not silently change the signature scheme, grant an unlimited budget, or substitute an optimistic dispute protocol.

## 2. Project context

The conversation began with an educational guide to classical signatures, quantum attacks, post-quantum signatures, and Bitcoin integration. The user wanted first-principles explanations, more illustrations, precise LaTeX, clearly explained variables, and concise technical prose inspired by makingsoftware.com. Hardware-wallet implications, GSR versus a native SHRINCS operation, Falcon, and proposal status were also discussed.

That guide is a separate project:

- Private GitHub repository: https://github.com/otaliptus/after-quantum
- Published guide: https://after-quantum.pages.dev/
- Original local directory: `/Users/talip/Desktop/pivotal/pq-signatures`
- Its research plan: `docs/gsr-shrincs-plan.md`, copied into this repository as `PLAN.md`.

Do not make the guide's browser bundle the cryptographic runner. This repository is the independent reproducible experiment. A later guide update could visualize exported reports.

The user supplied the experimental GSR fork at https://github.com/jmoik/bitcoin/tree/gsr-full and said its latest commit added a direct v2 evaluator. They asked for a sensible plan for a SHRINCS verifier, comparison with BitVM-style Script engineering, and other GSR applications. `PLAN.md` preserves those research findings and links.

The initial social-media link was https://x.com/starknet/status/2100250531549663604?s=46. This handoff does not treat that post as technical evidence for SHRINCS or GSR.

## 3. Exact state at handoff

Completed and checked locally:

- Initialized this repository on branch `main`.
- Copied the detailed research plan into `PLAN.md`.
- Downloaded the two upstream source repositories and registered them as submodules.
- Confirmed their exact commits, listed below.
- Corrected `.gitmodules` to use public upstream HTTPS URLs so another machine can fetch them.
- Inspected the evaluator, SHRINCS reference functions, build options, and relevant upstream test filenames.
- Configured a Release build with CMake and Ninja successfully. Configuration finished with exit code 0.
- Added this handoff, a README, and build/cache exclusions. The handoff is published through the private `otaliptus/gsr-shrincs` repository; inspect `origin` and the checked-out revision when resuming.

Not done:

- No C++ compilation has been started.
- No upstream unit or functional tests have been executed for this project.
- No evaluator adapter, Script generator, fixture corpus, or SHRINCS Script has been written.
- No verification or performance results exist.
- No transaction integration or hardware-wallet implementation exists.
- No formal proof or independent external review has been performed.

There is no continuing build process to resume. The CMake configuration process completed. Do not attempt to reuse a tool session ID on another machine.

Empty directories such as `reports`, `tests`, and `scripts` may exist on the original machine, but Git does not preserve empty directories. Create them when adding real files.

The original working directory was `/Users/talip/Desktop/pivotal/gsr-shrincs`. Paths under that location and `/private/tmp/after-quantum-plan2` are not portable dependencies. Any earlier scratch research files must be recreated from the linked upstream sources if needed.

## 4. Pinned sources and provenance

| Source | Exact revision | Role |
|---|---|---|
| `vendor/bitcoin` — jmoik/bitcoin | `d2799052604eb138c5a79acf88514a0c8b07f4ef` | Experimental GSR C++ execution target, from `gsr-full` |
| `vendor/shrincs-spec` — SHRINCS/shrincs-bip | `4cd63a6497a0ba7c5e99699b94d33973546d9e37` | SHRINCS executable specification and draft documents |
| BitVM/BitVM | `7d1ca3660cac08aab62e76f3aa4daec0d7403ecc` | Previously inspected comparison source; not vendored |
| remix7531/libshrincs | `911c583cc9c4e5e54a91695a1c6d2a114968715c` | Previously inspected WOTS+C component/proof research; not vendored |

Do not track moving branch heads in result claims. Record source commits, generated script hashes, compiler/build flags, platform, and test input hashes. Any upstream upgrade needs a deliberate comparison and a new result set.

The SHRINCS repository explicitly describes the scheme and code as experimental. Its Python signer is an executable specification: naive, non-constant-time, without production key protection or signer-state management.

The native SHRINCS leaf proposal in `leaf-version-0xC2.mediawiki` is a different proposal from the GSR fork. A shared experimental leaf-version number is not evidence that they compose or are activated.

## 5. Continue on another machine

Authenticate to GitHub as an account with access to the private repository. Then:

```sh
git clone --recurse-submodules https://github.com/otaliptus/gsr-shrincs.git
cd gsr-shrincs
git status --short
git submodule status
git -C vendor/bitcoin rev-parse HEAD
git -C vendor/shrincs-spec rev-parse HEAD
```

For an existing clone:

```sh
git pull --ff-only
git submodule sync --recursive
git submodule update --init --recursive
```

Read any applicable `AGENTS.md` or repository contribution instructions on the new machine. No applicable `AGENTS.md` was found in this project or its vendor trees during the initial inspection. `vendor/bitcoin/doc/AI_POLICY.md` exists; read it before any upstream contribution. We have not modified the upstream code.

Read the pinned platform build instructions, rather than assuming the original computer's packages:

- macOS: `vendor/bitcoin/doc/build-osx.md`
- Linux: `vendor/bitcoin/doc/build-unix.md`

The originating machine had CMake 4.2.1, Ninja, Boost headers, Python, and AppleClang 17.0.0.17000603. CMake selected `/usr/bin/c++` and Python 3.13.3 at `/opt/local/bin/python3.13`; an interactive `python3` elsewhere on PATH was version 3.14.6. Do not assume these are the same interpreter. Rust/Cargo were available but have not been used. IPC was disabled to avoid requiring Cap'n Proto; wallet and GUI support were disabled for this verification experiment.

The following configuration was successfully executed; build and test commands below it are next steps, not previously successful results:

```sh
cmake -S vendor/bitcoin -B build/bitcoin -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_IPC=OFF \
  -DENABLE_WALLET=OFF \
  -DBUILD_GUI=OFF \
  -DWITH_CCACHE=OFF

cmake --build build/bitcoin --target bitcoin-util -j 4
```

The configured output directory is `build/bitcoin/bin`. After compilation, exercise the evaluator with a trivial script:

```sh
printf '%s\n' '{"protocol":1,"sigversion":"tapscript_v2","script":"51","stack":[],"varops_budget":100000}' \
  | build/bitcoin/bin/bitcoin-util evalscript
```

Then build the node, CLI, and tests; list test suites before selecting them:

```sh
cmake --build build/bitcoin --target bitcoind bitcoin-cli bitcoin-tx test_bitcoin -j 4
build/bitcoin/bin/test_bitcoin --list_content
```

Relevant upstream test sources are listed in section 8. Use the pinned functional test runner's documented options and generated build configuration. Keep node execution on an isolated local regtest; no public-network coins are needed.

`build/` is intentionally not committed. Configure from scratch on the new machine. Do not copy an absolute-path CMake cache from the original computer.

## 6. Scope and acceptance contract

Research question: can the pinned SHRINCS verifier run directly in GSR at useful cost, and can its result enforce a fully specified spending policy?

Initial input profile:

- Exactly 32 message bytes.
- One fixed, documented laboratory context; suggested value `after-quantum/gsr-lab/v1`, not yet implemented or frozen.
- Exactly 48 public-key bytes.
- Both stateful and stateless modes before declaring the verifier complete for this profile.
- Exact signature encodings from the pinned specification.

The standalone verifier may accept the message, key, context, and signature as inputs for testing. The transaction wrapper must instead commit the authorized key/context and derive the message from authenticated transaction data. A spender selecting all four values proves no spending authority.

Write an acceptance document with exact lengths, permitted indices, widths, byte order, domain separation, rejection behavior, and final stack rules. Map each rule to an upstream function and a generated component.

The verifier cannot establish that the signer never reused a one-time leaf. That is a signer-state obligation. Production signing, seed handling, hardware counters, backups, recovery, activation, and a complete wallet remain outside this verification project. Public test seeds are sufficient for fixture generation and must be labeled as such.

## 7. Milestones and required evidence

### M0 — Reproducible execution environment

Build the pinned GSR fork; run relevant upstream tests; implement the standalone evaluator adapter; create the source/feature manifest and acceptance profile.

Evidence: a reproducible executable, recorded environment, runner contract tests, explicit handling of VM rejection versus budget exhaustion versus process failure. Configuration alone does not complete M0.

### M1 — Exact byte, integer, address, and hash components

Implement length validation, bounded slicing, concatenation, unsigned/fixed-width conversions, address construction, tweaked hashes, and required message hashing.

Evidence: byte-for-byte intermediate agreement with the pinned Python functions. Cover zero bytes, high bits, leading/trailing zeros, index boundaries, byte order, truncation, and exact length rejection. Preserve bytes as bytes; numeric equality is not a substitute.

### M2 — WOTS+C verification

Build one hash step, one chain, all chains, counter validation, digest-digit decomposition, the constant-sum check, and endpoint compression.

Evidence: recovered public keys match the reference; all allowed chain step counts are exercised; invalid counters/encodings and mismatched statements reject as specified. Produce the first script-size and execution-cost breakdown.

The signer searches for a counter. The verifier only checks the supplied counter. Do not compile the grinding search into the verifier.

### M3 — Complete stateful SHRINCS verification

Integrate the top-level stateful parser, randomizer, context/message/root bindings, WOTS+C, FXMSS authentication path, and final root equality.

First get one narrow fixture working. Then cover the full supported encoding and path-depth range. Clearly separate genuine signing round trips from synthetic component/boundary vectors where full tree generation is impractical.

Evidence: valid reference-generated signatures accepted; incorrect messages, keys, contexts, indices, and paths rejected as required; exact parser boundaries covered; complete resource report for tested classes. One short-path fixture does not finish this milestone.

### M4 — Stateless fallback and unified verification

Implement FORS, WOTS-TW, XMSS, the hypertree, stateless message binding, and top-level mode selection. Preserve binding to the other root in both modes.

Evidence: both modes match the reference under the declared input profile, including rejection and boundary cases. Process intermediate nodes incrementally where feasible. A WOTS+C-only implementation is not full SHRINCS.

### M5 — Complete cost accounting and optimization

Measure from M1 onward. At this milestone compare the published restoration baseline against full-branch helper operations with identical accepted-input rules.

Report signature, public key, program, control block, full transaction weight/vsize, varops consumed/allowed, stack entries/bytes, maximum item, function storage/execution allowances, and runtime distribution. Separate CLI startup from interpreter timing. Include rejected-input costs and several-input budget sharing.

Compare inline repetition with `OP_DEFINE`/`OP_INVOKE`, and one combined program with separately committed mode-specific leaves. Preserve the same public-key and context bindings in either placement.

Evidence: reproducible reports and tests showing unchanged acceptance. Apply the honest transaction's actual allowance, not a huge chosen standalone budget. Report padding used only to buy budget separately. Smaller Script can also reduce the allowance, so bytes and budget headroom are distinct measurements.

### M6 — Transaction-bound regtest spend

Commit the key/context in the policy. Use authenticated `OP_TX` data in a transaction-aware checker. Define an unambiguous versioned transcript, initially for one input with explicit input/output coverage.

Include outpoints, spent-output amounts/scripts, sequences, output amounts/scripts, version, locktime, current input, and executing policy as appropriate to the defined signing rule. Specify field ordering and lengths. Either reproduce an established sighash exactly or name the result a distinct laboratory transcript.

Exclude self-referential signature/witness-dependent fields from the initial transcript. Explicitly reject unsupported annex/code-separator cases or bind their semantics. Never accept an unverified host-supplied digest as the transaction message.

Evidence: a real local spend succeeds; changes to each covered field and cross-policy replay fail; actual transaction budget enforced. A pure standalone evaluator test cannot finish M6.

A PQ leaf in ordinary Taproot does not remove the quantum-vulnerable key path, including when an internal key is a NUMS point. Document the output wrapper. If a regtest-only key-path restriction or a P2MR-style rule is required, identify it as an additional consensus assumption, not a consequence of GSR.

### M7 — Reproducible review package

Package source pins, accepted-input rules, generated Script and source maps, fixture provenance, runnable tests, transaction examples, reports, and limitations. Audit requirements against actual evidence.

Evidence: another developer can rebuild and reproduce the results. Do not claim an independent review, consensus readiness, or a full cryptographic proof merely because the package is reproducible.

## 8. GSR implementation facts to preserve

Read these authoritative sources in `vendor/bitcoin`:

- `src/bitcoin-util.cpp`: evaluator interface.
- `src/script/script.h`: opcode assignments.
- `src/script/interpreter.cpp`: execution and final-result semantics.
- `src/script/op_tx.cpp` and `.h`: transaction selectors and serialization.
- `src/script/varops.h`: resource accounting definitions; follow its call sites in the interpreter.
- `src/test/tapscript_v2_tests.cpp`, `tapscript_v2_json_tests.cpp`, `varops_tests.cpp`, `op_tx_tests.cpp`.
- `src/test/data/tapscript_v2_restored_ops.json`, `tapscript_v2_varops.json`, `op_tx.json`.
- `test/functional/feature_tapscript_v2.py`, `feature_tapscript_v2_taproot.py`, `feature_tapscript_v2_op_tx_vaults.py`, `tool_utils.py`.

Evaluator request, read as one JSON object from stdin:

```json
{
  "protocol": 1,
  "sigversion": "tapscript_v2",
  "script": "51",
  "stack": [],
  "varops_budget": 100000
}
```

Response fields include `protocol`, `context: "standalone"`, `sigversion`, `success`, `error`, `stack-after`, and `varops-budget-remaining`.

Important details:

- VM rejection can still return process exit code zero. Read `success` and `error`.
- Process errors, timeouts, and malformed response JSON are harness failures, not valid negative signature tests.
- The final-result checker consumes the truthy result. A successful `stack-after` may be empty.
- Execution uses `BaseSignatureChecker{}`. It does not supply authenticated transaction data for `OP_TX`.
- Restored arithmetic uses unsigned little-endian values; do not reuse legacy signed Script-number encoding blindly.
- The scheme uses fixed-width big-endian fields too. Test conversions explicitly.
- Success-reserved opcodes and certain unknown selector versions can trigger immediate success. Use an opcode/selector allowlist and inspect generated function bodies too; a raw success flag does not by itself prove the intended comparison ran.
- Function invocation rejects active recursion and has body/execution constraints. This is bounded verification, not arbitrary looping.

Maintain three profiles:

1. Published restoration baseline: BIPs 440/441 operations and limits.
2. Full supplied branch: extra byte/function helpers, identified individually.
3. Transaction integration: full branch plus authenticated `OP_TX` execution.

The opcode table contains, among other operations, CAT `0x7e`, SUBSTR `0x7f`, LEFT `0x80`, RIGHT `0x81`, LSHIFT `0x98`, RSHIFT `0x99`, DEFINE `0xbb`, INVOKE `0xbc`, TX `0xbd`, TWEAKADD `0xbe`, MULTI `0xbf`, CHECKSIGFROMSTACK `0xcc`, and BYTEREV `0xcf`. Consult the actual interpreter for semantics. Presence in this fork does not mean presence in the published restoration baseline.

The plan records BIP 440's transaction-wide allowance as `10,000 × transaction weight`. Recheck the pinned implementation and proposal when writing measured reports. Similarly verify actual stack/item/body limits rather than copying limits from older Script versions.

## 9. SHRINCS implementation facts to preserve

Authoritative files in `vendor/shrincs-spec`:

- `SHRINCS.md`
- `impl/shrincs.py`
- `impl/test.py`
- `impl/meta.py`
- `docs/state.md`
- `leaf-version-0xC2.mediawiki`

At the pinned version:

- Public key: 48 bytes, `pk_seed[16] || sl_root[16] || sf_root[16]`.
- Stateful signatures: 548 through 4619 bytes.
- Stateless signatures: 5777 bytes.
- Mode byte 255 selects stateless; 0 through 254 represent the stateful leaf height.
- Stateful depth is `255 - leaf_height`.
- Stateful leaf-index width is `ceil(min(depth, 64) / 8)` bytes, big-endian, with the specified range check.
- WOTS+C: 32 chains, 4-bit digits, digit sum 240; a 2-byte supplied counter plus 512 bytes of chain values.
- WOTS-TW: 4-bit chains with its specified checksum.
- Stateless hypertree: 5 layers, XMSS height 9.
- FORS: 10 trees, height 13.
- ADRS is 22 bytes. Fields and type switches must match the exact function being implemented.

Useful hash relations, with all concatenations byte-exact:

```text
F / H / T: SHA256(pk_seed || zero[48] || ADRS || input)[0:16]
H_grind:   SHA256(pk_seed || zero[48] || ADRS[0:10] || digest[32]
                  || zero[4] || counter_BE[2])[0:16]
H_msg_sf:  SHA256(R || pk_seed
                  || SHA256(R || pk_seed || sf_root || ADRS[0:9] || M)
                  || ADRS[0:9])
H_msg_sl:  SHA256(R || pk_seed
                  || SHA256(R || pk_seed || sl_root || M) || zero[4])
```

Stateful top-level framing includes `0x00 || len(ctx)[1] || ctx || sl_root || message`. Its randomizer and stateful location also feed digest computation. Stateless verification is invoked with `sf_root || message` and the specified context framing. Read the top-level wrapper rather than assuming that a valid Merkle path alone verifies the signature.

`wots_c_map_digest` sets the grinding address type and checks the digit sum. Chain reconstruction uses the chain hash type and clears reserved fields as specified; endpoint compression uses the public-key type. Domain bytes are not optional metadata.

The reference mutates ADRS bytearrays in place. Fixture adapters should copy where required and record intermediate addresses, so accidental host-side mutation cannot make a bad translation appear correct.

The stateless parameters are not automatically interchangeable with standardized SLH-DSA. Do not describe a parameter-modified verifier as the pinned scheme. Any stated security category, signature budget, or proof status should be attributed to the specific proposal, not inferred from similar constructions.

## 10. Implementation architecture and test discipline

The proposed architecture is Python for reference adapters, public fixtures, orchestration, and reports; a small Rust Script builder for generation with named stack values, explicit widths, and checked stack effects. This is a design choice, not existing code. Reassess before introducing unnecessary dependencies; record any change in the design document.

Suggested layout as files are added:

```text
versions.json
spec/             input contract, feature profiles, transaction transcript
reference/        pinned Python adapter and fixture provenance
fixtures/         public vectors and intermediate values
generator/        typed values, stack tracking, generated components
runner/           standalone and transaction-aware execution adapters
tests/            components, parser boundaries, full signatures, transactions
reports/          measured JSON/CSV and readable reports
vendor/           pinned upstream submodules
```

Every component needs named inputs/outputs, widths, consumed/preserved values, stack effect, source mapping, and a local cost measurement. Detect inconsistent branch stack shapes and missing named values during generation.

Testing priorities:

- Compare intermediate bytes, not only final acceptance.
- Exercise all bounded chain lengths and both tree directions.
- Cover exact lengths, omitted/appended bytes, integer-width transitions, and index bounds.
- Change the message, context, public seed, either root, path order, index, and mode independently.
- Use the reference relation for expected results; not every arbitrary byte mutation necessarily changes the decoded mathematical value.
- Any witness-provided helper value must be checked. Never treat a supplied hash-chain endpoint or digest as authenticated without computing or proving the omitted relation.
- Make final clean-stack behavior and budget-boundary checks explicit.
- Track the original signature's retained bytes separately from scratch memory. Repeatedly copying a large signature for small slices can dominate VM cost.
- Agreement with the Python reference tests translation, not the cryptographic security of the specification or correctness of the VM itself.

Avoid a broad compiler framework or the full BitVM bridge workspace. Build the smallest toolchain that makes this fixed verifier readable and testable.

## 11. Related Script research and what to borrow

The detailed comparisons and links are in `PLAN.md`, sections 8 and 9.

- BitVM demonstrates deterministic Script generation, stack tracking, checked auxiliary values, and component boundaries. Its optimistic dispute protocol is not equivalent to direct signature verification on every spend.
- BitVM's inspected Winternitz module uses 20-byte HASH160 values; it is not a drop-in replacement for addressed, truncated-SHA256 WOTS+C.
- `BitVM/rust-bitcoin-script` and `FairgateLabs/rust-bitcoin-script-stack` are candidate tooling references. Verify their arithmetic and serialization assumptions against GSR before reuse.
- `BitVM/rust-bitcoin-scriptexec` explicitly is not a consensus authority. The pinned C++ target remains the execution reference here.
- `remix7531/libshrincs` is WOTS+C component/proof research at the inspected pin, not a proof of the complete SHRINCS scheme or this Script translation. Check exact parameter compatibility before using vectors.
- `jonasnick/GreatRSI` is related WOTS+ Script research, with different scheme/measurement limitations.
- `BlockstreamResearch/shrincs-simplicity-verifier` may inform decomposition, but parameters and encoding need comparison. Simplicity costs do not directly transfer to GSR.
- Wrapping the computation in a Groth16/BN254 proof introduces quantum-vulnerable algebraic assumptions. It does not preserve a PQ claim merely because the circuit verifies a PQ signature.

Other GSR possibilities identified include Merkle proofs, other hash-based signatures, classical-plus-PQ policies, PQ multisignature policies, signed attestations, transaction templates, vaults, fee sponsorship, continuing spending limits, UTXO state machines, payout trees, shared-UTXO protocols, fraud-proof steps, and direct proof verifiers. These are a research map, not deliverables to substitute for M0–M7. Many require transaction introspection and a complete protocol beyond restored arithmetic/hash operations. GSR supplies neither Internet access nor automatic external-chain truth or globally mutable state.

## 12. Next actions in order

1. Clone with submodules, inspect current changes, and confirm the pins. Read this file and `PLAN.md`.
2. Configure and compile the evaluator. Run its smoke test and relevant upstream tests. Record results rather than assuming the successful configuration implies successful compilation.
3. Write the input contract, feature manifest, source-version metadata, and evaluator adapter. Test failure classification and final-stack semantics.
4. Generate a small deterministic reference corpus with public seeds and intermediate values. Keep this distinct from production signing.
5. Implement and test M1, then one WOTS+C chain, then M2. Measure costs at each step.
6. Complete a real stateful verification path; expand to full M3 coverage. Report exact omissions until filled.
7. Implement the stateless route, optimize with acceptance-equivalence checks, integrate actual regtest transactions, and finish the reproducible release audit.

Commit concrete, reviewable increments to the private repository. Keep milestone status evidence-based. Do not ask the user to repeat authorization for ordinary implementation, tests, commits, or private pushes within this scope. Do not send messages to upstream maintainers or publish a public repository without an explicit request.

For a new coding-agent session, the user can start with:

> Read HANDOFF.md and PLAN.md. Inspect the current repo and its pinned submodules. Continue the full M0–M7 GSR SHRINCS verifier project in this private repository, starting from the first uncompleted gate. Keep source-derived claims separate from measured results. Work autonomously within the scope recorded in the handoff.
