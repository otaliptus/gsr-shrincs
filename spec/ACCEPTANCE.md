# Accepted relation and scope

This laboratory implements the pinned `shrincs_verify` relation in Bitcoin Script,
with exactly 32 message bytes and exactly 48 public-key bytes. The default context
is the 24 bytes `after-quantum/gsr-lab/v1`, committed in the generated program.
Generation can explicitly select a different context of at most 255 bytes; that
produces a different policy, not a witness-selected context. Context framing is
`00 || uint8(context_length) || context`.

`pk = pk_seed[16] || sl_root[16] || sf_root[16]`. Both roots are bound in both modes.
All hash comparisons use byte equality, not numeric equality. All integers in
addresses/signatures are fixed-width **big endian**. GSR arithmetic uses unsigned
little-endian byte strings; conversion preserves leading/trailing zero bytes.

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

Indicator `h` is 0..254; depth `d=255-h` is 1..255. Let `w=ceil(min(d,64)/8)`.
The signature is exactly `h[1] || R[16] || index[w] || counter[2] || chains[512]
|| authentication[16*d]`, or `531+w+16*d` bytes (548..4619).
`0 <= index < 2**min(d,64)`; unused high bits must be zero.

`location=h[1] || index_BE[8]`. The contextualized message is framing || sl_root
|| message. `H_msg_sf` includes R, pk_seed, **sf_root**, location, and that bound
message in its nested SHA256 construction. `H_grind` is
`SHA256(pk_seed || zero[48] || location || 16_hex || digest[32] || zero[4]
|| counter_BE[2])[:16]`. Its 32 high-nibble-first digits must sum to 240.
Every uint16 counter satisfying that condition is accepted; the verifier does
not require it to be the first working counter and never searches for one.

The 32 WOTS+C chains each finish at index 15, using type 16 and reserved zeros;
compression uses type 17. FXMSS parents use height h+k+1, index>>(k+1), type 18,
and twelve zero bytes. Child ordering uses index bit k. The recovered root must
be byte-equal to sf_root.

## Stateless encoding

Indicator 255 selects exactly 5777 bytes:
`ff || R[16] || FORS[2240] || hypertree[3520]`.
The contextualized message is framing || sf_root || message. H_msg_sl also binds
sl_root. Digest bytes 0..16 hold 130 high-order FORS bits (the final six bits are
unused); bytes 17..21 interpreted big endian modulo 2**36 select the tree; bytes
22..23 modulo 512 select the leaf. The remaining digest bytes are unused exactly
as in the pinned specification.

FORS has ten height-13 trees, types 3 (nodes) and 4 (roots). Each of five hypertree
layers has a height-9 XMSS tree. WOTS-TW has 32 message digits and three checksum
digits encoding `480-sum(message_digits)` in big-endian base 16. Types 0, 1 and 2
identify WOTS-TW chains, endpoint compression, and XMSS nodes. The final root
must be byte-equal to sl_root. No SHA256 chain or tree step is replaced by a hint.

## Rejection and final result

Standalone stack, bottom to top: signature, public key, message. All parsing and
cryptographic checks run inside Script. Generated Script leaves exactly one
truth value; the pinned final-result checker consumes it, yielding an empty
stack on acceptance. Extra initial items fail clean-stack checking. Exact-length
checks precede slices, since the VM's slice operation clamps rather than rejects.

A malformed encoding, false comparison, unsupported mode-specific path, or failed
constant sum rejects. Budget exhaustion is a distinct VM result. Missing binaries,
timeouts, process errors, malformed JSON, and invalid response fields are harness
errors, never successful negative signature tests. The adapter requires a bounded
uint64 allowance. Large standalone allowances test semantics only; transaction
feasibility is evaluated with 10,000 times the actual serialized transaction weight.

The opcode auditor rejects all unknown/reserved-success opcodes, including
OP_1NEGATE, and checks every generated function body. The byte 0x81 cannot use
its legacy minimal-push opcode in this fork: the compiler constructs it as
128+1. OP_TX selectors are fixed, version-zero constants in the transaction wrapper.

## Laboratory limitations

These are experimental source pins, not activated Bitcoin consensus. Reference
signing is used only with public test seeds. This verifier cannot enforce one-time
signer state, rollback protection, seed custody, backup safety, or scheme security.
Synthetic boundary fixtures use genuine WOTS signing and computed roots with
synthetic siblings; they are not claims of generating enormous complete trees.
No independent external review or formal proof is claimed.
