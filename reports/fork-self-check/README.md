# Fork-comparison self-check

The complete replay and recompile run passed on 18 September 2026.
This experiment checks the harness against two independent builds of the same revision.
It does not test a new calling convention or cost table.

Both sides use harness commit `937e05811e45b1b61f505201ac8f06c05abf2253` and fork commit `d2799052604eb138c5a79acf88514a0c8b07f4ef`.
The comparison driver is from `490242cd18dad38c5d81c6e80d8e520e6b2fb52f`; `config.json` records its exact file hashes.

| Check | Replay | Recompile |
|---|---:|---:|
| Cases | 2,632 | 2,632 |
| Unexpected baseline results | 0 | 0 |
| Unexpected candidate results | 0 | 0 |
| Acceptance changes | 0 | 0 |
| Changed inputs | 0 | 142 |
| Changed varops | 0 | 99 |
| Changed error text | 0 | 1 |

All recompile cost changes occur in cases with changed input bytes.
Fresh funding transactions and signatures account for the changed inputs.
The one changed error occurs in `rejections/baseline-unified/spent-script`; both inputs are rejected.
The 2,490 standalone cases retain identical requests, costs, and outcomes.
All generated verifier program bytes also match between the two sides.

Each checkout separately mined fourteen valid spends and recorded 128 expected node rejections.
The transaction tests used no padding. The node logs and transaction records are included here.
Some node rejections are policy checks; the separate offline Script replay records its own failure classification.

The readable [comparison tables](RESULTS.md) include complete spend weights and measured timing ratios.
Positive transactions have five samples after warm-up. Other cases have one recorded sample.
The machine was not isolated from other work. Timing variation in this identical-revision experiment is not evidence of a speed improvement.

## Evidence

- `results.json.gz`: complete results and binary provenance.
- `fixed-corpus.json.gz`: fixed programs, inputs, and expected results.
- `baseline-recompiled.json.gz` and `candidate-recompiled.json.gz`: regenerated inputs.
- `baseline-node-evidence.json.gz` and `candidate-node-evidence.json.gz`: mined transactions and node rejection records.
- Separate node logs, build log, CMake caches, and profiling source/build manifests.
- `sha256.json`: hashes of the archived evidence files.

Paths in the archived configuration describe the machine that ran the experiment.
Use the [comparison procedure](../../spec/FORK-COMPARISON.md) to create new checkouts on another machine.
The compressed corpora preserve the transaction bytes needed for exact offline replay.

## Subsequent metadata correction

After this run, the exporter was corrected to locate the signature immediately before the script and control block.
Previously, the eight `extra-witness` negative cases recorded the prepended five-byte item as `signature_bytes`.
The archived files retain that historical metadata so their recorded hashes remain valid.
Their requests, acceptance, varops, transaction weights, and all valid-spend size tables are unaffected.
The corrected exporter has a regression test against all eight recorded cases.

## Next gate

Select a committed fork change and run both comparison modes against it.
For a new function convention, port the compiler and observation adapter in an explicit harness commit.
Keep function semantics and cost-table changes separate until their individual effects are measured.
