"""Accountable task characterisation from finite observable signals.

No embedding is invented. Host supplies versioned, comparable exact feature
vectors and independently produced interpretation groups. Distance is L1.
Reversibility is a conservative declared action-space bound, not an omniscient
estimate of consequences outside the host's containment model.
"""

from dataclasses import dataclass
from fractions import Fraction
from ._contracts import ContractError, ratio, integer, sha
from .strategy import TaskCharacterisation


@dataclass(frozen=True)
class MetaObservation:
    field: str
    prediction: Fraction
    observed: bool
    evidence: str


def meta_calibration_review(history, *, max_ece, minimum_samples):
    ratio(max_ece)
    integer(minimum_samples, minimum=2)
    if type(history) is not tuple or len(history) > 4096:
        raise ContractError("bounded resolved meta-history required")
    groups = {}
    for h in history:
        if (
            h.field not in ("novelty", "ambiguity", "reversibility", "verifiability", "budget")
            or type(h.observed) is not bool
        ):
            raise ContractError("typed resolved meta-judgement required")
        ratio(h.prediction)
        sha(h.evidence)
        groups.setdefault(h.field, []).append(h)
    report = {}
    for field in ("novelty", "ambiguity", "reversibility", "verifiability", "budget"):
        rows = groups.get(field, [])
        bins = {}
        for h in rows:
            bins.setdefault(min(9, int(h.prediction * 10)), []).append(h)
        ece = (
            (
                sum(
                    abs(sum((h.prediction - int(h.observed) for h in rs), Fraction(0)))
                    for rs in bins.values()
                )
                / len(rows)
            )
            if rows
            else None
        )
        report[field] = {
            "n": len(rows),
            "ece": ece,
            "usable": len(rows) >= minimum_samples and ece <= max_ece,
        }
    return report


def characterise(
    task_key,
    features,
    known_classes,
    interpretations,
    action_reversible,
    verifier_tests,
    remaining_budget,
    meta_report,
    *,
    minimum_interpretations,
):
    integer(minimum_interpretations, minimum=2)
    integer(remaining_budget)
    if type(features) is not tuple or not features or len(features) > 128:
        raise ContractError("bounded comparable task features required")
    for x in features:
        ratio(x)
    distances = []
    if type(known_classes) is not tuple or len(known_classes) > 256:
        raise ContractError("bounded task registry required")
    for row in known_classes:
        if type(row) is not tuple or len(row) != len(features):
            raise ContractError("incomparable task features")
        for x in row:
            ratio(x)
        distances.append(
            sum((abs(x - y) for x, y in zip(features, row)), Fraction(0)) / len(features)
        )
    novelty = min(distances) if distances else Fraction(1)
    if (
        type(interpretations) is not tuple
        or len({group for group, label in interpretations}) < minimum_interpretations
    ):
        raise ContractError("independent diverse interpretation groups required")
    counts = {}
    for group, label in interpretations:
        counts[label] = counts.get(label, 0) + 1
    ambiguity = 1 - Fraction(max(counts.values()), len(interpretations))
    if type(action_reversible) is not tuple or any(type(x) is not bool for x in action_reversible):
        raise ContractError("declared worst-case action-space reversibility required")
    reversibility = "REVERSIBLE" if action_reversible and all(action_reversible) else "IRREVERSIBLE"
    if (
        type(verifier_tests) is not tuple
        or len(verifier_tests) != 2
        or any(type(x) is not bool for x in verifier_tests)
    ):
        raise ContractError("local/tool verifier membership tests required")
    verifiability = (
        "LOCAL" if verifier_tests[0] else "TOOL" if verifier_tests[1] else "EXTERNAL_ONLY"
    )
    usable = lambda field: meta_report.get(field, {}).get("usable") is True
    if not usable("novelty"):
        novelty = Fraction(1)
    if not usable("ambiguity"):
        ambiguity = Fraction(1)
    if not usable("reversibility"):
        reversibility = "IRREVERSIBLE"
    if not usable("verifiability"):
        verifiability = "EXTERNAL_ONLY"
    if not usable("budget"):
        remaining_budget = 0
    confidence = (
        Fraction(1)
        if all(usable(f) for f in meta_report) and len(meta_report) == 5
        else Fraction(0)
    )
    return TaskCharacterisation(
        task_key,
        novelty,
        ambiguity,
        reversibility,
        verifiability,
        remaining_budget,
        (),
        (),
        confidence,
    )


@dataclass(frozen=True)
class SuccessEstimate:
    mean: Fraction
    lower_confidence_bound: Fraction
    sample_size: int
    effective_sample_size: Fraction
    distribution_distance: Fraction
    temporal_recency: Fraction


def predict_success(
    *,
    prior,
    observed_rate,
    observed_lower_bound,
    sample_size,
    similarity,
    shrinkage_strength,
    recency,
):
    for x in (prior, observed_rate, observed_lower_bound, similarity, recency):
        ratio(x)
    if prior > Fraction(1, 2) or observed_lower_bound > observed_rate:
        raise ContractError("pessimistic prior and ordered empirical estimates required")
    integer(sample_size)
    integer(shrinkage_strength, minimum=1)
    weight = similarity * recency * Fraction(sample_size, sample_size + shrinkage_strength)
    # One reference cohort at a time, avoiding order-dependent repeated blends.
    return SuccessEstimate(
        prior * (1 - weight) + observed_rate * weight,
        prior * (1 - weight) + observed_lower_bound * weight,
        sample_size,
        similarity * recency * sample_size,
        1 - similarity,
        recency,
    )
