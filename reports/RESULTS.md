# Measured results

These results use the pinned fork and exact SHRINCS parameters. All listed spends were accepted and mined by the unmodified local regtest node. No budget padding was added.

| Program / signature mode | Script bytes | Signature bytes | Weight | vbytes | Varops used / allowed | Budget used |
|---|---:|---:|---:|---:|---:|---:|
| full-unified | 39607 | 660 | 40,794 | 10,199 | 22,340,525 / 407,940,000 | 5.5% |
| full-stateful | 26328 | 660 | 27,515 | 6,879 | 22,275,014 / 275,150,000 | 8.1% |
| full-stateless | 14091 | 5777 | 20,395 | 5,099 | 124,235,969 / 203,950,000 | 60.9% |
| baseline-unified | 228549 | 660 | 229,738 | 57,435 | 34,665,030 / 2,297,380,000 | 1.5% |
| baseline-stateful | 95350 | 660 | 96,539 | 24,135 | 24,150,486 / 965,390,000 | 2.5% |
| baseline-stateless | 133452 | 5777 | 139,758 | 34,940 | 132,702,270 / 1,397,580,000 | 9.5% |
| full-unified-sl | 39607 | 5777 | 45,911 | 11,478 | 118,696,349 / 459,110,000 | 25.9% |
| baseline-unified-sl | 228549 | 5777 | 234,855 | 58,714 | 138,801,108 / 2,348,550,000 | 5.9% |
| full-2-input-mixed | 79214 | 6437 | 86,227 | 21,557 | 143,869,442 / 862,270,000 | 16.7% |
| full-4-input-mixed | 158428 | 12874 | 172,288 | 43,072 | 295,315,341 / 1,722,880,000 | 17.1% |

The public key is 48 bytes, embedded in each policy. Single-input rows use a 65-byte control block (two committed leaves); the mixed-input rows use a 33-byte control block per input. The latter use a separate all-input/all-output policy with an explicit four-input cap. Mode-specific leaves are paired with their opposite mode in one tree; combined leaves have an extra mode-specific sibling for cross-policy replay tests.

Program size and execution allowance are distinct: compressed programs reduce witness weight and therefore the budget they purchase. The full mode-specific stateless leaf has substantially less budget headroom than the larger combined leaf, while performing the same signature computation.

| Program | Peak stack bytes | Stack + functions bytes | Maximum item | Invoked body bytes | Median interpreter ms, counters off |
|---|---:|---:|---:|---:|---:|
| full-unified | 23,550 | 42,895 | 22,809 | 42,105 | 0.830 |
| full-stateful | 23,550 | 29,656 | 22,809 | 42,105 | 0.817 |
| full-stateless | 17,876 | 31,666 | 7,411 | 121,184 | 3.266 |
| baseline-unified | 3,624 | 3,624 | 660 | 0 | 2.500 |
| baseline-stateful | 3,624 | 3,624 | 660 | 0 | 1.257 |
| baseline-stateless | 17,875 | 17,875 | 5,777 | 0 | 3.606 |
| full-unified-sl | 28,667 | 57,147 | 22,809 | 121,184 | 3.170 |
| baseline-unified-sl | 17,876 | 17,876 | 5,777 | 0 | 4.275 |
| full-2-input-mixed | 28,667 | 57,147 | 22,809 | 121,184 | 4.105 |
| full-4-input-mixed | 28,667 | 57,146 | 22,809 | 121,184 | 8.248 |

All 124 recorded transaction mutations also fail the offline transaction-aware Script checker, including annex and oversized two-input cases that relay policy rejects first. This distinguishes cryptographic/policy rejection from process failure or insufficient budget.

Detailed accepted and rejected costs, function calls, inclusive component costs, SHA256 counts/compressions, stack entries, timing distributions, script/input hashes, and byte-helper-only comparisons are in `costs.json`. Early parser/message failures and late authentication-path failures are recorded separately. `components.json` contains 384 local component contract measurements; `boundary-costs.json.gz` covers all 1,530 stateful boundary executions. `environment.json` records source/binary hashes, platform and compiler flags. `regtest-details.json.gz` holds full transactions, transcripts, and authenticated spent-output records from the test.

Consensus limits: 32,768 entries including definitions, 4,000,000 bytes per item, 8,000,000 stack/altstack/function bytes, and 4,000,000 cumulative invoked body bytes. The measured programs fit. This does not establish everyday-payment economics or production readiness. Fee at any chosen rate is vbytes × sat/vbyte.

Ordinary Taproot retains its quantum-vulnerable key path. These are direct SHRINCS leaf-verification measurements, not an end-to-end post-quantum Bitcoin output. No independent review or formal proof is claimed.

## Measurement boundaries

- Timing excludes process startup/JSON parsing from interpreter_ns.
- Unobserved timings use the same overlay binary with counters disabled; remaining conditional overhead is not subtracted.
- CLI overhead includes launch, initialization, JSON IO and teardown; it is not pure process startup.
- Function-body costs are inclusive of nested calls and must not be summed.
- Executed-function-body bytes is the maximum per input evaluation, matching the per-evaluation limit; invocation counts and varops sum across inputs.
- Peak memory is logical VM bytes, not allocator capacity or process RSS.
- Rejected-input peaks include completed opcode states; transient values before failing operations can be larger.
