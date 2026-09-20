# Simplicity compatibility check

This is a source comparison. No Simplicity program was compiled or measured for this note.

The comparison pins these sources:

| Implementation | Revision |
|---|---|
| GSR SHRINCS specification | `4cd63a6497a0ba7c5e99699b94d33973546d9e37` |
| BlockstreamResearch Simplicity verifier | `d13165d3d21bac73e8794eede21f0f1527f3b837` |

The inspected type definitions already establish that the workloads differ.

| Item | Pinned GSR specification | Pinned Simplicity types |
|---|---|---|
| FORS trees | 10 | 5, represented as groups of 4 and 1 |
| FORS authentication height | 13 | 22 |
| Hypertree layers | 5 | 2 |
| XMSS authentication height | 9 | 12 |
| Stateful authentication path | Depths 1 through 255 | A list type with capacity below 512 |
| Stateless Winternitz representation | 35 chain values, including checksum chains | 64 chain values plus other typed fields |

Sources: [GSR parameters](https://github.com/SHRINCS/shrincs-bip/blob/4cd63a6497a0ba7c5e99699b94d33973546d9e37/impl/shrincs.py), [Simplicity types](https://github.com/BlockstreamResearch/shrincs-simplicity-verifier/blob/d13165d3d21bac73e8794eede21f0f1527f3b837/types.simf).

These type dimensions do not establish encoded witness sizes.
The compiler and witness encoding can affect the actual bytes that a spend reveals.

The top-level key relation also differs.
The GSR specification has a public seed and separate stateful and stateless roots in its 48-byte public key.
The inspected Simplicity wrapper combines the recovered root with a supplied unused root, hashes that pair, and compares the result with its expected root.

Source: [Simplicity wrapper](https://github.com/BlockstreamResearch/shrincs-simplicity-verifier/blob/d13165d3d21bac73e8794eede21f0f1527f3b837/shrincs/shrincs.simf).

Thus, matching numeric parameters alone is insufficient.
The comparison must also align the public-key relation, hash addresses, message/context binding, parsing, and rejection rules.
Use shared positive and negative vectors to test that relation.

The project README requires a bundled `simfony` executable because of upstream incompatibilities.
Record its provenance and obtain a reproducible compiler build before publishing a matched benchmark.
The bundled executable has not been run here.

Source: [compiler requirement](https://github.com/BlockstreamResearch/shrincs-simplicity-verifier/blob/d13165d3d21bac73e8794eede21f0f1527f3b837/README.md).

## Next experiment

Preserve the current GSR baseline.
Prefer a Simplicity implementation of the same pinned verification relation.
If another parameter set is selected, give that experiment a separate name and result set.

Measure encoded program bytes, signature bytes, complete witness bytes, complete spend weight, memory, and execution time separately.
State the available jet catalogue and compiler revision. A jet is a native implementation of a specified Simplicity operation.

Report each VM's charged resource units separately. Raw varops and Simplicity costs have different meanings.
Measure runtime on matched hardware with a documented method.

The source of the quoted approximate 50 kB figure remains unverified.
Do not use that figure as a measured comparison row without its program revision, mode, and size definition.

## Separate follow-up

The [simplicity-version-comparison experiment](../experiments/simplicity-version-comparison/README.md)
implements the pinned Simplicity construction in GSR and measures both languages.
It uses shared public fixtures, separate mode-specific entry points, and a compiler built from pinned source.
It does not change this repository's original SHRINCS specification or transaction measurements.
Its initial measurements cover standalone verification, not complete spends.
