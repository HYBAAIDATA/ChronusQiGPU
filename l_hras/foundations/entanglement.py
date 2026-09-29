"""D3 — F4 naming and real multipartite entanglement measures.

Two demands bundled here:

1. *"F4 is a 52-dimensional exceptional Lie group."* — In this codebase
   ``F4`` is **not** the Lie group. It is the cyclotomic field
   ``Q(zeta_8) = Q(sqrt(2)) + iQ(sqrt(2))`` (degree 4 over Q, hence the
   name), used because every Clifford+T amplitude lands exactly in it.
   No exceptional-group representation is claimed anywhere;
   ``field_info`` states the renaming precisely.

2. *"Schmidt rank is bipartite; you cannot use it as a witness for a
   6-partite state."* — Correct, and the fix is a real multipartite
   monotone: the Meyer-Wallach measure

       Q(psi) = 2 * (1 - (1/k) * sum_i Tr(rho_i^2))

   computed **exactly in F4** over the k intelligence parties, plus the
   per-cut Schmidt rank of each ``party | rest`` bipartition. Both are
   genuine measures: Q vanishes iff the state is a full product, and
   each Schmidt rank is the bipartite rank across that cut.

The honest measured result: the six-intelligence joint is a tensor
product of computational-basis states, so every party purity is
exactly 1, every cut has Schmidt rank 1, and Q = 0. There is no
multipartite entanglement to claim — the report says so.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping, Optional, Sequence

from .. import substrates

F4 = substrates.F4
_ZERO = F4(0)
_ONE = F4(1)


def field_info() -> dict[str, str]:
    """Disambiguate this codebase's ``F4`` from the exceptional Lie group."""
    return {
        "name_in_code": "F4",
        "mathematical_object": "Q(zeta_8) = Q(sqrt(2)) + iQ(sqrt(2))",
        "structure": "cyclotomic field, degree 4 over Q",
        "not": "the 52-dimensional exceptional Lie group F4 (Albert algebra)",
        "why": (
            "every Clifford+T gate amplitude is exactly representable in "
            "Q(zeta_8); off-grid phases raise NotInF4 rather than rounding"
        ),
        "element_repr": "(a, b, c, d) Fractions = (a + b*sqrt(2)) + i(c + d*sqrt(2))",
    }


def is_basis_state(state: Any) -> Optional[int]:
    """Basis index if ``state`` is a computational-basis state, else None."""
    index = None
    for i, amp in enumerate(state.amplitudes):
        if amp == _ZERO:
            continue
        if index is not None or amp != _ONE:
            return None
        index = i
    return index


def joint_exact_state(projections: Mapping[str, Any]) -> Any:
    """Tensor the per-party projections into one joint state vector.

    For the Guardian's actual projections (one basis state per party)
    the result is again a basis state — use ``joint_is_basis`` to detect
    that cheaply instead of materializing 2^(k*dim) amplitudes.
    """
    return substrates.exact_tensor_product(list(projections.values()))


def joint_is_basis(projections: Mapping[str, Any]) -> Optional[int]:
    """Joint basis index when every party is a basis state, else None.

    A tensor product of basis states is a basis state, so checking each
    party answers the question without building the joint.
    """
    joint = 0
    for name, state in projections.items():
        idx = is_basis_state(state)
        if idx is None:
            return None
        joint = (joint << state.num_qubits) | idx
    return joint


def partial_trace(state: Any, keep: Sequence[int]) -> list[list[F4]]:
    """Exact reduced density matrix rho_keep = Tr_rest |psi><psi| in F4.

    ``keep`` lists the retained qubit indices; the result is a
    ``2^len(keep)`` x ``2^len(keep)`` Hermitian matrix over F4.
    """
    keep = tuple(keep)
    n = state.num_qubits
    d_keep = 1 << len(keep)
    rest = tuple(q for q in range(n) if q not in set(keep))
    rho = [[F4(0) for _ in range(d_keep)] for _ in range(d_keep)]
    amps = state.amplitudes
    for i, a in enumerate(amps):
        if a == _ZERO:
            continue
        ka = sum(((i >> q) & 1) << j for j, q in enumerate(keep))
        for j, b in enumerate(amps):
            if b == _ZERO:
                continue
            if all(((i ^ j) >> q) & 1 == 0 for q in rest):
                kb = sum(((j >> q) & 1) << t for t, q in enumerate(keep))
                rho[ka][kb] = rho[ka][kb] + a * b.conjugate()
    return rho


def purity(rho: Sequence[Sequence[F4]]) -> Any:
    """Tr(rho^2) — real, in Q(sqrt(2)) subset of F4, for Hermitian rho."""
    d = len(rho)
    total = F4(0)
    for i in range(d):
        for j in range(d):
            total = total + rho[i][j] * rho[j][i]
    return total.real


def matrix_rank(matrix: Sequence[Sequence[F4]]) -> int:
    """Exact rank over F4 via Gaussian elimination (field arithmetic)."""
    rows = [list(r) for r in matrix]
    n_rows = len(rows)
    n_cols = len(rows[0]) if n_rows else 0
    rank = 0
    col = 0
    while rank < n_rows and col < n_cols:
        pivot = next((r for r in range(rank, n_rows) if rows[r][col] != _ZERO), None)
        if pivot is None:
            col += 1
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        inv = rows[rank][col].inverse()
        rows[rank] = [x * inv for x in rows[rank]]
        for r in range(n_rows):
            if r != rank and rows[r][col] != _ZERO:
                factor = rows[r][col]
                rows[r] = [x - factor * y for x, y in zip(rows[r], rows[rank])]
        rank += 1
        col += 1
    return rank


def schmidt_rank_per_party(state: Any, party_qubits: int) -> list[int]:
    """Schmidt rank of each ``party | rest`` cut for equal-size parties.

    For a pure state the Schmidt rank across a cut equals the rank of
    the coefficient matrix reshaped as party x rest — or equivalently
    the rank of rho_party, which is what we compute exactly.
    """
    n = state.num_qubits
    if n % party_qubits:
        raise ValueError("num_qubits must be a multiple of party_qubits")
    ranks = []
    for p in range(0, n, party_qubits):
        rho = partial_trace(state, tuple(range(p, p + party_qubits)))
        ranks.append(matrix_rank(rho))
    return ranks


def meyer_wallach_q(state: Any, party_qubits: int = 1) -> dict[str, Any]:
    """Meyer-Wallach multipartite measure over the parties, exact in F4.

    Q = 2 * (1 - (1/k) * sum_i Tr(rho_i^2)) for single-qubit parties
    (k qubits). For multi-qubit parties we report the same mean purity
    gap unnormalized — it is a faithful monotone (vanishes iff product)
    but not a normalized measure; the field is stated.
    """
    n = state.num_qubits
    if n % party_qubits:
        raise ValueError("num_qubits must be a multiple of party_qubits")
    parties = n // party_qubits
    purities = []
    for p in range(0, n, party_qubits):
        rho = partial_trace(state, tuple(range(p, p + party_qubits)))
        purities.append(purity(rho))
    inv_k = F4(Fraction(1, parties)).real  # 1/parties in Q(sqrt(2))
    mean = sum(purities) * inv_k  # exact field arithmetic
    normalized = party_qubits == 1
    one = F4(1).real
    two = F4(2).real
    q_val = two * (one - mean) if normalized else (one - mean)
    return {
        "Q": q_val.to_float(),
        "Q_exact": q_val,
        "party_purities": [p.to_float() for p in purities],
        "party_purities_exact": purities,
        "normalized": normalized,
        "measure": ("Meyer-Wallach Q in [0,1]" if normalized else "mean purity gap (monotone)"),
    }


def six_party_report(cfg: Any = None, materialize: bool = False) -> dict[str, Any]:
    """The honest entanglement audit of the six-intelligence joint.

    Detects the product structure without materializing the joint, then
    (optionally, on the default ``state_dim``) computes the exact
    Meyer-Wallach Q and per-party Schmidt ranks of the real joint.
    """
    from ..intelligences import INTELLIGENCES, init_intelligence_subspace

    if cfg is None:

        class _Cfg:
            state_dim = 3

        cfg = _Cfg()

    projections = {name: init_intelligence_subspace(name, cfg) for name in INTELLIGENCES}
    report: dict[str, Any] = {
        "field": field_info(),
        "parties": len(projections),
        "party_qubits": cfg.state_dim,
    }

    joint_idx = joint_is_basis(projections)
    report["joint_is_basis_product"] = joint_idx is not None
    if joint_idx is not None:
        report["joint_basis_index"] = joint_idx
        report["party_purities"] = [1.0] * len(projections)
        report["schmidt_ranks_per_cut"] = [1] * len(projections)
        report["meyer_wallach_q"] = 0.0
        report["verdict"] = (
            "the joint is a computational-basis product state: every party "
            "purity is exactly 1, every bipartition Schmidt rank is 1, and "
            "the Meyer-Wallach measure is exactly 0 — no multipartite "
            "entanglement is present"
        )
        return report

    if materialize:
        joint = joint_exact_state(projections)
        report["meyer_wallach"] = meyer_wallach_q(joint, cfg.state_dim)
        report["schmidt_ranks_per_cut"] = schmidt_rank_per_party(joint, cfg.state_dim)
        report["verdict"] = "measured on the materialized joint"
    else:
        report["verdict"] = (
            "joint is not a basis product; call with materialize=True to "
            "compute exact purities on the materialized state"
        )
    return report


__all__ = [
    "field_info",
    "is_basis_state",
    "joint_exact_state",
    "joint_is_basis",
    "partial_trace",
    "purity",
    "matrix_rank",
    "schmidt_rank_per_party",
    "meyer_wallach_q",
    "six_party_report",
]
