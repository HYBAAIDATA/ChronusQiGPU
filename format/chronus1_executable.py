"""Normative Chronus-1 executable reader/writer (container v1.1)."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import struct, zlib
MAGIC=b"CHRN"; META_MAGIC=b"META"; HEADER=struct.Struct("<4sHHIIIIII")
@dataclass(frozen=True)
class Symbol:
 name:str; value:int; size:int=0; kind:int=0; flags:int=0
@dataclass(frozen=True)
class Executable:
 code:tuple[int,...]; entry:int=0; required_global_bytes:int=0; flags:int=0
 symbols:tuple[Symbol,...]=(); reconvergence:tuple[tuple[int,int],...]=(); major:int=1; minor:int=1

def _pad4(b:bytes)->bytes:return b+b"\0"*((-len(b))%4)
def pack_metadata(exe:Executable)->bytes:
 out=bytearray(struct.pack("<4sIII",META_MAGIC,len(exe.symbols),len(exe.reconvergence),0))
 names=set()
 for s in exe.symbols:
  raw=s.name.encode("utf-8")
  if not raw or len(raw)>255 or s.name in names: raise ValueError("invalid or duplicate symbol")
  names.add(s.name);out+=struct.pack("<HBBII",len(raw),s.kind,s.flags,s.value,s.size)+_pad4(raw)
 for branch,reconv in exe.reconvergence:
  if branch%4 or reconv%4: raise ValueError("reconvergence PCs must be aligned")
  out+=struct.pack("<II",branch,reconv)
 return bytes(out)
def pack(exe:Executable)->bytes:
 if exe.major!=1 or exe.minor<1: raise ValueError("writer emits Chronus container 1.1+")
 if exe.entry%4 or exe.entry//4>=max(1,len(exe.code)): raise ValueError("entry outside code")
 code=struct.pack(f"<{len(exe.code)}I",*exe.code) if exe.code else b""
 conditional={i*4 for i,w in enumerate(exe.code) if ((w>>26)&0x3f) in (17,18)}
 if conditional!={b for b,_ in exe.reconvergence}: raise ValueError("every conditional branch requires one reconvergence record")
 meta=pack_metadata(exe); payload=code+meta; checksum=zlib.crc32(payload)&0xffffffff
 return HEADER.pack(MAGIC,exe.major,exe.minor,exe.flags,exe.entry,len(exe.code),exe.required_global_bytes,checksum,len(meta))+payload
def unpack(data:bytes)->Executable:
 if len(data)<HEADER.size: raise ValueError("truncated header")
 magic,major,minor,flags,entry,words,global_bytes,checksum,meta_bytes=HEADER.unpack_from(data)
 if magic!=MAGIC or major!=1 or minor<1: raise ValueError("unsupported executable identity/version")
 code_bytes=words*4; expected=HEADER.size+code_bytes+meta_bytes
 if len(data)!=expected or entry%4 or entry//4>=max(1,words): raise ValueError("invalid executable size/entry")
 payload=data[HEADER.size:]
 if zlib.crc32(payload)&0xffffffff!=checksum: raise ValueError("container checksum mismatch")
 code=struct.unpack_from(f"<{words}I",data,HEADER.size) if words else ()
 meta=data[HEADER.size+code_bytes:]; symbols=[]; reconv=[]
 if len(meta)<16: raise ValueError("missing metadata header")
 mm,ns,nr,reserved=struct.unpack_from("<4sIII",meta)
 if mm!=META_MAGIC or reserved: raise ValueError("invalid metadata header")
 off=16; names=set()
 for _ in range(ns):
  if off+12>len(meta): raise ValueError("truncated symbol")
  n,kind,sflags,value,size=struct.unpack_from("<HBBII",meta,off);off+=12
  padded=(n+3)&~3
  if not n or off+padded>len(meta): raise ValueError("invalid symbol length")
  raw=meta[off:off+n];off+=padded
  try:name=raw.decode("utf-8")
  except UnicodeDecodeError as exc: raise ValueError("invalid symbol UTF-8") from exc
  if name in names: raise ValueError("duplicate symbol")
  names.add(name);symbols.append(Symbol(name,value,size,kind,sflags))
 for _ in range(nr):
  if off+8>len(meta): raise ValueError("truncated reconvergence record")
  branch,target=struct.unpack_from("<II",meta,off);off+=8
  if branch%4 or target%4 or branch//4>=words or target//4>=words: raise ValueError("invalid reconvergence PC")
  reconv.append((branch,target))
 if off!=len(meta) or len({b for b,_ in reconv})!=len(reconv): raise ValueError("trailing or duplicate metadata")
 conditional={i*4 for i,w in enumerate(code) if ((w>>26)&0x3f) in (17,18)}
 if conditional!={b for b,_ in reconv}: raise ValueError("missing or surplus reconvergence metadata")
 return Executable(tuple(code),entry,global_bytes,flags,tuple(symbols),tuple(reconv),major,minor)
def write(path,exe):Path(path).write_bytes(pack(exe))
def load(path):return unpack(Path(path).read_bytes())
