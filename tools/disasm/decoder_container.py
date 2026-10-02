from format.chronus1_executable import unpack
from .decoder import decode
from .printer import render
def disassemble(blob):
 exe=unpack(blob);symbols=sorted(exe.symbols,key=lambda s:(s.value,s.name));labels={s.value:s.name for s in symbols}
 targets=set()
 for pc,raw in enumerate(exe.code):
  d=decode(raw,pc*4)
  if d.name in ('BRA','BRAZ','BRANZ'):targets.add(d.pc+4+d.imm*4)
 targets.update(t for _,t in exe.reconvergence);targets.update(b for b,_ in exe.reconvergence)
 for pc in sorted(targets):labels.setdefault(pc,f"L_{pc:08x}")
 lines=['.section .text']
 for s in symbols:
  if s.flags&1:lines.append(f".global {s.name}")
 for s in symbols:
  if s.kind==1:lines.append(f".symbol {s.name}")
 branch_names={pc:labels[pc] for pc,_ in exe.reconvergence};target_names={t:labels[t] for _,t in exe.reconvergence}
 for b,t in exe.reconvergence:lines.append(f".reconv {branch_names[b]}, {target_names[t]}")
 for index,raw in enumerate(exe.code):
  pc=index*4
  for s in [x for x in symbols if x.value==pc]:lines.append(f"{s.name}:")
  if pc in labels and not any(x.value==pc for x in symbols):lines.append(f"{labels[pc]}:")
  lines.append('    '+render(decode(raw,pc),labels))
 return '\n'.join(lines)+'\n'
