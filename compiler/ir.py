"""Typed, deliberately small Chronus IR v0.1."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Mapping
SUPPORTED_OPS=frozenset({'vector_add','reduce_sum_local','matmul_tiled'})
@dataclass(frozen=True)
class ChronusIR:
 schema:str;name:str;op:str;dtype:str;shape:Mapping[str,int]
 @classmethod
 def from_dict(cls,v:Mapping[str,Any]):
  if not isinstance(v,Mapping):raise ValueError('IR must be an object')
  shape=v.get('shape')
  ir=cls(str(v.get('schema','')),str(v.get('name','')),str(v.get('op','')),str(v.get('dtype','')),dict(shape) if isinstance(shape,Mapping) else {});ir.validate();return ir
 def validate(self):
  if self.schema!='chronus.ir.v0.1':raise ValueError('unsupported IR schema')
  if not self.name or not self.name.replace('_','a').isalnum():raise ValueError('invalid IR name')
  if self.op not in SUPPORTED_OPS:raise ValueError(f'unsupported IR op {self.op!r}')
  if self.dtype!='f32':raise ValueError('Chronus subset compiler supports f32 only')
  if not self.shape or any(type(v) is not int or v<=0 for v in self.shape.values()):raise ValueError('shape dimensions must be positive integers')
  if self.op=='vector_add' and (set(self.shape)!={'n'} or self.shape['n']>4080):raise ValueError('vector_add requires 1<=n<=4080')
  if self.op=='reduce_sum_local' and (set(self.shape)!={'n'} or self.shape['n']>256):raise ValueError('local reduction requires 1<=n<=256')
  if self.op=='matmul_tiled' and self.shape!={'m':32,'k':32,'n':32}:raise ValueError('v0.1 tiled matmul is fixed at 32x32x32')
