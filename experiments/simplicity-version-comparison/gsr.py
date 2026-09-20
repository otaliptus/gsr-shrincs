"""GSR translation of the upstream Simplicity relation, separate from baseline.

The compiler never reads a witness. Fixed-width arithmetic follows upstream jets.
The top-level input is (signature fields, public key, message, unused root).
"""
from functools import reduce
from generator.script import Builder, Library, Ref, cat, cut, op, sha
from generator.verifier import Program, be, from_be

R = Ref
U32 = 2**32


def add(a, b): return op("ADD", a, b)
def sub(a, b): return op("SUB", a, b)
def mod(a, b): return op("MOD", a, b)
def shr(a, b): return op("RSHIFT", a, b)
def eq(a, b): return op("EQUAL", a, b)
def size(x): return op("SIZE", x)
def first16(x): return op("LEFT", sha(x), 16)


def addr(b, layer=0, tree=0, kind=0, key=0, height=0, index=0):
    return cat(be(b, layer, 4), be(b, tree, 12), be(b, kind, 4), be(b, key, 4), be(b, height, 4), be(b, index, 4))


def domain(kind):
    return bytes(16) + kind.to_bytes(4, "big") + bytes(12)


def chain_body(b):
    b.let("node", R("node"))
    for j in range(3):
        b.branch(op("LESSTHANOREQUAL", R("digit"), j), lambda b, j=j:
                 b.let("node", first16(cat(R("prefix"), j.to_bytes(4, "big"), R("node")))))
    b.finish(R("node"))


def wots_body(b):
    b.let("tips", b"")
    b.let("sum", 0)
    for i in range(64):
        digit = mod(shr(cut(R("mapped"), i // 4, 1), (3 - i % 4) * 2), 4)
        b.let("digit", digit)
        b.let("sum", add(R("sum"), R("digit")))
        prefix = cat(R("pad"), R("location"), be(b, R("kind"), 4), be(b, R("key"), 4), i.to_bytes(4, "big"))
        b.call("wots_chain", ("node", "digit", "prefix"), chain_body,
               (cut(R("values"), i * 16, 16), R("digit"), prefix), "tip")
        b.let("tips", cat(R("tips"), R("tip")))
        b.drop("tip")
    b.require(op("NUMEQUAL", R("sum"), 140))
    b.finish(first16(cat(R("pad"), R("location"), be(b, add(R("kind"), 1), 4), be(b, R("key"), 4), bytes(8), R("tips"))))


def wots(b, values, mapped, layer, tree, key, kind):
    b.call("wots", ("values", "mapped", "pad", "location", "key", "kind"), wots_body,
           (values, mapped, R("pad"), cat(be(b, layer, 4), be(b, tree, 12)), key, kind), "node")


def pair_body(b):
    b.branch(R("right"),
             lambda b: b.let("children", cat(R("sibling"), R("node"))),
             lambda b: b.let("children", cat(R("node"), R("sibling"))))
    b.finish(first16(cat(R("pad"), R("address"), R("children"))))


def pair(b, sibling, right, address):
    b.call("pair", ("node", "sibling", "right", "pad", "address"), pair_body,
           (R("node"), sibling, right, R("pad"), address), "node")


AUTH = ("node", "path", "height", "right", "pad")


def auth_block(b, level):
    if level == 0:
        pair(b, R("path"), R("right"), addr(b, kind=2, height=R("height")))
    else:
        split = 2**(level - 1)
        def call(b, path, height, right):
            b.call(f"stateful_path_{level-1}", AUTH, lambda b: auth_block(b, level - 1),
                   (R("node"), path, height, right, R("pad")), "node")
        call(b, cut(R("path"), 0, split * 16), R("height"), R("right"))
        b.branch(op("LESSTHAN", split * 16, size(R("path"))),
                 lambda b: call(b, cut(R("path"), split * 16, split * 16), mod(add(R("height"), split), U32), 1))
    b.finish(R("node"))


def stateful(b):
    b.require(op("LESSTHANOREQUAL", 1064, size(R("sig"))))
    b.require(op("LESSTHAN", size(R("sig")), 1064 + 512 * 16))
    b.require(op("NUMEQUAL", mod(sub(size(R("sig")), 1064), 16), 0))
    b.let("key", from_be(b, op("RIGHT", R("sig"), 4), 4))
    msg = first16(cat(domain(4), cut(R("sig"), 0, 32), R("pk"), R("msg")))
    b.let("mapped", first16(cat(addr(b, kind=3, key=R("key")), R("seed"), msg, cut(R("sig"), 32, 4))))
    wots(b, cut(R("sig"), 36, 1024), R("mapped"), 0, 0, R("key"), 0)
    b.let("path", cut(R("sig"), 1060, sub(size(R("sig")), 1064)))
    b.branch(op("NUMEQUAL", R("key"), 207), lambda b: b.let("height", 1),
             lambda b: b.let("height", mod(sub(U32 + 207, R("key")), U32)))
    b.let("node", R("node"))
    b.branch(op("LESSTHAN", 0, size(R("path"))), lambda b: b.call("stateful_path_9", AUTH, lambda b: auth_block(b, 9),
             (R("node"), R("path"), R("height"), op("NUMEQUAL", R("key"), 207), R("pad")), "node"))
    return cat(R("node"), R("unused"))


def fors_body(b):
    b.let("node", first16(cat(R("pad"), addr(b, tree=R("tree"), kind=6, key=R("tree_no"), index=R("index")), cut(R("part"), 0, 16))))
    for h in range(1, 23):
        pair(b, cut(R("part"), h * 16, 16), mod(R("index"), 2),
             addr(b, tree=R("tree"), kind=7, key=R("tree_no"), height=h, index=shr(R("index"), 1)))
        b.let("index", shr(R("index"), 1))
    b.finish(R("node"))


def xmss_body(b):
    mapped = first16(cat(addr(b, R("layer"), R("tree"), 13, R("key")), R("seed"), R("message"), cut(R("part"), 32, 4)))
    wots(b, cut(R("part"), 36, 1024), mapped, R("layer"), R("tree"), R("key"), 10)
    for h in range(1, 13):
        pair(b, cut(R("part"), 1060 + (h - 1) * 16, 16), mod(R("key"), 2),
             addr(b, R("layer"), R("tree"), 12, height=h, index=shr(R("key"), 1)))
        b.let("key", shr(R("key"), 1))
    b.finish(R("node"))


def stateless(b):
    b.exact(R("sig"), 4376)
    b.let("digest", sha(cat(domain(14), cut(R("sig"), 0, 32), R("pk"), R("msg"))))
    b.let("digest_int", from_be(b, R("digest"), 32))
    b.require(op("NUMEQUAL", mod(shr(R("digest_int"), 124), 2**22), 0))
    b.let("idx", mod(shr(from_be(b, cut(R("digest"), 16, 4), 4), 4), 2**24))
    b.let("roots", b"")
    for i in range(5):
        b.call("fors", ("part", "pad", "tree", "tree_no", "index"), fors_body,
               (cut(R("sig"), 32 + i * 368, 368), R("pad"), R("idx"), i,
                mod(shr(R("digest_int"), 234 - i * 22), 2**22)), "root")
        b.let("roots", cat(R("roots"), R("root")))
    b.let("node", first16(cat(R("pad"), addr(b, tree=R("idx"), kind=8), R("roots"))))
    b.let("key", mod(R("idx"), 4096))
    b.let("tree", shr(R("idx"), 12))
    for layer in range(2):
        b.call("xmss", ("part", "pad", "seed", "message", "layer", "tree", "key"), xmss_body,
               (cut(R("sig"), 1872 + layer * 1252, 1252), R("pad"), R("seed"), R("node"), layer, R("tree"), R("key")), "node")
        b.let("key", R("tree"))
        b.let("tree", shr(R("tree"), 12))
    return cat(R("unused"), R("node"))


def compile_verifier(mode, profile="full"):
    if mode not in ("stateful", "stateless") or profile not in ("baseline", "bytes", "full", "catfix"):
        raise ValueError("unknown configuration")
    global cat
    saved = cat
    if profile == "catfix":
        cat = lambda *xs: reduce(lambda a, b: op("CAT", a, b), xs) if xs else b""
    try:
        lib = Library(inline=profile == "bytes")
        b = Builder(("sig", "pk", "msg", "unused"), "baseline" if profile == "baseline" else "full", lib)
        b.exact(R("pk"), 32)
        b.exact(R("msg"), 32)
        b.exact(R("unused"), 16)
        b.let("seed", cut(R("pk"), 0, 16))
        b.let("pad", cat(R("seed"), bytes(48)))
        roots = (stateful if mode == "stateful" else stateless)(b)
        b.finish(eq(first16(cat(R("pad"), domain(16), roots)), cut(R("pk"), 16, 16)))
        prefix = lib.prefix() if profile in ("full", "catfix") else b""
        p = Program(prefix + bytes(b.code), "baseline" if profile == "baseline" else "full", mode, [], lib.functions)
        p.audit()
        return p
    finally:
        cat = saved
