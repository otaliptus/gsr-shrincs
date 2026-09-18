# Measured results

These results use the pinned fork and exact SHRINCS parameters. All listed spends were accepted and mined by the unmodified local regtest node. No budget padding was added.

| Program / signature mode | Script bytes | Signature bytes | Weight | vbytes | Varops used / allowed | Budget used |
|---|---:|---:|---:|---:|---:|---:|
| full-unified | 17755 | 660 | 18,942 | 4,736 | 20,643,015 / 189,420,000 | 10.9% |
| full-stateful | 4476 | 660 | 5,663 | 1,416 | 20,577,516 / 56,630,000 | 36.3% |
| full-stateless | 14091 | 5777 | 20,395 | 5,099 | 122,351,759 / 203,950,000 | 60.0% |
| baseline-unified | 228549 | 660 | 229,738 | 57,435 | 34,665,042 / 2,297,380,000 | 1.5% |
| baseline-stateful | 95350 | 660 | 96,539 | 24,135 | 24,150,510 / 965,390,000 | 2.5% |
| baseline-stateless | 133452 | 5777 | 139,758 | 34,940 | 132,702,858 / 1,397,580,000 | 9.5% |
| full-unified-sl | 17755 | 5777 | 24,059 | 6,015 | 121,491,584 / 240,590,000 | 50.5% |
| baseline-unified-sl | 228549 | 5777 | 234,855 | 58,714 | 135,972,516 / 2,348,550,000 | 5.8% |
| full-2-input-mixed | 35510 | 6437 | 42,523 | 10,631 | 140,256,195 / 425,230,000 | 33.0% |
| full-4-input-mixed | 71020 | 12874 | 84,880 | 21,220 | 283,846,613 / 848,800,000 | 33.4% |
| full-cap1-boundary | 4476 | 660 | 5,507 | 1,377 | 20,575,792 / 55,070,000 | 37.4% |
| full-cap2-boundary | 8952 | 1320 | 10,848 | 2,712 | 41,160,856 / 108,480,000 | 37.9% |
| full-cap3-boundary | 13428 | 1980 | 16,189 | 4,048 | 61,755,216 / 161,890,000 | 38.1% |
| full-cap4-boundary | 17904 | 2640 | 21,530 | 5,383 | 82,358,917 / 215,300,000 | 38.3% |

The stateful-only spend is now 1,416 vbytes, compared with 6,879 vbytes at the reviewed commit 6e1e807 (79.4% smaller). Its Script uses a bounded acyclic tree of shared authentication functions; each child receives only its portion of the path. The inline profiles retain their expanded authentication logic as differential controls. The 660-byte stateful signature and transaction/control-block shape are unchanged. Varops comparisons use newly signed transactions, so their hash-chain digit distributions can differ.

The public key is 48 bytes, embedded in each policy. Original single-input rows use a 65-byte control block (two committed leaves); the mixed-input and cap-boundary rows use a 33-byte control block per input. Mixed-input policies have a four-input cap; cap-boundary policies exercise each limit from one through four. Mode-specific leaves are paired with their opposite mode in one tree; combined leaves have an extra mode-specific sibling for cross-policy replay tests.

Program size and execution allowance are distinct: compressed programs reduce witness weight and therefore the budget they purchase. The full mode-specific stateless leaf has substantially less budget headroom than the larger combined leaf, while performing the same signature computation.

| Program | Peak stack bytes | Stack + functions bytes | Maximum item | Invoked body bytes | Median interpreter ms, counters off |
|---|---:|---:|---:|---:|---:|
| full-unified | 8,152 | 21,210 | 7,411 | 21,039 | 0.694 |
| full-stateful | 3,824 | 7,971 | 2,672 | 21,039 | 0.668 |
| full-stateless | 17,875 | 31,665 | 7,411 | 121,184 | 3.223 |
| baseline-unified | 3,624 | 3,624 | 660 | 0 | 2.539 |
| baseline-stateful | 3,624 | 3,624 | 660 | 0 | 1.280 |
| baseline-stateless | 17,876 | 17,876 | 5,777 | 0 | 3.619 |
| full-unified-sl | 17,875 | 35,261 | 7,411 | 121,184 | 3.417 |
| baseline-unified-sl | 17,876 | 17,876 | 5,777 | 0 | 4.408 |
| full-2-input-mixed | 17,876 | 35,262 | 7,411 | 121,184 | 3.835 |
| full-4-input-mixed | 17,876 | 35,262 | 7,411 | 121,184 | 7.760 |
| full-cap1-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 0.657 |
| full-cap2-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 1.195 |
| full-cap3-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 1.798 |
| full-cap4-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 2.360 |

All 128 recorded negative transactions also fail the offline transaction-aware Script checker, including annex and oversized two-input cases that relay policy rejects first. Four cap+1 cases carry fresh, independently valid signatures for every input; the one-through-four-input caps are the rejecting condition. Each allowed cap boundary is accepted and mined. The older append-input cases remain transcript-binding tests. This distinguishes cryptographic/policy rejection from process failure or insufficient budget.

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
