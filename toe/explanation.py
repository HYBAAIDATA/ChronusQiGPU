"""Faithful, outcome-specific explanation by intervention.

An explanation answers one question: for THIS target outcome, THIS input and
THIS model, how much of the prediction does each input account for? It is a
computed artifact, not prose.

Method: interventional Shapley values by exact coalition enumeration. The
value of a coalition S is the model's prediction when the inputs in S keep
their actual values and every other input is set, by intervention, to a
reference row drawn from the supplied background:

    v(S) = mean_b f(do(X_S = x_S, X_rest = b_rest))[target]

    phi_i = sum over S not containing i of
            |S|! (k - |S| - 1)! / k! * (v(S + i) - v(S))

Consequences that the adversarial tests check:

- An input the model does not read gets exactly zero, however large its
  values are, because v(S + i) == v(S) for every S.
- Attributions sum to f(x) - v(empty) (completeness), so they account for
  the actual prediction and nothing else.
- Inputs are processed in sorted order, so input order cannot change the
  result, and a different target is a different computation.
- Every attribution comes from real model evaluations; the per-input
  ablation deltas f(x) - v(all but i) are reported beside them.

When the evidence needed for that computation is missing (no model
identifier, a missing input value, no background, a target the model does
not produce, a model that fails) the result is ``available=False`` with the
reason. No attribution or ranking is produced in that case.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union

EXPLANATION_METHOD = "interventional_shapley_exact/v1"
MAX_EXACT_INPUTS = 12

ModelOutput = Union[float, Mapping[str, float]]
ModelFn = Callable[[Mapping[str, float]], ModelOutput]


def _digest(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class Explanation:
    """The explanation of one target outcome for one input under one model."""

    available: bool
    target: str
    reason: Optional[str] = None
    method: str = EXPLANATION_METHOD
    model_id: Optional[str] = None
    inputs: List[str] = field(default_factory=list)
    factual_prediction: Optional[float] = None
    baseline_prediction: Optional[float] = None
    attributions: Dict[str, float] = field(default_factory=dict)
    ranking: List[str] = field(default_factory=list)
    relevant_inputs: List[str] = field(default_factory=list)
    ablations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    completeness_residual: Optional[float] = None
    causal_parents: Optional[List[str]] = None
    model_evaluations: int = 0
    input_sha256: Optional[str] = None
    background_sha256: Optional[str] = None
    evidence_sha256: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "target": self.target,
            "reason": self.reason,
            "method": self.method,
            "model_id": self.model_id,
            "inputs": list(self.inputs),
            "factual_prediction": self.factual_prediction,
            "baseline_prediction": self.baseline_prediction,
            "attributions": dict(self.attributions),
            "ranking": list(self.ranking),
            "relevant_inputs": list(self.relevant_inputs),
            "ablations": {k: dict(v) for k, v in self.ablations.items()},
            "completeness_residual": self.completeness_residual,
            "causal_parents": None if self.causal_parents is None else list(self.causal_parents),
            "model_evaluations": self.model_evaluations,
            "input_sha256": self.input_sha256,
            "background_sha256": self.background_sha256,
            "evidence_sha256": self.evidence_sha256,
        }


class _ModelFailure(Exception):
    pass


def _finite(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def explain(
    model: ModelFn,
    instance: Mapping[str, Any],
    *,
    target: str,
    background: Union[Mapping[str, Any], Sequence[Mapping[str, Any]]],
    model_id: Optional[str],
    causal_parents: Optional[Sequence[str]] = None,
    relevance_tolerance: float = 1e-9,
    max_inputs: int = MAX_EXACT_INPUTS,
) -> Explanation:
    """Explain ``target`` for ``instance`` under ``model`` by intervention.

    ``model`` maps an input assignment to either a mapping of named outcomes
    or a single number. ``background`` is one reference row or a sequence of
    rows supplying every input; it defines what "removing" an input means.
    ``model_id`` binds the explanation to the model's exact configuration
    and is required. ``causal_parents`` (optional) records the target's
    parents in a supplied causal graph; it is reported, never used to
    shape the attributions.
    """

    def unavailable(reason: str) -> Explanation:
        return Explanation(available=False, target=str(target), reason=reason, model_id=model_id)

    if not model_id:
        return unavailable("no model identifier: the explanation cannot be bound to a model")
    if not target:
        return unavailable("no target outcome named")
    if not instance:
        return unavailable("no input evidence supplied")
    names = sorted(str(k) for k in instance)
    missing = [k for k in names if not _finite(instance[k])]
    if missing:
        return unavailable(f"missing or non-finite input evidence: {missing}")
    if len(names) > max_inputs:
        return unavailable(
            f"{len(names)} inputs exceed the exact-enumeration limit of {max_inputs}"
        )
    rows = [background] if isinstance(background, Mapping) else list(background or [])
    if not rows:
        return unavailable("no background evidence: ablation has no reference values")
    for index, row in enumerate(rows):
        absent = [k for k in names if not _finite(row.get(k))]
        if absent:
            return unavailable(f"background row {index} lacks inputs {absent}")
    x = {k: float(instance[k]) for k in names}
    reference = [{k: float(row[k]) for k in names} for row in rows]

    evaluations = 0

    def evaluate(assignment: Dict[str, float]) -> float:
        nonlocal evaluations
        evaluations += 1
        try:
            output = model(dict(assignment))
        except Exception as exc:  # the model's own failure is evidence
            raise _ModelFailure(f"model evaluation failed: {type(exc).__name__}: {exc}") from exc
        if isinstance(output, Mapping):
            if target not in output:
                raise _ModelFailure(f"model does not produce target {target!r}")
            value = output[target]
        else:
            value = output
        if not _finite(value):
            raise _ModelFailure(f"model produced a non-finite value for {target!r}")
        return float(value)

    k = len(names)
    cache: Dict[int, float] = {}

    def coalition_value(mask: int) -> float:
        if mask not in cache:
            outcomes = []
            for row in reference:
                assignment = {
                    name: (x[name] if mask >> i & 1 else row[name]) for i, name in enumerate(names)
                }
                outcomes.append(evaluate(assignment))
            cache[mask] = math.fsum(outcomes) / len(outcomes)
        return cache[mask]

    full = (1 << k) - 1
    try:
        factual = evaluate(dict(x))
        for mask in range(full + 1):
            coalition_value(mask)
    except _ModelFailure as exc:
        return unavailable(str(exc))

    weights = [math.factorial(s) * math.factorial(k - s - 1) / math.factorial(k) for s in range(k)]
    attributions: Dict[str, float] = {}
    for i, name in enumerate(names):
        bit = 1 << i
        terms = [
            weights[bin(mask).count("1")] * (cache[mask | bit] - cache[mask])
            for mask in range(full + 1)
            if not mask & bit
        ]
        attributions[name] = math.fsum(terms)

    baseline = cache[0]
    scale = max(1.0, abs(factual), abs(baseline))
    tolerance = relevance_tolerance * scale
    ranking = sorted(names, key=lambda n: (-abs(attributions[n]), n))
    relevant = [n for n in ranking if abs(attributions[n]) > tolerance]
    ablations = {
        name: {
            "counterfactual_prediction": cache[full & ~(1 << i)],
            "delta": factual - cache[full & ~(1 << i)],
        }
        for i, name in enumerate(names)
    }
    residual = math.fsum(attributions.values()) - (cache[full] - baseline)
    input_sha = _digest({"inputs": x})
    background_sha = _digest({"background": reference})
    parents = None if causal_parents is None else sorted(str(p) for p in causal_parents)
    evidence = {
        "method": EXPLANATION_METHOD,
        "model_id": model_id,
        "target": target,
        "input_sha256": input_sha,
        "background_sha256": background_sha,
        "factual_prediction": factual,
        "baseline_prediction": baseline,
        "attributions": attributions,
        "ablations": ablations,
        "causal_parents": parents,
    }
    return Explanation(
        available=True,
        target=str(target),
        model_id=model_id,
        inputs=names,
        factual_prediction=factual,
        baseline_prediction=baseline,
        attributions=attributions,
        ranking=ranking,
        relevant_inputs=relevant,
        ablations=ablations,
        completeness_residual=residual,
        causal_parents=parents,
        model_evaluations=evaluations,
        input_sha256=input_sha,
        background_sha256=background_sha,
        evidence_sha256=_digest(evidence),
    )


def structural_model(
    scm: Any,
    *,
    exogenous: Optional[Mapping[str, float]] = None,
) -> ModelFn:
    """A structural causal model as an input -> outcomes function.

    Inputs are applied as do() interventions; every other node follows its
    structural equation with the given noise (default: its mean, 0). The
    returned mapping holds every node, so any node can be the target.
    """
    noise = dict(exogenous or {})

    def evaluate(inputs: Mapping[str, float]) -> Dict[str, float]:
        return scm.evaluate_all(interventions=dict(inputs), exogenous=noise)

    return evaluate


__all__ = [
    "EXPLANATION_METHOD",
    "MAX_EXACT_INPUTS",
    "Explanation",
    "explain",
    "structural_model",
]
