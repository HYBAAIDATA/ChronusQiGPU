# mps_tools.py -- Elevated MPS tensor-structure utilities.
#
# Adds structure inspection and safer local expectations on top of
# academic.tensor_compression.MatrixProductState without changing its
# SVD truncation semantics.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from ..academic.tensor_compression import MatrixProductState


@dataclass
class MPSStructureReport:
    n_sites: int
    bond_dim_cap: int
    bond_dimensions: List[int]          # χ at each bond (len n-1)
    tensor_shapes: List[Tuple[int, int, int]]
    parameter_count: int
    dense_amplitude_count: float
    compression_ratio: float
    max_bond: int
    is_left_normalized_approx: bool


def bond_dimensions(mps: MatrixProductState) -> List[int]:
    """Bond dimension χ_k between sites (k-1, k), for k=1..n-1."""
    dims = []
    for i in range(mps.n - 1):
        # right bond of tensor i equals left bond of tensor i+1
        dims.append(int(mps.tensors[i].shape[2]))
    return dims


def structure_report(mps: MatrixProductState) -> MPSStructureReport:
    shapes = [tuple(int(x) for x in t.shape) for t in mps.tensors]
    bonds = bond_dimensions(mps)
    params = sum(t.size for t in mps.tensors)
    dense = float(2 ** mps.n)
    # Cheap left-normalization check: for each site, sum over phys+right ≈ I on left
    left_ok = True
    for t in mps.tensors:
        # t: (χL, d, χR)
        # contract phys and right: result should be ~ I_{χL}
        gram = np.einsum("adr,bdr->ab", t.conj(), t)
        chi_l = t.shape[0]
        if chi_l > 0:
            err = np.linalg.norm(gram - np.eye(chi_l))
            if err > 1e-6 * max(chi_l, 1):
                left_ok = False
                break
    return MPSStructureReport(
        n_sites=mps.n,
        bond_dim_cap=mps.chi,
        bond_dimensions=bonds,
        tensor_shapes=shapes,
        parameter_count=params,
        dense_amplitude_count=dense,
        compression_ratio=dense / params if params else 0.0,
        max_bond=max(bonds) if bonds else 1,
        is_left_normalized_approx=left_ok,
    )


def local_expectation_contracted(
    mps: MatrixProductState,
    site: int,
    op: np.ndarray,
) -> float:
    """⟨O_site⟩ by contracting the full MPS network (exact for the MPS).

    More reliable than the single-tensor formula when the MPS is not in
    mixed canonical form at `site`. Cost O(n χ³ d) — fine for moderate n.
    """
    op = np.asarray(op, dtype=complex)
    if op.shape != (mps.d, mps.d):
        raise ValueError(f"op must be {mps.d}x{mps.d}")

    # Left environment: transfer from site 0 .. site-1
    # E_left[α,α'] accumulates
    e_left = np.array([[1.0 + 0j]])  # bond dim 1 at boundary
    for i in range(site):
        t = mps.tensors[i]
        # e_left: (χL, χL'), t: (χL, d, χR)
        e_left = np.einsum("ab,adr,bds->rs", e_left, t.conj(), t)

    # Right environment: site+1 .. n-1
    e_right = np.array([[1.0 + 0j]])
    for i in range(mps.n - 1, site, -1):
        t = mps.tensors[i]
        e_right = np.einsum("adr,bds,rs->ab", t.conj(), t, e_right)

    t = mps.tensors[site]
    # e_left[a,b], conj(t)[a,s,l], op[s,x], t[b,x,r], e_right[l,r]
    num = np.einsum("ab,asl,sx,bxr,lr->", e_left, t.conj(), op, t, e_right)
    den = np.einsum("ab,asl,bsl,lr->", e_left, t.conj(), t, e_right)
    return float(np.real(num / den)) if abs(den) > 1e-30 else 0.0


def build_ghz_mps(n: int, bond_dim: int = 4) -> Tuple[MatrixProductState, float]:
    """GHZ via H + CNOT cascade; returns (mps, max_truncation_error)."""
    mps = MatrixProductState(n_qubits=n, bond_dim=bond_dim)
    h = (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)
    cnot = np.array(
        [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex
    )
    mps.apply_single_qubit_gate(0, h)
    max_err = 0.0
    for i in range(n - 1):
        max_err = max(max_err, mps.apply_two_qubit_gate(i, cnot))
    return mps, max_err


def _self_test() -> str:
    mps, err = build_ghz_mps(6, bond_dim=8)
    assert err == 0.0
    rep = structure_report(mps)
    assert rep.n_sites == 6
    assert rep.max_bond >= 2
    assert rep.compression_ratio > 1.0

    # Contracted ⟨Z⟩ on GHZ: each site has ⟨Z⟩=0
    z = np.array([[1, 0], [0, -1]], dtype=complex)
    for s in range(6):
        ez = local_expectation_contracted(mps, s, z)
        assert abs(ez) < 1e-8, f"GHZ ⟨Z_{s}⟩={ez}"

    # Product |0...0⟩: ⟨Z⟩=+1
    prod = MatrixProductState(n_qubits=5, bond_dim=4)
    for s in range(5):
        assert abs(local_expectation_contracted(prod, s, z) - 1.0) < 1e-10

    return "compression.mps_tools._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
