import json,re
from pathlib import Path
from .lexer import AsmError
SPEC=json.loads((Path(__file__).resolve().parents[2]/'isa/chronus1.json').read_text())
OPS=SPEC['opcodes']
FORMATS={**{k:'R' for k in ('NOP','MOV','ADD','SUB','MUL','FMA','EXIT')},**{k:'I' for k in ('MOVI','LOAD','LLOAD')},**{k:'M' for k in ('STORE','LSTORE')},**{k:'B' for k in ('BRA','BRAZ','BRANZ')},**{k:'S' for k in ('BARRIER','GET_GID','GET_LID','GET_GSIZE','GET_LSIZE')}}
def reg(x,line):
 m=re.fullmatch(r'R([0-9]|[12][0-9]|3[01])',x,re.I)
 if not m:raise AsmError(line,f"invalid register {x}")
 return int(m.group(1))
def integer(x,line):
 try:return int(x,0)
 except ValueError as exc:raise AsmError(line,f"invalid integer {x}") from exc
def mem(x,line):
 m=re.fullmatch(r'\[\s*(R(?:[0-9]|[12][0-9]|3[01]))\s*([+-])\s*(0[xX][0-9a-fA-F]+|[0-9]+)\s*\]',x,re.I)
 if not m:raise AsmError(line,f"invalid memory operand {x}")
 value=int(m.group(3),0);return reg(m.group(1),line),value if m.group(2)=='+' else -value
def _imm16(v,line):
 if not -32768<=v<=32767:raise AsmError(line,f"signed imm16 out of range: {v}")
 return v&0xffff
def encode(inst,index,labels):
 n,o,line=inst.name,inst.operands,inst.line
 if n not in OPS:raise AsmError(line,f"unknown opcode {n}")
 op=OPS[n];fmt=FORMATS[n]
 if fmt=='R':
  counts={'NOP':0,'EXIT':0,'MOV':2,'ADD':3,'SUB':3,'MUL':3,'FMA':4}
  if len(o)!=counts[n]:raise AsmError(line,f"{n} expects {counts[n]} operands")
  if n in ('NOP','EXIT'):return op<<26
  rd,a=reg(o[0],line),reg(o[1],line);b=reg(o[2],line) if len(o)>2 else 0;aux=reg(o[3],line) if n=='FMA' else 0
  return(op<<26)|(rd<<21)|(a<<16)|(b<<11)|(aux<<6)
 if n=='MOVI':
  if len(o)!=2:raise AsmError(line,"MOVI expects two operands")
  return(op<<26)|(reg(o[0],line)<<21)|_imm16(integer(o[1],line),line)
 if fmt in ('I','M'):
  if len(o)!=2:raise AsmError(line,f"{n} expects register and memory")
  base,off=mem(o[1],line);return(op<<26)|(reg(o[0],line)<<21)|(base<<16)|_imm16(off,line)
 if fmt=='B':
  if len(o)!=(1 if n=='BRA' else 2):raise AsmError(line,f"invalid {n} operands")
  target_name=o[-1]
  if target_name not in labels:raise AsmError(line,f"unknown label {target_name}")
  delta=labels[target_name]-(index+1)
  if not -(1<<20)<=delta<(1<<20):raise AsmError(line,"branch offset21 out of range")
  selector=0 if n=='BRA' else reg(o[0],line)
  return(op<<26)|(selector<<21)|(delta&0x1fffff)
 if n=='BARRIER':
  if len(o)>1:raise AsmError(line,"BARRIER expects optional scope")
  scope=1 if not o else integer(o[0],line)
  if not 0<=scope<=3:raise AsmError(line,"barrier scope out of range")
  return(op<<26)|(scope<<21)
 if len(o)!=2:raise AsmError(line,f"{n} expects register and dimension")
 dim=integer(o[1],line)
 if not 0<=dim<=2:raise AsmError(line,"dimension out of range")
 return(op<<26)|(reg(o[0],line)<<21)|(dim<<16)
