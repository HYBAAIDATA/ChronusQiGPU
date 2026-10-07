"""IntelligenceState — one observation bound to many mathematical views.

Implements the multi-representation layer of the TOE elevation pass
(§3–§5): an observation enters once, is normalised into a single
canonical numeric view, and each lens (statistical, tensor, temporal,
algebraic, geometric, topological, causal-graph) is a *view over the same
identity* — not a copy of the data.

Invariant (§4):

    Every bound view carries ``observation_sha256`` — the digest of the
    observation's canonical view — and ``bind()`` refuses a view whose
    digest differs. Divergent representations cannot accumulate silently.

Availability is honest: a lens that cannot be built reports
``available=False`` with a reason instead of manufacturing a value. The
causal-graph lens is admitted *only* when the caller supplies the graph —
``infer_causal_graph`` is a correlation heuristic, not discovery, and is
deliberately not wired here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from toe.receipts import ReceiptLedger, digest as receipt_digest

LENS_NAMES = (
    "statistical",
    "tensor",
    "temporal",
    "algebraic",
    "geometric",
    "topological",
    "causal_graph",
)


class DivergenceError(ValueError):
    """A view whose observation digest differs from the state's identity."""


# ---------------------------------------------------------------------------
# Canonical observation view
# ---------------------------------------------------------------------------


def canonical_numeric_view(
    data: Any,
) -> Tuple[Tuple[str, ...], Tuple[float, ...], str]:
    """Project arbitrary input into one ordered (fields, values) pair.

    The same projection feeds every lens, so lens results are views of the
    same numeric observation. Ordering is deterministic: dict keys sort,
    sequences flatten in order, bytes decode as bytes/255, a scalar is a
    length-1 vector. Non-numeric entries are skipped (not coerced).
    """
    fields: List[str] = []
    values: List[float] = []

    def take(name: str, v: Any) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            f = float(v)
            if math.isfinite(f):
                fields.append(name)
                values.append(f)
        elif isinstance(v, (list, tuple)):
            for i, e in enumerate(v):
                take(f"{name}[{i}]", e)

    if isinstance(data, Mapping):
        for key in sorted(data, key=str):
            take(str(key), data[key])
        kind = "mapping"
    elif isinstance(data, (list, tuple)):
        for i, v in enumerate(data):
            take(f"v[{i}]", v)
        kind = "sequence"
    elif isinstance(data, (bytes, bytearray)):
        for i, b in enumerate(data):
            fields.append(f"b[{i}]")
            values.append(b / 255.0)
        kind = "bytes"
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        v = float(data)
        if math.isfinite(v):
            fields.append("v")
            values.append(v)
        kind = "scalar"
    else:
        kind = "unsupported"
    return tuple(fields), tuple(values), kind


def observation_digest(data: Any) -> str:
    """The observation identity every lens must carry."""
    fields, values, kind = canonical_numeric_view(data)
    return receipt_digest(
        {"kind": kind, "fields": list(fields), "values": list(values)}
    )


# ---------------------------------------------------------------------------
# Lens view
# ---------------------------------------------------------------------------


@dataclass
class LensView:
    """One mathematical lens bound to an observation identity.

    ``summary`` is the JSON-safe digest of the lens result (scalars and
    small dicts); ``artifact`` holds the live object (QuantumState,
    CausalGraph, point cloud, ...) for callers in-process and is never
    serialised into ``as_dict``.
    """

    name: str
    available: bool
    observation_sha256: str
    derivation: str
    reason: Optional[str] = None
    summary: Dict[str, Any] = field(default_factory=dict)
    artifact: Any = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "observation_sha256": self.observation_sha256,
            "derivation": self.derivation,
            "reason": self.reason,
            "summary": self.summary,
        }


def _unavailable(name: str, digest_hex: str, derivation: str, reason: str) -> LensView:
    return LensView(
        name=name,
        available=False,
        observation_sha256=digest_hex,
        derivation=derivation,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Lens builders — thin, honest wrappers over the measured substrates
# ---------------------------------------------------------------------------


def _series_columns(data: Any) -> List[Tuple[str, List[float]]]:
    """Extract univariate series from dict/list input for series-aware lenses."""
    cols: List[Tuple[str, List[float]]] = []
    if isinstance(data, Mapping):
        for key in sorted(data, key=str):
            v = data[key]
            if isinstance(v, (list, tuple)):
                s = [
                    float(e)
                    for e in v
                    if isinstance(e, (int, float)) and not isinstance(e, bool)
                ]
                if s:
                    cols.append((str(key), s))
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                cols.append((str(key), [float(v)]))
    elif isinstance(data, (list, tuple)):
        s = [
            float(e)
            for e in data
            if isinstance(e, (int, float)) and not isinstance(e, bool)
        ]
        if s:
            cols.append(("v", s))
    return cols


def build_statistical(data: Any, sha: str) -> LensView:
    fields, values, kind = canonical_numeric_view(data)
    if not values:
        return _unavailable(
            "statistical", sha, "canonical_numeric_view", "observation has no finite numeric values"
        )
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n if n > 1 else 0.0
    summary: Dict[str, Any] = {
        "kind": kind,
        "n_fields": len(fields),
        "n_values": n,
        "mean": mean,
        "std": math.sqrt(var),
        "min": min(values),
        "max": max(values),
        "state_bytes_lower_bound": n * 8,
    }
    cols = [(name, s) for name, s in _series_columns(data) if len(s) >= 2]
    if len(cols) >= 2:
        corr: Dict[str, float] = {}
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a, b = cols[i][1], cols[j][1]
                m = min(len(a), len(b))
                a, b = a[:m], b[:m]
                ma, mb = sum(a) / m, sum(b) / m
                va = sum((x - ma) ** 2 for x in a)
                vb = sum((x - mb) ** 2 for x in b)
                if va > 0 and vb > 0:
                    cov = sum((a[k] - ma) * (b[k] - mb) for k in range(m))
                    corr[f"{cols[i][0]}~{cols[j][0]}"] = cov / math.sqrt(va * vb)
        if corr:
            summary["pairwise_correlations"] = corr
    return LensView(
        "statistical",
        True,
        sha,
        "canonical_numeric_view -> moments + pairwise Pearson correlations",
        summary=summary,
    )


def build_tensor(data: Any, sha: str, bridge: Any) -> LensView:
    tomo = bridge.state_tomography(data)
    if not tomo.available:
        return _unavailable(
            "tensor", sha, "TOEBridge.state_tomography", tomo.diagnostics.get("error", "failed")
        )
    return LensView(
        "tensor",
        True,
        sha,
        "encode_data_to_state -> QuantumState; Born probs + observables",
        summary={
            "hilbert_dim": tomo.diagnostics.get("dim"),
            "energy": tomo.energy,
            "momentum": tomo.momentum,
            "entropy": tomo.entropy,
            "coherence": tomo.coherence,
            "fisher_info": tomo.fisher_info,
            "effective_dimension": tomo.diagnostics.get("effective_dimension"),
            "confidence": tomo.confidence,
        },
        artifact=tomo,
    )


def build_temporal(data: Any, sha: str, bridge: Any) -> LensView:
    fields, values, _ = canonical_numeric_view(data)
    if len(values) < 4:
        return _unavailable(
            "temporal",
            sha,
            "TOEBridge.predict_trajectory",
            "fewer than 4 numeric values — no dynamical support to propagate",
        )
    traj = bridge.predict_trajectory(data)
    if not traj.available:
        return _unavailable(
            "temporal", sha, "TOEBridge.predict_trajectory", traj.diagnostics.get("error", "failed")
        )
    energies = traj.diagnostics.get("energies", [])
    return LensView(
        "temporal",
        True,
        sha,
        "|psi(t)> = exp(-iHt/hbar)|psi(0)> at 6 forecast times",
        summary={
            "trend": traj.trend,
            "trend_rate": traj.trend_rate,
            "current_state": traj.current_state,
            "forecast_3_step": traj.forecast_3_step,
            "forecast_6_step": traj.forecast_6_step,
            "energies": energies,
            "time_sensitivity": traj.time_sensitivity,
            "confidence": traj.confidence,
        },
        artifact=traj,
    )


def _exact_circulant_det(coeffs: Sequence[int]) -> int:
    """Exact determinant of the circulant built from ``coeffs`` (Bareiss).

    The butterfly matrix is C[k][n] = coeffs[(n + k) % n]; Bareiss keeps
    every intermediate an exact integer, so invertibility evidence is
    arithmetic-exact, not float-epsilon.
    """
    n = len(coeffs)
    if n == 0:
        return 0
    a = [[coeffs[(j + i) % n] for j in range(n)] for i in range(n)]
    det_sign = 1
    prev = 1
    for k in range(n - 1):
        if a[k][k] == 0:
            swap = next((r for r in range(k + 1, n) if a[r][k] != 0), None)
            if swap is None:
                return 0
            a[k], a[swap] = a[swap], a[k]
            det_sign = -det_sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                a[i][j] = (a[i][j] * a[k][k] - a[i][k] * a[k][j]) // prev
        prev = a[k][k]
    return det_sign * a[n - 1][n - 1]


def fibonacci_butterfly_contract(n_max: int = 40) -> Dict[str, Any]:
    """Supported-N contract for the N-point Fibonacci butterfly.

    The 2x2 companion matrix's det(M^n) = ±1 does NOT transfer to the
    N-point circular transform; invertibility per N must be proven
    separately. This table is that measurement — exact Bareiss
    determinants over the integer circulant.
    """

    def fib(n: int) -> List[int]:
        b = [0, 1]
        for _ in range(2, n):
            b.append(b[-1] + b[-2])
        return b[:n]

    rows = {}
    for n in range(1, n_max + 1):
        det = _exact_circulant_det(fib(n)) if n >= 2 else 0
        rows[n] = {"invertible": det != 0, "det_bits": abs(det).bit_length() if det else 0}
    return rows


FAMILY_DETECTOR = "toe.engine.ExtendedAlgebraicFamily.detect_family_signature"


def family_detector() -> Callable[[Sequence[float]], Dict[str, Any]]:
    """The one algebraic-family detector TOE uses.

    ``ExtendedAlgebraicFamily.detect_family_signature`` delegates to the
    shared ``turing_core`` substrate when that monorepo module is importable
    and otherwise runs its own exact-Decimal implementation, so the lens is
    available in a standalone install with the same output contract.
    """
    from toe.engine import ExtendedAlgebraicFamily

    return ExtendedAlgebraicFamily().detect_family_signature


def build_algebraic(data: Any, sha: str) -> LensView:
    cols = _series_columns(data)
    if not cols:
        return _unavailable(
            "algebraic", sha, FAMILY_DETECTOR, "no univariate series present"
        )
    detector = family_detector()
    name, series = max(cols, key=lambda kv: len(kv[1]))
    if len(series) < 5:
        return _unavailable(
            "algebraic",
            sha,
            FAMILY_DETECTOR,
            f"longest series has {len(series)} values; recurrence detection needs >= 5",
        )
    sig = detector(series)
    residuals = sig.get("residuals", {})
    best, runner = sig.get("family"), sig.get("runner_up")
    margin = None
    if best and runner and best in residuals and runner in residuals:
        r_best, r_run = float(residuals[best]), float(residuals[runner])
        margin = r_run - r_best
    summary: Dict[str, Any] = {
        "series": name,
        "series_len": len(series),
        "family": best,
        "family_confidence": float(sig.get("confidence", 0.0)),
        "runner_up": runner,
        "residual_margin": margin,
        "families": sorted(residuals),
    }
    # Exact-integer butterfly only where the data is genuinely integral —
    # quantising floats would fabricate an exactness the data lacks.
    if all(float(v).is_integer() for v in series):
        n = len(series)
        basis = [0, 1]
        for _ in range(2, n):
            basis.append(basis[-1] + basis[-2])
        y = [
            sum(int(series[m]) * basis[(m + k) % n] for m in range(n))
            for k in range(n)
        ]
        summary["butterfly"] = {
            "n": n,
            "y_head": y[:6],
            "invertible_at_n": _exact_circulant_det(basis) != 0,
            "arithmetic": "arbitrary-precision integer (Python int)",
        }
    return LensView(
        "algebraic",
        True,
        sha,
        "Pisot-family lag-template fit (golden/plastic/supergolden/tribonacci)"
        + (" + exact integer Fibonacci butterfly" if "butterfly" in summary else ""),
        summary=summary,
    )


def build_geometric(data: Any, sha: str) -> LensView:
    fields, values, _ = canonical_numeric_view(data)
    if len(values) < 2:
        return _unavailable(
            "geometric",
            sha,
            "poincare_golden_11d fold",
            "fewer than 2 numeric values — no point to place on the ball",
        )
    import numpy as np

    from toe.phi_klein import klein_identity, phi_norm
    from toe.poincare_golden_11d import fold_poincare_11d_vector, unfold_poincare_11d_vector

    x = np.zeros(11, dtype=np.float64)
    vec = np.asarray(values[:11], dtype=np.float64)
    scale = float(np.max(np.abs(vec))) or 1.0
    x[: len(vec)] = vec / scale
    folded, _passes = fold_poincare_11d_vector(x)
    unfolded = unfold_poincare_11d_vector(folded)
    roundtrip_err = float(np.max(np.abs(unfolded - x)))
    summary: Dict[str, Any] = {
        "phi_norm_folded": phi_norm(folded),
        "klein_identity": klein_identity(x),
        "fold_roundtrip_max_err": roundtrip_err,
        "input_scale": scale,
    }
    cols = [(n, s) for n, s in _series_columns(data) if len(s) >= 4]
    if len(cols) >= 2:
        m = min(len(s) for _, s in cols)
        mat = np.array([s[:m] for _, s in cols], dtype=np.float64)
        corr = np.corrcoef(mat)
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 0.0)
        adj = np.abs(corr)
        try:
            from toe.geometry import SpectralGeometry

            sg = SpectralGeometry(adj)
            gap = float(sg.eigenvalues[1]) if len(sg.eigenvalues) > 1 else 0.0
            labels = sg.spectral_clustering(2)
            summary["spectral"] = {
                "spectral_gap": gap,
                "ricci_mean": float(np.mean(sg.ricci_curvature())),
                "two_cluster_sizes": [
                    int((labels == c).sum()) for c in sorted(set(labels.tolist()))
                ],
                "engine": "toe.geometry.SpectralGeometry",
            }
        except Exception as exc:
            summary["spectral"] = {"available": False, "reason": str(exc)}
    return LensView(
        "geometric",
        True,
        sha,
        "fold_poincare_11d_vector(normalised first 11 components)"
        + (" + |corr| Laplacian spectral geometry" if "spectral" in summary else ""),
        summary=summary,
    )


def _point_cloud(data: Any) -> Optional[Tuple[Any, str]]:
    """Rows-of-features cloud for multivariate data; delay embedding otherwise."""
    import numpy as np

    cols = [(n, s) for n, s in _series_columns(data) if len(s) >= 2]
    if len(cols) >= 2:
        m = min(len(s) for _, s in cols)
        if m >= 4:
            pts = np.array([s[:m] for _, s in cols], dtype=np.float64).T
            return pts, f"{len(cols)}-variate rows as points in R^{len(cols)}"
    # Univariate (or single-column) fallback: delay embedding, dim 3, tau 1.
    series = cols[0][1] if cols else None
    if series is None:
        _, values, _ = canonical_numeric_view(data)
        series = list(values)
    if len(series) >= 8:
        s = np.asarray(series, dtype=np.float64)
        pts = np.stack([s[:-2], s[1:-1], s[2:]], axis=1)
        return pts, "delay embedding dim=3 tau=1"
    return None


def build_topological(data: Any, sha: str) -> LensView:
    cloud = _point_cloud(data)
    if cloud is None:
        return _unavailable(
            "topological",
            sha,
            "toe.topology.TopologicalAnalytics",
            "insufficient points for a Vietoris-Rips complex "
            "(need >=4 multivariate rows or >=8 univariate samples)",
        )
    import numpy as np

    from toe.topology import TopologicalAnalytics

    pts, how = cloud
    diff = pts[:, None, :] - pts[None, :, :]
    dist = np.linalg.norm(diff, axis=2)
    upper = dist[np.triu_indices(len(pts), k=1)]
    median = float(np.median(upper)) or 1e-9
    ta = TopologicalAnalytics(manifold_dimension=min(pts.shape[1], 5))
    h1 = ta.compute_persistent_homology(pts, median)
    h2 = ta.compute_persistent_homology(pts, 1.5 * median)
    summary = {
        "n_points": int(len(pts)),
        "embedding": how,
        "epsilon_median": median,
        "betti_at_median": h1["betti_numbers"],
        "euler_at_median": h1["euler_characteristic"],
        "betti_at_1p5x_median": h2["betti_numbers"],
        "persistence_stable": h1["betti_numbers"] == h2["betti_numbers"],
        "n_edges": h1["n_edges"],
        "n_triangles": h1["n_triangles"],
        "engine": "toe.topology.TopologicalAnalytics (VR + GF(2) rank)",
    }
    return LensView(
        "topological",
        True,
        sha,
        f"Vietoris-Rips persistent homology on {how}",
        summary=summary,
        artifact=pts,
    )


def _as_graph(graph: Any) -> Any:
    from toe.causal_ladder import CausalGraph, StructuralCausalModel

    if isinstance(graph, CausalGraph):
        return graph
    if isinstance(graph, StructuralCausalModel):
        return graph.graph
    if isinstance(graph, Mapping):
        return CausalGraph.from_edges(graph.get("edges", []), graph.get("nodes", ()))
    return CausalGraph.from_edges(graph)


def build_causal_graph(data: Any, sha: str, graph: Any) -> LensView:
    if graph is None:
        return _unavailable(
            "causal_graph",
            sha,
            "supplied CausalGraph",
            "no causal structure supplied; correlation-inferred graphs are "
            "not admitted (infer_causal_graph is a correlation heuristic, "
            "not causal discovery)",
        )
    g = _as_graph(graph)
    return LensView(
        "causal_graph",
        True,
        sha,
        "supplied causal structure (admitted only when provided)",
        summary={
            "n_nodes": len(g.nodes),
            "is_dag": g.is_dag(),
            "graph_sha256": g.digest(),
        },
        artifact=g,
    )


# ---------------------------------------------------------------------------
# IntelligenceState
# ---------------------------------------------------------------------------

_LEN_BUILDERS: Dict[str, Callable[..., LensView]] = {
    "statistical": build_statistical,
    "tensor": build_tensor,
    "temporal": build_temporal,
    "algebraic": build_algebraic,
    "geometric": build_geometric,
    "topological": build_topological,
    "causal_graph": build_causal_graph,
}


class IntelligenceState:
    """One observation, many bound mathematical views.

    ``observe(data, graph=...)`` normalises the input once, computes the
    observation digest, and binds each requested lens to that identity.
    ``bind`` enforces the §4 invariant — a view carrying a foreign digest
    raises :class:`DivergenceError`. Every bind issues a provenance
    receipt so the view's lineage is replayable.
    """

    def __init__(self, data: Any) -> None:
        self.fields, self.vector, self.kind = canonical_numeric_view(data)
        self.observation_sha256 = receipt_digest(
            {
                "kind": self.kind,
                "fields": list(self.fields),
                "values": list(self.vector),
            }
        )
        self.views: Dict[str, LensView] = {}
        self.receipts = ReceiptLedger()

    def bind(self, view: LensView) -> LensView:
        if view.observation_sha256 != self.observation_sha256:
            raise DivergenceError(
                f"lens {view.name!r} carries observation {view.observation_sha256[:12]}… "
                f"but this state is {self.observation_sha256[:12]}… — divergent "
                "representations are not admitted"
            )
        self.views[view.name] = view
        self.receipts.issue(
            "representation",
            inputs={"observation_sha256": self.observation_sha256},
            config={"lens": view.name, "derivation": view.derivation},
            output=view.as_dict(),
            execution_evidence={"engine": "toe.intelligence_state", "lens": view.name},
        )
        return view

    def view(self, name: str) -> LensView:
        try:
            return self.views[name]
        except KeyError:
            raise KeyError(f"lens {name!r} was never bound to this state") from None

    def available_views(self) -> List[str]:
        return sorted(n for n, v in self.views.items() if v.available)

    def verify_views(self) -> Dict[str, Any]:
        """Re-check every bound view against this state's identity."""
        bad = [
            n
            for n, v in self.views.items()
            if v.observation_sha256 != self.observation_sha256
        ]
        return {"ok": not bad, "divergent_views": bad, "ledger": self.receipts.verify()}

    def as_dict(self) -> Dict[str, Any]:
        return {
            "observation_sha256": self.observation_sha256,
            "kind": self.kind,
            "n_fields": len(self.fields),
            "n_values": len(self.vector),
            "views": {n: v.as_dict() for n, v in self.views.items()},
            "available_views": self.available_views(),
            "provenance": self.receipts.verify(),
        }

    @classmethod
    def observe(
        cls,
        data: Any,
        *,
        graph: Any = None,
        lenses: Optional[Sequence[str]] = None,
        bridge: Any = None,
    ) -> "IntelligenceState":
        """Normalise ``data`` once and bind the requested lenses to its identity."""
        if bridge is None:
            from toe.bridge import TOEBridge

            bridge = TOEBridge()
        state = cls(data)
        sha = state.observation_sha256
        for name in lenses or LENS_NAMES:
            builder = _LEN_BUILDERS.get(name)
            if builder is None:
                state.bind(
                    _unavailable(name, sha, "registry", f"unknown lens {name!r}")
                )
                continue
            if name in ("tensor", "temporal"):
                view = builder(data, sha, bridge)
            elif name == "causal_graph":
                view = builder(data, sha, graph)
            else:
                view = builder(data, sha)
            state.bind(view)
        return state


__all__ = [
    "DivergenceError",
    "IntelligenceState",
    "LENS_NAMES",
    "LensView",
    "canonical_numeric_view",
    "fibonacci_butterfly_contract",
    "observation_digest",
]
