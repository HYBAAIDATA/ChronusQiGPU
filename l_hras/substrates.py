"""The CONSUME seam — every blueprint ``CONSUME:`` resolves here.

This module is the only place ``l_hras`` imports the substrates. When the
package is lifted to the enterprise repo, this file is the whole boundary:
keep it satisfied and the Guardian stands anywhere kellogg/aethel/toe
stand.

    kellogg.exact_tensor     exact F4 state vectors, Bell state, Schmidt rank
    kellogg.quantum_tensor   von Neumann entropy, purity, density matrices
    kellogg.tensor_ml        joint/partial-trace over the exact tensor
    kellogg.scales           Lucas ladder, Zeckendorf legality, Cassini
    kellogg.first_principles standard-map Lyapunov / Greene / action variance
    aethel.storage           Fibonacci-addressed block space + Cassini ledger
    aethel.zeckendorf        hardened Zeckendorf codec (non-adjacent masks)
    aethel.fibonacci         Cassini quadruples / fibonacci_index
    toe.phi_klein            Klein → Poincaré 11D fold/unfold
    toe.poincare_golden_11d  Zeckendorf certificate, golden distance
    toe.poincare_yangmills   finite gauge gap (mass-gap provenance)
    toe.operator_compilers   compile/digest/cost of a request
    toe.causal_ladder        Pearl L1/L2/L3
    toe.bridge               trajectory prediction, state tomography
"""

from __future__ import annotations

import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np

# The package is a consumer of the repo's substrates. When l_hras is
# lifted, these imports resolve against the enterprise checkout the same
# way; they are not vendored here.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aethel.fibonacci import cassini_holds, cassini_quadruple  # noqa: E402
from aethel.storage import AddressSpace  # noqa: E402
from aethel.zeckendorf import (  # noqa: E402
    HardenedZeckendorfCodec,
    apply_zeckendorf_compression,
)
from kellogg.exact_tensor import (  # noqa: E402
    F4,
    ExactStateVector,
    hermitian_eigenvalues,
)
from kellogg.first_principles import (  # noqa: E402
    action_variance,
    golden_ratio,
    greene_residue,
    maximal_lyapunov,
)
from kellogg.quantum_tensor import (  # noqa: E402
    Complex,
    ComplexMatrix,
    QuantumState,
    project_to_32_face,
    von_neumann_entropy,
)
from kellogg.scales import lucas  # noqa: E402
from toe.bridge import TOEBridge  # noqa: E402
from toe.causal_ladder import (  # noqa: E402
    CausalGraph,
    StructuralCausalModel,
    association_query,
    counterfactual_query,
    do_operator,
)
from toe.operator_compilers import compile_operator  # noqa: E402
from toe.phi_klein import fold as klein_fold, unfold as klein_unfold  # noqa: E402
from toe.poincare_golden_11d import (  # noqa: E402
    compute_zeckendorf_certificate,
    poincare_golden_distance,
)
from toe.poincare_yangmills import finite_gauge_gap  # noqa: E402

# ---------------------------------------------------------------------------
# Exact tensor (CONSUME:kellogg.exact_tensor)
# ---------------------------------------------------------------------------

_HALF_SQRT2 = F4(0, Fraction(1, 2), 0, 0)  # 1/sqrt(2), exactly
_F4_ZERO = F4(0)
_F4_ONE = F4(1)


def exact_zeros(num_qubits: int) -> ExactStateVector:
    """The vacuum joint state |0...0> — the substrate's ``zeros``."""
    return ExactStateVector.basis(num_qubits, 0)


def exact_basis(num_qubits: int, index: int) -> ExactStateVector:
    return ExactStateVector.basis(num_qubits, index)


def exact_tensor_product(vectors: Sequence[ExactStateVector]) -> ExactStateVector:
    if not vectors:
        raise ValueError("tensor product requires at least one vector")
    combined = vectors[0]
    for vec in vectors[1:]:
        combined = combined.tensor(vec)
    return combined


def bell_state() -> ExactStateVector:
    """|00>+|11> over sqrt(2), built exactly in F4."""
    return ExactStateVector(2, (_HALF_SQRT2, _F4_ZERO, _F4_ZERO, _HALF_SQRT2))


def _f4_partial_trace(state: ExactStateVector, keep: int) -> list[list[F4]]:
    """Reduced 2x2 density matrix of a two-qubit exact state.

    ``keep=0`` returns Tr_B(rho); ``keep=1`` returns Tr_A(rho).
    """
    if state.num_qubits != 2:
        raise ValueError("f4 partial trace is declared for two qubits")
    amps = state.amplitudes
    rho = [[_F4_ZERO, _F4_ZERO], [_F4_ZERO, _F4_ZERO]]
    for i in range(2):
        for j in range(2):
            acc = _F4_ZERO
            for k in range(2):
                if keep == 0:
                    left, right = amps[2 * i + k], amps[2 * j + k]
                else:
                    left, right = amps[i + 2 * k], amps[j + 2 * k]
                acc = acc + left * right.conjugate()
            rho[i][j] = acc
    return rho


def schmidt_rank(state: ExactStateVector, *, tol: float = 1e-12) -> int:
    """Number of non-zero eigenvalues of the reduced state."""
    rho = _f4_partial_trace(state, 0)
    eigs = hermitian_eigenvalues(rho, tol=tol)
    return sum(1 for lam in eigs if lam > tol)


def partial_trace_bell(state: ExactStateVector, keep: int) -> list[list[F4]]:
    return _f4_partial_trace(state, keep)


def is_maximally_mixed(rho: Sequence[Sequence[F4]]) -> bool:
    dim = len(rho)
    for i in range(dim):
        for j in range(dim):
            expected = F4(Fraction(1, dim)) if i == j else _F4_ZERO
            if rho[i][j] != expected:
                return False
    return True


def f4_correlations(
    graph: Mapping[tuple[int, int], Any],
    projections: Mapping[str, ExactStateVector],
    order: Sequence[str],
) -> dict[tuple[str, str], F4]:
    """Pairwise ZZ-parity correlations over the F4 basis projections.

    For basis index ``b`` the ZZ parity of edge ``(i, j)`` on the two
    low-order qubits is ``(-1)^(b_i[0] ^ b_j[0])`` — exact, in F4.
    """
    out: dict[tuple[str, str], F4] = {}
    for a_name, b_name in ((a, b) for a, b in graph if a in order and b in order):
        ia = _basis_index_of(projections[a_name])
        ib = _basis_index_of(projections[b_name])
        parity = ((ia & 1) ^ (ib & 1)) or (((ia >> 1) & 1) ^ ((ib >> 1) & 1))
        out[(a_name, b_name)] = F4(-1) if parity else _F4_ONE
    return out


def _basis_index_of(state: ExactStateVector) -> int:
    for i, amp in enumerate(state.amplitudes):
        if amp == _F4_ONE:
            return i
    return 0


def f4_to_float(value: F4) -> float:
    return value.real.to_float() + float(value.c) * 0.0  # real channel only


# ---------------------------------------------------------------------------
# Quantum tensor — entropy / purity (CONSUME:toe.bridge.von_neumann_entropy,
# CONSUME:toe.bridge.purity, CONSUME:kellogg.quantum_tensor)
# ---------------------------------------------------------------------------


def density_matrix(rows: Sequence[Sequence[Any]]) -> ComplexMatrix:
    """Lift a real/F4 density matrix onto the ComplexMatrix substrate."""

    def _f(v: Any) -> float:
        return v.real.to_float() if isinstance(v, F4) else float(v)

    data = [[Complex(_f(v), 0.0) for v in row] for row in rows]
    n = len(data)
    return ComplexMatrix(n, len(data[0]) if n else 0, data)


def vn_entropy(rows: Sequence[Sequence[float]]) -> float:
    return float(von_neumann_entropy(density_matrix(rows)))


def purity(rows: Sequence[Sequence[float]]) -> float:
    rho = density_matrix(rows)
    return float(rho.matmul(rho).trace().re)


def apply_unitary_to_density(
    rows: Sequence[Sequence[float]], unitary: ComplexMatrix
) -> list[list[float]]:
    """rho -> U rho U^dagger, projected back to real parts."""
    rho = density_matrix(rows)
    out = unitary.matmul(rho).matmul(unitary.dagger())
    return [[out.data[i][j].re for j in range(out.cols)] for i in range(out.rows)]


def rotation_unitary(angle: float) -> ComplexMatrix:
    c, s = math.cos(angle), math.sin(angle)
    return ComplexMatrix(
        2, 2, [[Complex(c, 0.0), Complex(-s, 0.0)], [Complex(s, 0.0), Complex(c, 0.0)]]
    )


def dephase(rows: Sequence[Sequence[float]], keep: float = 0.0) -> list[list[float]]:
    """Kill off-diagonals (decoherence). ``keep`` in [0,1] scales what
    coherence survives — 0 is full dephasing."""
    n = len(rows)
    return [[rows[i][j] if i == j else rows[i][j] * keep for j in range(n)] for i in range(n)]


def mix_with_identity(rows: Sequence[Sequence[float]], epsilon: float) -> list[list[float]]:
    """rho -> (1-eps) rho + eps I/d — the depolarizing channel."""
    n = len(rows)
    return [
        [(1.0 - epsilon) * rows[i][j] + (epsilon / n if i == j else 0.0) for j in range(n)]
        for i in range(n)
    ]


def state_distance(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> float:
    """Frobenius distance ||a - b||_F between two real matrices — the
    declared divergence measure for belief states."""
    n = len(a)
    return math.sqrt(
        sum((float(a[i][j]) - float(b[i][j])) ** 2 for i in range(n) for j in range(len(a[i])))
    )


def reachable_faces(state_3d: Sequence[float]) -> int:
    """Count non-trivial faces on the 32-face dual-overlay frame."""
    weights = project_to_32_face(tuple(float(v) for v in state_3d[:3]))
    return sum(1 for w in weights if abs(w) > 1e-9)


# ---------------------------------------------------------------------------
# Traversal map + first principles (CONSUME:toe.traversal_map,
# CONSUME:toe.first_principles)
# ---------------------------------------------------------------------------

_TWO_PI = 2.0 * math.pi


def to_point(position: Sequence[float]) -> tuple[float, float]:
    """Map an event position onto the unit torus [0,1)^2."""
    x, y = float(position[0]), float(position[1])
    return (x % 1.0, y % 1.0)


def distance(position: Sequence[float], target: Sequence[float]) -> float:
    """Torus geodesic distance between two manifold points."""
    p, t = to_point(position), to_point(target)
    dx = min(abs(p[0] - t[0]), 1.0 - abs(p[0] - t[0]))
    dy = min(abs(p[1] - t[1]), 1.0 - abs(p[1] - t[1]))
    return math.hypot(dx, dy)


def boundary() -> dict[str, Any]:
    return {"shape": "torus", "period": 1.0, "unit": "poincare_ball"}


def lyapunov_at(point: Sequence[float], steps: int = 64, K: float = 0.971635) -> float:
    """Measured standard-map Lyapunov exponent at a torus point.

    The returned value is ``1 + max(0, raw)`` — the gauge multiplier of
    the Yang–Mills evaluator. It is measured, never asserted.
    """
    raw = maximal_lyapunov(float(K), float(point[0]) % 1.0, float(point[1]) % 1.0, int(steps))
    return 1.0 + max(0.0, raw)


def manifold_classify(point: Sequence[float]) -> dict[str, Any]:
    """Classify a torus point by measured KAM diagnostics."""
    p = to_point(point)
    lyap = maximal_lyapunov(0.971635, p[0], p[1], 64)
    greene, _approx = greene_residue(0.5, 8, 1)
    act_var = action_variance(0.5, p[0], p[1], 64)
    region = "chaotic_sea" if lyap > 0.05 else "elliptic_island"
    winding = int((p[0] * 4) % 4)
    return {
        "manifold": "standard_map_torus",
        "region": region,
        "radius": math.hypot(p[0] - 0.5, p[1] - 0.5),
        "homotopy": f"winding_{winding}",
        "lyapunov": float(lyap),
        "greene": float(greene),
        "action_variance": float(act_var),
        "period1": abs(p[0] - p[1]) < 1e-12,
    }


def curvature_at(point: Sequence[float]) -> dict[str, float]:
    """Sectional curvature proxy from measured local dynamics."""
    p = to_point(point)
    lyap = maximal_lyapunov(0.971635, p[0], p[1], 32)
    scalar = -float(lyap)  # chaotic regions carry negative sectional curvature
    return {
        "ricci": scalar * 2.0,
        "scalar": scalar,
        "sectional": scalar,
        "geodesic_distance_to_origin": math.hypot(p[0], p[1]),
    }


def poincare_distance(u: Sequence[float], v: Sequence[float]) -> float:
    return float(
        poincare_golden_distance(np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64))
    )


def gauge_gap() -> float:
    """The declared Yang–Mills mass gap, from the substrate's record."""
    return float(finite_gauge_gap())


def golden() -> float:
    return float(golden_ratio())


# ---------------------------------------------------------------------------
# Operator compilers (CONSUME:toe.operator_compilers)
# ---------------------------------------------------------------------------


def compile_request(request: Any) -> Any:
    return compile_operator(request.canonical_payload())


def digest_cost(request: Any) -> int:
    """Verification effort: the compiled operator's measured dimensions."""
    spec = compile_operator(request.canonical_payload())
    return max(int(spec.dimensions), 1)


def decompose_attack(attack_vector: Sequence[float], basis: Sequence[str]) -> list[Any]:
    """Project an attack vector onto the declared Hodge basis.

    Each declared basis class collects the component at its index; a
    component whose index exceeds the declared basis dimension feeds the
    ``__unknown__`` class and fails closed upstream.
    """
    from .types import HodgeClass

    vec = [float(v) for v in attack_vector]
    if not vec:
        return []
    classes: list[HodgeClass] = [
        HodgeClass(name=name, weight=abs(vec[i]) if i < len(vec) else 0.0)
        for i, name in enumerate(basis)
    ]
    residual = sum(abs(v) for i, v in enumerate(vec) if i >= len(basis))
    if residual > 0:
        classes.append(HodgeClass(name="__unknown__", weight=residual))
    return classes


# ---------------------------------------------------------------------------
# Fidelity kernel (CONSUME:toe.unified.data_layer.fidelity_kernel)
# ---------------------------------------------------------------------------


def fidelity_kernel(adversary_class: Any, event: Any) -> Any:
    """Measured signal distribution of an event's telemetry.

    The kernel is a sorted-percentile estimator over the telemetry
    channel plus the attack vector; mean is the channel's centre of mass.
    """
    from .types import Distribution

    samples = [float(v) for v in event.telemetry] or [0.0]
    n = len(samples)
    mean = sum(samples) / n
    var = sum((v - mean) ** 2 for v in samples) / max(n, 1)
    ordered = sorted(samples)

    def _pct(p: float) -> float:
        idx = min(n - 1, max(0, int(round(p * (n - 1)))))
        return ordered[idx]

    return Distribution(
        mean=mean,
        stddev=math.sqrt(var),
        samples=n,
        p50=_pct(0.50),
        p95=_pct(0.95),
        p99=_pct(0.99),
    )


# ---------------------------------------------------------------------------
# Causal ladder (CONSUME:toe.causal_ladder)
# ---------------------------------------------------------------------------


def causal_association(state: QuantumState, observable: ComplexMatrix) -> dict:
    return dict(association_query(state, observable))


def causal_intervention(
    state: QuantumState,
    node: str,
    value: float,
    observables: dict[str, ComplexMatrix],
    scm: StructuralCausalModel,
) -> tuple[QuantumState, dict]:
    return do_operator(state, node, value, observables, scm)


def causal_counterfactual(
    scm: StructuralCausalModel,
    state: QuantumState,
    node: str,
    value: float,
    observed: dict[str, float],
    observables: dict[str, ComplexMatrix],
) -> tuple[float, dict]:
    return counterfactual_query(scm, state, node, value, observed, observables)


def build_causal_scm(
    nodes: Sequence[str], edges: Sequence[tuple[str, str, float]]
) -> StructuralCausalModel:
    graph = CausalGraph()
    for parent, child, weight in edges:
        graph.add_edge(parent, child, float(weight))
    return StructuralCausalModel(graph=graph, dim=max(2, len(nodes)))


def default_observables(nodes: Sequence[str], dim: int = 2) -> dict[str, ComplexMatrix]:
    """One diagonal observable per factor — eigenvalues = node index."""
    obs: dict[str, ComplexMatrix] = {}
    for i, name in enumerate(nodes):
        diag = [Complex(float(i + 1) if j == i % dim else 0.0, 0.0) for j in range(dim)]
        obs[name] = ComplexMatrix.diagonal(diag)
    return obs


def quantum_state_from_observation(obs: Mapping[str, float], dim: int = 2) -> QuantumState:
    if obs:
        amps = [Complex(float(abs(v)), 0.0) for _, v in sorted(obs.items())[:dim]]
        while len(amps) < dim:
            amps.append(Complex(0.0, 0.0))
        return QuantumState(dim, amps, normalize=True)
    return QuantumState.from_basis(dim, 0)


# ---------------------------------------------------------------------------
# Bridge (CONSUME:toe.bridge)
# ---------------------------------------------------------------------------

_bridge: Optional[TOEBridge] = None


def toe_bridge() -> TOEBridge:
    global _bridge
    if _bridge is None:
        _bridge = TOEBridge({"hilbert_dim": 32})
    return _bridge


def predict_flow(attack_vector: Sequence[float]) -> Any:
    return toe_bridge().predict_trajectory(list(attack_vector) or [0.0])


def flow_lyapunov(flow: Any, attack_vector: Sequence[float]) -> float:
    """Instability of the predicted flow — measured from the trajectory
    forecast and the driving vector's standard-map exponent."""
    trend = abs(float(getattr(flow, "trend_rate", 0.0)))
    if attack_vector:
        theta = abs(float(attack_vector[0])) % 1.0
        mom = abs(float(attack_vector[-1])) % 1.0
        K = min(40.0, sum(abs(float(v)) for v in attack_vector))
        chaotic = max(0.0, maximal_lyapunov(K, theta, mom, 48))
    else:
        chaotic = 0.0
    return trend + chaotic


# ---------------------------------------------------------------------------
# 11D fold (CONSUME:kellogg.exact_tensor.fold_to_zeckendorf → phi_klein)
# ---------------------------------------------------------------------------


def fold_11d_vector(x: Sequence[float]) -> tuple[np.ndarray, int]:
    return klein_fold(np.asarray(list(x)[:11], dtype=np.float64))


def unfold_11d_vector(y: Sequence[float]) -> np.ndarray:
    return klein_unfold(np.asarray(list(y)[:11], dtype=np.float64))


def zeckendorf_cert_token(x: Sequence[float], context_id: str = ""):
    return compute_zeckendorf_certificate(np.asarray(list(x)[:11], dtype=np.float64), context_id)


def zeckendorf_mask(component: int) -> int:
    return int(HardenedZeckendorfCodec.encode(int(component)))


def mask_non_adjacent(mask: int) -> bool:
    return bool(HardenedZeckendorfCodec.verify_non_adjacent(int(mask)))


def zeckendorf_fold_payload(payload: bytes) -> bytes:
    """Fold a canonical JSON payload through the Zeckendorf codec into a
    storable block encoding."""
    topo = apply_zeckendorf_compression(payload)
    parts = [f"{offset}:{mask}" for offset, mask in topo.items()]
    return "|".join(parts).encode("utf-8")


def lucas_ladder(n: int = 11) -> list[int]:
    return [int(lucas(i)) for i in range(n)]


# ---------------------------------------------------------------------------
# Aethel store (CONSUME:aethel.unified.open/put,
# CONSUME:aethel.next_fibonacci_index, CONSUME:aethel.cassini.quadruple)
# ---------------------------------------------------------------------------


class AethelStore:
    """Fibonacci-addressed certificate store over ``aethel.storage``.

    ``path=None`` gives an in-memory space; a real path persists via the
    substrate journal so ``attach`` can re-open it.
    """

    def __init__(self, path: Optional[str] = None, *, writer: int = 0):
        self.path = None if path in (None, "", ":memory:") else Path(path)
        if self.path and (self.path / "aethel_journal.jsonl").is_file():
            self.space = AddressSpace.attach(self.path)
        else:
            self.space = AddressSpace(writer=writer)
        self._pending = False

    def next_fibonacci_index(self) -> int:
        return int(self.space._cursor) + 1

    def put(self, payload: bytes, advance: int = 1) -> Any:
        addr = self.space.write(payload, advance=advance)
        self._pending = True
        return addr

    def cassini_quadruple(self, index: int) -> tuple[int, int, int, int]:
        return tuple(int(v) for v in cassini_quadruple(index))

    def verify(self) -> bool:
        return bool(self.space.verify())

    def commit(self) -> None:
        if self.path and self._pending:
            self.path.mkdir(parents=True, exist_ok=True)
            self.space.snapshot(self.path)
            self._pending = False

    def subspace(self, name: str) -> "AethelStore":
        sub_path = None if self.path is None else str(self.path / f"tenant_{name}")
        sub = AethelStore(sub_path, writer=self.space.writer)
        return sub


def open_aethel(path: Optional[str]) -> AethelStore:
    return AethelStore(path)


def aethel_put(
    store: AethelStore, index_hint: int, block: bytes, cassini: tuple[int, int, int, int]
) -> Any:
    """Place a block at the next Fibonacci index and verify its Cassini
    quadruple against the ledger — tampering raises via ``space.verify``."""
    addr = store.put(block, advance=max(1, index_hint - int(store.space._cursor)))
    quad = cassini_quadruple(addr.index)
    if not cassini_holds(quad):
        raise ValueError(f"cassini quadruple violated at index {addr.index}")
    if not store.verify():
        raise ValueError("aethel ledger inconsistent after write")
    return addr
