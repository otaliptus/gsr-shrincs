# GSR-SHRINCS laboratory transaction transcript v1

The transcript is the exact byte sequence whose SHA256 hash becomes the SHRINCS
message. This laboratory transcript has its own format. It is not BIP-341
SIGHASH_ALL.

The policy commits the 48-byte public key, context, verifier layout, and permitted
input count. Inside the VM, `OP_TX` obtains authenticated transaction fields.
The policy does not accept a message digest supplied by the witness.

## Byte order and fields

The domain is ASCII `GSR-SHRINCS/transaction/v1` followed by one zero byte.
The combined output of selector `00 57 8b 22 2f 03` follows the domain.
The fields occur in the order shown below.

| Group | Fields in order |
|---|---|
| Transaction header | Version: uint32 LE. Locktime: uint32 LE. Input count: uint32 LE. |
| Each input, in transaction order | Outpoint txid: raw internal serialization, 32 bytes. Outpoint index: uint32 LE. Spent amount: uint64 LE. Spent scriptPubKey: CompactSize prefix and bytes. Sequence: uint32 LE. |
| Output header | Output count: uint32 LE. |
| Each output, in transaction order | Amount: uint64 LE. ScriptPubKey: CompactSize prefix and bytes. |
| Current execution | Current input index: uint32 LE. Annex: CompactSize prefix and bytes. Executing TapLeaf hash: 32 bytes. Code-separator position: uint32 LE. |

LE means little endian. CompactSize is Bitcoin's canonical variable-length
serialization. The spent amount and scriptPubKey come from authenticated spent
outputs. The annex must be empty. The code-separator position must be `ffffffff`.

The TapLeaf hash uses tagged SHA256 with tag `TapLeaf` and this input:

```text
c2 || CompactSize(script length) || complete executing script
```

This hash commits the key, context, and all verifier instructions.
It does not depend on the signature, so there is no circular dependency.
`OP_TX` supplies the specified combined bytes directly.
The Script transcript uses no host-defined integer casts.

## Input limits and covered data

The default policy requires exactly one input.
It also requires exactly one initial stack item: the signature.
The experiment with several inputs compiles a separate policy with a maximum of four inputs.
Each input has its own signature covering all inputs and outputs.
Each signature also binds the current input index.

The input limit forms part of the committed policy.
All signatures share the transaction-wide execution budget.

Script rejects annexes, although relay policy can reject them first.
The compiler emits no code separator.
The opcode audit checks this condition, and the policy checks the authenticated position.

The digest excludes signatures, witness item counts, witness contents, witness
weight, and the control block.
It also excludes input scriptSig.
Consensus requires an empty scriptSig for the native Taproot spends in this experiment.
Input and output amounts determine the fee; there is no separate fee field.

## Taproot output

The experiment uses ordinary Taproot with the BIP-341 NUMS internal key and
experimental `0xc2` leaves.
NUMS identifies a point selected without a known private key.
This choice does not remove the key path or protect it against quantum attacks.
Thus, these outputs do not provide complete post-quantum protection.

A rule that removes or secures the key path would require an additional consensus specification.
The measured node has no such change.
It activates the pinned Script-restoration deployment on an isolated local regtest chain.
The tests use public keys intended for testing and no public-network funds.
