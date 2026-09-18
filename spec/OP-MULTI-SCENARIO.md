# OP_MULTI inside the SHRINCS checker

This note measures OP_MULTI where it could help the checker most: hashing a list of parts.
It extends the audited profiles without changing the audited compiler.
`generator/multi.py` patches the compiler for one compile at a time.
`scripts/multi_scenario.py` checks acceptance and measures cost.
`reports/multi-scenario.json` records the result with the same provenance record as the other follow-up experiments.
The follow-up audit re-derives sizes from the recorded transactions, re-verifies each signature,
and re-executes every measurement when the local executables are present.

## Variants

| Variant | Change |
|---|---|
| `full` | The audited profile: byte reversal and shared functions. |
| `catfix` | Each join starts from its first part. The audited compiler starts from an empty push, which costs two opcodes per join. |
| `multi` | `catfix`, plus OP_MULTI everywhere it applies: `MULTI SHA256` over the parts of each hashed join, `MULTI CAT` for other joins of three or more parts, `MULTI DROP` for cleanups of three or more items. |
| `multisel` | `catfix`, plus `MULTI SHA256` only where the cost table makes it cheaper. See the rule below. |

## Agreement

All extended variants accept and reject the same inputs as the audited verifier on the 40 public vectors
in both leaf forms, with five argument variants each, and on stateful depths 1, 64, and 255 at both index extremes.
That is 406 cases. The report records the inventory, and the audit recomputes the expected count from it.
Budget exhaustion never occurs. `tests/test_multi.py` repeats a small part of this check in the test suite.

## Two measurements

Complete transactions give real spend sizes, but their charged costs are not directly comparable across programs.
The script is part of the signed message, so each program signs a different message, and a different message
changes the hash-chain work of the signature. An earlier version of this note compared those rows directly; that was wrong.

Matched-input standalone runs isolate the program. One public fixture per signature type is evaluated by every program,
so the signature bytes are identical and only the program differs.

### Matched input, standalone

| Program | Bytes | Charged units | Change |
|---|---:|---:|---:|
| `full`, stateful | 4,335 | 19,645,115 | |
| `catfix`, stateful | 3,989 | 17,957,817 | −8.6% |
| `multi`, stateful | 3,923 | 18,241,221 | +1.6% over `catfix` |
| `multisel`, stateful | 3,983 | 17,956,698 | −1,119 units over `catfix` |
| `full`, stateless | 13,950 | 122,293,006 | |
| `catfix`, stateless | 12,772 | 111,270,250 | −9.0% |
| `multi`, stateless | 12,520 | 113,227,624 | +1.8% over `catfix` |
| `multisel`, stateless | 12,726 | 111,269,830 | −420 units over `catfix` |

### Complete transactions

| Program | Program bytes | vbytes | Charged units | Share of allowance |
|---|---:|---:|---:|---:|
| `full`, stateful | 4,476 | 1,416 | 20,577,528 | 36.3% |
| `catfix`, stateful | 4,130 | 1,330 | 18,838,994 | 35.4% |
| `multi`, stateful | 4,064 | 1,313 | 19,143,887 | 36.5% |
| `multisel`, stateful | 4,124 | 1,328 | 18,837,884 | 35.5% |
| `full`, stateless | 14,091 | 5,099 | 119,995,961 | 58.8% |
| `catfix`, stateless | 12,913 | 4,805 | 112,114,253 | 58.3% |
| `multi`, stateless | 12,661 | 4,742 | 120,942,956 | 63.8% |
| `multisel`, stateless | 12,867 | 4,793 | 112,898,411 | 58.9% |

These are separately constructed offline transactions. The `full` rows match the mined regtest spends in program size,
signature size, and transaction shape, not in transaction bytes: their outpoints, outputs, and signatures differ.
The report also measures the `baseline` and `bytes` profiles the same way.

## The charging rule

The OP_MULTI byte pays no fixed charge. Its count operand is an ordinary push and pays 1,250.
The opcode then charges the target's fixed price once per logical operation:
`count` times for SHA256 and DROP, `count − 1` times for CAT.

A chain of CATs pays 3 units per byte of every intermediate result.
Hashing `n` parts with OP_MULTI costs `(n + 1) × 1,250` plus the hash charge.
Joining and hashing costs `n × 1,250` plus the hash charge plus `3 × (sum of intermediate lengths)`.
Decoding the count costs a further 16 units for small counts, measured on the pinned evaluator.
OP_MULTI is therefore cheaper when three times the intermediate lengths exceed 1,266 plus the part count,
that is, above about 422 intermediate bytes for three parts. Parts of 83, 84, and 83 bytes sum to 417
intermediate bytes and cost 22,065 units joined and hashed against 22,080 with `MULTI SHA256`;
three 200-byte parts cost 42,364 against 40,630. The 16-byte hashes that dominate this checker do not come close.
`tests/test_multi.py` checks the rule against the evaluator on both sides of the line.

`MULTI CAT` charges the same copying as the chain plus the count push, so it never wins under this table.
`MULTI DROP` charges one fixed price per item plus the count push, so it never wins either.

The `multisel` variant applies the rule with static width estimates for the values the verifier joins.
It finds 2 qualifying sites in the stateful checker and 12 in the stateless one: endpoint compressions,
root compressions, and the grinding hash. The saving is under 0.01% of the charged cost.

## Reading

The join fix is the useful result. It removes 8 to 9% of the program bytes and of the charged cost with no new opcode,
and it should go into the audited compiler in a normal evidence-regenerating commit.

For this checker, OP_MULTI used everywhere raises the charged cost by about 2% and saves under 2% of bytes.
Used only where the cost table favors it, the effect is a rounding error.
This does not show that OP_MULTI is useless in general: a program that hashes long lists of large items would gain.
It shows that a hash-based signature verifier, whose joins are short, does not.

## Instrumentation

The profiling overlay originally counted hashes only at the OP_SHA256 opcode.
Hashes and logical operations inside OP_MULTI now have their own counters,
and the derived fixed charge prices OP_MULTI by its logical operations instead of as one opcode.
An earlier version of the report showed one SHA256 call for the `multi` programs; that was the missing counter.

## Limits

The extension is a laboratory patch, and its programs were not spent on a node.
The audited programs in `generated/` are unchanged.
The comparison holds for the pinned cost table; a different price for the count operand or for copying would move the line.
