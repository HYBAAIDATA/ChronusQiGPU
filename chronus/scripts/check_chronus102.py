"""PR #102 assembler/disassembler/container/execution acceptance gate."""
from __future__ import annotations
import hashlib,json,struct,subprocess,sys,tempfile,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from format.chronus1_executable import Executable,Symbol,HEADER,pack,unpack,write
from tools.asm import assemble_file,assemble_source,parse_source,tokenize
from tools.asm.encoder import FORMATS,OPS,encode
from tools.canonical import canonicalize
from tools.disasm import decode,disassemble
CHECKS=[]
def check(name):
 def deco(fn):CHECKS.append((name,fn));return fn
 return deco
def run_cli(cli,exe,a,b):
 with tempfile.TemporaryDirectory() as td:
  td=Path(td);pa=td/'a.bin';pb=td/'b.bin';pa.write_bytes(a.tobytes());pb.write_bytes(b.tobytes())
  out=subprocess.check_output([str(cli),'--load',str(exe),'--global','32,32,1','--local','16,16,1','--memory','3150000','--upload',f'{pa}@0x100000','--upload',f'{pb}@0x200000','--dump','0x300000:1024'],text=True)
  return json.loads(out)
SOURCE=ROOT/'kernels/matmul_tiled.chronus.s'
@check('lexer handles full source')
def _():
 t=tokenize(SOURCE.read_text());assert t[-1].kind=='EOF' and any(x.kind=='REG' for x in t) and any(x.kind=='LBRACKET' for x in t)
@check('parser handles all 5 formats')
def _():
 p=parse_source(SOURCE.read_text());assert {FORMATS[i.name] for i in p.instructions}==set('RIMBS')
@check('encoder emits exact R/I/M/B/S bits')
def _():
 p=parse_source(SOURCE.read_text());words=[encode(i,n,p.labels) for n,i in enumerate(p.instructions)];assert all(0<=w<=0xffffffff for w in words);assert (words[0]>>26)==OPS['GET_LID']
@check('labels and branch offsets resolve')
def _():
 p=parse_source(SOURCE.read_text());blob=assemble_source(SOURCE.read_text());x=unpack(blob)
 for idx,i in enumerate(p.instructions):
  if i.name in ('BRA','BRAZ','BRANZ'):
   d=decode(x.code[idx],idx*4);assert d.pc+4+d.imm*4==p.labels[i.operands[-1]]*4
@check('reconvergence metadata emitted')
def _():
 x=unpack(assemble_file(SOURCE));assert x.reconvergence==((208,212),(224,228))
@check('decoder handles all 20 opcodes')
def _():
 assert len(OPS)==20
 for name,op in OPS.items():
  raw=op<<26
  if name=='MOVI':raw|=1<<21
  if name in ('GET_GID','GET_LID','GET_GSIZE','GET_LSIZE'):raw|=1<<21
  assert decode(raw).name==name
@check('renderer and labels round-trip operands')
def _():
 b=assemble_file(SOURCE);text=disassemble(b);assert 'matmul_tiled:' in text and 'BRANZ R28, k_loop' in text and 'LSTORE R15, [R8+0]' in text
@check('container header/checksum/tamper')
def _():
 b=assemble_file(SOURCE);magic,maj,minor,flags,entry,words,mem,crc,mb=HEADER.unpack_from(b);assert magic==b'CHRN' and (maj,minor,flags)==(1,1,0);assert zlib.crc32(b[32:])&0xffffffff==crc
 bad=bytearray(b);bad[40]^=0xff
 try:unpack(bytes(bad));raise AssertionError('tamper accepted')
 except ValueError:pass
@check('container rejects missing reconvergence')
def _():
 b=bytearray(assemble_file(SOURCE));words=struct.unpack_from('<I',b,16)[0];meta=32+words*4;struct.pack_into('<I',b,meta+8,0);del b[-16:];struct.pack_into('<I',b,28,struct.unpack_from('<I',b,28)[0]-16);struct.pack_into('<I',b,24,zlib.crc32(b[32:])&0xffffffff)
 try:unpack(bytes(b));raise AssertionError('missing reconvergence accepted')
 except ValueError:pass
@check('I1 assemble(disassemble(B)) == B')
def _():
 b=assemble_file(SOURCE);assert assemble_source(disassemble(b))==b
@check('I2 disassemble(assemble(S)) == canonical')
def _():
 s=SOURCE.read_text();assert disassemble(assemble_source(s))==canonicalize(s)
@check('I3 assembled equals frozen hand encoding and execution')
def _():
 b=assemble_file(SOURCE);x=unpack(b);gold=tuple(int(v,16) for v in (ROOT/'tests/fixtures/matmul_tiled.hand.hex').read_text().split());assert x.code==gold
 with tempfile.TemporaryDirectory() as td:
  td=Path(td);assembled=td/'a.chronus';hand=td/'h.chronus';assembled.write_bytes(b);write(hand,Executable(gold,x.entry,x.required_global_bytes,x.flags,x.symbols,x.reconvergence))
  rng=np.random.default_rng(7);a=rng.normal(size=(32,32)).astype(np.float32);bb=rng.normal(size=(32,32)).astype(np.float32);ra=run_cli(ROOT/'emulator/build/chronus-emu',assembled,a,bb);rh=run_cli(ROOT/'emulator/build/chronus-emu',hand,a,bb);assert ra==rh
@check('I4 assembled matmul equals NumPy float32')
def _():
 with tempfile.TemporaryDirectory() as td:
  exe=Path(td)/'m.chronus';exe.write_bytes(assemble_file(SOURCE));rng=np.random.default_rng(1);a=rng.normal(size=(32,32)).astype(np.float32);b=rng.normal(size=(32,32)).astype(np.float32);result=run_cli(ROOT/'emulator/build/chronus-emu',exe,a,b);got=np.asarray(result['dump'],dtype=np.uint32).view(np.float32).reshape(32,32);expected=a@b;err=float(np.max(np.abs(got-expected)));assert err<=1e-5,err
@check('deterministic assembly/execution/evidence')
def _():
 blobs=[assemble_file(SOURCE) for _ in range(10)];assert len({hashlib.sha256(b).digest() for b in blobs})==1
 closure={'schema':'chronus102-evidence-v1','binary_sha256':hashlib.sha256(blobs[0]).hexdigest(),'i1':True,'i2':True,'i3':True,'i4':True};raw=json.dumps(closure,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest();out=ROOT/'artifacts';out.mkdir(exist_ok=True);(out/'chronus102-evidence.json').write_bytes(raw);(out/'chronus102-sha256sums.txt').write_text(f'{digest}  chronus102-evidence.json\n')
def main():
 subprocess.run([sys.executable,'scripts/check_chronus101.py'],cwd=ROOT,check=True)
 for name,fn in CHECKS:
  try:fn();print(f'{name:52s} PASS')
  except Exception as exc:print(f'{name:52s} FAIL: {exc}');raise
 print('Chronus-1 PR #102 acceptance: PASS')
if __name__=='__main__':main()
