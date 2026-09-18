# Simplicity, jets, and the size of a SHRINCS verifier

This report explains the discussion supplied on 18 September 2026. It also explains
what this repository can contribute.

Our experiment shows that shared functions can substantially reduce the size of a
SHRINCS program. It does not establish the smallest possible Simplicity program.
The two implementations use different signature parameters and execution systems.

## Signature and verifier

A signature is data that a signer supplies to authorize a message. A verifier is
the program that checks this data against a public key and the message.
Their sizes measure different things.

A node contains the implementation of a native signature instruction. A transaction
can select that instruction with a small opcode. A custom verifier can require
many instructions to perform the same task.

A commitment is a hash that identifies a program without containing the complete
program. It can keep the funding output small. The spending transaction must still
supply the required program and witness data. Simplicity can omit unused branches
from the program that it reveals. [Simplicity commitments and sharing](https://blog.blockstream.com/simplicity-sharing-of-witness-and-disconnect/)

The witness contains data needed to authorize a spend. Depending on the output,
this data can include signatures, a program, and proofs of program membership.
Thus, signature size alone does not give the size of a spend.

## Simplicity and bounded computation

Simplicity is a language for programs that check blockchain spending conditions.
Its core uses a small set of combinators. A combinator connects smaller expressions
to make a larger expression. Types specify the permitted input and output values.

The core excludes unrestricted loops and recursion. This design supports analysis
of termination and resource use. Formal semantics give precise rules for program
behavior. These rules help proofs, but they do not automatically prove that an
application is correct. [Simplicity paper](https://arxiv.org/abs/1711.03028)

SimplicityHL is a higher-level language that compiles to Simplicity. It has bounded
iteration operations, including `for_while`, `fold`, and `array_fold`. A programmer
can use these operations without writing each repeated step by hand.
[SimplicityHL built-in functions](https://docs.simplicity-lang.org/simplicityhl-reference/builtin/)

The size of the source text can differ greatly from the size of the encoded program.
A short loop in source text does not guarantee a small program on the blockchain.
Simplicity is available on Liquid. Its Liquid deployment does not activate it on
Bitcoin mainnet. [Liquid launch](https://blockstream.com/press-releases/2025-07-31-blockstream-launches-simplicity/)

## Unrolling and shared expressions

Loop unrolling replaces repeated execution with a fixed sequence of steps. If a
compiler copies the complete step 256 times, the encoded program can become large.

Shared definitions can reduce this duplication. The following example describes
the structure. It is not executable Simplicity or Script code.

```text
run1   = step
run2   = run1; run1
run4   = run2; run2
run8   = run4; run4
run16  = run8; run8
run32  = run16; run16
run64  = run32; run32
run128 = run64; run64
run256 = run128; run128
```

The program stores nine definitions. It still executes `step` 256 times.
Each definition calls only a lower-level definition. Thus, the call graph has no
cycle, and the execution count has a fixed bound.

Simplicity already supports shared expressions. Its encoding uses a directed
acyclic graph, or DAG. Multiple references can identify one expression without
storing a separate copy for each reference. Types and witness values affect
whether expressions can share a node. [Simplicity sharing rules](https://blog.blockstream.com/simplicity-sharing-of-witness-and-disconnect/)

Our proposed investigation concerns how much sharing this particular verifier can
use. For example, different embedded indices can make otherwise similar expressions
different. Passing an index as input might permit more sharing. This is a research
hypothesis; this repository contains no Simplicity measurement that confirms it.

## Jets and consensus changes

A jet is an optimized implementation of a specified Simplicity expression. A node
executes the native implementation instead of evaluating all the underlying
combinators. A supported jet also has a compact encoding. Thus, jets can reduce
both execution cost and encoded program size. [Simplicity jets](https://blog.blockstream.com/simplicity-jets-release/)

A general jet performs an operation that many applications use. Integer arithmetic
and SHA256 are examples. A specialized jet performs a narrower task, such as the
complete verification of one signature scheme.

The distinction is not absolute. A Merkle-path operation could serve several
signature schemes and other applications. Its usefulness would depend on its
parameters and on which programs can use it. The existing catalogue already
contains many general operations. [Jet catalogue](https://docs.simplicity-lang.org/documentation/jets/)

A network must agree on the meaning and acceptance rules of program encodings.
An implementation can execute an existing expression faster without changing those
rules. A new jet encoding requires agreement under the network's upgrade rules.

A soft fork restricts the set of blocks that consensus rules accept. Whether a
particular jet addition can use a soft fork depends on the existing extension rules.
A developer cannot assume that a new encoding needs only a local software change.
[Soft-fork definition](https://developer.bitcoin.org/glossary.html#term-Soft-fork)

A general operation that repeats an arbitrary program also needs precise semantics.
Its design must specify types, resource limits, and execution cost.
It is not automatically equivalent to an ordinary jet with fixed input and output types.

## SHRINCS and post-quantum signatures

SHRINCS combines a stateful signature path with a stateless backup path. Its main
components use hash functions. A Merkle tree combines many hash values into a root.
An authentication path supplies the sibling values needed to check membership
under that root. [Pinned SHRINCS specification](https://github.com/SHRINCS/shrincs-bip/blob/4cd63a6497a0ba7c5e99699b94d33973546d9e37/SHRINCS.md)

The stateful signer records which one-time signing keys it has used. This state
prevents unsafe reuse. The word “stateful” does not mean that the verifier must
maintain a database of all earlier signatures.

The stateless path permits signing from a static backup without that changing
signer state. Its signatures and verification work differ from the stateful path.
The backup path does not make incorrect use of the stateful path safe.
[SHRINCS design](https://github.com/SHRINCS/shrincs-bip/blob/4cd63a6497a0ba7c5e99699b94d33973546d9e37/SHRINCS.md)

SHRINCS-L changes the parameters for Liquid. It accepts larger signatures to reduce
the number of hash operations. Its report lists a 1,092-byte stateful example and
a 4,396-byte stateless signature. Our measured examples use 660 and 5,777 bytes,
respectively. These are different workloads. [SHRINCS-L report](https://delvingbitcoin.org/t/shrincs-324-byte-stateful-post-quantum-signatures-with-static-backups/2158/20)

Post-quantum signature schemes use different mathematical problems. ML-DSA and
Falcon use lattice constructions. Hash-based schemes use different operations.
Their security depends on assumptions about attacks, including quantum attacks.
Efficient SHRINCS verification does not establish efficient verification of every
post-quantum scheme. [NIST overview](https://www.nist.gov/news-events/news/2024/08/nist-releases-first-3-finalized-post-quantum-encryption-standards)

Isogeny-based schemes form another family. An isogeny is a mathematical map between
elliptic curves. SQIsign is an example of a signature scheme from this family.
Its verifier has different computational requirements. [SQIsign specification](https://csrc.nist.gov/csrc/media/Projects/pqc-dig-sig/documents/round-2/spec-files/sqisign-spec-round2-web.pdf)

## Bytes, weight, and execution cost

The following quantities answer different questions.

| Quantity | Meaning |
|---|---|
| Source bytes | Size of the text that a programmer writes |
| Program bytes | Size of the encoded instructions |
| Signature bytes | Size of the signature data |
| Witness bytes | Size of all witness data in the transaction |
| Transaction weight | Consensus size measure with a discount for witness data |
| Virtual bytes, or vbytes | Transaction weight divided by four, rounded up |
| Execution cost | Work charged by the execution system |

For Bitcoin, weight equals four times the base transaction size plus the witness
size. Equivalently, it equals three times the base size plus the total size.
Virtual size is `ceil(weight / 4)`. [BIP 141](https://github.com/bitcoin/bips/blob/master/bip-0141.mediawiki)

The supplied discussion gives approximate figures of 38 kB and 93 kB. The linked
Liquid report labels its detailed results as witness vbytes and kiloweight units.
Its first stateful row gives 37.755 kWU; its stateless row gives 92.450 kWU.
These figures alone do not establish the separate encoded program sizes.
[SHRINCS-L measurements](https://delvingbitcoin.org/t/shrincs-324-byte-stateful-post-quantum-signatures-with-static-backups/2158/20)

A valid comparison needs the same parameters and the same measured quantity.
It also needs equivalent message binding and acceptance rules. Dividing an
approximate program size by an unrelated signature size can give a misleading ratio.

## Assessment of the discussion

The discussion raises two separate requirements: expressive power and practical cost.
JW Weatherman's point agrees with the long-standing role of jets in Simplicity.
Jets were already part of its documented design. [Original Simplicity paper](https://arxiv.org/abs/1711.03028)

Robin Linus raises a valid engineering concern. A language can express a verifier
while producing transactions that users consider too expensive. Requiring a new
consensus feature for each application could limit independent experimentation.

However, a large current implementation does not prove a minimum possible size.
The Liquid report also links actual mainnet transactions. Thus, real execution has
occurred; broad economic use is a separate question. [Published Liquid transactions](https://delvingbitcoin.org/t/shrincs-324-byte-stateful-post-quantum-signatures-with-static-backups/2158/20)

Jonas Nick's proposed investigation is useful. Measurements of general operations
could show which changes help several applications. The next decision should depend
on those measurements, including results with the existing language and jets.

## What our experiment contributes

The GSR experiment uses general byte operations, arithmetic, SHA256, and shared
functions. GSR refers to the experimental Script-restoration fork pinned in this
repository. It adds no dedicated SHRINCS opcode.

The revised stateful verifier uses nine shared authentication functions. Each
function receives only the path portion that it needs. The parser still accepts
depths 1 through 255. [Implementation and tests](reports/REVIEW-FOLLOWUP.md)

| Same stateful transaction shape | Before, `6e1e807` | After, `891d77a` |
|---|---:|---:|
| Script bytes, including spending policy | 26,328 | 4,476 |
| Signature bytes | 660 | 660 |
| Complete transaction vbytes | 6,879 | 1,416 |

The Script size decreased by approximately 83%. The complete spend decreased by
79.4%. It uses approximately 36.3% of its execution allowance, with no padding.
The allowance is 10,000 times the actual transaction weight. [Measured results](reports/RESULTS.md)

These results establish a substantial reduction within our GSR implementation.
They do not establish that GSR is smaller than the best Simplicity implementation.
Simplicity already has expression sharing. Our experiment also uses a different
SHRINCS variant and an experimental execution system.

Our node runs on a local regtest chain. Regtest is an isolated test network under
the operator's control. The Liquid results concern a deployed network.
Those deployment conditions matter when interpreting the comparison.

The repository provides reproducible programs, test inputs, and transaction records.
These can support a matched comparison. The next research steps are:

1. Select identical signature parameters, messages, contexts, and acceptance rules.
2. Use equivalent transaction authorization in both implementations.
3. Measure program bytes, signature bytes, complete transaction size, and execution cost separately.
4. Test shared blocks with the existing Simplicity encoding and jets.
5. Measure the remaining costs of hashing, indexing, slicing, and data movement.
6. Evaluate proposed general jets across more than one application.

This work can help identify where compact programs are possible. A Simplicity
implementation with matching parameters remains future work. Ordinary Taproot also
retains a key path that is vulnerable to quantum attacks. Our SHRINCS leaf does
not make the complete output post-quantum safe. [Experiment limits](reports/AUDIT.md)
