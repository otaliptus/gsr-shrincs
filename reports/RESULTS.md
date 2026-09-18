# Measured results

Timing environment: **Linux-6.12.105+deb13-amd64-x86_64-with-glibc2.41**, x86_64, Python 3.13.5.
These timings apply to this machine and method. Do not infer performance regressions from timings across different environments.
The [environment manifest](environment.json) records build and executable details. The baseline tag retains the earlier Linux measurements.

These measurements use the pinned fork and SHRINCS parameters. The unmodified local regtest node accepted and mined every listed spend. The transactions contain no budget padding.

| Program / signature mode | Script bytes | Signature bytes | Weight | vbytes | Varops used / allowed | Budget used |
|---|---:|---:|---:|---:|---:|---:|
| full-unified | 17755 | 660 | 18,942 | 4,736 | 20,643,003 / 189,420,000 | 10.9% |
| full-stateful | 4476 | 660 | 5,663 | 1,416 | 20,577,516 / 56,630,000 | 36.3% |
| full-stateless | 14091 | 5777 | 20,395 | 5,099 | 123,292,103 / 203,950,000 | 60.5% |
| baseline-unified | 228549 | 660 | 229,738 | 57,435 | 34,665,030 / 2,297,380,000 | 1.5% |
| baseline-stateful | 95350 | 660 | 96,539 | 24,135 | 24,150,510 / 965,390,000 | 2.5% |
| baseline-stateless | 133452 | 5777 | 139,758 | 34,940 | 136,472,394 / 1,397,580,000 | 9.8% |
| full-unified-sl | 17755 | 5777 | 24,059 | 6,015 | 121,020,257 / 240,590,000 | 50.3% |
| baseline-unified-sl | 228549 | 5777 | 234,855 | 58,714 | 136,444,980 / 2,348,550,000 | 5.8% |
| full-2-input-mixed | 35510 | 6437 | 42,523 | 10,631 | 143,554,578 / 425,230,000 | 33.8% |
| full-4-input-mixed | 71020 | 12874 | 84,880 | 21,220 | 290,913,896 / 848,800,000 | 34.3% |
| full-cap1-boundary | 4476 | 660 | 5,507 | 1,377 | 20,575,768 / 55,070,000 | 37.4% |
| full-cap2-boundary | 8952 | 1320 | 10,848 | 2,712 | 41,160,880 / 108,480,000 | 37.9% |
| full-cap3-boundary | 13428 | 1980 | 16,189 | 4,048 | 61,755,204 / 161,890,000 | 38.1% |
| full-cap4-boundary | 17904 | 2640 | 21,530 | 5,383 | 82,358,908 / 215,300,000 | 38.3% |

The stateful spend uses 1,416 vbytes. The same transaction shape used 6,879 vbytes at commit `6e1e807`. This is a reduction of 79.4%. The Script uses shared authentication functions with a fixed execution bound and no call cycle. Each child receives only its required path portion.

The inline profiles retain their expanded authentication code for comparison. The signature remains 660 bytes. The transaction and control-block shapes remain unchanged. Newly signed transactions can have different hash-chain digits, which affect varops comparisons.

Each policy contains a 48-byte public key. Original single-input rows use a 65-byte control block for two committed leaves. Mixed-input and cap-boundary rows use a 33-byte control block per input.

Mixed-input policies permit a maximum of four inputs. Cap-boundary policies test each limit from one through four. A mode-specific tree pairs its leaf with the opposite mode. A combined leaf has an additional mode-specific sibling for replay tests under another policy.

A smaller program reduces witness weight. In this fork, lower weight also reduces the execution allowance. The full stateless leaf therefore has less unused allowance than the larger combined leaf. Both perform the same signature computation.

| Program | Peak stack bytes | Stack + functions bytes | Maximum item | Invoked body bytes | Median interpreter ms, counters off |
|---|---:|---:|---:|---:|---:|
| full-unified | 8,152 | 21,210 | 7,411 | 21,039 | 0.679 |
| full-stateful | 3,824 | 7,971 | 2,672 | 21,039 | 0.653 |
| full-stateless | 17,875 | 31,665 | 7,411 | 121,184 | 3.248 |
| baseline-unified | 3,624 | 3,624 | 660 | 0 | 2.394 |
| baseline-stateful | 3,624 | 3,624 | 660 | 0 | 1.234 |
| baseline-stateless | 17,875 | 17,875 | 5,777 | 0 | 3.564 |
| full-unified-sl | 17,875 | 35,261 | 7,411 | 121,184 | 3.224 |
| baseline-unified-sl | 17,876 | 17,876 | 5,777 | 0 | 4.377 |
| full-2-input-mixed | 17,876 | 35,262 | 7,411 | 121,184 | 3.926 |
| full-4-input-mixed | 17,876 | 35,262 | 7,411 | 121,184 | 7.823 |
| full-cap1-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 0.657 |
| full-cap2-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 1.216 |
| full-cap3-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 1.817 |
| full-cap4-boundary | 3,824 | 7,971 | 2,672 | 21,039 | 2.372 |

All 128 recorded negative transactions also fail the offline Script checker with transaction data. These include annex and large two-input cases that relay policy rejects before Script executes.

Four over-limit cases have fresh, independently valid signatures for every input. The input-count limits cause these rejections. The node accepts and mines each corresponding transaction at its permitted limit. The older append-input cases check transcript binding. The checks distinguish cryptographic and policy rejection from process failure and insufficient budget.

`costs.json` records accepted and rejected execution costs, function calls, hash operations, stack entries, timing distributions, and script and input hashes. It also compares the byte-helper profile. Function costs include nested calls. The records distinguish early parser and message failures from later authentication-path failures.

`components.json` contains 384 component measurements. `boundary-costs.json.gz` covers all 1,530 stateful boundary executions. `environment.json` records source and executable hashes, platform details, and compiler flags. `regtest-details.json.gz` contains complete transactions, transcripts, and authenticated spent-output records.

The measured programs fit the pinned consensus limits. These limits permit 32,768 entries, including definitions, and 4,000,000 bytes per item. Total stack, altstack, and function storage cannot exceed 8,000,000 bytes. Cumulative invoked function-body bytes cannot exceed 4,000,000 per evaluation.

These results do not establish low payment costs or production readiness. The fee at a selected rate is `vbytes × sat/vbyte`.

Ordinary Taproot retains its key path, which remains vulnerable to quantum attacks. These measurements concern SHRINCS leaf verification. They do not establish complete post-quantum protection for the output. The implementation has no independent cryptographic audit or formal proof.

## Measurement boundaries

- Interpreter timing excludes process startup and JSON parsing.
- Timing with counters disabled uses the profiling executable. Conditional measurement hooks remain active. Their overhead is not subtracted.
- CLI overhead includes launch, initialization, JSON input and output, and teardown. It does not measure process startup alone.
- Each function cost includes its nested calls. Adding these costs would count some work more than once.
- Executed function-body bytes give the maximum for one input evaluation. The limit applies per evaluation. Invocation counts and varops sum across inputs.
- Peak memory measures logical VM bytes. It excludes allocator capacity and process resident memory.
- Peaks for rejected inputs include completed opcode states. Temporary values before a failing operation can be larger.
