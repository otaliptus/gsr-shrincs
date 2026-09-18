# Review follow-up

This revision addresses the five tooling/compiler findings against `6e1e807`,
adds regression coverage, and reduces the complete stateful spend size. Current
measurements are in [RESULTS.md](RESULTS.md); executable evidence is bound by
[audit.json](audit.json). The original plan and handoff remain historical records.

| Review finding | Change | Regression evidence |
|---|---|---|
| Stale profiling source cache | Synchronize every source file, delete stale files, preserve unchanged mtimes, verify the permitted overlay diff, and bind source/overlay identity to the built executable | A temporary source tree changes revision, gains/loses files, and has its cache deliberately altered; refresh restores it and verification rejects stale contents |
| Validation disappears with Python optimization | Explicit exceptions replace assertions in adapters, generators, oracle fixture checks, measurement scripts, regtest checks, export and audit gates | The full suite also runs under `-O`; malformed protocol/type/budget responses and stale audit evidence are rejected |
| Function name collisions | Compile each requested definition and compare its input contract and emitted body; reject conflicts and roll back failed registrations | Repeated equivalent lambdas succeed; changed bodies/contracts fail; registration remains usable after errors |
| Unchecked function arity | Validate argument count before emission, enforce one result, and check expression opcode arities | Too few/many arguments fail without changing the caller; zero-argument calls preserve outer stack values in all profiles |
| Input-cap test attribution | Keep append-input cases labeled as transcript-binding checks; add independently verified fresh signatures for cap+1 transactions, with allowed-boundary transactions for caps 1–4 | Each allowed boundary is mined; every over-limit transaction fails Script with valid signatures for its complete proposed transcript |

The audit also compares regenerated disassemblies and source maps, not just binary
hashes. Structured test IDs/outcomes replace the fixed `Ran 16 tests` string.
Python sources are consistently formatted so stack operations and checks can be
reviewed individually. The GitHub Actions workflow builds both executables from a
fresh checkout, regenerates public fixtures, runs all checks, and compares the
generated review artifacts.

## Stateful authentication optimization

The full-function profile uses nine acyclic authentication functions for blocks of
up to 1, 2, 4, …, 256 siblings. Each nonempty block splits its actual path between
lower-level functions; the second child executes only when that part exists. The
leaf combines exactly one sibling with the current node, using the same address
and parity rules. The parser still accepts precisely depths 1–255 and the original
index range. Only the path fragment needed by a child is passed into its frame,
which limits copying costs for deep signatures.

The baseline and byte-helper profiles retain the expanded implementation as
comparison controls. All 510 depth/index-extreme cases run through all three
profiles. The baseline and byte-helper binaries, and the full stateless binary,
remain byte-for-byte identical to the reviewed commit. Additional coverage preserves mixed-bit interior indices and valid
empty, binary and maximum-length contexts from the review. Eighteen synthetic
stateful transactions spanning depth/index boundaries, including depth 255, are
checked with their actual serialized weight-derived budgets; these are offline
Script checks, separately identified from the funded and mined regtest spends.

The size comparison in RESULTS uses the same signature length and transaction
shape as the original stateful-only spend. Newly signed transaction transcripts
can have different hash-chain digit distributions, so timing and varops differences
are not attributed solely to the optimization.

## Measured before/after

| Same stateful-only transaction shape | Reviewed commit | This revision |
|---|---:|---:|
| Script bytes | 26,328 | 4,476 |
| Signature bytes | 660 | 660 |
| Complete transaction vbytes | 6,879 | 1,416 |

The complete spend is **79.4% smaller** and fits its 56,630,000-varop allowance
without padding. Exact current execution costs are generated in RESULTS.md.
The stateless-only Script and its 5,099-vbyte transaction shape are unchanged.

## Remaining research scope

A native-verifier economic comparison would require a separately specified and
implemented consensus experiment. This revision does not supply that comparison,
a production signer/state manager, a formal proof, or an independent cryptographic
audit. The ordinary Taproot key-path limitation remains unchanged. These limits
are separate from the repaired laboratory tooling and measured Script verifier.
