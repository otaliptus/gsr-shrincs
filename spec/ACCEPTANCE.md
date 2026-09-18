# Accepted inputs and verification rules

This laboratory implements the pinned `shrincs_verify` relation in Bitcoin Script.
Messages have exactly 32 bytes, and public keys have exactly 48 bytes.
The default context is the 24-byte string `after-quantum/gsr-lab/v1`.
The generated program commits this context.

Generation can select another context with zero through 255 bytes.
A different context produces a different policy.
The witness cannot select the context.
Context framing has this format:

```text
00 || uint8(context_length) || context
```

The public key has this format:

```text
pk = pk_seed[16] || sl_root[16] || sf_root[16]
```

Both modes bind both roots.
Hash comparisons require byte equality.
Integers in addresses and signatures use fixed-width big-endian encoding.
GSR arithmetic uses unsigned little-endian byte strings.
Conversions preserve leading and trailing zero bytes.

## Reference mapping

| Requirement | Pinned reference (`impl/shrincs.py`) | Compiler |
|---|---|---|
| Public key/message lengths; mode and exact signature length | `shrincs_verify` (plus lab message restriction) | `compile_verifier`, mode bodies |
| Stateful location and range | `shrincs_verify`, `fxmss_pubkey_from_sig` | `stateful_body` |
| Context and both roots | `shrincs_verify`, `H_msg_sf`, `H_msg_sl` | `h_msg_sf`, `h_msg_sl`, mode bodies |
| 22-byte addresses, domain byte at offset 9 | `F`, `H`, `T_sf`, `T_sl`, `T_k` | `hash16`, address expressions |
| WOTS+C supplied counter and digit sum | `H_grind`, `wots_c_map_digest`, `wots_c_pubkey_from_sig` | `h_grind`, `wots_body(True)` |
| Bounded chain suffix | `wots_c_chain_iter`, `wots_tw_chain_iter` | `chain_body` |
| Authentication order/indices | `fxmss_pubkey_from_sig`, `xmss_pubkey_from_sig` | `pair_body`, mode bodies |
| FORS recovery and compression | `fors_pubkey_from_sig` | `fors_body` |
| WOTS-TW checksum and hypertree | `wots_tw_pubkey_from_sig`, `hypertree_verify` | `wots_body(False)`, `stateless_body` |

## Stateful encoding

The indicator `h` has a value from 0 through 254.
The depth is `d = 255 - h`, with a range from 1 through 255.
The index width is `w = ceil(min(d,64)/8)` bytes.
The signature has exactly this format:

```text
h[1] || R[16] || index[w] || counter[2] || chains[512] || authentication[16*d]
```

The length is `531+w+16*d` bytes, with a range from 548 through 4,619.
The index must satisfy `0 <= index < 2**min(d,64)`.
Unused high bits must be zero.
The location is `h[1] || index_BE[8]`.

The bound message is `framing || sl_root || message`.
The nested SHA256 construction of `H_msg_sf` includes `R`, `pk_seed`, `sf_root`,
`location`, and the bound message.
`H_grind` has this definition:

```text
SHA256(pk_seed || zero[48] || location || 16_hex || digest[32] || zero[4]
       || counter_BE[2])[:16]
```

The 32 digits use the high nibble first and must sum to 240.
The verifier accepts any uint16 counter that meets this condition.
It does not search for a counter or require the first valid counter.

Each of the 32 WOTS+C chains ends at index 15.
The chains use type 16 and reserved zero bytes.
Endpoint compression uses type 17.
FXMSS parents use height `h+k+1`, index `index>>(k+1)`, type 18, and twelve zero bytes.
Bit `k` of the index determines child order.
The recovered root must equal `sf_root` byte for byte.

## Stateless encoding

Indicator 255 selects a signature of exactly 5,777 bytes:

```text
ff || R[16] || FORS[2240] || hypertree[3520]
```

The bound message is `framing || sf_root || message`.
`H_msg_sl` also binds `sl_root`.
The digest fields have the following meanings.

| Digest bytes | Meaning |
|---|---|
| 0 through 16 | The 130 high-order FORS bits. The final six bits are unused. |
| 17 through 21 | Big-endian integer modulo `2**36`, which selects the tree. |
| 22 through 23 | Big-endian integer modulo 512, which selects the leaf. |
| Remaining bytes | Unused, as specified by the pinned reference. |

FORS uses ten trees of height 13.
Type 3 identifies nodes, and type 4 identifies root compression.
Each of the five hypertree layers has an XMSS tree of height 9.

WOTS-TW uses 32 message digits and three checksum digits.
The checksum encodes `480-sum(message_digits)` in big-endian base 16.
Types 0, 1, and 2 identify chains, endpoint compression, and XMSS nodes, respectively.
The final root must equal `sl_root` byte for byte.
Script computes every SHA256 chain and tree step.

## Rejection and final result

The standalone initial stack contains signature, public key, and message, from bottom to top.
Script performs all parsing and cryptographic checks.
The generated program leaves exactly one truth value.
The final-result checker consumes that value, so successful execution leaves an empty stack.
Extra initial items fail the clean-stack check.

Exact-length checks occur before slicing.
This order matters because the VM clamps slices to available data instead of rejecting them.

Malformed encodings, false comparisons, unsupported mode-specific paths, and incorrect digit sums cause rejection.
Budget exhaustion has a distinct VM result.
Missing executables, timeouts, process errors, malformed JSON, and invalid response fields are harness errors.
These errors do not count as successful negative signature tests.

The adapter requires an allowance within the uint64 range.
Large standalone allowances test semantics only.
Transaction feasibility uses an allowance of 10,000 times the actual serialized transaction weight.

The opcode auditor checks every generated function body.
It rejects unknown opcodes and reserved opcodes that would cause immediate success.
These include `OP_1NEGATE` in this fork.
The compiler constructs byte `0x81` as `128+1` because its legacy minimal-push opcode is unavailable.
The transaction policy uses fixed version-zero `OP_TX` selectors.

## Laboratory limits

The pinned sources are experimental and do not define activated Bitcoin mainnet consensus.
Reference signing uses public test seeds only.
The verifier cannot enforce one-time signer state, rollback protection, seed custody,
backup safety, or scheme security.

Synthetic boundary inputs use genuine WOTS signing and computed roots with synthetic siblings.
They do not imply generation of enormous complete trees.
The implementation has no independent external audit or formal proof.
