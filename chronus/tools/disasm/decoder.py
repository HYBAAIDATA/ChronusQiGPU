from dataclasses import dataclass
import json
from pathlib import Path
SPEC=json.loads((Path(__file__).resolve().parents[2]/'isa/chronus1.json').read_text());NAMES={v:k for k,v in SPEC['opcodes'].items()}
FORMATS={**{k:'R' for k in ('NOP','MOV','ADD','SUB','MUL','FMA','EXIT')},**{k:'I' for k in ('MOVI','LOAD','LLOAD')},**{k:'M' for k in ('STORE','LSTORE')},**{k:'B' for k in ('BRA','BRAZ','BRANZ')},**{k:'S' for k in ('BARRIER','GET_GID','GET_LID','GET_GSIZE','GET_LSIZE')}}
def sx(v,b):m=1<<(b-1);return(v^m)-m
@dataclass(frozen=True)
class Decoded:name:str;fmt:str;rd:int;rs1:int;rs2:int;aux:int;imm:int;pc:int;raw:int
def decode(raw,pc=0):
 op=(raw>>26)&63
 if op not in NAMES:raise ValueError(f"reserved opcode {op}")
 name=NAMES[op];fmt=FORMATS[name];rd=(raw>>21)&31;rs1=(raw>>16)&31;rs2=(raw>>11)&31;aux=(raw>>6)&31;imm=sx(raw&0xffff,16) if fmt in ('I','M','S') else sx(raw&0x1fffff,21) if fmt=='B' else 0
 return Decoded(name,fmt,rd,rs1,rs2,aux,imm,pc,raw)
