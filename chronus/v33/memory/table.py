"""
Classical look-up table — the data object that QRAM unitaries are built from.

Matches the typed oracle algebra:
  type Table:
      domain_bits : int
      value_bits  : int
      data        : array[0 .. 2^domain_bits - 1] of bitstring(value_bits)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple, Union

import numpy as np

Bitstring = Tuple[int, ...]


def _to_bitstring(value: Union[int, Sequence[int]], n_bits: int) -> Bitstring:
    if isinstance(value, (list, tuple, np.ndarray)):
        bits = [int(b) & 1 for b in value]
        if len(bits) < n_bits:
            bits = [0] * (n_bits - len(bits)) + bits
        return tuple(bits[:n_bits])
    v = int(value) & ((1 << n_bits) - 1)
    return tuple((v >> (n_bits - 1 - i)) & 1 for i in range(n_bits))


@dataclass
class Table:
    """Finite classical map {0,1}^n → {0,1}^k stored densely for small n,
    or as an address→payload dict for sparse tables."""

    domain_bits: int
    value_bits: int
    data: List[Bitstring] = field(default_factory=list)
    sparse: dict = field(default_factory=dict)  # address_int → Bitstring

    def __post_init__(self) -> None:
        if self.domain_bits < 0 or self.value_bits < 0:
            raise ValueError("domain_bits and value_bits must be non-negative")
        n = 1 << self.domain_bits if self.domain_bits <= 20 else 0
        if self.data and (n == 0 or len(self.data) != n) and not self.sparse:
            raise ValueError("partial dense tables require sparse storage")
        if not self.data and not self.sparse and self.domain_bits <= 16:
            # Default zero table
            self.data = [tuple(0 for _ in range(self.value_bits)) for _ in range(1 << self.domain_bits)]

    @classmethod
    def from_integers(
        cls,
        values: Sequence[int],
        domain_bits: int | None = None,
        value_bits: int | None = None,
    ) -> "Table":
        n = len(values)
        db = domain_bits if domain_bits is not None else max(1, (n - 1).bit_length())
        vb = value_bits if value_bits is not None else max(1, max(values).bit_length() if values else 1)
        data = [_to_bitstring(v, vb) for v in values]
        # Pad to full power-of-two domain if needed
        while len(data) < (1 << db):
            data.append(tuple(0 for _ in range(vb)))
        return cls(domain_bits=db, value_bits=vb, data=data[: 1 << db])

    @classmethod
    def sparse_from_dict(
        cls,
        mapping: dict,
        domain_bits: int,
        value_bits: int,
    ) -> "Table":
        sparse = {int(k): _to_bitstring(v, value_bits) for k, v in mapping.items()}
        return cls(domain_bits=domain_bits, value_bits=value_bits, data=[], sparse=sparse)

    def lookup(self, address: int) -> Bitstring:
        address = int(address) & ((1 << self.domain_bits) - 1)
        if self.sparse:
            return self.sparse.get(address, tuple(0 for _ in range(self.value_bits)))
        if address < len(self.data):
            return self.data[address]
        return tuple(0 for _ in range(self.value_bits))

    def lookup_int(self, address: int) -> int:
        bits = self.lookup(address)
        v = 0
        for b in bits:
            v = (v << 1) | (b & 1)
        return v

    def set(self, address: int, value: Union[int, Sequence[int]]) -> None:
        address = int(address) & ((1 << self.domain_bits) - 1)
        bits = _to_bitstring(value, self.value_bits)
        if self.sparse is not None and (self.sparse or not self.data):
            self.sparse[address] = bits
        elif address < len(self.data):
            self.data[address] = bits
        else:
            self.sparse[address] = bits

    def size_bytes(self) -> int:
        if self.sparse:
            return len(self.sparse) * (self.domain_bits + self.value_bits) // 8 + 1
        return len(self.data) * self.value_bits // 8 + 1

    def n_entries(self) -> int:
        if self.sparse:
            return len(self.sparse)
        return len(self.data)


def _self_test() -> str:
    t = Table.from_integers([3, 1, 4, 1, 5], domain_bits=3, value_bits=3)
    assert t.lookup_int(0) == 3
    assert t.lookup_int(2) == 4
    t.set(2, 7)
    assert t.lookup_int(2) == 7
    s = Table.sparse_from_dict({0: 1, 5: 2}, domain_bits=4, value_bits=2)
    assert s.lookup_int(0) == 1
    assert s.lookup_int(5) == 2
    assert s.lookup_int(1) == 0
    return "memory.table._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
