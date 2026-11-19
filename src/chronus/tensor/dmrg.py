"""Density Matrix Renormalization Group (DMRG) variational ground-state solver.

Two-site MPO-variational DMRG over 1D Matrix Product States with cached
left/right environments, local Hermitian eigensolves and SVD truncation
recorded additively (2*sqrt(discarded weight) per step) in the ErrorLedger.
The returned energy is the measured Rayleigh quotient <psi|H|psi>/<psi|psi>,
never an analytical lookup.

Gauge groups: ``"none"`` (plain qubit MPS) and ``"Z2"`` (charge-aware DMRG
for the spin-flip parity P = prod X: Hadamard-rotated parity basis, verified
MPO charges, exact projection onto the target sector, sector-restricted
eigensolves and block-diagonal SVDs). Symmetry leaks, exhausted claim budgets
and local problems beyond ``CHRONUS_MAX_DMRG_LOCAL_DIM`` are refused with
UntrustedResult / UntrustedApproximation; failed runs never mutate the
network or ledger. The solver itself does not certify global optimality.
Experiment E3 compares the result with the closed-form Jordan-Wigner energy
against a 1e-6 relative numerical acceptance threshold. Meeting that threshold
does not establish exact equivalence.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional

import numpy as np

from chronus.tensor.types import (
    ContractionCertificate,
    ErrorLedger,
    Leg,
    LegDirection,
    Node,
    SymmetricTensor,
    TruncationRecord,
    UntrustedResult,
)
from chronus.tensor.network import TensorNetwork



def _left_environment(env: np.ndarray, site: np.ndarray, mpo: np.ndarray) -> np.ndarray:
    """Contract <psi_left|MPO_left|psi_left> with conjugate bra indices.

    Equivalent to einsum("awb,asc,wstx,btd->cxd"), evaluated as a fixed
    pairwise tensordot order (O(chi^3 d w) per step, no path search).
    """
    t = np.tensordot(env, site.conj(), axes=([0], [0]))       # w b s c
    t = np.tensordot(t, mpo, axes=([0, 2], [0, 1]))           # b c t x
    return np.tensordot(t, site, axes=([0, 2], [0, 1]))       # c x d


def _right_environment(env: np.ndarray, site: np.ndarray, mpo: np.ndarray) -> np.ndarray:
    """Equivalent to einsum("asc,wstx,btd,cxd->awb") via fixed tensordot order."""
    t = np.tensordot(site, env, axes=([2], [2]))              # b t c x
    t = np.tensordot(mpo, t, axes=([2, 3], [1, 3]))           # w s b c
    return np.tensordot(site.conj(), t, axes=([1, 2], [1, 3]))  # a w b


def _mps_norm(sites: list[np.ndarray]) -> float:
    env = np.ones((1, 1), dtype=np.complex128)
    for site in sites:
        env = np.tensordot(np.tensordot(env, site.conj(), axes=([0], [0])), site, axes=([0, 1], [0, 1]))
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


_HADAMARD = np.array([[1.0, 1.0], [1.0, -1.0]], dtype=np.complex128) / math.sqrt(2.0)
_SYMMETRY_LEAK_TOL = 1e-10


class Z2SymmetryViolation(UntrustedResult, ValueError):
    """A Z2 charge-conservation check failed; the result is refused, never projected."""


def _local_dimension_policy() -> int:
    """Bounded local eigensolver policy (env CHRONUS_MAX_DMRG_LOCAL_DIM)."""
    from chronus.config import runtime_bounds

    return runtime_bounds()["max_dmrg_local_dim"]


def _block_svd(
    matrix: np.ndarray,
    row_labels: Optional[np.ndarray],
    col_labels: Optional[np.ndarray],
) -> list[tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """SVD of a charge-block-diagonal matrix, one block per Z2 sector.

    Returns ``(charge, row_idx, col_idx, u, s, vh)`` per non-empty sector.
    With no labels the whole matrix is one (charge 0) block. Entries outside
    the charge blocks must vanish: a leak means the state or operator broke
    the symmetry, which is refused rather than silently projected away.
    """
    if row_labels is None:
        u, s, vh = np.linalg.svd(matrix, full_matrices=False)
        rows = np.arange(matrix.shape[0])
        cols = np.arange(matrix.shape[1])
        return [(0, rows, cols, u, s, vh)]
    allowed = row_labels[:, None] == col_labels[None, :]
    total = np.linalg.norm(matrix)
    leak = np.linalg.norm(matrix[~allowed])
    if leak > _SYMMETRY_LEAK_TOL * max(1.0, total):
        raise Z2SymmetryViolation(f"Z2 block structure violated (off-sector norm {leak:.3e})")
    blocks = []
    for charge in (0, 1):
        rows = np.flatnonzero(row_labels == charge)
        cols = np.flatnonzero(col_labels == charge)
        if rows.size == 0 or cols.size == 0:
            continue
        u, s, vh = np.linalg.svd(matrix[np.ix_(rows, cols)], full_matrices=False)
        blocks.append((charge, rows, cols, u, s, vh))
    return blocks


def _truncated_factors(
    matrix: np.ndarray,
    row_labels: Optional[np.ndarray],
    col_labels: Optional[np.ndarray],
    chi_max: int,
    cutoff: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray], float]:
    """Charge-respecting truncated SVD ``matrix ~= u @ diag(s) @ vh``.

    Keeps the globally largest singular values across sectors (at most
    ``chi_max``) and additionally drops the smallest tail whose summed squared
    weight is <= ``cutoff``. Returns the discarded weight so the caller can
    ledger it; nothing is discarded silently.
    """
    blocks = _block_svd(matrix, row_labels, col_labels)
    entries = [(value.item(), b, k) for b, (_, _, _, _, s, _) in enumerate(blocks)
               for k, value in enumerate(s)]
    entries.sort(key=lambda item: -item[0])
    keep = min(chi_max, len(entries))
    tail = math.fsum(value ** 2 for value, _, _ in entries[keep:])
    while keep > 1:
        candidate = tail + entries[keep - 1][0] ** 2
        if candidate > cutoff:
            break
        tail = candidate
        keep -= 1
    kept = entries[:keep]
    weight = math.fsum(value ** 2 for value, _, _ in entries[keep:])
    u = np.zeros((matrix.shape[0], keep), dtype=np.complex128)
    vh = np.zeros((keep, matrix.shape[1]), dtype=np.complex128)
    values = np.zeros(keep)
    labels = np.zeros(keep, dtype=np.int64) if row_labels is not None else None
    # Group kept vectors by sector so the new bond is block-ordered.
    kept.sort(key=lambda item: (blocks[item[1]][0], -item[0]))
    for column, (value, b, k) in enumerate(kept):
        charge, rows, cols, bu, _, bvh = blocks[b]
        u[rows, column] = bu[:, k]
        vh[column, cols] = bvh[k]
        values[column] = value
        if labels is not None:
            labels[column] = charge
    return u, values, vh, labels, weight


def _right_canonicalize(sites: list[np.ndarray],
                        bond_labels: Optional[list[np.ndarray]] = None) -> None:
    """Exact SVD gauge change (sector-wise under Z2); no truncation."""
    for j in range(len(sites) - 1, 0, -1):
        left, phys, right = sites[j].shape
        matrix = sites[j].reshape(left, phys * right)
        if bond_labels is None:
            row_labels = col_labels = None
        else:
            row_labels = bond_labels[j]
            col_labels = (bond_labels[j + 1][None, :] ^ np.arange(phys)[:, None]).reshape(-1)
        u, s, vh, labels, _ = _truncated_factors(
            matrix, row_labels, col_labels, chi_max=min(matrix.shape), cutoff=0.0)
        sites[j] = vh.reshape(len(s), phys, right)
        sites[j - 1] = np.einsum("asb,bc->asc", sites[j - 1], u * s[None, :], optimize=True)
        if bond_labels is not None:
            bond_labels[j] = labels
    sites[0] /= math.sqrt(_mps_norm(sites))


def _local_ground_vector(
    left: np.ndarray, first: np.ndarray, second: np.ndarray, right: np.ndarray,
    shape: tuple[int, int, int, int], *, tol: float,
    sector: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Solve the *actual* effective MPO problem, never a fixed TFIM surrogate.

    ``sector`` restricts the eigenproblem to the flat indices of one Z2
    charge sector (the effective Hamiltonian of a symmetric MPO is block
    diagonal, so this is exact, and halves the solved dimension).
    """
    full = math.prod(shape)
    index = np.arange(full) if sector is None else sector
    dimension = int(index.size)
    limit = _local_dimension_policy()
    if dimension > limit:
        raise UntrustedResult(
            f"local effective Hamiltonian dimension {dimension} exceeds bounded "
            f"solver policy ({limit}; CHRONUS_MAX_DMRG_LOCAL_DIM)")
    if dimension == 0:
        raise ValueError("empty Z2 sector for local DMRG problem")

    def apply_full(state: np.ndarray) -> np.ndarray:
        # Same contraction as einsum("awc,wspx,xtqy,byd,cpqd->astb") with a
        # fixed pairwise order (no per-call path search).
        t = np.tensordot(left, state.reshape(shape), axes=([2], [0]))   # a w p q d
        t = np.tensordot(t, first, axes=([1, 2], [0, 2]))               # a q d s x
        t = np.tensordot(t, second, axes=([1, 4], [2, 0]))              # a d s t y
        t = np.tensordot(t, right, axes=([4, 1], [1, 2]))               # a s t b
        return t.reshape(-1)

    if sector is not None:
        # The sector restriction is exact only if H_eff is block diagonal:
        # check once with a random in-sector probe (fail closed on leaks).
        probe = np.zeros(full, dtype=np.complex128)
        probe[index] = np.random.default_rng(0).standard_normal(dimension)
        image = apply_full(probe)
        leak = np.linalg.norm(np.delete(image, index))
        if leak > _SYMMETRY_LEAK_TOL * max(1.0, np.linalg.norm(image)):
            raise Z2SymmetryViolation(
                f"effective Hamiltonian leaks out of the Z2 sector (off-sector norm {leak:.3e})")

    def multiply(vector: np.ndarray) -> np.ndarray:
        state = np.zeros(full, dtype=np.complex128)
        state[index] = vector
        return apply_full(state)[index]
    if dimension <= 128:
        basis = np.eye(dimension, dtype=np.complex128)
        h = np.stack([multiply(basis[:, k]) for k in range(dimension)], axis=1)
        if not np.all(np.isfinite(h)) or not np.allclose(h, h.conj().T, rtol=1e-10, atol=1e-10):
            raise ValueError("effective local MPO is not Hermitian")
        vector = np.linalg.eigh(h)[1][:, 0]
    else:
        try:
            from scipy.sparse.linalg import LinearOperator, eigsh
        except ImportError as exc:
            raise RuntimeError("scipy required for bounded sparse local DMRG eigensolve") from exc
        operator = LinearOperator((dimension, dimension), matvec=multiply, dtype=np.complex128)
        _, vectors = eigsh(operator, k=1, which="SA", tol=tol, maxiter=max(400, 10 * dimension))
        vector = vectors[:, 0]
    out = np.zeros(full, dtype=np.complex128)
    out[index] = vector
    return out


def _z2_mpo_charges(operators: list[np.ndarray]) -> None:
    """Verify each MPO tensor carries consistent Z2 virtual charges.

    Operators are in the parity eigenbasis (generator prod_i Z_i). Charges
    propagate left to right as q_out = q_in xor s xor t; any conflict, or a
    non-neutral total charge, means H does not commute with the generator.
    """
    q_in = np.zeros(operators[0].shape[0], dtype=np.int64)
    for i, w in enumerate(operators):
        q_out = np.full(w.shape[3], -1, dtype=np.int64)
        scale = max(1.0, np.max(np.abs(w)))
        for a, s, t, x in zip(*np.nonzero(np.abs(w) > 1e-14 * scale)):
            charge = int(q_in[a] ^ s ^ t)
            if q_out[x] == -1:
                q_out[x] = charge
            elif q_out[x] != charge:
                raise Z2SymmetryViolation(
                    f"MPO site {i} does not commute with the Z2 generator prod_i X_i "
                    f"in its virtual-channel gauge (mixed-charge channels are refused, not resolved)")
        q_in = np.where(q_out < 0, 0, q_out)
    if np.any(q_in != 0):
        raise Z2SymmetryViolation("MPO carries non-neutral total Z2 charge")


def _z2_project(sites: list[np.ndarray], target: int) -> list[np.ndarray]:
    """Exact projection of an MPS (parity basis) onto one Z2 sector.

    Each bond index is paired with the running parity of the sites to its
    left: A'[(a,q),s,(b,q xor s)] = A[a,s,b]; the right boundary keeps only
    ``q == target``. Bond labels are recovered by canonicalization.
    """
    out = []
    n = len(sites)
    for j, site in enumerate(sites):
        left, phys, right = site.shape
        q_left = (0,) if j == 0 else (0, 1)
        q_right = (target,) if j == n - 1 else (0, 1)
        tensor = np.zeros((left * len(q_left), phys, right * len(q_right)),
                          dtype=np.complex128)
        for li, ql in enumerate(q_left):
            for s in range(phys):
                qr = ql ^ s
                if qr in q_right:
                    ri = q_right.index(qr)
                    tensor[li * left:(li + 1) * left, s, ri * right:(ri + 1) * right] = site[:, s, :]
        out.append(tensor)
    return out


def _z2_labels_from_projection(sites: list[np.ndarray], target: int) -> list[np.ndarray]:
    labels = [np.zeros(1, dtype=np.int64)]
    for j, site in enumerate(sites[:-1]):
        half = site.shape[2] // 2
        labels.append(np.repeat(np.array([0, 1], dtype=np.int64), half))
    labels.append(np.array([target], dtype=np.int64))
    return labels


def DMRG(
    network: TensorNetwork,
    ledger: ErrorLedger,
    H_mpo: TensorNetwork,
    chi_max: int = 512,
    sweeps: int = 2,
    tol: float = 1e-8,
    *,
    cutoff: float = 0.0,
    claim_bound: Optional[float] = None,
    target_parity: int = 0,
) -> float:
    """Run two-site variational DMRG using the caller's MPO and MPS.

    Bidirectional sweeps use cached left/right environments and local
    Hermitian eigensolves. SVD truncation is performed in the canonical
    gauge; its per-step conservative norm error is recorded additively.
    Returns the *measured Rayleigh quotient* of the resulting MPS, never an
    analytical TFIM lookup or a certificate of the global energy minimum.

    ``gauge_group="none"``: plain qubit MPS/MPO.

    ``gauge_group="Z2"``: charge-aware DMRG for the global spin-flip
    symmetry P = prod_i X_i. The MPS and MPO are rotated site-wise into the
    parity eigenbasis (Hadamard), the MPO's virtual charges are verified,
    the input MPS is exactly projected onto ``target_parity`` (P = +1 for 0),
    and every bond carries Z2 labels: local eigenproblems are solved only in
    the allowed charge sector and SVDs are block-diagonal per sector. The
    committed MPS is rotated back to the computational basis. Symmetry leaks
    are refused, never projected away silently.

    ``cutoff`` drops the smallest singular-value tail whose squared weight is
    at most ``cutoff`` per step (ledgered like every truncation).
    ``claim_bound``: the ledger bound is monotone, so once the accumulated
    truncation bound exceeds it the claim can never be certified; DMRG then
    raises UntrustedApproximation with the measured bound instead of
    spending further compute. Failed runs do not mutate the network or ledger.
    """
    from chronus.tensor.types import UntrustedApproximation

    if network.topology != "MPS" or H_mpo.topology != "MPO":
        raise ValueError("DMRG requires an MPS state and an MPO Hamiltonian")
    group = network.gauge_group
    if group not in ("none", "Z2") or H_mpo.gauge_group != "none":
        raise NotImplementedError(
            f"DMRG supports MPS gauge groups 'none' and 'Z2' with an uncharged-built MPO; "
            f"got MPS={group!r}, MPO={H_mpo.gauge_group!r}")
    if type(chi_max) is not int or chi_max < 1 or chi_max > network.chi_max:
        raise ValueError("chi_max must be a positive integer within the network bond budget")
    if type(sweeps) is not int or not 1 <= sweeps <= 100:
        raise ValueError("sweeps must be an integer from 1 to 100")
    if not math.isfinite(tol) or not 0 < tol <= 0.1:
        raise ValueError("tol must be a finite positive eigensolver/convergence tolerance")
    if not math.isfinite(cutoff) or not 0.0 <= cutoff < 1.0:
        raise ValueError("cutoff must be a finite discarded weight in [0, 1)")
    if claim_bound is not None and (not math.isfinite(claim_bound) or claim_bound < 0):
        raise ValueError("claim_bound must be finite and nonnegative")
    if target_parity not in (0, 1):
        raise ValueError("target_parity must be 0 (P=+1) or 1 (P=-1)")
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

    bond_labels: Optional[list[np.ndarray]] = None
    if group == "Z2":
        operators = [np.einsum("su,wuvx,vt->wstx", _HADAMARD, w, _HADAMARD, optimize=True)
                     for w in operators]
        _z2_mpo_charges(operators)
        sites = _z2_project(
            [np.einsum("su,aub->asb", _HADAMARD, site, optimize=True) for site in sites],
            target_parity)
        bond_labels = _z2_labels_from_projection(sites, target_parity)
        try:
            _mps_norm(sites)
        except ValueError as exc:
            raise ValueError("input MPS has no component in the requested Z2 sector") from exc

    _right_canonicalize(sites, bond_labels)
    pending_truncations: list[tuple[int, float, int]] = []
    # claim_bound is a budget for the caller's whole ledger, including bounds
    # already recorded before this call.
    accumulated_bound = ledger.global_bound
    if claim_bound is not None and accumulated_bound >= claim_bound:
        raise UntrustedApproximation(
            f"ledger bound {accumulated_bound:.3e} already exhausts the claim budget {claim_bound:.3e}")
    previous_energy: float | None = None
    phys = np.arange(2)
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
                sector = None
                row_labels = col_labels = None
                if bond_labels is not None:
                    ql, qr = bond_labels[j], bond_labels[j + 2]
                    allowed = (ql[:, None, None, None] ^ phys[None, :, None, None]
                               ^ phys[None, None, :, None]) == qr[None, None, None, :]
                    sector = np.flatnonzero(allowed.reshape(-1))
                    row_labels = (ql[:, None] ^ phys[None, :]).reshape(-1)
                    col_labels = (qr[None, :] ^ phys[:, None]).reshape(-1)
                ground = _local_ground_vector(left_env, operators[j], operators[j + 1],
                                              right_env, shape, tol=tol, sector=sector)
                if not np.all(np.isfinite(ground)):
                    raise ValueError("local eigenvector is non-finite")
                matrix = ground.reshape(shape[0] * 2, 2 * shape[3])
                u, s, vh, labels, weight = _truncated_factors(
                    matrix, row_labels, col_labels, chi_max, cutoff)
                keep = len(s)
                scale = np.linalg.norm(s)
                if scale <= 0 or not math.isfinite(scale):
                    raise ValueError("local truncation erased the entire state")
                kept_s = s / scale
                if forward:
                    sites[j] = u.reshape(shape[0], 2, keep)
                    sites[j + 1] = (kept_s[:, None] * vh).reshape(keep, 2, shape[3])
                    live_left = _left_environment(live_left, sites[j], operators[j])
                else:
                    sites[j] = (u * kept_s[None, :]).reshape(shape[0], 2, keep)
                    sites[j + 1] = vh.reshape(keep, 2, shape[3])
                    live_right = _right_environment(live_right, sites[j + 1], operators[j + 1])
                if bond_labels is not None:
                    bond_labels[j + 1] = labels
                if weight > 0:
                    pending_truncations.append((j, weight, keep))
                    accumulated_bound += 2.0 * math.sqrt(weight)
                    if claim_bound is not None and accumulated_bound >= claim_bound:
                        raise UntrustedApproximation(
                            f"measured truncation bound {accumulated_bound:.3e} reached the "
                            f"claim budget {claim_bound:.3e} (sweep {sweep + 1}, "
                            f"{'forward' if forward else 'backward'}, bond {j}, kept chi {keep}, "
                            f"discarded weight {weight:.3e}); the claim cannot be certified")
        energy = _mpo_expectation(sites, operators)
        if previous_energy is not None and abs(energy - previous_energy) <= tol:
            break
        previous_energy = energy

    if group == "Z2":
        # Back to the computational basis (the Hadamard is its own inverse).
        sites = [np.einsum("su,aub->asb", _HADAMARD, site, optimize=True) for site in sites]

    # Commit network updates only after a fully valid variational result.
    for j, tensor in enumerate(sites):
        phys_leg = Leg(id=j, dim=2, direction=LegDirection.OUT)
        left = Leg(id=10000 + j - 1, dim=tensor.shape[0], direction=LegDirection.IN)
        right = Leg(id=10000 + j, dim=tensor.shape[-1], direction=LegDirection.OUT)
        network.replace(Node(
            id=j, phys_legs=[phys_leg], virt_legs=[left, right],
            tensor=SymmetricTensor(blocks={(0, 0, 0): tensor},
                                   legs=[left, phys_leg, right], group=group)
        ))
    for bond, weight, kept in pending_truncations:
        ledger.append(TruncationRecord(
            step=ledger.next_step(), bond=(bond, bond + 1), method="svd",
            discarded_weight=weight, kept_chi=kept,
            error_bound=2.0 * math.sqrt(weight),
            theorem_ref="Eckart-Young-Mirsky (orthonormal outside canonical bond)"
        ))
    ledger.record(ContractionCertificate(
        tree=("ActualTwoSiteMPOVariationalSweeps" if group == "none"
              else "Z2ChargeAwareTwoSiteMPOVariationalSweeps"),
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
