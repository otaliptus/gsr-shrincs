"""Laboratory extension: compile the verifier with OP_MULTI, without touching the audited profiles.

Two variants build on the ``full`` profile (byte reversal and shared functions):

- ``catfix``: concatenation starts from its first part instead of an empty push.
  The audited compiler emits ``<> a CAT b CAT ...``; this emits ``a b CAT ...``.
- ``multi``: the same, plus OP_MULTI wherever it applies: one MULTI SHA256 over the
  parts of every hashed concatenation, MULTI CAT for concatenations of three or more
  parts that are not hashed, and MULTI DROP for cleanup runs of three or more items.

The extension patches the compiler's builder and helpers only for the duration of a
compile, so importing this module changes nothing for the audited programs.
"""

from contextlib import contextmanager
from functools import reduce

from generator import script, transaction, verifier
from generator.script import Builder, Expr, OPS, EXTRA, push

OPS.setdefault("MULTI", 0xBF)
EXTRA.add("MULTI")
MULTI_MIN_PARTS = 3


def flatten(args, kind):
    parts = []
    for arg in args:
        if isinstance(arg, Expr) and arg.op == kind:
            parts.extend(flatten(arg.args, kind))
        else:
            parts.append(arg)
    return tuple(parts)


def cat_fixed(*args):
    if not args:
        return b""
    return reduce(lambda a, b: Expr("CAT", (a, b)), args)


def cat_multi(*args):
    parts = flatten(args, "MULTICAT")
    if len(parts) >= MULTI_MIN_PARTS:
        return Expr("MULTICAT", parts)
    return cat_fixed(*parts)


def sha_multi(value):
    if isinstance(value, Expr) and value.op == "MULTICAT":
        return Expr("MULTISHA", value.args)
    if isinstance(value, Expr) and value.op == "CAT":
        parts = flatten((value,), "CAT")
        if len(parts) >= MULTI_MIN_PARTS:
            return Expr("MULTISHA", parts)
    return Expr("SHA256", (value,))


class MultiBuilder(Builder):
    """Builder that emits OP_MULTI forms for the two variable-arity expression kinds."""

    def expr(self, value):
        if isinstance(value, Expr) and value.op in ("MULTICAT", "MULTISHA"):
            target = "CAT" if value.op == "MULTICAT" else "SHA256"
            for arg in value.args:
                self.expr(arg)
            self.literal(len(value.args))
            self.emit("MULTI")
            self.code.append(OPS[target])
            self.stack = self.stack[: -len(value.args) - 1] + [None]
            self.peak_entries = max(self.peak_entries, len(self.stack))
            return
        super().expr(value)

    def finish(self, value):
        self.expr(value)
        self.emit("TOALTSTACK")
        self.stack.pop()
        if len(self.stack) >= MULTI_MIN_PARTS:
            self.literal(len(self.stack))
            self.emit("MULTI")
            self.code.append(OPS["DROP"])
        else:
            for _ in self.stack:
                self.emit("DROP")
        self.emit("FROMALTSTACK")
        self.stack = ["result"]


@contextmanager
def variant(name):
    if name not in ("catfix", "multi"):
        raise ValueError("unknown variant")
    saved = (script.Builder, verifier.Builder, transaction.Builder, verifier.cat, verifier.sha)
    try:
        if name == "multi":
            script.Builder = verifier.Builder = transaction.Builder = MultiBuilder
            verifier.cat, verifier.sha = cat_multi, sha_multi
        else:
            verifier.cat = cat_fixed
        yield
    finally:
        script.Builder, verifier.Builder, transaction.Builder, verifier.cat, verifier.sha = saved


def compile_verifier(name, mode="unified", context=verifier.CONTEXT):
    with variant(name):
        program = verifier.compile_verifier("full", mode, context)
    program.profile = name
    program.audit = lambda: script.audit(program.code, "full", [v[1] for v in program.functions.values()])
    program.audit()
    return program


def compile_policy(name, public_key, mode="unified", max_inputs=1, context=verifier.CONTEXT):
    with variant(name):
        program = transaction.compile_policy(public_key, context, mode, max_inputs, "full")
    program.profile = name
    return program


def multi_uses(code, function_bodies=()):
    """Count OP_MULTI occurrences by target in a program and its function bodies."""
    counts = {}
    for program in (code, *function_bodies):
        pos = 0
        while pos < len(program):
            opcode = program[pos]
            pos += 1
            if opcode <= 75:
                pos += opcode
            elif opcode in (76, 77, 78):
                width = 1 << (opcode - 76)
                pos += width + int.from_bytes(program[pos : pos + width], "little")
            elif opcode == OPS["MULTI"]:
                target = program[pos]
                pos += 1
                name = {OPS["CAT"]: "CAT", OPS["SHA256"]: "SHA256", OPS["DROP"]: "DROP"}.get(target, hex(target))
                counts[name] = counts.get(name, 0) + 1
    return counts
