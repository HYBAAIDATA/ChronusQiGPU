from dataclasses import dataclass,field
import re
from .lexer import AsmError
@dataclass(frozen=True)
class Instruction: name:str; operands:tuple[str,...]; line:int
@dataclass
class Program:
 instructions:list[Instruction]=field(default_factory=list); labels:dict[str,int]=field(default_factory=dict)
 globals:list[str]=field(default_factory=list); declared_symbols:list[str]=field(default_factory=list); required_memory:int=0x301000
 reconvergence:list[tuple[str,str]]=field(default_factory=list); has_data:bool=False

def _split_operands(text):
 out=[];cur='';depth=0
 for ch in text:
  if ch=='[':depth+=1
  elif ch==']':depth-=1
  if ch==',' and depth==0:out.append(cur.strip());cur=''
  else:cur+=ch
 if cur.strip():out.append(cur.strip())
 return tuple(out)
def parse_source(source):
 p=Program();section=None
 for line_no,raw in enumerate(source.splitlines(),1):
  text=raw.split(';',1)[0].strip()
  if not text:continue
  if text.startswith('.'):
   parts=text.split()
   directive=parts[0].lower()
   if directive=='.section' and len(parts)==2:
    section=parts[1];p.has_data|=section=='.data'
   elif directive=='.global' and len(parts)==2:p.globals.append(parts[1])
   elif directive=='.symbol' and len(parts)==2:p.declared_symbols.append(parts[1])
   elif directive=='.reconv' and len(parts)==3:p.reconvergence.append((parts[1].rstrip(','),parts[2]))
   elif directive=='.memory' and len(parts)==2:p.required_memory=int(parts[1],0)
   else:raise AsmError(line_no,f"invalid directive {text}")
   continue
  if text.endswith(':'):
   name=text[:-1].strip()
   if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name) or name in p.labels:raise AsmError(line_no,"invalid or duplicate label")
   if section!='.text':raise AsmError(line_no,"labels require .text")
   p.labels[name]=len(p.instructions);continue
  if section!='.text':raise AsmError(line_no,"instructions require .text")
  parts=text.split(None,1);p.instructions.append(Instruction(parts[0].upper(),_split_operands(parts[1] if len(parts)>1 else ''),line_no))
 if not p.instructions:raise AsmError(0,"empty .text")
 for name in p.globals+p.declared_symbols:
  if name not in p.labels:raise AsmError(0,f"symbol {name!r} has no label")
 return p
