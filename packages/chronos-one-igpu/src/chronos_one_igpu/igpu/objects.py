from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from .core import cassini, fib_pair, lucas, nth_prime, zeckendorf, zeckendorf_decode
from ..core_hash import sha256_json

@dataclass(frozen=True)
class MLAObject:
    payload: Any
    family: str
    scale: int
    sequence_index: int
    fibonacci_pair: tuple[int, int]
    lucas_scale: int
    zeckendorf_mask: int
    prime_index: int
    prime_address: int
    cassini_seal: int
    object_id: str
    schema_version: int = 1
    @classmethod
    def create(cls, payload, sequence_index: int, scale: int = 15, family: str = 'fibonacci'):
        if sequence_index < 1 or scale < 1: raise ValueError('sequence_index and scale must be positive')
        pair=fib_pair(sequence_index); mask,_=zeckendorf(sequence_index)
        body={'payload':payload,'family':family,'scale':scale,'sequence_index':sequence_index,'fibonacci_pair':pair,'lucas_scale':lucas(scale),'zeckendorf_mask':mask,'prime_index':sequence_index,'prime_address':nth_prime(sequence_index),'cassini_seal':cassini(sequence_index),'schema_version':1}
        return cls(**body, object_id=sha256_json(body))
    def validate(self):
        if self.schema_version != 1: raise ValueError('unsupported schema')
        if self.fibonacci_pair != fib_pair(self.sequence_index): raise ValueError('Fibonacci mismatch')
        if self.lucas_scale != lucas(self.scale): raise ValueError('Lucas mismatch')
        if self.zeckendorf_mask != zeckendorf(self.sequence_index)[0] or zeckendorf_decode(self.zeckendorf_mask) != self.sequence_index: raise ValueError('Zeckendorf mismatch')
        if self.prime_address != nth_prime(self.prime_index): raise ValueError('prime mismatch')
        if self.cassini_seal != cassini(self.sequence_index): raise ValueError('Cassini mismatch')
        body=asdict(self); body.pop('object_id')
        if sha256_json(body) != self.object_id: raise ValueError('object digest mismatch')
    def to_dict(self): return asdict(self)
