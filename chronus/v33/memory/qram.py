"""
QRAM as a mathematical unitary oracle.

U_f |x⟩|y⟩ = |x⟩|y ⊕ f(x)⟩

Pure linear algebra on basis states. No physical memory hardware.
Matches the oracle algebra developed for HYBA / Chronos.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .table import Table


@dataclass
class QRAM:
    """Unitary oracle defined by a classical Table."""

    table: Table
    name: str = "QRAM"

    @property
    def domain_bits(self) -> int:
        return self.table.domain_bits

    @property
    def value_bits(self) -> int:
        return self.table.value_bits

    @property
    def dimension(self) -> int:
        return 1 << (self.domain_bits + self.value_bits)

    def apply_basis(self, address: int, bus: int) -> tuple[int, int]:
        """Apply U_f to computational-basis labels (address, bus)."""
        f_x = self.table.lookup_int(address)
        new_bus = bus ^ f_x
        return address, new_bus

    def apply_state_vector(self, state: np.ndarray) -> np.ndarray:
        """Apply U_f to a dense state vector of dimension 2^(n+k).

        Only tractable for small n+k (≤ ~20). For large systems use
        the basis-level API or an MPS-backed store.
        """
        n = self.domain_bits
        k = self.value_bits
        dim = 1 << (n + k)
        if state.shape[0] != dim:
            raise ValueError(f"state dimension {state.shape[0]} != 2^({n}+{k})={dim}")
        out = np.zeros_like(state)
        mask_bus = (1 << k) - 1
        for idx in range(dim):
            address = idx >> k
            bus = idx & mask_bus
            _, new_bus = self.apply_basis(address, bus)
            new_idx = (address << k) | new_bus
            out[new_idx] = state[idx]
        return out

    def is_self_inverse(self) -> bool:
        """U_f² = I for any table (XOR is involutory)."""
        return True


def qram_apply(table: Table, address: int, bus: int = 0) -> int:
    """Convenience: return bus ⊕ table[address]."""
    return bus ^ table.lookup_int(address)


def _self_test() -> str:
    t = Table.from_integers([0b01, 0b10, 0b11, 0b00], domain_bits=2, value_bits=2)
    q = QRAM(t)
    assert q.apply_basis(0, 0) == (0, 0b01)
    assert q.apply_basis(1, 0) == (1, 0b10)
    # Self-inverse
    a, b = q.apply_basis(2, 0)
    a2, b2 = q.apply_basis(a, b)
    assert (a2, b2) == (2, 0)
    # Dense state (small)
    dim = q.dimension
    psi = np.zeros(dim, dtype=complex)
    psi[0] = 1.0  # |00⟩|00⟩
    out = q.apply_state_vector(psi)
    # Should land on |00⟩|01⟩ = index 1
    assert abs(out[0b0001]) == 1.0
    return "memory.qram._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
