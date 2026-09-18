"""Small stack-checked compiler for the pinned unsigned GSR virtual machine.

Bytes constants are never encoded as signed Script numbers. Each expression leaves
one value; branches must have identical named stacks. Functions are nonrecursive.
"""

from dataclasses import dataclass
from functools import reduce

OPS = dict(
    DROP=0x75,
    DUP=0x76,
    PICK=0x79,
    ROLL=0x7A,
    SWAP=0x7C,
    CAT=0x7E,
    SUBSTR=0x7F,
    LEFT=0x80,
    RIGHT=0x81,
    SIZE=0x82,
    EQUAL=0x87,
    ADD=0x93,
    SUB=0x94,
    MUL=0x95,
    DIV=0x96,
    MOD=0x97,
    LSHIFT=0x98,
    RSHIFT=0x99,
    NUMEQUAL=0x9C,
    LESSTHAN=0x9F,
    LESSTHANOREQUAL=0xA1,
    MIN=0xA3,
    SHA256=0xA8,
    BYTEREV=0xCF,
    IF=0x63,
    ELSE=0x67,
    ENDIF=0x68,
    VERIFY=0x69,
    TOALTSTACK=0x6B,
    FROMALTSTACK=0x6C,
    DEFINE=0xBB,
    INVOKE=0xBC,
    DEPTH=0x74,
    TX=0xBD,
)
EXTRA = {"BYTEREV", "DEFINE", "INVOKE", "TX"}
# Expressions must produce exactly one value; stack-control opcodes use emit().
EXPR_ARITY = {
    "CAT": 2,
    "SUBSTR": 3,
    "LEFT": 2,
    "RIGHT": 2,
    "SIZE": 1,
    "EQUAL": 2,
    "ADD": 2,
    "SUB": 2,
    "MUL": 2,
    "DIV": 2,
    "MOD": 2,
    "LSHIFT": 2,
    "RSHIFT": 2,
    "NUMEQUAL": 2,
    "LESSTHAN": 2,
    "LESSTHANOREQUAL": 2,
    "MIN": 2,
    "SHA256": 1,
    "BYTEREV": 1,
    "TX": 1,
}


def uint(n):
    if type(n) is not int or n < 0:
        raise ValueError("GSR integers must be unsigned")
    return n.to_bytes((n.bit_length() + 7) // 8, "little")


def push(data):
    if isinstance(data, int):
        data = uint(data)
    if data == b"\x81":
        return b"\x01\x80\x51\x93"  # 128 + 1: OP_1NEGATE is reserved-success in v2
    if not data:
        return b"\x00"
    if len(data) == 1 and 1 <= data[0] <= 16:
        return bytes([0x50 + data[0]])
    n = len(data)
    if n < 76:
        return bytes([n]) + data
    if n <= 255:
        return b"\x4c" + bytes([n]) + data
    if n <= 65535:
        return b"\x4d" + n.to_bytes(2, "little") + data
    return b"\x4e" + n.to_bytes(4, "little") + data


@dataclass(frozen=True)
class Ref:
    name: str


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple


def op(name, *args):
    return Expr(name, args)


def cat(*args):
    return reduce(lambda a, b: op("CAT", a, b), args, b"")


def cut(value, start, size):
    return op("SUBSTR", value, start, size)


def sha(value):
    return op("SHA256", value)


class Builder:
    def __init__(self, inputs=(), profile="full", library=None):
        self.stack = list(inputs)
        self.code = bytearray()
        self.profile = profile
        self.library = library
        self.source_map = []
        self.peak_entries = len(inputs)

    def mark(self, label):
        self.source_map.append(
            {"offset": len(self.code), "component": label, "stack": self.stack.copy()}
        )

    def emit(self, name):
        if self.profile == "baseline" and name in EXTRA:
            raise ValueError(f"{name} is outside baseline")
        self.code.append(OPS[name])

    def literal(self, value):
        self.code.extend(push(value))
        self.stack.append(None)
        self.peak_entries = max(self.peak_entries, len(self.stack))

    def expr(self, value):
        if isinstance(value, Ref):
            if value.name not in self.stack:
                raise ValueError(f"missing stack value {value.name}: {self.stack}")
            self.literal(len(self.stack) - 1 - self.stack.index(value.name))
            self.emit("PICK")
        elif isinstance(value, Expr):
            if EXPR_ARITY.get(value.op) != len(value.args):
                raise ValueError(f"invalid expression contract: {value.op}")
            for arg in value.args:
                self.expr(arg)
            self.emit(value.op)
            if value.op == "SIZE":  # SIZE preserves operand; remove it beneath size
                self.emit("SWAP")
                self.emit("DROP")
            self.stack = self.stack[: -len(value.args)] + [None]
        else:
            self.literal(value)
        self.peak_entries = max(self.peak_entries, len(self.stack))

    def let(self, name, value):
        self.expr(value)
        if name in self.stack:
            idx = self.stack.index(name)
            self.literal(len(self.stack) - 1 - idx)
            self.emit("ROLL")
            self.stack.pop()
            self.stack.pop(idx)
            self.emit("DROP")
        self.stack[-1] = name
        return Ref(name)

    def drop(self, name):
        idx = self.stack.index(name)
        self.literal(len(self.stack) - 1 - idx)
        self.emit("ROLL")
        self.stack.pop()
        self.stack.pop(idx)
        self.emit("DROP")

    def require(self, expr):
        self.expr(expr)
        self.emit("VERIFY")
        self.stack.pop()

    def exact(self, expr, size):
        self.require(op("NUMEQUAL", op("SIZE", expr), size))

    def branch(self, condition, yes, no=lambda b: None):
        self.expr(condition)
        self.emit("IF")
        self.stack.pop()
        before = self.stack.copy()
        yes(self)
        after = self.stack.copy()
        self.emit("ELSE")
        self.stack = before
        no(self)
        if self.stack != after:
            raise ValueError(f"inconsistent branch stacks: {after} != {self.stack}")
        self.emit("ENDIF")

    def call(self, name, inputs, compile_body, args, output):
        inputs, args = tuple(inputs), tuple(args)
        if len(inputs) != len(args):
            raise ValueError(
                f"{name}: expected {len(inputs)} arguments, got {len(args)}"
            )
        if len(set(inputs)) != len(inputs):
            raise ValueError(f"{name}: duplicate input names")
        if self.profile == "full" and not self.library.inline:
            fid = self.library.define(name, inputs, compile_body)
            for arg in args:
                self.expr(arg)
            self.literal(fid)
            self.emit("INVOKE")
            self.stack = self.stack[: -len(args) - 1] + [None]
        else:
            # Inline using an isolated frame. Outer values are never addressed by body.
            sub = Builder(inputs, self.profile, self.library)
            compile_body(sub)
            if sub.stack != ["result"]:
                raise ValueError(f"{name}: function must return one result")
            for arg in args:
                self.expr(arg)
            offset = len(self.code)
            self.source_map.extend(
                dict(row, offset=row["offset"] + offset) for row in sub.source_map
            )
            self.code.extend(sub.code)
            self.stack = (self.stack[: -len(args)] if args else self.stack) + [None]
            self.peak_entries = max(
                self.peak_entries, len(self.stack) + sub.peak_entries
            )
        if output in self.stack:
            idx = self.stack.index(output)
            self.literal(len(self.stack) - 1 - idx)
            self.emit("ROLL")
            self.stack.pop()
            self.stack.pop(idx)
            self.emit("DROP")
        self.stack[-1] = output
        return Ref(output)

    def finish(self, value):
        self.expr(value)
        self.emit("TOALTSTACK")
        self.stack.pop()
        for _ in self.stack:
            self.emit("DROP")
        self.emit("FROMALTSTACK")
        self.stack = ["result"]


class Library:
    def __init__(self, inline=False):
        self.inline = inline
        self.functions = {}
        self.contracts = {}
        self.active = set()

    def define(self, name, inputs, compile_body):
        if name in self.active:
            raise ValueError("recursive function")
        inputs = tuple(inputs)
        if len(set(inputs)) != len(inputs):
            raise ValueError(f"{name}: duplicate input names")
        # Compile every requested definition. Fresh lambdas are legitimate;
        # equality means the same input contract and emitted implementation.
        previous = self.functions.copy(), self.contracts.copy()
        self.active.add(name)
        try:
            sub = Builder(inputs, "full", self)
            sub.mark(name)
            compile_body(sub)
            if sub.stack != ["result"]:
                raise ValueError(f"{name}: function must return one result")
            if name in self.functions:
                if self.contracts[name] != inputs or self.functions[name][1] != bytes(
                    sub.code
                ):
                    raise ValueError(f"conflicting definition: {name}")
                return self.functions[name][0]
            fid = len(self.functions)
            if fid > 255:
                raise ValueError("too many functions")
            self.functions[name] = (fid, bytes(sub.code), sub.source_map)
            self.contracts[name] = inputs
            return fid
        except Exception:
            self.functions, self.contracts = previous
            raise
        finally:
            self.active.remove(name)

    def prefix(self):
        return b"".join(
            push(code) + push(fid) + bytes([OPS["DEFINE"]])
            for fid, code, _ in self.functions.values()
        )


def audit(code, profile="full", function_bodies=()):
    """Reject every opcode outside our compiler allowlist, including dead branches.

    Defined bodies must be passed separately: arbitrary pushed hash bytes are data.
    """
    allowed = {v for k, v in OPS.items() if profile != "baseline" or k not in EXTRA}
    for program in (code, *function_bodies):
        pos = 0
        while pos < len(program):
            opcode = program[pos]
            pos += 1
            if opcode <= 75:
                pos += opcode
            elif opcode in (76, 77, 78):
                width = 1 << (opcode - 76)
                if pos + width > len(program):
                    raise ValueError("truncated push length")
                n = int.from_bytes(program[pos : pos + width], "little")
                pos += width + n
            elif 81 <= opcode <= 96:
                pass
            elif opcode not in allowed:
                raise ValueError(f"opcode outside allowlist: {opcode:02x}")
            if pos > len(program):
                raise ValueError("truncated pushed value")
