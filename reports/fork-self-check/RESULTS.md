# Fork comparison

Status: complete.

The replay uses fixed programs and input bytes. The recompile uses newly generated policies and signatures.
Transaction results are offline Script checks against recorded spent outputs. They are not new node validation.
Fresh node acceptance is recorded separately for the recompile mode.

Timing includes profiling hooks with counters disabled. Timing changes are observations, not acceptance failures.
Boundary and negative cases have one recorded timing sample. Positive transactions have repeated samples.

## replay

```json
{
  "cases": 2632,
  "acceptance_changes": 0,
  "baseline_unexpected": 0,
  "candidate_unexpected": 0,
  "accounting_changes": 0,
  "error_changes": 0,
  "stack_changes": 0,
  "changed_inputs": 0
}
```

| Spend | Script bytes, before → after | Signature bytes, before → after | Weight, before → after | Varops change | Time ratio | Inputs changed |
|---|---:|---:|---:|---:|---:|---|
| full-unified | 17755 → 17755 | 660 → 660 | 18942 → 18942 | +0 | 0.987 | False |
| full-stateful | 4476 → 4476 | 660 → 660 | 5663 → 5663 | +0 | 1.066 | False |
| full-stateless | 14091 → 14091 | 5777 → 5777 | 20395 → 20395 | +0 | 0.990 | False |
| baseline-unified | 228549 → 228549 | 660 → 660 | 229738 → 229738 | +0 | 1.217 | False |
| baseline-stateful | 95350 → 95350 | 660 → 660 | 96539 → 96539 | +0 | 1.031 | False |
| baseline-stateless | 133452 → 133452 | 5777 → 5777 | 139758 → 139758 | +0 | 1.006 | False |
| full-unified-sl | 17755 → 17755 | 5777 → 5777 | 24059 → 24059 | +0 | 0.976 | False |
| baseline-unified-sl | 228549 → 228549 | 5777 → 5777 | 234855 → 234855 | +0 | 1.026 | False |
| full-2-input-mixed | 35510 → 35510 | 6437 → 6437 | 42523 → 42523 | +0 | 0.988 | False |
| full-4-input-mixed | 71020 → 71020 | 12874 → 12874 | 84880 → 84880 | +0 | 1.011 | False |
| full-cap1-boundary | 4476 → 4476 | 660 → 660 | 5507 → 5507 | +0 | 0.975 | False |
| full-cap2-boundary | 8952 → 8952 | 1320 → 1320 | 10848 → 10848 | +0 | 0.997 | False |
| full-cap3-boundary | 13428 → 13428 | 1980 → 1980 | 16189 → 16189 | +0 | 1.010 | False |
| full-cap4-boundary | 17904 → 17904 | 2640 → 2640 | 21530 → 21530 | +0 | 1.012 | False |

Changed signatures can change hash-chain work. Recompile timings do not isolate compiler effects.

## recompile

```json
{
  "cases": 2632,
  "acceptance_changes": 0,
  "baseline_unexpected": 0,
  "candidate_unexpected": 0,
  "accounting_changes": 99,
  "error_changes": 1,
  "stack_changes": 0,
  "changed_inputs": 142
}
```

| Spend | Script bytes, before → after | Signature bytes, before → after | Weight, before → after | Varops change | Time ratio | Inputs changed |
|---|---:|---:|---:|---:|---:|---|
| full-unified | 17755 → 17755 | 660 → 660 | 18942 → 18942 | -24 | 0.994 | True |
| full-stateful | 4476 → 4476 | 660 → 660 | 5663 → 5663 | +12 | 1.010 | True |
| full-stateless | 14091 → 14091 | 5777 → 5777 | 20395 → 20395 | -369 | 1.000 | True |
| baseline-unified | 228549 → 228549 | 660 → 660 | 229738 → 229738 | -36 | 1.000 | True |
| baseline-stateful | 95350 → 95350 | 660 → 660 | 96539 → 96539 | +12 | 1.006 | True |
| baseline-stateless | 133452 → 133452 | 5777 → 5777 | 139758 → 139758 | +1,929 | 1.001 | True |
| full-unified-sl | 17755 → 17755 | 5777 → 5777 | 24059 → 24059 | +1,884,843 | 1.014 | True |
| baseline-unified-sl | 228549 → 228549 | 5777 → 5777 | 234855 → 234855 | +2,826,855 | 1.013 | True |
| full-2-input-mixed | 35510 → 35510 | 6437 → 6437 | 42523 → 42523 | -2,357,166 | 0.988 | True |
| full-4-input-mixed | 71020 → 71020 | 12874 → 12874 | 84880 → 84880 | +2,354,325 | 1.004 | True |
| full-cap1-boundary | 4476 → 4476 | 660 → 660 | 5507 → 5507 | +0 | 1.002 | True |
| full-cap2-boundary | 8952 → 8952 | 1320 → 1320 | 10848 → 10848 | +24 | 0.996 | True |
| full-cap3-boundary | 13428 → 13428 | 1980 → 1980 | 16189 → 16189 | -3 | 0.998 | True |
| full-cap4-boundary | 17904 → 17904 | 2640 → 2640 | 21530 → 21530 | -3 | 1.001 | True |

Changed signatures can change hash-chain work. Recompile timings do not isolate compiler effects.
