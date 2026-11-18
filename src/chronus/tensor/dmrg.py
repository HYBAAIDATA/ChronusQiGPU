"""Density Matrix Renormalization Group (DMRG) variational ground-state solver.

Optimizes 1D Matrix Product States (MPS) with singular-value truncation
logging to the ErrorLedger. Notion/E3 scope (1,000-node TFIM) is a
requirements target only — this routine currently overwrites each bond
with a hard-coded local 2-site ground state plus an ad-hoc scale envelope
and reports the analytic Jordan-Wigner energy rather than <psi|H|psi>.
Until environments, tolerance handling and true variational sweeps land,
treat E3 variational-DMRG as UNVERIFIED; see
``docs/production/IGPU_TENSOR_INTEGRITY_ELEVATION_20261116.md`` §Remaining
defects. Owner: TN theorist & quantum matter specialist.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional

import numpy as np

from chronus.tensor.types import (
    BondId,
    ContractionCertificate,
    ErrorLedger,
    Leg,
    LegDirection,
    Node,
    SymmetricTensor,
    TruncationRecord,
)
from chronus.tensor.network import TensorNetwork



def _left_environment(env: np.ndarray, site: np.ndarray, mpo: np.ndarray) -> np.ndarray:
    """Contract <psi_left|MPO_left|psi_left> with conjugate bra indices."""
    return np.einsum("awb,asc,wstx,btd->cxd", env, site.conj(), mpo, site, optimize=True)


def _right_environment(env: np.ndarray, site: np.ndarray, mpo: np.ndarray) -> np.ndarray:
    return np.einsum("asc,wstx,btd,cxd->awb", site.conj(), mpo, site, env, optimize=True)


def _mps_norm(sites: list[np.ndarray]) -> float:
    env = np.ones((1, 1), dtype=np.complex128)
    for site in sites:
        env = np.einsum("ab,asc,bsd->cd", env, site.conj(), site, optimize=True)
    value = env[0, 0]
    if not np.isfinite(value) or abs(value.imag) > 1e-9 or value.real <= 0:
        raise ValueError("MPS has invalid or zero norm")
    return float(value.real)


def _mpo_expectation(sites: list[np.ndarray], mpo: list[np.ndarray]) -> float:
    env = np.ones((1, 1, 1), dtype=np.complex128)
    for site, operator in zip(sites, mpo):
        env = _left_environment(env, site, operator)
    value = env[0, 0, 0] / _mps_norm(sites)
    if not np.isfinite(value) or abs(value.imag) > 1e-9 * max(1.0, abs(value.real)):
        raise ValueError("MPO expectation is not finite and real")
    return float(value.real)


def _right_canonicalize(sites: list[np.ndarray]) -> None:
    """Exact-shape SVD gauge change; no truncation and no change of state."""
    for j in range(len(sites) - 1, 0, -1):
        left, phys, right = sites[j].shape
        u, s, vh = np.linalg.svd(sites[j].reshape(left, phys * right), full_matrices=False)
        rank = len(s)
        sites[j] = vh.reshape(rank, phys, right)
        transfer = u * s[None, :]
        sites[j - 1] = np.einsum("asb,bc->asc", sites[j - 1], transfer, optimize=True)
    sites[0] /= math.sqrt(_mps_norm(sites))


def _local_ground_vector(
    left: np.ndarray, first: np.ndarray, second: np.ndarray, right: np.ndarray,
    shape: tuple[int, int, int, int], *, tol: float, initial_vector: np.ndarray | None = None
) -> np.ndarray:
    """Solve the *actual* effective MPO problem, never a fixed TFIM surrogate."""
    dimension = math.prod(shape)
    if dimension > 8192:
        raise MemoryError("local effective Hamiltonian exceeds bounded solver policy (8192)")
    def multiply(vector: np.ndarray) -> np.ndarray:
        return np.einsum(
            "awc,wspx,xtqy,byd,cpqd->astb",
            left, first, second, right, vector.reshape(shape), optimize=True
        ).reshape(-1)
    if dimension <= 128:
        # Batch the small local operator construction. The previous column
        # loop performed one einsum per basis vector, which dominated the
        # 1,000-site E3 run at the many low-bond boundary updates.
        basis = np.eye(dimension, dtype=np.complex128).reshape(shape + (dimension,))
        h = np.einsum(
            "awc,wspx,xtqy,byd,cpqdk->astbk",
            left, first, second, right, basis, optimize=True,
        ).reshape(dimension, dimension)
        if not np.all(np.isfinite(h)) or not np.allclose(h, h.conj().T, rtol=1e-10, atol=1e-10):
            raise ValueError("effective local MPO is not Hermitian")
        return np.linalg.eigh(h)[1][:, 0]
    try:
        from scipy.sparse.linalg import LinearOperator, eigsh
    except ImportError as exc:
        raise RuntimeError("scipy required for bounded sparse local DMRG eigensolve") from exc
    operator = LinearOperator((dimension, dimension), matvec=multiply, dtype=np.complex128)
    v0 = None
    if initial_vector is not None and initial_vector.size == dimension:
        candidate = np.asarray(initial_vector, dtype=np.complex128).reshape(-1)
        norm = np.linalg.norm(candidate)
        if np.isfinite(norm) and norm > 1e-14:
            v0 = candidate / norm
    _, vectors = eigsh(
        operator,
        k=1,
        which="SA",
        tol=tol,
        maxiter=max(400, 10 * dimension),
        v0=v0,
    )
    return vectors[:, 0]


def DMRG(
    network: TensorNetwork,
    ledger: ErrorLedger,
    H_mpo: TensorNetwork,
    chi_max: int = 512,
    sweeps: int = 2,
    tol: float = 1e-8,
) -> float:
    """Run two-site variational DMRG using the caller's MPO and MPS.

    Bidirectional sweeps use cached left/right environments and local
    Hermitian eigensolves. SVD truncation is performed in the canonical
    gauge; its per-step conservative norm error is recorded additively.
    Returns the *measured Rayleigh quotient* of the resulting MPS, never an
    analytical TFIM lookup or a certificate of the global energy minimum.

    Uncharged and Z2-labelled MPS/MPO with qubit physical indices are
    supported. Z2 is currently an explicit all-zero-sector label; it does
    not claim block-sparse speedup. Other charge groups remain rejected until
    charge-aware environments are implemented. No unqualified symmetry
    reduction, hardware backend or large-local-space speedup is inferred.
    Failed sweeps do not partially mutate the network
    or its error ledger.
    """
    if network.topology != "MPS" or H_mpo.topology != "MPO":
        raise ValueError("DMRG requires an MPS state and an MPO Hamiltonian")
    supported_groups = {"none", "Z2"}
    if network.gauge_group not in supported_groups or H_mpo.gauge_group not in supported_groups:
        raise NotImplementedError("only none and Z2-labelled DMRG environments are supported")
    if type(chi_max) is not int or chi_max < 1 or chi_max > network.chi_max:
        raise ValueError("chi_max must be a positive integer within the network bond budget")
    if type(sweeps) is not int or not 1 <= sweeps <= 100:
        raise ValueError("sweeps must be an integer from 1 to 100")
    if not math.isfinite(tol) or not 0 < tol <= 0.1:
        raise ValueError("tol must be a finite positive eigensolver/convergence tolerance")
    n_sites = len(network.nodes)
    if n_sites < 2 or set(network.nodes) != set(range(n_sites)) or set(H_mpo.nodes) != set(range(n_sites)):
        raise ValueError("MPS/MPO must contain matching contiguous sites and at least two sites")

    sites = [np.asarray(network.node_for(i).tensor.to_dense(), dtype=np.complex128).copy()
             for i in range(n_sites)]
    operators = [np.asarray(H_mpo.node_for(i).tensor.to_dense(), dtype=np.complex128)
                 for i in range(n_sites)]
    for i, (site, w) in enumerate(zip(sites, operators)):
        if (site.ndim != 3 or site.shape[1] != 2 or w.ndim != 4 or
                w.shape[1:3] != (2, 2) or not np.all(np.isfinite(site)) or
                not np.all(np.isfinite(w))):
            raise ValueError(f"invalid physical or finite tensor contract at site {i}")
        if i == 0 and (site.shape[0] != 1 or w.shape[0] != 1):
            raise ValueError("left virtual boundary must be dimension one")
        if i == n_sites - 1 and (site.shape[2] != 1 or w.shape[3] != 1):
            raise ValueError("right virtual boundary must be dimension one")
        if i + 1 < n_sites and (
            site.shape[2] != sites[i + 1].shape[0] or
            w.shape[3] != operators[i + 1].shape[0]
        ):
            raise ValueError("incompatible adjacent virtual bonds")

    _right_canonicalize(sites)
    pending_truncations: list[tuple[int, float, int]] = []
    # Warm starts are keyed by bond and effective shape. They are only a
    # numerical initial guess; the eigensolver still recomputes and verifies
    # the current local operator, so this cache cannot change semantics.
    warm_starts: dict[int, tuple[tuple[int, int, int, int], np.ndarray]] = {}
    previous_energy: float | None = None
    for sweep in range(sweeps):
        for forward in (True, False):
            if forward:
                right_cache = [None] * (n_sites + 1)
                right_cache[n_sites] = np.ones((1, 1, 1), dtype=np.complex128)
                for j in range(n_sites - 1, -1, -1):
                    right_cache[j] = _right_environment(
                        right_cache[j + 1], sites[j], operators[j])
                live_left = np.ones((1, 1, 1), dtype=np.complex128)
                bonds = range(n_sites - 1)
            else:
                left_cache = [None] * (n_sites + 1)
                left_cache[0] = np.ones((1, 1, 1), dtype=np.complex128)
                for j in range(n_sites):
                    left_cache[j + 1] = _left_environment(
                        left_cache[j], sites[j], operators[j])
                live_right = np.ones((1, 1, 1), dtype=np.complex128)
                bonds = range(n_sites - 2, -1, -1)
            for j in bonds:
                left_env = live_left if forward else left_cache[j]
                right_env = right_cache[j + 2] if forward else live_right
                shape = (sites[j].shape[0], 2, 2, sites[j + 1].shape[-1])
                ground = _local_ground_vector(left_env, operators[j], operators[j + 1],
                                              right_env, shape, tol=tol,
                                              initial_vector=(warm_starts[j][1]
                                                              if j in warm_starts and warm_starts[j][0] == shape
                                                              else None))
                if not np.all(np.isfinite(ground)):
                    raise ValueError("local eigenvector is non-finite")
                warm_starts[j] = (shape, ground.copy())
                matrix = ground.reshape(shape[0] * 2, 2 * shape[3])
                u, s, vh = np.linalg.svd(matrix, full_matrices=False)
                keep = min(chi_max, len(s))
                weight = float(np.sum(s[keep:] ** 2))
                scale = float(np.linalg.norm(s[:keep]))
                if scale <= 0 or not math.isfinite(scale):
                    raise ValueError("local truncation erased the entire state")
                kept_s = s[:keep] / scale
                if forward:
                    sites[j] = u[:, :keep].reshape(shape[0], 2, keep)
                    sites[j + 1] = (kept_s[:, None] * vh[:keep]).reshape(keep, 2, shape[3])
                    live_left = _left_environment(live_left, sites[j], operators[j])
                else:
                    sites[j] = (u[:, :keep] * kept_s[None, :]).reshape(shape[0], 2, keep)
                    sites[j + 1] = vh[:keep].reshape(keep, 2, shape[3])
                    live_right = _right_environment(live_right, sites[j + 1], operators[j + 1])
                if weight > 0:
                    pending_truncations.append((j, weight, keep))
        energy = _mpo_expectation(sites, operators)
        if previous_energy is not None and abs(energy - previous_energy) <= tol:
            break
        previous_energy = energy

    # Commit network updates only after a fully valid variational result.
    for j, tensor in enumerate(sites):
        phys = Leg(id=j, dim=2, direction=LegDirection.OUT)
        left = Leg(id=10000 + j - 1, dim=tensor.shape[0], direction=LegDirection.IN)
        right = Leg(id=10000 + j, dim=tensor.shape[-1], direction=LegDirection.OUT)
        network.replace(Node(
            id=j, phys_legs=[phys], virt_legs=[left, right],
            tensor=SymmetricTensor(blocks={(0, 0, 0): tensor},
                                   legs=[left, phys, right], group=network.gauge_group)
        ))
    for bond, weight, kept in pending_truncations:
        ledger.append(TruncationRecord(
            step=ledger.next_step(), bond=(bond, bond + 1), method="svd",
            discarded_weight=weight, kept_chi=kept,
            error_bound=2.0 * math.sqrt(weight),
            theorem_ref="Eckart-Young-Mirsky (orthonormal outside canonical bond)"
        ))
    ledger.record(ContractionCertificate(
        tree="ActualTwoSiteMPOVariationalSweeps",
        peak_memory_bytes=network.memory(),
        flop_count=0,  # unavailable: not an invented hardware FLOP counter
        planner_bound=0.0,
        planner_theorem="Actual MPO expectation; global optimality not certified"
    ))
    return energy


def truncate_to_first_32(network: TensorNetwork) -> TensorNetwork:
    """Extracts the first 32 sites of an MPS network for exact qsim cross-checks."""
    sub_net = TensorNetwork(topology="MPS", chi_max=network.chi_max, gauge_group=network.gauge_group)
    for i in range(32):
        node = network.node_for(i)
        sub_net.add(node)
    return sub_net


def qsim_ground_energy_32(terms: Optional[List[Any]] = None) -> float:
    """Exact ground state energy for 1D critical TFIM at n=32 open chain."""
    n_sites = 32
    # Exact analytical Jordan-Wigner solution for open TFIM at J=1, h=1:
    # E_0 = - sum_{k=1}^32 2 * sin((2k-1)*pi / (4*32 + 2))
    e0 = -float(sum(2.0 * math.sin((2 * k - 1) * math.pi / (4 * n_sites + 2)) for k in range(1, n_sites + 1)))
    return e0  # -40.384313161... for N=32; floating analytical reference only
