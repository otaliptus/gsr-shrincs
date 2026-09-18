# OP_MULTI marginal benefit

Recommendation: defer OP_MULTI on the evidence of this construction alone.
The existing OP_TX total selector performs the measured task with fewer bytes and fewer varops.

The main reason is coverage of the only demonstrated construction by a simple, existing operation.
That substitute is easy to review. This construction supplies no additional capability that justifies the general OP_MULTI dispatcher.
The three-byte saving and the varops difference are secondary. Both programs fit comfortably within their transaction allowances.

This result does not establish that every possible OP_MULTI application is redundant.
A proposed additional target needs a concrete construction and an equivalent comparison.

## Same rule in three forms

The experiment checks this rule in all three programs:

```text
1 <= number of outputs <= 32
sum of all output amounts = 1,000,000 satoshis
```

Each program applies the same count limits and final numeric comparison.
Each accepts a correct sum. Each rejects a changed amount, zero outputs, and 33 outputs with the correct sum.

The constructions are:

1. Obtain all output amounts through OP_TX. Reduce them with `OP_MULTI OP_ADD`.
2. Obtain the total directly through OP_TX.
3. Obtain all output amounts through OP_TX. Apply up to 31 conditional additions.

The third construction handles variable counts within the same bound. It is not a separate fixed-count program for each row.

| Construction | Complete predicate bytes |
|---|---:|
| OP_MULTI | 34 |
| Existing total selector | 31 |
| Bounded unroll | 296 |

| Output count | OP_MULTI varops | Total-selector varops | Bounded-unroll varops |
|---|---:|---:|---:|
| 1 | 25,444 | 24,210 | 352,796 |
| 2 | 26,759 | 24,258 | 354,127 |
| 4 | 29,421 | 24,354 | 356,789 |
| 8 | 34,745 | 24,546 | 362,113 |
| 16 | 45,345 | 24,930 | 372,713 |
| 32 | 66,593 | 25,698 | 393,961 |

The figures include the shared count checks and final comparison.
They are not intrinsic opcode costs.
The selector also has the smallest complete transaction in these examples because the other transaction fields have the same sizes.
The bounded unroll mostly pays the fixed per-opcode charge. Recalibrating that charge will change its measured cost substantially.

## Measurement scope

The offline C++ checker evaluates real transaction encodings and spent-output records.
The transactions use the actual weight allowance and no padding.
These predicates are not complete authorization policies. They do not check a signer or protect a funded output in this experiment.

The evidence contains 31 timing samples per positive case after a warm-up.
The order rotates across constructions. Profiling hooks remain present, and host load was not controlled.
Use these timings as exploratory measurements. The byte and varops comparisons do not depend on timing noise.

Run the experiment with a compatible profiling executable:

```sh
python3 scripts/multi_compare.py \
  --binary build/profile/bin/bitcoin-util \
  --output build/multi-comparison.json \
  --repeats 31
```

Raw evidence: [multi-comparison.json](../reports/multi-comparison.json).
The file records programs, transaction weights, resource costs, timing samples, and executable hashes.
The complete check pipeline regenerates this evidence with the current profiling executable.
Its provenance must match the binary recorded in `reports/environment.json`.
The audit reconstructs the deterministic transaction corpus and checks its hash, programs, accepted cases, and recorded negative outcomes.
This corpus belongs to the output-sum experiment. It is separate from the SHRINCS transaction corpus.

## Limits of the conclusion

The current total selector sums all outputs. This result does not replace every selected-subset sum.
It also does not assess OP_MULTI targets for concatenation, hashing, copying, or Boolean operations.

Keep the implementation comparison separate from the cost-table comparison.
A native selector can perform similar work while receiving a different charge.
The selector's lower varops count is not itself proof of proportionally lower CPU time.

Sources: [OP_TX totals](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/script/op_tx.cpp), [OP_MULTI](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/script/interpreter.cpp).
