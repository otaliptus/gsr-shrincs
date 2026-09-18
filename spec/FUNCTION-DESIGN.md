# Function design requirements

Status: proposed requirements. This document changes no opcode or consensus rule.

The current fork defines a function from stack bytes. A call shares the main stack and alternate stack with its caller.
The compiler checks its own argument and result contracts. The VM does not enforce those compiler contracts.

The proposed design makes code identifiable before execution. It also makes each function's stack access explicit.

## Code and commitments

Store function definitions in a defined code region of the committed program.
Do not derive executable bodies from witness values or arithmetic results.
A function identifier must select an immutable definition.
Specify whether calls use literal identifiers. Dynamic identifiers prevent an exact static call graph unless analysis proves their possible values.

A literal pushed body can already be committed by an enclosing Script.
The required property is fixed executable code, not a particular spelling of the definition instruction.

Validate definition structure before execution. Specify duplicate identifiers, missing definitions, forward references, and unused definitions.
Opcode validation must parse instructions. Bytes inside data pushes are data, even if their values match opcode numbers.

## Call frames

A frame is the set of values a function can access during a call.
Specify an argument count and a result count for each definition.
Reject a call that supplies too few arguments or returns the wrong result count.

The function can access its arguments and local values. It cannot remove or inspect the caller's other values.
Give each frame its own alternate stack, or prohibit alternate-stack use inside functions.
Require the local alternate stack to be empty on return if it exists.

Specify argument ownership and copying. An implementation detail must not change charged resource use.
Count frame storage, arguments, local values, and function storage against explicit limits.

The current SHRINCS compiler returns one value from each function. It should be the first consumer of the new frame rules.
Test zero-argument helpers, nested authentication functions, and variable-length path inputs.

## Control flow and failure

Keep the no-recursion requirement. An acyclic static call graph is stronger than rejecting only calls to currently active functions.
Define a maximum call depth and retain the cumulative executed-body limit.

An unsupported instruction in a validated function body must cause an error under this proposed design.
It must not make the enclosing spend succeed.
Specify whether all committed bodies are checked, including uncalled bodies and untaken branches. This proposal requires that check.

Specify interactions with code separators and transaction context.
Transaction introspection must retain the original spending context. A nested function must not create a different signed policy accidentally.

These rules can change the acceptance of existing programs. Record the compatibility boundary and activation assumptions before deployment work.

## Static analysis

Fixed definitions and call targets permit the following checks:

- Definition and instruction validity.
- Call-graph cycles and maximum call depth.
- Argument and result counts.
- Maximum expanded body execution, for bounded call paths.
- Stack effects, where every branch has a compatible contract.

They do not automatically prove exact memory use or varops bounds.
Those bounds also require limits on value lengths, arithmetic widths, and data-dependent operations.
The analysis must include both branch outcomes and checked input constraints.

This design does not claim equivalence with Simplicity's type system or proofs.
It identifies properties that can be checked for this VM.

## Acceptance before implementation

The regression harness must first replay the frozen workload successfully.
Then compile the SHRINCS verifier under the new calling convention.
Compare acceptance, program size, complete spend size, memory, calls, and execution costs.
Keep function changes separate from cost-table changes until each result is understood.

Source: [pinned interpreter](https://github.com/jmoik/bitcoin/blob/d2799052604eb138c5a79acf88514a0c8b07f4ef/src/script/interpreter.cpp).
