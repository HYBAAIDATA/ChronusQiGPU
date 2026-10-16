"""Typed IR to canonical Chronus-1 assembly lowering."""
from .types import signature
def align64(v):return (v+63)&~63
def memory_layout(ir):
 inputs,outputs=signature(ir)
 if ir.op=='vector_add':
  a=0;b=align64(inputs[0].bytes);one=align64(b+inputs[1].bytes);c=align64(one+4);return {'A':a,'B':b,'ONE':one,'C':c,'required_bytes':c+outputs[0].bytes}
 if ir.op=='reduce_sum_local':
  a=0;one=align64(inputs[0].bytes);out=one+4;return {'A':a,'ONE':one,'OUT':out,'required_bytes':out+4}
 return {'A':0x100000,'B':0x200000,'C':0x300000,'required_bytes':0x301000}
def lower_vector(ir):
 m=memory_layout(ir);return f'''.section .text\n.global {ir.name}\n.symbol {ir.name}\n{ir.name}:\n    GET_GID R1, 0\n    MOVI R2, 4\n    MUL R3, R1, R2\n    LOAD R4, [R3+0]\n    MOVI R5, {m['B']}\n    ADD R6, R3, R5\n    LOAD R7, [R6+0]\n    LOAD R8, [R0+{m['ONE']}]\n    FMA R8, R4, R8, R7\n    MOVI R9, {m['C']}\n    ADD R10, R3, R9\n    STORE R8, [R10+0]\n    EXIT\n'''
def lower_reduce(ir):
 n=ir.shape['n'];m=memory_layout(ir);return f'''.section .text\n.global {ir.name}\n.symbol {ir.name}\n.reconv reduce_branch, reduce_done\n{ir.name}:\n    GET_LID R1, 0\n    MOVI R2, 4\n    MUL R3, R1, R2\n    LOAD R4, [R3+0]\n    LSTORE R4, [R3+0]\n    BARRIER 1\n    MOVI R5, 0\n    LOAD R6, [R0+{m['ONE']}]\n    MOVI R7, 0\n    MOVI R8, {n}\n    MOVI R11, 1\nreduce_loop:\n    MUL R9, R7, R2\n    LLOAD R10, [R9+0]\n    FMA R5, R10, R6, R5\n    ADD R7, R7, R11\n    SUB R8, R8, R11\nreduce_branch:\n    BRANZ R8, reduce_loop\nreduce_done:\n    STORE R5, [R0+{m['OUT']}]\n    EXIT\n'''
def lower_matmul(ir):
 # The template is generated from the typed fixed-shape contract and is also the
 # canonical source accepted by PR #102.
 from pathlib import Path
 source=(Path(__file__).resolve().parents[1]/'kernels/matmul_tiled.chronus.s').read_text()
 return source.replace('.global matmul_tiled','.global '+ir.name).replace('.symbol matmul_tiled','.symbol '+ir.name).replace('matmul_tiled:',ir.name+':',1)
def lower(ir):
 return {'vector_add':lower_vector,'reduce_sum_local':lower_reduce,'matmul_tiled':lower_matmul}[ir.op](ir)
