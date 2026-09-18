# Follow-up evidence provenance

The earlier follow-up reports referred to an older transaction corpus and separate measurement executables.
Regenerating the main reports did not regenerate those experiments.
The previous audit included their file hashes but did not validate their dependencies.

The complete check pipeline now regenerates all three experiments after recording fresh transactions and costs.

| Evidence | Audited inputs | Audited executables |
|---|---|---|
| `parsing-counts.json` | Current transaction corpus and cost report | Current profiling reference and separate counting build |
| `parser-benchmark.json` | Current corpus, costs, and parsing counts | Separate parser benchmark build |
| `multi-comparison.json` | Reconstructed deterministic output-sum transaction corpus | Current profiling build |

Each report records the measurement code hashes and environment.
The audit checks exact input hashes and links each executable to `environment.json`.
The local audit also checks the observation source trees, manifests, executable bytes, and build configurations.

The parsing audit reconstructs every schedule from the current program and function-call counts.
It checks parsing counts against those schedules and observed costs against the main cost report.
The OP_MULTI audit checks the generated programs, corpus hash, row inventory, accepted cases, and recorded semantic rejections.
Both timing audits check sample counts and reported medians.

## Separate builds

The counting executable remains under `build/parsing-probe`.
The isolated parser benchmark now uses `build/parser-benchmark`.
Previously, the benchmark replaced the counting executable in the same build directory.
The separate directories preserve both executable hashes for local verification.

## Check before regeneration

Run the portable check without the original executables:

```sh
python3 scripts/audit_followups.py --portable
```

This checks committed inputs, code, recorded binary links, source manifests, schedules, and result consistency.
It does not verify local executables or reproduce timing measurements.
CI runs it before regeneration, so regeneration cannot conceal stale committed follow-up inputs.

The complete local audit still requires the recorded binaries and build directories.
Run `./scripts/check.sh` to build the follow-up tools and regenerate the entire package on another machine.

## Timing and input interpretation

The results page now displays its timing environment above the tables.
The historical parsing tables link to immutable records at `490242c` and the baseline corpus.
Current measurements remain in the audited JSON files.

During this repair, total parsed bytes and instruction counts remained unchanged across all fourteen spends.
Skipped-work counts changed in six rows with fresh stateless signatures.
Thus, skipped-work counters also need exact corpus binding. They are not entirely properties of the program shape.

Same-machine parser and interpreter measurements permit a better comparison than cross-machine timings.
They still use different loops and allocation behavior. Their ratio does not establish a causal CPU-time share.

## Validation for this repair

The complete pipeline passed on 18 September 2026:

- All 37 tests passed in native, profiled, and optimized modes.
- The upstream suites, fourteen mined spends, and 128 expected rejections passed.
- All 384 component and 1,530 boundary measurements completed.
- All fourteen parsing observations matched reference acceptance and varops.
- All fourteen parser schedules matched observed bytes and instruction counts.
- All eighteen OP_MULTI comparison rows completed, including their negative cases.
- Both normal and optimized full evidence audits passed.
- Generated verifier artifacts remained unchanged.

An isolated copy without a build directory passed the portable check.
Changing its copied cost file caused that check to fail before regeneration.
The full check correctly failed without the local executable.
Unit tests also cover changed inputs, binaries, code, schedules, sample summaries, and invalid negative outcomes.
