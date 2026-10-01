"""Representation selection — which lens exposes which structure (§5).

``structural_signature`` measures what kind of structure an observation
carries; ``select_views`` maps that signature to the lenses worth paying
for and the operators each selected lens admits. A lens is only *chosen*
when the signature justifies it — an irrelevant representation is
explicitly rejected with its reason, never run "because it exists".
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from toe.intelligence_state import canonical_numeric_view

# Operators admissible under each lens. These name what a view supports,
# not what ran — a lens that binds ``available=False`` admits nothing.
LENS_OPERATORS: Dict[str, Tuple[str, ...]] = {
    "statistical": ("moments", "correlations", "histogram"),
    "tensor": (
        "state_tomography",
        "born_probabilities",
        "observable_expectation",
        "fisher_information",
    ),
    "temporal": (
        "schrodinger_propagation",
        "forecast_energies",
        "fisher_intervention_points",
    ),
    "algebraic": (
        "pisot_family_detection",
        "fibonacci_butterfly",
        "fibonacci_butterfly_inverse",
        "zeckendorf_addressing",
    ),
    "geometric": (
        "poincare_fold",
        "poincare_unfold",
        "geodesic_distance",
        "spectral_clustering",
        "ricci_curvature",
    ),
    "topological": (
        "vietoris_rips_complex",
        "betti_numbers",
        "persistence_compare",
    ),
    "causal_graph": (
        "d_separation",
        "backdoor_adjustment",
        "frontdoor_adjustment",
        "do_operator",
        "counterfactual",
    ),
}


def _series_columns(data: Any) -> List[Tuple[str, List[float]]]:
    cols: List[Tuple[str, List[float]]] = []
    if isinstance(data, dict):
        for key in sorted(data, key=str):
            v = data[key]
            if isinstance(v, (list, tuple)):
                s = [
                    float(e)
                    for e in v
                    if isinstance(e, (int, float)) and not isinstance(e, bool)
                ]
                if len(s) >= 2:
                    cols.append((str(key), s))
    elif isinstance(data, (list, tuple)):
        s = [
            float(e)
            for e in data
            if isinstance(e, (int, float)) and not isinstance(e, bool)
        ]
        if len(s) >= 2:
            cols.append(("v", s))
    return cols


def _pearson_absmax(cols: List[Tuple[str, List[float]]]) -> Optional[float]:
    best: Optional[float] = None
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = cols[i][1], cols[j][1]
            m = min(len(a), len(b))
            if m < 2:
                continue
            a, b = a[:m], b[:m]
            ma, mb = sum(a) / m, sum(b) / m
            va = sum((x - ma) ** 2 for x in a)
            vb = sum((x - mb) ** 2 for x in b)
            if va <= 0 or vb <= 0:
                continue
            r = abs(sum((a[k] - ma) * (b[k] - mb) for k in range(m)) / math.sqrt(va * vb))
            if best is None or r > best:
                best = r
    return best


def structural_signature(data: Any, *, graph: Any = None) -> Dict[str, Any]:
    """Measure what kind of structure an observation carries.

    Pure measurement — every field is computed, none assumed. The
    signature is the input to :func:`select_views`.
    """
    fields, values, kind = canonical_numeric_view(data)
    cols = _series_columns(data)
    longest = max(cols, key=lambda kv: len(kv[1]), default=(None, []))
    signature: Dict[str, Any] = {
        "kind": kind,
        "n_fields": len(fields),
        "vector_dim": len(values),
        "n_series": len(cols),
        "series_len": len(longest[1]),
        "integral": bool(values) and all(float(v).is_integer() for v in values),
        "supplied_graph": graph is not None,
        "temporal_support": len(values) >= 4,
    }
    # Recurrence structure: Pisot-family lag-template fit on the longest series.
    if longest[0] is not None and len(longest[1]) >= 5:
        try:
            import turing_core

            detector = getattr(turing_core, "detect_family_signature", None)
            sig = detector(longest[1]) if detector else None
        except Exception:
            sig = None
        if sig:
            residuals = {k: float(v) for k, v in (sig.get("residuals") or {}).items()}
            best, runner = sig.get("family"), sig.get("runner_up")
            margin = (
                residuals[runner] - residuals[best]
                if best in residuals and runner in residuals
                else None
            )
            signature["recurrence"] = {
                "series": longest[0],
                "family": best,
                "confidence": float(sig.get("confidence", 0.0)),
                "residual_margin_over_runner_up": margin,
            }
    # Cross-series correlation structure (needs >=2 series).
    if len(cols) >= 2:
        signature["correlation_max_abs"] = _pearson_absmax(cols)
    return signature


def select_views(
    signature: Dict[str, Any],
    *,
    goal: Optional[str] = None,
) -> Dict[str, Any]:
    """Choose which lenses to bind, in priority order, with rejections.

    Returns ``{"selected": [(lens, reason)...], "rejected": [(lens,
    reason)...], "admissible_operators": {lens: [ops...]}}``. Selection is
    structural: each choice cites the measured signature field that
    justifies it.
    """
    selected: List[Tuple[str, str]] = []
    rejected: List[Tuple[str, str]] = []
    dim = signature.get("vector_dim", 0)

    def pick(name: str, why: str) -> None:
        selected.append((name, why))

    def drop(name: str, why: str) -> None:
        rejected.append((name, why))

    if dim == 0:
        return {
            "selected": [],
            "rejected": [
                (n, "observation carries no finite numeric values")
                for n in LENS_OPERATORS
            ],
            "admissible_operators": {},
        }

    pick("statistical", "baseline descriptive layer — always admissible")

    if dim >= 2:
        pick("tensor", "vector_dim >= 2 supports a non-degenerate quantum state")
    else:
        drop("tensor", "single scalar — tomography on dim-1 state carries no structure")

    if signature.get("temporal_support"):
        pick("temporal", ">=4 values support Schrödinger propagation")
    else:
        drop("temporal", "fewer than 4 values — no dynamical support")

    rec = signature.get("recurrence") or {}
    margin = rec.get("residual_margin_over_runner_up")
    if (rec.get("confidence") or 0.0) > 0.6 and margin is not None and margin > 0:
        pick(
            "algebraic",
            f"recurrence detected: family={rec.get('family')!r} "
            f"conf={rec.get('confidence'):.3f} margin={margin:.3g}",
        )
    elif signature.get("integral") and dim >= 3:
        pick("algebraic", "integral vector supports the exact-integer butterfly")
    else:
        drop(
            "algebraic",
            "no Pisot-family recurrence above the confidence/margin floor "
            "and no integral structure to transform",
        )

    if dim >= 2 and (signature.get("n_series", 0) >= 2 or dim >= 4):
        pick("geometric", "fold to the 11-ball is non-degenerate; spectral layer applies")
    else:
        drop("geometric", "no multivariate or >=4-dim structure to fold/spectralise")

    if signature.get("n_series", 0) >= 2 and signature.get("series_len", 0) >= 4:
        pick("topological", "multivariate rows give a real point cloud for VR homology")
    elif signature.get("series_len", 0) >= 8 or (signature.get("n_series", 0) <= 1 and signature.get("series_len", 0) == 0 and dim >= 8):
        pick(
            "topological",
            "univariate series >= 8 admits delay embedding dim=3",
        )
    else:
        drop(
            "topological",
            "insufficient points for a Vietoris-Rips complex "
            "(need >=4 multivariate rows or >=8 univariate samples)",
        )

    if signature.get("supplied_graph"):
        pick("causal_graph", "causal structure supplied — admissible")
    else:
        drop(
            "causal_graph",
            "no graph supplied; correlation inference is not causal discovery",
        )

    return {
        "selected": selected,
        "rejected": rejected,
        "admissible_operators": {
            name: list(LENS_OPERATORS[name]) for name, _ in selected
        },
    }


def choose(
    data: Any,
    *,
    graph: Any = None,
    goal: Optional[str] = None,
) -> Dict[str, Any]:
    """signature → selection in one call."""
    sig = structural_signature(data, graph=graph)
    return {"signature": sig, "selection": select_views(sig, goal=goal)}


__all__ = [
    "LENS_OPERATORS",
    "choose",
    "select_views",
    "structural_signature",
]
