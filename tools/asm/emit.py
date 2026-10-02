from format.chronus1_executable import Executable,Symbol,pack
from .encoder import encode
from .lexer import AsmError
from .parser import parse_source
def assemble_source(source):
 p=parse_source(source);words=tuple(encode(i,n,p.labels) for n,i in enumerate(p.instructions))
 declared=set(p.declared_symbols);globals_=set(p.globals);symbols=[]
 for name,index in sorted(p.labels.items(),key=lambda x:(x[1],x[0])):
  kind=1 if name in declared or name in globals_ else 2;flags=1 if name in globals_ else 0
  symbols.append(Symbol(name,index*4,0,kind,flags))
 reconv=[];seen=set()
 for branch,target in p.reconvergence:
  if branch not in p.labels or target not in p.labels:raise AsmError(0,"unknown .reconv label")
  b=p.labels[branch]*4;t=p.labels[target]*4
  if b in seen:raise AsmError(0,"duplicate .reconv branch")
  if p.instructions[p.labels[branch]].name not in ('BRAZ','BRANZ'):raise AsmError(p.instructions[p.labels[branch]].line,".reconv source is not conditional branch")
  seen.add(b);reconv.append((b,t))
 conditional={n*4 for n,i in enumerate(p.instructions) if i.name in ('BRAZ','BRANZ')}
 if conditional!=seen:raise AsmError(0,f"conditional branches require explicit .reconv records: {sorted(conditional-seen)}")
 entry=(p.labels[p.globals[0]]*4 if p.globals else 0)
 return pack(Executable(words,entry=entry,required_global_bytes=0x301000,symbols=tuple(symbols),reconvergence=tuple(sorted(reconv))))
def assemble_file(path):return assemble_source(open(path,encoding='utf-8').read())
