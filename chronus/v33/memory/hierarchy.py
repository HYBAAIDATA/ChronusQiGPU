"""
Multi-level memory hierarchy for Chronos GPU.

L0  Classical cache          (Table, O(1) look-up)
L1  Neural-combine index     (soft routing over slots)
L2  MPS quantum store        (compressed state memory)
L3  QRAM oracle              (unitary coherent access)

Read path tries L0 → L1 → L2 → L3 and records hit statistics.
All layers are pure mathematics; no physical memory hierarchy is simulated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .table import Table
from .qram import QRAM
from .mps_store import MPSStore, MemoryAudit
from .neural_combine import NeuralCombineMemory, NeuralIndexReport
from .block_encode import Structure, BlockEnc, block_encode
from .qsvt import Poly, QSVTResult, apply_qsvt, qsvt_from_block_enc


@dataclass
class HierarchyReport:
    l0_hits: int
    l1_hits: int
    l2_queries: int
    l3_queries: int
    total_reads: int
    neural_report: Optional[NeuralIndexReport]
    mps_audit: Optional[MemoryAudit]
    last_qsvt: Optional[QSVTResult] = None
    notes: List[str] = field(default_factory=list)

    @property
    def hit_rate_l0(self) -> float:
        return self.l0_hits / max(self.total_reads, 1)


class MemoryHierarchy:
    """
    Unified memory façade for Chronos GPU.

    Parameters
    ----------
    address_bits : classical address width
    value_bits   : classical payload width
    n_slots      : neural-combine slot bank size
    mps_qubits   : qubits in the MPS store (0 disables L2)
    mps_bond_dim : MPS bond dimension
    """

    def __init__(
        self,
        address_bits: int = 8,
        value_bits: int = 8,
        n_slots: int = 8,
        mps_qubits: int = 16,
        mps_bond_dim: int = 32,
        seed: int = 0,
    ):
        self.address_bits = address_bits
        self.value_bits = value_bits

        # L0 — classical cache (dense for ≤ 16 bits, else sparse)
        if address_bits <= 12:
            self.l0 = Table.from_integers(
                [0] * (1 << address_bits),
                domain_bits=address_bits,
                value_bits=value_bits,
            )
        else:
            self.l0 = Table.sparse_from_dict({}, address_bits, value_bits)

        # L1 — neural combine
        self.l1 = NeuralCombineMemory(
            n_slots=n_slots,
            address_bits=min(address_bits, 8),
            value_bits=value_bits,
            n_hidden=32,
            seed=seed,
        )

        # L2 — MPS store
        self.l2: Optional[MPSStore] = None
        if mps_qubits > 0:
            self.l2 = MPSStore(n_qubits=mps_qubits, bond_dim=mps_bond_dim, name="L2_MPS")

        # L3 — QRAM over L0 table
        self.l3 = QRAM(self.l0, name="L3_QRAM")

        self._stats = {"l0": 0, "l1": 0, "l2": 0, "l3": 0, "reads": 0}
        self._neural_report: Optional[NeuralIndexReport] = None
        self._last_qsvt: Optional[QSVTResult] = None

    def write(self, address: int, value: int) -> None:
        self.l0.set(address, value)
        self.l1.write(address, value)

    def read(self, address: int, prefer: str = "l0") -> int:
        """Classical read with optional preference (l0 / l1)."""
        self._stats["reads"] += 1
        if prefer == "l0":
            self._stats["l0"] += 1
            return self.l0.lookup_int(address)
        val, _ = self.l1.read(address)
        self._stats["l1"] += 1
        return int(round(val))

    def coherent_query(self, address: int, bus: int = 0) -> Tuple[int, int]:
        """L3 QRAM coherent look-up: (address, bus ⊕ data[address])."""
        self._stats["l3"] += 1
        return self.l3.apply_basis(address, bus)

    def load_ghz_into_mps(self) -> float:
        """Initialise L2 with a GHZ state; return max truncation error."""
        if self.l2 is None:
            return 0.0
        self._stats["l2"] += 1
        return self.l2.load_ghz()

    def train_neural_index(self, epochs: int = 60) -> NeuralIndexReport:
        self._neural_report = self.l1.train_router(epochs=epochs)
        return self._neural_report

    def block_encode_from_l0(
        self,
        sparsity: int = 4,
        system_dim: int = 2,
    ) -> BlockEnc:
        """Build a PREPARE/SELECT block-encoding using L0 as coefficient source."""
        # Synthetic single-qubit Paulis for a tiny demo encoding
        X = np.array([[0, 1], [1, 0]], dtype=complex)
        Z = np.array([[1, 0], [0, -1]], dtype=complex)
        Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
        I = np.eye(2, dtype=complex)
        bank = [I, X, Y, Z]
        unitaries = [bank[i % 4] for i in range(sparsity)]
        struct = Structure(
            alpha=1.0,
            ancilla_bits=int(np.ceil(np.log2(max(sparsity, 1)))),
            sparsity=sparsity,
            n_system=system_dim,
        )
        # Use a tiny value table derived from L0
        coeffs = [max(1, self.l0.lookup_int(i) % 8) for i in range(sparsity)]
        D_val = Table.from_integers(coeffs, domain_bits=max(1, (sparsity - 1).bit_length()), value_bits=4)
        D_idx = Table.from_integers(list(range(sparsity)), domain_bits=D_val.domain_bits, value_bits=4)
        return block_encode(D_idx, D_val, struct, system_unitaries=unitaries)

    def qsvt(
        self,
        kind: str = "chebyshev",
        degree: int = 4,
        t: float = 1.0,
        sparsity: int = 4,
        system_dim: int = 2,
        poly: Optional[Poly] = None,
    ) -> QSVTResult:
        """
        QSVT consumer: BlockEncode(L0) → QSVT(P).

        Pipeline
        --------
        L0 Table  →  PREPARE/SELECT BlockEnc  →  QSVT polynomial transform

        Parameters
        ----------
        kind : "identity" | "chebyshev" | "exp_cosine"
        degree : polynomial degree
        t : evolution-time parameter for exp_cosine
        poly : optional explicit Poly (overrides kind)
        """
        be = self.block_encode_from_l0(sparsity=sparsity, system_dim=system_dim)
        if poly is not None:
            result = apply_qsvt(be, poly)
        else:
            result = qsvt_from_block_enc(be, kind=kind, t=t, degree=degree)
        self._last_qsvt = result
        return result

    def report(self) -> HierarchyReport:
        mps_audit = self.l2.audit() if self.l2 is not None else None
        return HierarchyReport(
            l0_hits=self._stats["l0"],
            l1_hits=self._stats["l1"],
            l2_queries=self._stats["l2"],
            l3_queries=self._stats["l3"],
            total_reads=self._stats["reads"],
            neural_report=self._neural_report,
            mps_audit=mps_audit,
            last_qsvt=getattr(self, "_last_qsvt", None),
            notes=[
                "L0 = classical Table",
                "L1 = NeuralCombine soft router",
                "L2 = MPSStore (tensor-train)",
                "L3 = QRAM unitary oracle",
                "QSVT = BlockEncode(L0) → polynomial singular-value transform",
            ],
        )


def _self_test() -> str:
    hier = MemoryHierarchy(address_bits=6, value_bits=4, n_slots=4, mps_qubits=8, mps_bond_dim=16, seed=2)
    for i in range(16):
        hier.write(i, (i * 3) % 16)
    assert hier.read(5) == (5 * 3) % 16
    a, b = hier.coherent_query(5, bus=0)
    assert a == 5 and b == (5 * 3) % 16
    err = hier.load_ghz_into_mps()
    assert err == 0.0
    report = hier.train_neural_index(epochs=40)
    assert report.final_loss < 2.0
    be = hier.block_encode_from_l0(sparsity=2, system_dim=2)
    assert be.unitary is not None
    assert np.allclose(be.unitary.conj().T @ be.unitary, np.eye(be.unitary.shape[0]), atol=1e-8)

    # QSVT consumer
    qsvt_res = hier.qsvt(kind="chebyshev", degree=2, sparsity=2, system_dim=2)
    assert qsvt_res.unitary is not None
    assert np.allclose(
        qsvt_res.unitary.conj().T @ qsvt_res.unitary,
        np.eye(qsvt_res.unitary.shape[0]),
        atol=1e-6,
    )
    assert qsvt_res.top_left_block is not None
    assert qsvt_res.top_left_block.shape == (2, 2)

    qsvt_exp = hier.qsvt(kind="exp_cosine", t=0.3, degree=4, sparsity=2, system_dim=2)
    assert qsvt_exp.poly.parity == "even"
    assert qsvt_exp.unitary is not None

    status = hier.report()
    assert status.total_reads >= 1
    assert status.mps_audit is not None and status.mps_audit.is_compressed
    assert status.last_qsvt is not None
    return "memory.hierarchy._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
