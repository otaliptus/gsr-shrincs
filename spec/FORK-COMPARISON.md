# Compare fork revisions

This procedure separates VM changes from compiler changes. A VM is the interpreter that executes Script.

The historical package is commit `937e05811e45b1b61f505201ac8f06c05abf2253`. Its fork revision is `d2799052604eb138c5a79acf88514a0c8b07f4ef`.

The comparison does not replace files in `vendor/`, `generated/`, or `reports/`. It creates separate checkouts under the selected output directory.

## Two modes

**Replay** executes the same programs, signatures, transactions, and spent-output records on both forks.
This mode tests compatibility and accounting changes. An intended compatibility break is still reported as a change.

**Recompile** generates each program with its selected compiler revision.
It also creates fresh transactions through each fork's regtest node.
The reference specification, acceptance document, and transaction transcript must remain unchanged.

The transaction signatures can change after recompilation. These changes can alter hash-chain work.
The report therefore includes request hashes and identifies changed inputs.
Fixed-message standalone checks help separate these effects.

## Workload

The fixed corpus contains:

- Fourteen recorded valid spends.
- 128 recorded negative transactions.
- 1,530 stateful depth and extreme-index cases across three compiler profiles.
- The forty public vectors, both applicable leaf forms, and message, length, and path checks.

The exporter obtains expected mutation results from the reference verifier.
The corpus stores programs once and refers to them by SHA256 hash.
Recompilation must retain the case identifiers and expected results.

Standalone checks use the existing functional allowance. They do not establish transaction affordability.
Transaction checks use their serialized weight and the fork's transaction allowance.

## Run a comparison

First, obtain the candidate commit in a local clone of the fork.
Use a committed candidate. Uncommitted fork edits are not a revision.

```sh
python3 scripts/compare_forks.py \
  --candidate-fork-ref CANDIDATE_COMMIT \
  --output build/comparisons/candidate-1 \
  --mode both
```

The default fork repository is `vendor/bitcoin`.
Use `--fork-repository /path/to/bitcoin` for another local clone.
This command does not fetch or select a moving remote branch automatically.

The candidate compiler defaults to this repository's committed `HEAD`.
Set `--candidate-harness-ref` when the new calling convention needs a different compiler revision.

For an initial self-comparison, select the historical revision on both sides:

```sh
python3 scripts/compare_forks.py \
  --candidate-fork-ref d2799052604eb138c5a79acf88514a0c8b07f4ef \
  --candidate-harness-ref 937e05811e45b1b61f505201ac8f06c05abf2253 \
  --output build/comparisons/self-check \
  --mode both
```

Use `--jobs` to control compilation parallelism.
Use `--repeats` to set the positive-transaction timing sample count. The default is eleven.

An interrupted run can use `--resume` with the same arguments.
The resolved revisions and driver files must match the saved configuration.
Build commands run again with their existing caches. Measurements run again; partial measurements do not count as complete.

Use `--build-cache PATH` to reuse isolated checkouts from an earlier comparison.
Both checkout revisions must match exactly. The command rejects changed source files.
The new result directory records fresh measurements and the reused binary hashes.

The profiling overlay has explicit source anchors. It stops if a fork change moves an expected interface.
Port the overlay in a new harness commit before comparing that fork.
Do not weaken the overlay checks to make an unsupported fork appear compatible.

## Evidence

Each output directory contains:

- `config.json`: resolved revisions and comparison-driver hashes.
- `build.log`: exact build commands and output.
- `fixed-corpus.json.gz`: programs, fixed inputs, expected results, and source hashes.
- `replay.jsonl` and `recompile.jsonl`: completed case records, written as execution progresses.
- `results.json.gz`: complete results, binary hashes, build provenance, and environment.
- `RESULTS.md`: a readable summary.
- Separate regtest logs and regenerated corpora when recompilation runs.

Exit code zero means the requested comparison completed without unexpected acceptance or rejection.
Exit code one means at least one expected acceptance result changed.
Exit code two means the experiment did not complete. Build failure, unsupported instrumentation, timeout, or malformed output can cause this result.

The report keeps byte changes, varops changes, and timing changes separate.
A budget failure does not count as a successful negative test.
The unmodified and profiling evaluators must agree on standalone acceptance and varops.

Positive transaction timing uses an excluded warm-up and alternating measurement order.
Boundary and negative cases retain one timing sample. These samples support diagnosis, not precise timing claims.
Both timing paths retain profiling hooks with counters disabled.
Do not compare local timings directly with timings from a different CI machine.

## Change order

Run four separately pinned experiments where the fork supports them:

1. Existing functions and existing costs.
2. New functions and otherwise unchanged costs.
3. Existing functions and revised costs.
4. New functions and revised costs.

Preserve every result set. A changed cost table does not invalidate the old pin; it creates a new comparison target.
