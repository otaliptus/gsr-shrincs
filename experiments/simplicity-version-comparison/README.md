# Simplicity version comparison

This separate experiment follows Blockstream Research's Simplicity SHRINCS verifier.
It preserves the original GSR experiment and its reports.

The comparison uses the same public keys, messages, and signature fields in both languages.
It measures standalone verification. It does not measure a complete transaction.
Neither standalone entry point binds the supplied public key to a funded output.
Do not use these entry points as wallet spending policies.

## Sources

- [SHRINCS Simplicity source](https://github.com/BlockstreamResearch/shrincs-simplicity-verifier/tree/d13165d3d21bac73e8794eede21f0f1527f3b837).
- [Compiler source](https://github.com/BlockstreamResearch/SimplicityHL/tree/f3fa882e77c221e96e10acde9f0e46e68e69930f), version 0.7.2.
- `Cargo.lock` pins the compiler dependencies, including simplicity-lang 0.8.0 and simplicity-sys 0.7.0.
- The Bitcoin fork remains at the original submodule revision. `results.json` records that revision.

The upstream typed construction has five supplied FORS paths. A sixth 22-bit message field must equal zero.
Thus, the upstream report's `k=6` includes a field without a supplied path.
The stateful WOTS construction uses 64 base-four digits with sum 140.
The public key contains a seed and a combined root. The witness supplies the unused branch's root.

`reference.py` independently translates the verification rules into Python.
`gsr.py` translates them into Script through the existing stack-checked compiler.
The generator does not read signature fixtures.
`run.py` preprocesses the upstream source with Clang. It does not change the verification functions.
It replaces only the entry point, to select one signature mode before compilation.
Both GSR and Simplicity therefore use separate stateful and stateless programs.
The bundled upstream executable is not used.

## Reproduce

Requirements: Python 3.11+, Git, Clang, Cargo, and the native and profiling GSR builds.
Use the repository's existing build instructions for those GSR executables.

```sh
bash experiments/simplicity-version-comparison/setup.sh
python3 experiments/simplicity-version-comparison/run.py measure
python3 experiments/simplicity-version-comparison/run.py audit --execute
python3 experiments/simplicity-version-comparison/build_page.py
```

The setup downloads pinned public source and builds the measurement runner.
All downloaded files and native binaries remain under `build/` or Cargo's cache.
The first build needs network access. Later locked builds can use Cargo's offline mode.

For portable evidence checks without the native tools:

```sh
python3 experiments/simplicity-version-comparison/run.py audit
```

Portable checks verify source hashes, fixture hashes, case inventories, reference outcomes, program sizes, and GSR compilation.
They do not re-execute Simplicity or establish the truth of recorded timings.
The execution audit also checks binary hashes and replays the full case corpus.
Different machines must regenerate local measurements before the execution audit.

## Measurement boundaries

- **GSR program bytes:** the complete mode-specific Script, including function definitions.
- **Simplicity program bytes:** the encoded program after witness-driven pruning. The unpruned size is also recorded.
- **Logical input bytes:** a lossless fixed-width representation of the public fixture's fields.
- **Simplicity witness bytes:** its actual encoded witness after pruning. Unused fields can disappear.
- **GSR varops:** the actual charge in the pinned evaluator, checked against its profiling build.
- **Simplicity cost bound:** the static bound, in milliweight units. C and Rust must agree.
- **GSR time:** the profiling build's interpreter timer with observation counters disabled.
- **Simplicity C execution time:** native evaluation, including its bounds analysis and execution memory allocation.
- **Simplicity C validation time:** decoding, type inference, witness filling, identity checks, evaluation, and cleanup.
- **Simplicity Rust time:** Rust Bit Machine execution after its machine allocation. This is a separate implementation.

Timing samples exclude compilation and process startup. They use the same host and record eleven repetitions by default.
The timed boundaries differ. Do not calculate a VM speed ratio from these columns.
GSR peak stack bytes and Simplicity's static bit-cell bound also measure different quantities.
Neither figure is total process memory.

No complete-spend sizes, fees, TPS, or block-validation estimates are claimed here.
The upstream Liquid report includes budget padding and a different transaction environment.
Its quoted witness vbytes are not the program bytes measured here.
The old GSR specification and this construction also differ. Their results are separate workloads.

## Native measurement adapter

The optional simplicity-sys 0.7.0 test binding omits the C evaluator's `minCost` argument.
`c_measure.rs` declares the function with the signature in that version's `eval.h`.
It supplies zero for the minimum cost and uses the standard C evaluator without source changes.
It checks decoding, types, witness data, unique identities, and the unit-to-unit program type before evaluation.
The independent upstream cost-analysis helper stops before the affected execution binding.
This adapter is measurement code and needs review with the rest of the experiment.

## Validation and limits

The two unchanged upstream fixtures are the positive reference inputs.
The corpus flips two bits separately in every supplied chain value and authentication node.
It also changes the message, seed, expected root, unused root, counters, and stateful index.
Changes to the unused stateless WOTS randomizers must remain accepted, as upstream specifies.
Python, Rust Simplicity, and all four GSR programs must agree on every case.
The C evaluator additionally verifies each accepted, pruned program and witness.
Budget exhaustion is a harness error, never a valid rejection.

These checks do not prove equivalence for all inputs or assess the construction's cryptographic security.
Only one original positive fixture per mode is measured. Stateful path depths are not exhaustively covered.
The GSR translation is an initial implementation, not a claim of optimal code generation.
Future work needs more independently generated positive signatures, boundary cases, and complete transaction policies.

The copied fixtures and translated algorithms derive from the upstream CC0-1.0 project.
The native adapter follows the CC0-1.0 simplicity-sys test interfaces.
