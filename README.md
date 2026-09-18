# SHRINCS verification in GSR Bitcoin Script

A reproducible laboratory implementation of **both complete SHRINCS verification
modes** in the pinned experimental GSR fork. It includes generated Script, a
reference fixture corpus, exact-byte tests, execution measurements, and actual
transaction-bound regtest spends.

Start with [measured results](reports/RESULTS.md), [accepted inputs](spec/ACCEPTANCE.md),
[transaction transcript](spec/TRANSCRIPT.md), and the [milestone audit](reports/AUDIT.md).
The original research plan is [PLAN.md](PLAN.md); [HANDOFF.md](HANDOFF.md) preserves
its requirements and the original pre-implementation snapshot.

## Reproduce

Requires Python 3.11+, a C++20 compiler supported by the pinned fork, CMake 3.22+,
Ninja, Boost headers (at least 1.74), Git, and localhost networking for regtest.
See the fork's [Linux build instructions](vendor/bitcoin/doc/build-unix.md) for
platform dependencies. This run used Python 3.13.5, GCC 14.2 and Boost 1.83; see
[environment.json](reports/environment.json) for exact flags and hashes.

```sh
git clone --recurse-submodules https://github.com/otaliptus/gsr-shrincs.git
cd gsr-shrincs
./scripts/build.sh
python3 scripts/profile_build.py
# Optional: regenerate the committed PUBLIC TEST fixtures.
python3 scripts/fixtures.py
./scripts/check.sh
```

`build.sh` defaults to four build jobs; set `GSR_BUILD_JOBS` to change it. If Boost
is unavailable system-wide on Debian, it can be downloaded and unpacked under
`build/deps/` with `apt-get download libboost1.83-dev` and `dpkg-deb -x`; both build
scripts detect `build/deps/usr`. No machine-specific build cache is committed.
The scripts create local regtest nodes only, activate the experimental deployment,
and stop them after testing. No real-network coins or production secrets are used.

To run just the verifier tests after the normal build:

```sh
python3 -m unittest discover -s tests -v
```

To regenerate bytecode and inspect it:

```sh
python3 scripts/export.py
python3 scripts/measure.py  # requires profiling build and recorded regtest transactions
python3 scripts/audit.py
```

The final audit checks source/binary hashes, clean source pins, fresh generated
programs, fixture verification, current transaction policy bytecode, actual weight
allowances, all recorded positive/negative transaction results, and test logs.
Timings, test durations, local block hashes and funding transactions can vary by
machine/run. Bytecode and public fixtures are deterministic.

## Use the laboratory API

```python
from generator.verifier import compile_verifier
from runner.evaluator import evaluate

program = compile_verifier(profile="full", mode="unified")
# Bytes: signature, 48-byte public key, 32-byte message.
result = evaluate(program.code, [signature, public_key, message], budget=allowance)
assert result.success and result.stack == []
```

`baseline` inlines the restoration-only verifier; `bytes` adds byte reversal while
retaining inline execution; `full` adds reusable functions. `mode` can also be
`stateful` or `stateless`. All preserve the same byte-level acceptance rules.
Standalone verification is not spending authorization: use `compile_policy` from
`generator.transaction` to commit a key/context and derive the message with OP_TX.
That wrapper is always an additional transaction-introspection extension.

## Package contents

- `generator/`: bounded stack-checked compiler, verifier, transaction policy.
- `reference/`, `fixtures/`: pinned oracle and public fixtures with provenance.
- `generated/`: deterministic binaries, disassemblies, source maps and hashes.
- `runner/`: strict C++ evaluator adapter and separate observation-only overlay.
- `tests/`: component, full-range parser, cross-profile, and actual regtest tests.
- `spec/`: acceptance, feature profiles and exact laboratory signing transcript.
- `reports/`: results, environment, raw logs, audit and compressed full transaction evidence.

This is experimental research, not a production wallet or an activation proposal.
One-time signer state, key custody and formal/independent review are outside this
package. The regtest output is ordinary Taproot: **its key path remains
quantum-vulnerable**, including with a NUMS internal key. Verifying SHRINCS in a
leaf does not make the complete output post-quantum safe.
