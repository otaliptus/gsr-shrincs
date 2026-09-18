# Committed evidence repair

The review identified a real coverage mismatch at `fb2c234`.
The repository contained 34 test methods. Each committed test-result file recorded only 26.
Direct coverage validation failed for native, profiled, and optimized results.

CI regenerated those files before the audit. It did not compare them with the committed versions.
Thus, a successful CI run did not establish consistency of the committed test records.
The CI run for `fb2c234` subsequently passed, but it had this limitation.

## Changes

The complete check pipeline regenerated the reports, environment manifest, and all three test-provenance files.
The workflow now compares the three deterministic test-result files after the check pipeline.
This check detects changes to the recorded test inventory and outcomes. It does not replace the full evidence audit.

The evaluator, comparison runner, measurement script, and audit now share an exact budget-error check.
Tests confirm that unrelated messages containing `budget` do not receive the budget classification.

The procedure documents shared-clone dependence on the source repositories.
The OP_MULTI note explains why an existing, simple substitute weakens the case for the general dispatcher.
It also identifies the bounded unroll's dependence on fixed execution charges.

The function note records the repeated success-opcode scan and the opportunity to validate immutable definitions once.
The scan has no separate charge. Invocation already charges for copying the body, so the scan is not wholly outside resource accounting.

The parsing note adds a per-instruction hypothesis for a controlled experiment.
Opcode decoding is already in the isolated benchmark. Interpreter checks are not.
Ordinary skipped instructions check execution state; conditional instructions update the condition stack.
Cross-machine parser and interpreter timings do not establish CPU-time shares.

## Validation

The complete local check pipeline passed on 18 September 2026.

| Check | Result |
|---|---|
| Native Python suite | 34 tests passed |
| Profiled Python suite | 34 tests passed |
| Optimized Python suite | 34 tests passed |
| Selected upstream C++ and functional suites | Passed |
| Component measurements | 384 accepted |
| Boundary measurements | 1,530 native/profile matches |
| Fresh valid transactions | 14 mined |
| Fresh negative transactions | 128 expected rejections |
| Evidence audit, normal and optimized Python | Passed |
| Generated program artifacts | Unchanged |

The new CI check detected the 26-to-34 correction before it was committed.
The archived fork self-check retains its original bytes and hashes.
The baseline tag preserves the earlier machine's reports.

The full audit compares local executable hashes. A new machine must build and regenerate evidence before using that audit.
The README now distinguishes full regeneration from checking unchanged local evidence.
