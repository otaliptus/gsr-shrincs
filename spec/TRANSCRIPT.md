# GSR-SHRINCS laboratory transaction transcript v1

This is a distinct laboratory transcript, **not BIP-341 SIGHASH_ALL**. The message
passed to SHRINCS is SHA256 of the bytes below. The policy commits the 48-byte
public key, context, verifier layout, and allowed input count. It obtains fields
inside the transaction-aware VM using OP_TX, never from a witness-supplied digest.

Domain: ASCII `GSR-SHRINCS/transaction/v1` followed by a zero byte. Then the collated
output of selector `00 57 8b 22 2f 03`, in this exact order:

1. Transaction version uint32 LE; locktime uint32 LE; input count uint32 LE.
2. For each input, in transaction order: outpoint txid raw 32-byte internal
   serialization; outpoint index uint32 LE; authenticated spent amount uint64 LE;
   CompactSize-prefixed spent scriptPubKey; sequence uint32 LE.
3. Output count uint32 LE, followed by every output's amount uint64 LE and
   CompactSize-prefixed scriptPubKey, in transaction order.
4. Current input index uint32 LE; CompactSize-prefixed annex (required empty);
   executing TapLeaf hash (32 bytes); code-separator position uint32 LE
   (required ffffffff).

The TapLeaf hash is tagged SHA256 `TapLeaf` over `c2 || CompactSize(script length)
|| complete executing script`. It commits the key, context, and all verifier
instructions without a circular signature dependency. CompactSize is Bitcoin's
canonical variable-length serialization. There are no host-defined integer casts
in the Script transcript: OP_TX supplies its specified collated bytes.

The default policy requires exactly one input and exactly one initial signature
stack item. The several-input experiment explicitly compiles an upper bound of
four inputs, signs every input independently with all-input/all-output coverage,
and binds the current input index. It is a different committed policy, not an
accidental omission of coverage. All signatures share the transaction-wide budget.

Annexes reject in Script (and may first reject under relay policy). The compiler
emits no code separator, audits against that opcode, and checks the authenticated
position. Signatures, witness item counts/content, witness weight, and control
block are not included in the digest. Input scriptSig is excluded: the tested
native Taproot spends require it empty under consensus. Changing an amount changes
fees through the covered input/output values; no independent fee field exists.

## Output wrapper

The experiment uses ordinary Taproot with the documented BIP-341 NUMS internal
key and experimental 0xc2 leaves. That does **not** remove the key path, even for
a NUMS point, and is **not end-to-end post-quantum protection**. GSR is not itself
a quantum-safe output wrapper. An output rule removing or securing the key path
would be an additional consensus assumption, outside these measured ordinary
Taproot spends. No such extra rule is silently patched into the node.

The regtest node activates the pinned experimental script-restoration deployment
on an isolated local chain. It uses public test keys and no public-network funds.
