def render(d,labels):
 n=d.name
 if n in ('NOP','EXIT'):return n
 if n=='MOV':return f"MOV R{d.rd}, R{d.rs1}"
 if n in ('ADD','SUB','MUL'):return f"{n} R{d.rd}, R{d.rs1}, R{d.rs2}"
 if n=='FMA':return f"FMA R{d.rd}, R{d.rs1}, R{d.rs2}, R{d.aux}"
 if n=='MOVI':return f"MOVI R{d.rd}, {d.imm}"
 if n in ('LOAD','LLOAD','STORE','LSTORE'):
  sign='+' if d.imm>=0 else '-';return f"{n} R{d.rd}, [R{d.rs1}{sign}{abs(d.imm)}]"
 if n in ('BRA','BRAZ','BRANZ'):
  target=d.pc+4+d.imm*4;label=labels[target]
  return f"BRA {label}" if n=='BRA' else f"{n} R{d.rd}, {label}"
 if n=='BARRIER':return f"BARRIER {d.rd}"
 return f"{n} R{d.rd}, {d.rs1}"
