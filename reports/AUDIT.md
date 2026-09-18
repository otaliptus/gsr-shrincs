# Milestone completion audit

Scope: a direct, proper implementation of both modes of the pinned SHRINCS verifier
under the 32-byte-message laboratory profile, including authenticated transaction
binding and a reproducible review package. No milestone is replaced by a component
example, a different scheme, a host-trusted digest, or an unlimited transaction budget.

| Gate | Implementation and authoritative evidence | Result |
|---|---|---|
| M0 — reproducible execution | Both clean source pins in `versions.json`; `scripts/build.sh`; actual evaluator/node/test binaries; `reports/environment.json`; 76 selected upstream C++ tests; four upstream functional suites; strict runner failure/timeout/JSON/budget contracts | Complete |
| M1 — bytes, integers, addresses, hashes | `generator/script.py`, hash expressions in `generator/verifier.py`; byte-for-byte tests for widths 1/2/4/8/17, zeros/high bits/0x81, fixed-width endian reversal, truncation, address domains, all tweaked hash input sizes, H_msg_sf/H_msg_sl and H_grind counters 0..65535 boundaries | Complete |
| M2 — WOTS+C | Supplied-counter check, nibble decomposition, sum=240, all 32 chains and endpoint compression in Script; every suffix length 0..15 checked against reference; recovered keys with valid counters 0,1,255,256,32768,65535; invalid encodings and statements; inclusive function costs in `costs.json` | Complete |
| M3 — full stateful range | Genuine balanced and unbalanced keygen/sign/verify fixtures; every depth 1..255 at index zero and maximum under three code-generation profiles; index-width/range failures, exact lengths, root/message/key/context/path mutations; resource metrics for all 1,530 boundary executions | Complete |
| M4 — stateless and unified | Full FORS, WOTS-TW, XMSS and five-layer hypertree; genuine stateless signatures under two public test keys; FORS all-zero/all-one digest and unused-bit agreement; WOTS-TW checksum extremes; both mode-specific leaves and unified dispatch; all cross-root/context checks preserved | Complete |
| M5 — costs and optimization | Baseline inline, byte-helper inline, and function profiles accept the same corpus; deterministic bytecode/source maps; exact varops, stack/item/function ceilings, SHA256 counts/compressions, per-function inclusive costs, rejected-input costs, timing distributions and CLI overhead; one-mode vs combined placement; two/four-input shared budgets; no padding | Complete |
| M6 — authenticated spend | `spec/TRANSCRIPT.md`, OP_TX policy and `tests/regtest.py`; ten actual accepted/mined spends under the unmodified fork; 124 covered-field/replay/annex/count/ordering failures; all also checked through transaction-aware C++ with recorded UTXOs; true weight×10,000 allowance | Complete |
| M7 — review package | `README.md` rebuild commands; public seeds/provenance; source pins and hashes; binaries/disassembly/maps under `generated/`; raw logs and compressed transaction/resource evidence; `scripts/check.sh` and `scripts/audit.py`; explicit limitations below | Complete |

## Evidence interpretation

- `tests.log` and `tests-profiled.log` run the same 16 test methods; their loops cover
  far more than 16 individual executions. Each checks the full supported stateful
  range under baseline, byte-helper and full-function generation. Process failures
  raise harness errors instead of counting as rejected signatures.
- `fixtures/vectors.json` contains 40 deterministic public fixtures: ten genuine
  reference keygen/sign/verify cases (two stateless), plus 30 explicitly synthetic
  boundary cases. The exhaustive 510 stateful cases are generated deterministically
  in tests and resource measurement, not falsely labeled as full-tree signing.
- `components.json` records 384 local component contract costs, including the
  expected-output comparison and cleanup, so these are not mislabeled as pure
  intrinsic hash-operation costs.
- `boundary-costs.json.gz` contains all 1,530 stateful boundary measurements with
  bytecode/input hashes and native/instrumented varops agreement. `costs.json`
  contains the representative timing/component and full-transaction measurements.
- `regtest-details.json.gz` contains exact serialized transactions, transcripts,
  public keys and spent-output records. `regtest.json` is its readable summary.
  The test sends accepted transactions and asserts their inclusion in newly mined
  local blocks. It obtains spent outputs from its own funded UTXOs.
- Outpoint txid and index are changed separately. Amounts, destinations, version,
  locktime, sequences, counts, order, current input, annex and executing policy are
  covered. Wrong spent amount/script tests sign the wrong proposed transcript and
  demonstrate rejection against the actual node-authenticated UTXO data.
- A paired mode-specific tree commits separate stateful/stateless leaves. Combined
  leaves include an additional mode-specific sibling to test cross-policy replay
  with the same key/context and valid relation. Control-block bytes are counted.
- Annexes and oversized baseline two-input mutations can reject at relay policy
  before Script runs. Their separate transaction-aware replay confirms an actual
  Script failure as well. These are not reported as node cryptographic failures.
- All source pins remain unchanged. The measurement overlay lives in a separate
  disposable source/build tree and never changes the regtest node or its limits.
  Timing with counters disabled still includes conditional instrumentation hooks;
  process/protocol overhead is measured separately. No native-only timing is inferred.

## Explicit limits

This completes the **laboratory verification plan**, not production deployment or
cryptographic certification. The reference is experimental. There is no independent
external review, formal proof, production seed protection, stateful signer management,
hardware wallet, activation, public-network spending, or full wallet implementation.
Those were excluded by the handoff and remain excluded.

Ordinary Taproot retains its key path, even with a NUMS internal key. The output used
here is therefore not end-to-end post-quantum safe. Removing/securing that path needs
a separate specified output/consensus rule; it is not an automatic consequence of GSR.
Consensus resource compliance does not establish sensible everyday fees or broad
relay support. Costs are for the exact pinned experimental VM and the recorded machine.
