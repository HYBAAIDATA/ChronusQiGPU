"""Native uncertainty taxonomy + calibration — elevation §§11-12.

Every causal/intelligence answer can carry five separate axes instead of
one fake confidence score::

    ALEATORIC     irreducible data noise (propagated exogenous sd)
    MODEL         spread of the answer across the admissible-DAG class
    STRUCTURAL    share of the admissible class where the question is
                  not identified at all
    IDENTIFIABILITY  the oracle verdict (§7)
    MISSING_EVIDENCE variables whose absence blocks the answer

``uncertainty_report`` composes the oracle, the equivalence-class
discovery, and exact moment propagation into that taxonomy.
``calibrate_effects`` / ``calibrate_futures`` measure claimed-vs-empirical
coverage on the repository's own SCM machinery — where probability
semantics are not justified, no probabilities are invented.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .causal_ladder import (
    CausalGraph,
    StructuralCausalModel,
    estimate_causal_effect,
)
from .causal_stack import (
    IDENTIFIED,
    NOT_IDENTIFIED,
    PARTIALLY_IDENTIFIED,
    _propagate_moments,
    discover_structures,
    identifiability,
)

UNCERTAINTY_VERSION = "toe.uncertainty/v1"

EVIDENCE_MEASURED = "MEASURED"
EVIDENCE_PROPAGATED = "PROPAGATED"
EVIDENCE_ASSUMPTION_BOUND = "ASSUMPTION_BOUND"
EVIDENCE_STRUCTURALLY_ABSENT = "STRUCTURALLY_ABSENT"
EVIDENCE_UNAVAILABLE = "UNAVAILABLE"


def uncertainty_report(
    scm: StructuralCausalModel,
    treatment: str,
    outcome: str,
    *,
    observed: Optional[Iterable[str]] = None,
    samples: Optional[Mapping[str, Sequence[Any]]] = None,
    do_values: Sequence[float] = (0.0, 1.0),
    noise_sd: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Decompose the answer's uncertainty into the five axes.

    Identifiability comes first: if the question is not identified, the
    report says so and refuses to manufacture an estimate.
    """
    ident = identifiability(scm.graph, treatment, outcome, observed=observed)
    axes: Dict[str, Any] = {
        "identifiability": ident["verdict"],
        "aleatoric": None,
        "model": None,
        "structural": None,
        "missing_evidence": [],
    }
    out: Dict[str, Any] = {
        "version": UNCERTAINTY_VERSION,
        "treatment": treatment,
        "outcome": outcome,
        "identifiability": ident,
        "axes": axes,
        "estimate": None,
        "confidence": None,
        "evidence_class": None,
        "assumptions": [
            "linear structural equations f_i = Σw x_j + φ u_i",
            "independent exogenous noise",
            "supplied graph is the identification surface",
        ],
    }

    if ident["verdict"] == "UNAVAILABLE":
        out["evidence_class"] = EVIDENCE_UNAVAILABLE
        out["reason"] = ident["reason"]
        return out
    if ident["verdict"] == NOT_IDENTIFIED:
        out["evidence_class"] = EVIDENCE_STRUCTURALLY_ABSENT
        out["reason"] = ident["reason"]
        return out

    # Aleatoric axis: exact propagated sd of the outcome under do(treatment).
    mutilated, _ = scm.mutilate({treatment: float(do_values[-1])})
    stats = _propagate_moments(mutilated, {treatment: float(do_values[-1])}, noise_sd)
    if outcome in stats:
        axes["aleatoric"] = stats[outcome]["sd"]

    # Measured axis: backdoor-adjusted estimate + SE when samples exist.
    if samples is not None:
        est = estimate_causal_effect(
            samples, scm.graph, treatment, outcome,
            observed=observed, do_values=do_values,
        )
        if est.available:
            out["estimate"] = {
                "adjusted_effect": est.adjusted_effect,
                "standard_error": est.standard_error,
                "method": est.method,
                "n_samples": est.n_samples,
            }
            out["confidence"] = None  # a bare SE is evidence, not a probability
            out["evidence_class"] = EVIDENCE_MEASURED
        else:
            axes["missing_evidence"] = [est.reason]
            out["evidence_class"] = EVIDENCE_PROPAGATED
    else:
        # No sample data: the answer is propagated structure only.
        out["estimate"] = {
            "interventional_mean": stats[outcome]["mean"] if outcome in stats else None,
            "note": "mean under do() at the intervention level; not a sample estimate",
        }
        out["evidence_class"] = (
            EVIDENCE_ASSUMPTION_BOUND
            if ident["verdict"] == PARTIALLY_IDENTIFIED
            else EVIDENCE_PROPAGATED
        )

    # Model/structural axes: spread across the admissible-DAG class when
    # observational samples are present.
    if samples is not None:
        disc = discover_structures(
            {k: [float(v) for v in vals] for k, vals in samples.items()}
        )
        if disc["available"] and disc["admissible_dags"]:
            effects: List[float] = []
            unidentified = 0
            for dag_edges in disc["admissible_dags"]:
                g = CausalGraph.from_edges(dag_edges)
                member = identifiability(
                    g, treatment, outcome, observed=observed
                )
                if member["verdict"] != IDENTIFIED:
                    unidentified += 1
                    continue
                est_m = estimate_causal_effect(
                    samples, g, treatment, outcome,
                    observed=observed, do_values=do_values,
                )
                if est_m.available and est_m.adjusted_effect is not None:
                    effects.append(est_m.adjusted_effect)
                else:
                    unidentified += 1
            if effects:
                axes["model"] = max(effects) - min(effects)
            if disc["admissible_dags"]:
                axes["structural"] = unidentified / len(disc["admissible_dags"])
            out["model_axis_detail"] = {
                "equivalence_class_size": len(disc["admissible_dags"]),
                "identified_members": len(effects),
                "effect_spread": axes["model"],
            }
    return out


def calibrate_effects(
    scm: StructuralCausalModel,
    treatment: str,
    outcome: str,
    *,
    k_experiments: int = 24,
    n_samples: int = 300,
    seed: int = 11,
    do_values: Sequence[float] = (0.0, 1.0),
    noise_sd: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Coverage of reported SEs vs the model's own do() truth.

    Generates ``k_experiments`` synthetic datasets from the SCM itself,
    re-estimates the effect, and checks how often the reported interval
    ``estimate ± z·SE`` contains the true effect. The SCM's own estimator
    is being calibrated against the SCM's own truth — this measures the
    estimator's honesty, not the world's.
    """
    truth_lo = scm.evaluate_all({treatment: float(do_values[0])})[outcome]
    truth_hi = scm.evaluate_all({treatment: float(do_values[-1])})[outcome]
    truth = (truth_hi - truth_lo) / (do_values[-1] - do_values[0])

    levels = {"90%": 1.6448536269514722, "95%": 1.959963984540054, "99%": 2.5758293035489004}
    covered = {k: 0 for k in levels}
    errors: List[float] = []
    ses: List[float] = []
    refused = 0
    for i in range(k_experiments):
        samples = scm.sample(n_samples, seed=seed + i, noise_sd=noise_sd)
        est = estimate_causal_effect(
            samples, scm.graph, treatment, outcome, do_values=do_values
        )
        if not est.available or est.standard_error is None or est.standard_error <= 0:
            refused += 1
            continue
        err = abs(est.adjusted_effect - truth)
        errors.append(err)
        ses.append(est.standard_error)
        for name, z in levels.items():
            if err <= z * est.standard_error:
                covered[name] += 1
    usable = len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / usable) if usable else None
    mean_se = sum(ses) / len(ses) if ses else None
    coverage = {k: (covered[k] / usable if usable else None) for k in levels}
    nominal = {"90%": 0.90, "95%": 0.95, "99%": 0.99}
    calib_err = {
        k: abs(coverage[k] - nominal[k]) if coverage[k] is not None else None
        for k in levels
    }
    return {
        "version": UNCERTAINTY_VERSION,
        "kind": "causal_effect_calibration",
        "true_effect": truth,
        "experiments": k_experiments,
        "usable": usable,
        "refusals": refused,
        "coverage": coverage,
        "nominal": nominal,
        "calibration_error": calib_err,
        "rmse": rmse,
        "mean_standard_error": mean_se,
        "rmse_vs_mean_se_ratio": (rmse / mean_se) if (rmse and mean_se) else None,
        "note": "calibrated against the model's own do() truth; a "
        "well-calibrated estimator has rmse ≈ mean_se and coverage ≈ nominal",
    }


def calibrate_futures(
    scm: StructuralCausalModel,
    actions: Sequence[Mapping[str, Any]],
    outcomes: Sequence[str],
    *,
    worlds: int = 40,
    seed: int = 5,
    noise_sd: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Empirical coverage of the propagated p05-p95 bands.

    Each world draws one realised exogenous-noise vector, propagates the
    SCM under the action, and checks whether the realised outcome falls
    inside the exact 90% band. Band semantics are Gaussian under the
    linear model, so coverage should sit near 0.90; the gap is the
    calibration error.
    """
    import random

    rng = random.Random(seed)
    order = scm.graph.topological_order()
    sd_map = {n: float((noise_sd or {}).get(n, 1.0)) for n in order}
    rows: List[Dict[str, Any]] = []
    covered = total = 0
    for a in actions:
        name = str(a.get("name", "A"))
        ivs = {k: float(v) for k, v in dict(a.get("interventions", {})).items()}
        mutilated, _ = scm.mutilate(ivs)
        stats = _propagate_moments(mutilated, ivs, noise_sd)
        hits = {o: 0 for o in outcomes}
        for w in range(worlds):
            noise = {n: rng.gauss(0.0, sd_map[n]) for n in order}
            realised = mutilated.evaluate_all(ivs, noise)
            for o in outcomes:
                lo, hi = stats[o]["p05"], stats[o]["p95"]
                if lo <= realised[o] <= hi:
                    hits[o] += 1
                    covered += 1
                total += 1
        rows.append(
            {
                "action": name,
                "empirical_coverage": {o: hits[o] / worlds for o in outcomes},
            }
        )
    empirical = covered / total if total else None
    return {
        "version": UNCERTAINTY_VERSION,
        "kind": "future_band_calibration",
        "band": "p05-p95 (nominal 0.90)",
        "worlds": worlds,
        "empirical_coverage": empirical,
        "calibration_error": abs(empirical - 0.90) if empirical is not None else None,
        "per_action": rows,
    }


__all__ = [
    "UNCERTAINTY_VERSION",
    "EVIDENCE_MEASURED",
    "EVIDENCE_PROPAGATED",
    "EVIDENCE_ASSUMPTION_BOUND",
    "EVIDENCE_STRUCTURALLY_ABSENT",
    "EVIDENCE_UNAVAILABLE",
    "uncertainty_report",
    "calibrate_effects",
    "calibrate_futures",
]
