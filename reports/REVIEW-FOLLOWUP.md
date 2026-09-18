# Review changes

Commit `891d77a` addresses five findings from the review of `6e1e807`.
It also reduces the size of the complete stateful spend.
[RESULTS.md](RESULTS.md) contains the measurements.
[audit.json](audit.json) records hashes of the supporting evidence.

## Profiling source cache

The build script synchronizes every source file and deletes obsolete files.
It preserves the modification times of unchanged files.
It checks that the profiling changes match the permitted changes.
A build manifest connects the executable to the source and profiling manifests.

The regression test changes a temporary source revision and adds and removes files.
It also changes cached content directly.
A cache refresh restores the expected content.
The manifest check rejects stale content.

## Checks under optimized Python

Explicit exceptions replace assertions in the validation code.
The checks remain active when Python runs with `-O`.
This change covers adapters, generators, reference checks, measurement scripts,
regtest checks, export, and audit.

The complete test suite also runs with `-O`.
It rejects malformed protocol responses, incorrect types, invalid budgets,
and stale audit evidence.

## Function definitions

The compiler checks each requested function definition.
It compares the input contract and emitted body with any existing definition
that has the same name.
It rejects conflicts and removes incomplete registrations after a failure.

Repeated equivalent lambda definitions succeed.
Definitions with different bodies or contracts fail.
Tests also confirm that registration remains usable after an error.

## Function arguments and results

The compiler checks argument counts before it emits a call.
Each function must return exactly one result.
The compiler also checks the argument counts of expression opcodes.

Calls with too few or too many arguments fail without changing the caller.
Calls with no arguments preserve the outer stack values in all profiles.

## Input-count limits

The new tests separately check transcript binding and input-count limits.
The existing append-input cases check transcript binding.
The new over-limit transactions have fresh signatures for every input.
An independent check confirms that each signature is valid for the complete proposed transcript.

Each limit from one through four inputs has a valid boundary transaction.
The node accepts and mines these transactions.
Each corresponding transaction with one extra input fails the Script limit check.
Thus, an invalid signature does not explain these four rejections.

## Other review checks

The audit compares regenerated disassemblies, source maps, and binaries.
Structured test records replace the fixed `Ran 16 tests` text check.
The records identify every test and its result.
Consistent Python formatting makes individual stack operations and checks easier to inspect.

The GitHub Actions workflow builds both executables from a fresh checkout.
It regenerates public test inputs, runs all checks, and compares generated files.
The local results provide execution evidence independently of hosted CI availability.

## Smaller stateful authentication code

The full profile uses nine shared authentication functions.
Their maximum block lengths are 1, 2, 4, 8, 16, 32, 64, 128, and 256 siblings.
Their call graph has no cycle.
Each nonempty block divides its actual path between lower-level functions.
The second child executes only when its path portion exists.

The leaf operation combines one sibling with the current node.
It uses the original address and parity rules.
The parser still accepts depths 1 through 255 and the original index range.
Each child receives only the path portion that it needs.
This reduces copying for deep signatures.

The baseline and byte-helper profiles keep their expanded implementations for comparison.
All 510 depth and extreme-index cases run through all three profiles.
The baseline and byte-helper binaries remain identical to `6e1e807`.
The full stateless binary also remains identical.

Additional tests cover interior indices with mixed bits.
They also cover empty, binary, and maximum-length contexts.
Eighteen synthetic transactions cover stateful depth and index boundaries, including depth 255.
These offline Script checks use budgets calculated from the actual serialized transaction weight.
They are separate from the funded and mined regtest spends.

## Size comparison

The comparison uses the same signature length and transaction shape.
New transaction transcripts can produce different hash-chain digits.
Thus, the changes in timing and varops cannot be attributed only to the smaller program.

| Same stateful transaction shape | Reviewed commit, `6e1e807` | Revised implementation, `891d77a` |
|---|---:|---:|
| Script bytes | 26,328 | 4,476 |
| Signature bytes | 660 | 660 |
| Complete transaction vbytes | 6,879 | 1,416 |

The complete spend is **79.4% smaller**.
It fits its allowance of 56,630,000 varops without padding.
[RESULTS.md](RESULTS.md) gives the exact execution costs.
The stateless Script and its transaction shape of 5,099 vbytes remain unchanged.

## Remaining research

A cost comparison with a native verifier needs a separate consensus specification
and implementation.
This repository does not supply that comparison.
It also supplies no production signer, state manager, formal proof, or independent cryptographic audit.
Ordinary Taproot retains its key path, which remains vulnerable to quantum attacks.
