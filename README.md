# SHRINCS verification in GSR Bitcoin Script

This repository implements both complete SHRINCS verification modes in an
experimental GSR fork. It is a reproducible laboratory experiment.
The package includes generated Script, reference test inputs, execution
measurements, and actual spends on a local regtest chain.

The [main report](report.md) explains Simplicity, jets, program size, and the
possible contribution of this experiment. The following documents describe the
implementation:

- [Measured results](reports/RESULTS.md)
- [Accepted inputs](spec/ACCEPTANCE.md)
- [Transaction transcript](spec/TRANSCRIPT.md)
- [Execution profiles](spec/FEATURES.md)
- [Milestone audit](reports/AUDIT.md)
- [Review changes](reports/REVIEW-FOLLOWUP.md)
- [Committed evidence repair](reports/EVIDENCE-REPAIR.md)
- [Follow-up provenance and portable checks](reports/FOLLOWUP-PROVENANCE.md)

A [plain-language summary page](https://otaliptus.github.io/gsr-shrincs/) gives the question,
the results, and the limits without technical detail.

## Things you can check

Read these files in this order. Each one answers a question.

1. [report.md](report.md): why verifier size matters, and what this experiment adds to the Script and Simplicity discussion.
2. [reports/RESULTS.md](reports/RESULTS.md): the measured sizes, budgets, and memory for every spend.
3. [spec/ACCEPTANCE.md](spec/ACCEPTANCE.md): exactly which inputs the verifier accepts, with the reference function for each rule.
4. [spec/TRANSCRIPT.md](spec/TRANSCRIPT.md): what a transaction signature commits to, and why it is not BIP-341 signing.
5. [spec/FEATURES.md](spec/FEATURES.md): the three compiler profiles and the fork's resource limits.
6. [generator/verifier.py](generator/verifier.py): the verifier. [generator/script.py](generator/script.py) is the compiler under it, and [generator/transaction.py](generator/transaction.py) is the spending policy.
7. [reports/AUDIT.md](reports/AUDIT.md): each milestone and the evidence that closed it.
8. [reports/REVIEW-FOLLOWUP.md](reports/REVIEW-FOLLOWUP.md): how shared functions reduced the stateful program from 26 kB to 4.5 kB.
9. The fork-change notes: [spec/OP-MULTI-BENEFIT.md](spec/OP-MULTI-BENEFIT.md), [spec/FUNCTION-DESIGN.md](spec/FUNCTION-DESIGN.md), [reports/PARSING-ANALYSIS.md](reports/PARSING-ANALYSIS.md), [spec/SIMPLICITY-COMPATIBILITY.md](spec/SIMPLICITY-COMPATIBILITY.md), and [spec/FORK-COMPARISON.md](spec/FORK-COMPARISON.md).
10. [tests/test_verifier.py](tests/test_verifier.py) and [tests/regtest.py](tests/regtest.py): what was tested against the reference and on the regtest node.

To check a claim rather than read about it, run `./scripts/check.sh` after the build. The [GitHub Actions workflow](.github/workflows/verify.yml) does the same from a clean checkout.

## Things you do not need to read

- `generated/`: compiler output. The audit compares these files; people do not read them.
- `reports/*.json`, `reports/*.json.gz`, and `reports/*.log`: raw evidence and captured logs. The Markdown reports summarize them.
- `reports/fork-self-check/`: an archived harness self-test. Its README is enough.
- `reports/EVIDENCE-REPAIR.md`, `reports/baseline-ci.json`, and `reports/follow-up-ci.json`: housekeeping records.
- [PLAN.md](PLAN.md) and [HANDOFF.md](HANDOFF.md): the plan before implementation and a handoff for a coding agent. Historical.
- `runner/` and `scripts/`: plumbing between Python and the C++ evaluator.
- `vendor/`: the two upstream projects, unmodified.
- `docs/`: the source of the summary page.

## Fork-change experiments

The measured package is frozen at tag `baseline-2026-09-18`, commit `937e058`.
The tag preserves the original reports. Top-level reports are regenerated with the current checkout's complete check procedure.
Separate experiments retain their own evidence.
Its [clean-checkout CI run](https://github.com/otaliptus/gsr-shrincs/actions/runs/35338011287) passed at that exact commit.

- [Replay and recompile comparison procedure](spec/FORK-COMPARISON.md)
- [Completed comparison self-check and raw evidence](reports/fork-self-check/README.md)
- [Proposed function design](spec/FUNCTION-DESIGN.md)
- [Measured OP_MULTI comparison](spec/OP-MULTI-BENEFIT.md)
- [Parsed-work counts and timing limits](reports/PARSING-ANALYSIS.md)
- [Pinned Simplicity compatibility check](spec/SIMPLICITY-COMPATIBILITY.md)

The comparison driver accepts another fork commit and an optional compiler commit.
It builds separate checkouts. It does not update the pinned submodules or overwrite historical reports.
No consensus costs or function opcodes have changed in this follow-up.
Both comparison modes passed 2,632 cases against independent builds of the baseline.
The implementation at `490242c` also passed [clean-checkout CI](https://github.com/otaliptus/gsr-shrincs/actions/runs/35340926491).
That run predates the committed-test-coverage check described in the evidence repair.

[PLAN.md](PLAN.md) and [HANDOFF.md](HANDOFF.md) preserve the original requirements
and project state. [WRITING.md](WRITING.md) gives the current writing instructions.

## Build and test

The build requires the following tools:

- Python 3.11 or later
- A C++20 compiler that the pinned fork supports
- CMake 3.22 or later
- Ninja
- Boost headers, version 1.74 or later
- Git
- Localhost networking for regtest

The fork's [Linux build instructions](vendor/bitcoin/doc/build-unix.md) list the
platform dependencies. [environment.json](reports/environment.json) records the
measured platform, compiler, build flags, and source hashes.

1. Clone the repository and its submodules.

   ```sh
   git clone --recurse-submodules https://github.com/otaliptus/gsr-shrincs.git
   ```

2. Open the project directory.

   ```sh
   cd gsr-shrincs
   ```

3. Build the unmodified fork.

   ```sh
   ./scripts/build.sh
   ```

4. Build the separate executable for measurements.

   ```sh
   python3 scripts/profile_build.py
   ```

5. If new copies of the public test inputs are necessary, regenerate them.

   ```sh
   python3 scripts/fixtures.py
   ```

6. Run the complete check procedure.

   ```sh
   ./scripts/check.sh
   ```

`build.sh` uses four build jobs by default. The `GSR_BUILD_JOBS` environment
variable changes this number. Both build scripts also detect Boost headers under
`build/deps/usr`.

If Debian has no suitable system installation of Boost, prepare a local copy:

1. Download `libboost1.83-dev` with `apt-get download`.
2. Extract the package into `build/deps/` with `dpkg-deb -x`.

The scripts start local regtest nodes, activate the experimental deployment, and
stop the nodes after the tests. They use public test keys and no public-network
funds. The repository contains no machine-specific build cache.

To run only the verifier tests after the normal build, use this command:

```sh
python3 -m unittest discover -s tests -v
```

After a source or build change, regenerate all evidence with `./scripts/check.sh`.
This includes test results, test provenance, fresh transactions, measurements, and the environment manifest.
Exporting programs and measurements alone does not refresh test provenance.

To recheck unchanged evidence on the machine that produced it, run:

```sh
python3 scripts/audit.py
```

The full audit checks local executable hashes. Another machine must build and regenerate its own evidence before running that audit.
CI also compares the three deterministic test-result files with their committed versions.

To check committed follow-up provenance without the original executables, run:

```sh
python3 scripts/audit_followups.py --portable
```

CI runs this check before regeneration. It verifies input hashes, measurement code, recorded binary links, and parser schedules.
It does not verify local binaries or reproduce performance measurements.
The complete pipeline also builds separate counting and parser executables, then regenerates parsing and OP_MULTI evidence.
The full audit checks those local builds against the environment manifest.

The audit checks source and executable hashes, upstream revisions, generated
programs, and test inputs. It also checks transaction policies, weight allowances,
and recorded transaction results. All three Python test runs must cover every
discovered test method: native, profiled, and optimized.

The audit regenerates the disassemblies and source maps for comparison. A
source map connects generated instructions to their source definitions. Source
and build manifests connect the profiling executable to its permitted source
changes. The GitHub Actions workflow runs the complete procedure from a fresh checkout.

Timing, test duration, local block hashes, and funding transactions can vary
between runs. Generated bytecode and public test inputs are deterministic.

## Use the laboratory API

```python
from generator.verifier import compile_verifier
from runner.evaluator import evaluate

program = compile_verifier(profile="full", mode="unified")
# Bytes: signature, 48-byte public key, 32-byte message.
result = evaluate(program.code, [signature, public_key, message], budget=allowance)
if not result.success or result.stack:
    raise ValueError("signature verification failed")
```

The `baseline` profile expands all operations inline. The `bytes` profile adds
byte reversal. The `full` profile also uses shared functions. All profiles use
the same acceptance rules. The mode can be `unified`, `stateful`, or `stateless`.

Standalone verification checks the supplied message. Transaction authorization
also requires a policy that derives the message from authenticated transaction data.
For this purpose, use `compile_policy` from `generator.transaction`.
This policy commits the key and context and uses the additional `OP_TX` extension.

## Package contents

| Directory | Contents |
|---|---|
| `generator/` | Compiler, verifier, and transaction policy |
| `reference/`, `fixtures/` | Pinned reference implementation and public test inputs |
| `generated/` | Binaries, disassemblies, source maps, and hashes |
| `runner/` | C++ evaluator adapter and separate measurement code |
| `tests/` | Component tests, parser tests, profile comparisons, and regtest tests |
| `spec/` | Acceptance rules, profiles, and signing transcript |
| `reports/` | Results, environment data, logs, audit, and transaction evidence |

## Limits

The package is experimental research. It supplies no production wallet, signer
state manager, or activation proposal. It has no formal proof or independent
cryptographic audit.

The regtest output uses ordinary Taproot. Its key path remains vulnerable to
quantum attacks, including with a NUMS internal key. A NUMS key is a point selected
without a known private key. SHRINCS verification in a leaf does not make the
complete output post-quantum safe.
