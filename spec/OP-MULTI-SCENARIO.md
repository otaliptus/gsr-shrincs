# OP_MULTI inside the SHRINCS checker

This note measures OP_MULTI where it could help the checker most: hashing a list of parts.
It extends the audited `full` profile without changing the audited compiler.
`generator/multi.py` patches the compiler for one compile at a time.
`scripts/multi_scenario.py` checks acceptance and measures cost.
`reports/multi-scenario.json` records the result.

## Variants

| Variant | Change |
|---|---|
| `full` | The audited profile: byte reversal and shared functions. |
| `catfix` | Each join starts from its first part. The audited compiler starts from an empty push, which costs two opcodes per join. |
| `multi` | `catfix`, plus OP_MULTI: one `MULTI SHA256` over the parts of each hashed join, `MULTI CAT` for other joins of three or more parts, `MULTI DROP` for cleanups of three or more items. |

## Agreement

All three variants accept and reject the same inputs on the 40 public vectors in both leaf forms,
with four mutations each, and on stateful depths 1, 64, and 255 at both index extremes.
That is 406 cases in the recorded run. Budget exhaustion never occurs.
`tests/test_multi.py` repeats a small part of this check in the test suite.
The check pipeline runs the full script and the follow-up audit validates its report.

## Measurement

One signature and one transaction shape per signature type: one input, two outputs, a two-leaf tree.
The offline C++ checker evaluates each transaction with its actual weight allowance.
The `full` rows reproduce the mined regtest spends byte for byte.

| Program | Program bytes | vbytes | Charged units | Share of allowance |
|---|---:|---:|---:|---:|
| `full`, stateful | 4,476 | 1,416 | 20,577,528 | 36.3% |
| `catfix`, stateful | 4,130 | 1,330 | 18,838,994 | 35.4% |
| `multi`, stateful | 4,064 | 1,313 | 19,143,887 | 36.5% |
| `full`, stateless | 14,091 | 5,099 | 119,995,961 | 58.8% |
| `catfix`, stateless | 12,913 | 4,805 | 112,114,253 | 58.3% |
| `multi`, stateless | 12,661 | 4,742 | 120,942,956 | 63.8% |

The stateful `multi` program uses OP_MULTI 68 times: 20 hashes, 34 joins, 14 cleanups.
The stateless program uses it 247 times: 30 hashes, 211 joins, 6 cleanups.

## Reading

The join fix removes 7.7% of the stateful program bytes and 8.4% of its charged cost.
It needs no new opcode. It should go into the audited compiler in a normal evidence-regenerating commit.

OP_MULTI then removes a further 1.6% of bytes and adds 1.6% to the charged cost.
For the stateless type it adds 7.9%, which is above the audited `full` cost.

The cause is the charging rule in the pinned interpreter.
The OP_MULTI byte pays no fixed charge.
Its count operand is an ordinary push and pays 1,250.
The opcode then charges the target's fixed price once per logical operation:
`count` times for SHA256 and DROP, `count - 1` times for CAT.
Hashing `n` parts therefore costs `(n + 1) × 1,250` plus the hash charge.
Joining and hashing costs `n × 1,250` plus the hash charge plus copying at 3 per byte.
For the joins in this checker, which are under 700 bytes, the copying is cheaper than one push.

Under this cost table OP_MULTI cannot reduce the charged cost of a hash-based verifier.
It can reduce bytes only where one operation has many operands, and this checker has no such place.
This result adds to [the earlier note](OP-MULTI-BENEFIT.md), which found the same for summing amounts.

## Limits

The extension is a laboratory patch, and its programs were not spent on a node.
Its report carries the same provenance record as the other follow-up experiments,
and the audited programs in `generated/` are unchanged.
The comparison holds for the pinned cost table.
A cost table that charged OP_MULTI less than the operations it replaces would change the result.
