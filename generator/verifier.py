"""SHRINCS -> GSR Script translation, pinned to vendor/shrincs-spec/impl/shrincs.py.

Generation depends on the scheme and feature profile, never on signature contents.
No host-provided digest or chain hint participates in the verification relation.
"""
from dataclasses import dataclass
from .script import Builder, Library, Ref, audit, cat, cut, op, sha

CONTEXT = b'after-quantum/gsr-lab/v1'
R = Ref

def add(a,b): return op('ADD',a,b)
def sub(a,b): return op('SUB',a,b)
def mod(a,b): return op('MOD',a,b)
def shr(a,b): return op('RSHIFT',a,b)
def eq(a,b): return op('EQUAL',a,b)
def numeq(a,b): return op('NUMEQUAL',a,b)

def reverse(b, value, width):
    if b.profile == 'full':
        return op('BYTEREV',value)
    # Baseline: exact byte slices, including every leading/trailing zero.
    return cat(*(cut(value,i,1) for i in range(width-1,-1,-1)))

def be(b, value, width):
    return reverse(b, op('LEFT',cat(value,bytes(width)),width), width)

def from_be(b, value, width):
    return reverse(b,value,width)

def hash16(pad, address, value):
    return op('LEFT',sha(cat(pad,address,value)),16)

def h_grind(pad, location, digest, counter_bytes):
    return op('LEFT',sha(cat(pad,location,b'\x16',digest,bytes(4),counter_bytes)),16)

def h_msg_sf(randomizer,seed,root,location,bound):
    return sha(cat(randomizer,seed,sha(cat(randomizer,seed,root,location,bound)),location))

def h_msg_sl(randomizer,seed,root,bound):
    return sha(cat(randomizer,seed,sha(cat(randomizer,seed,root,bound)),bytes(4)))

def chain_body(b):
    b.mark('bounded_chain_suffix')
    b.exact(R('node'),16)
    b.exact(R('prefix'),18)
    b.exact(R('pad'),64)
    b.require(op('LESSTHAN',R('digit'),16))
    b.let('node',R('node'))  # stable branch stack order
    # Only the supplied digit chooses the bounded suffix. No signing search.
    for j in range(15):
        b.branch(op('LESSTHANOREQUAL',R('digit'),j),
                 lambda b,j=j: b.let('node',hash16(R('pad'),cat(R('prefix'),j.to_bytes(4,'big')),R('node'))))
    b.finish(R('node'))

def wots_body(b, constant_sum):
    b.mark('wots_c_pubkey_from_sig' if constant_sum else 'wots_tw_pubkey_from_sig')
    b.exact(R('sig'),514 if constant_sum else 560)
    b.exact(R('msg'),32 if constant_sum else 16)
    b.exact(R('location'),9)
    b.exact(R('keypair'),4)
    if constant_sum:
        b.let('mapped',h_grind(R('pad'),R('location'),R('msg'),cut(R('sig'),0,2)))
    else:
        b.let('mapped',R('msg'))
    b.let('digits',b'')
    b.let('sum',0)
    for i in range(32):
        value = cut(R('mapped'),i//2,1)
        value = shr(value,4) if i%2 == 0 else mod(value,16)
        b.let('digit',value)
        b.let('digits',cat(R('digits'),be(b,R('digit'),1)))
        b.let('sum',add(R('sum'),R('digit')))
    b.drop('digit')
    if constant_sum:
        b.require(numeq(R('sum'),240))
    else:
        b.let('checksum',sub(480,R('sum')))
        for shift in (8,4,0):
            b.let('digits',cat(R('digits'),be(b,mod(shr(R('checksum'),shift),16),1)))
    b.let('tips',b'')
    for i in range(32 if constant_sum else 35):
        b.call('chain',('node','digit','prefix','pad'),chain_body,
               (cut(R('sig'),(2 if constant_sum else 0)+16*i,16),cut(R('digits'),i,1),
                cat(R('location'),bytes([16 if constant_sum else 0]),R('keypair'),i.to_bytes(4,'big')), R('pad')), 'tip')
        b.let('tips',cat(R('tips'),R('tip')))
        b.drop('tip')
    b.finish(hash16(R('pad'),cat(R('location'),bytes([17 if constant_sum else 1]),R('keypair'),bytes(8)),R('tips')))

WOTS_ARGS = ('sig','msg','pad','location','keypair')

def wots(b, sig, msg, location, keypair, constant_sum, output):
    return b.call('wots_c' if constant_sum else 'wots_tw',WOTS_ARGS,
                  lambda b: wots_body(b,constant_sum),(sig,msg,R('pad'),location,keypair),output)

def pair_body(b):
    b.mark('merkle_parent')
    # Parity chooses byte concatenation order; numeric equality is never used for nodes.
    b.branch(mod(R('index'),2),
             lambda b:b.let('children',cat(R('sibling'),R('node'))),
             lambda b:b.let('children',cat(R('node'),R('sibling'))))
    b.finish(hash16(R('pad'),R('address'),R('children')))

def pair(b, node, sibling, index, address, output):
    return b.call('merkle_pair',('node','sibling','index','address','pad'),pair_body,
                  (node,sibling,index,address,R('pad')),output)

def stateful_body(b):
    b.mark('shrincs_verify.stateful_parser')
    b.let('height',cut(R('sig'),0,1))
    b.require(op('LESSTHAN',R('height'),255))
    b.let('depth',sub(255,R('height')))
    b.let('width',op('DIV',add(op('MIN',R('depth'),64),7),8))
    b.exact(R('sig'),add(add(531,R('width')),op('MUL',R('depth'),16)))
    # Left-pad the exact big endian index to eight bytes before converting it.
    b.let('index_be',cat(op('LEFT',bytes(8),sub(8,R('width'))),cut(R('sig'),17,R('width'))))
    b.let('index',from_be(b,R('index_be'),8))
    b.require(op('LESSTHAN',R('index'),op('LSHIFT',1,op('MIN',R('depth'),64))))
    b.let('location',cat(R('height'),R('index_be')))
    b.let('randomizer',cut(R('sig'),1,16))
    b.let('bound',cat(R('framing'),cut(R('pk'),16,16),R('msg')))
    b.let('digest',h_msg_sf(R('randomizer'),R('seed'),cut(R('pk'),32,16),R('location'),R('bound')))
    wots(b,cut(R('sig'),add(17,R('width')),514),R('digest'),R('location'),bytes(4),True,'node')
    b.mark('fxmss_pubkey_from_sig.authentication_path')
    for k in range(255):
        def step(b,k=k):
            pair(b,R('node'),cut(R('sig'),add(add(531,R('width')),16*k),16),shr(R('index'),k),
                 cat(be(b,add(R('height'),k+1),1),be(b,shr(R('index'),k+1),8),b'\x12',bytes(12)),'node')
        b.branch(op('LESSTHAN',k,R('depth')),step)
    b.finish(eq(R('node'),cut(R('pk'),32,16)))

def fors_body(b):
    b.mark('fors_pubkey_from_sig')
    b.exact(R('sig'),2240)
    b.exact(R('digest'),17)
    b.let('digest_num',from_be(b,R('digest'),17))
    b.let('roots',b'')
    for i in range(10):
        b.let('index',add(i*8192,mod(shr(R('digest_num'),136-13*(i+1)),8192)))
        b.let('node',hash16(R('pad'),cat(R('location'),b'\x03',R('keypair'),bytes(4),be(b,R('index'),4)),cut(R('sig'),i*224,16)))
        for k in range(13):
            pair(b,R('node'),cut(R('sig'),i*224+16*(k+1),16),shr(R('index'),k),
                 cat(R('location'),b'\x03',R('keypair'),(k+1).to_bytes(4,'big'),be(b,shr(R('index'),k+1),4)),'node')
        b.let('roots',cat(R('roots'),R('node')))
        b.drop('node')
    b.finish(hash16(R('pad'),cat(R('location'),b'\x04',R('keypair'),bytes(8)),R('roots')))

def stateless_body(b):
    b.mark('shrincs_verify.stateless_parser')
    b.exact(R('sig'),5777)
    b.require(eq(cut(R('sig'),0,1),b'\xff'))
    b.let('randomizer',cut(R('sig'),1,16))
    b.let('bound',cat(R('framing'),cut(R('pk'),32,16),R('msg')))
    b.let('digest',h_msg_sl(R('randomizer'),R('seed'),cut(R('pk'),16,16),R('bound')))
    b.let('tree',mod(from_be(b,cut(R('digest'),17,5),5),2**36))
    b.let('leaf',mod(from_be(b,cut(R('digest'),22,2),2),512))
    b.call('fors',('sig','digest','pad','location','keypair'),fors_body,
           (cut(R('sig'),17,2240),cut(R('digest'),0,17),R('pad'),cat(b'\x00',be(b,R('tree'),8)),be(b,R('leaf'),4)),'node')
    for layer in range(5):
        b.mark(f'hypertree_verify.layer{layer}')
        b.let('location',cat(bytes([layer]),be(b,R('tree'),8)))
        wots(b,cut(R('sig'),2257+704*layer,560),R('node'),R('location'),be(b,R('leaf'),4),False,'node')
        for k in range(9):
            pair(b,R('node'),cut(R('sig'),2257+704*layer+560+16*k,16),shr(R('leaf'),k),
                 cat(R('location'),b'\x02',bytes(4),(k+1).to_bytes(4,'big'),be(b,shr(R('leaf'),k+1),4)),'node')
        if layer < 4:
            b.let('leaf',mod(R('tree'),512))
            b.let('tree',shr(R('tree'),9))
    b.finish(eq(R('node'),cut(R('pk'),16,16)))

MODE_ARGS = ('sig','pk','msg','seed','pad','framing')

@dataclass
class Program:
    code: bytes
    profile: str
    mode: str
    source_map: list
    functions: dict

    def audit(self):
        audit(self.code,self.profile,[v[1] for v in self.functions.values()])


def compile_verifier(profile='full', mode='unified', context=CONTEXT):
    if profile not in ('full','baseline','bytes') or mode not in ('unified','stateful','stateless'):
        raise ValueError('unknown profile or mode')
    if len(context) > 255:
        raise ValueError('context too long')
    lib = Library(inline=profile=='bytes')
    b = Builder(('sig','pk','msg'),'baseline' if profile=='baseline' else 'full',lib)
    b.mark('input_profile')
    b.exact(R('pk'),48)
    b.exact(R('msg'),32)
    b.require(op('LESSTHAN',0,op('SIZE',R('sig'))))
    b.let('seed',cut(R('pk'),0,16))
    b.let('pad',cat(R('seed'),bytes(48)))
    b.let('framing',b'\x00'+bytes([len(context)])+context)
    args = tuple(R(x) for x in MODE_ARGS)
    def sf(b): b.call('stateful',MODE_ARGS,stateful_body,args,'valid')
    def sl(b): b.call('stateless',MODE_ARGS,stateless_body,args,'valid')
    if mode == 'unified':
        b.branch(eq(cut(R('sig'),0,1),b'\xff'),sl,sf)
    else:
        (sf if mode == 'stateful' else sl)(b)
    b.finish(R('valid'))
    prefix = lib.prefix() if profile == 'full' else b''
    source_map = [dict(row,offset=row['offset']+len(prefix)) for row in b.source_map]
    program = Program(prefix+bytes(b.code),profile,mode,source_map,lib.functions)
    program.audit()
    return program
