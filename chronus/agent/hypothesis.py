"""Finite competing hypotheses with exact likelihood updates and falsifiers."""

from dataclasses import dataclass, replace
from fractions import Fraction
from ._contracts import ContractError, ratio, sha


@dataclass(frozen=True)
class Hypothesis:
    id: str
    statement: str
    predictions: tuple[str, ...]
    falsifiers: tuple[str, ...]
    prior: Fraction
    posterior: Fraction
    evidence: tuple[str, ...] = ()
    state: str = "GENERATED"

    def __post_init__(self):
        ratio(self.prior)
        ratio(self.posterior)
        if not self.predictions or not self.falsifiers:
            raise ContractError("testable predictions and falsifiers required")


@dataclass(frozen=True)
class ExperimentResult:
    evidence: str
    likelihood_if_true: Fraction
    likelihood_if_false: Fraction
    falsified: bool


def generate_competing_hypotheses(candidates):
    if (
        type(candidates) is not tuple
        or not 2 <= len(candidates) <= 64
        or len({h.id for h in candidates}) != len(candidates)
    ):
        raise ContractError("multiple distinct, bounded hypotheses required")
    return candidates


def scientific_cycle(candidates, *, run_experiment):
    results = []
    for h in generate_competing_hypotheses(candidates):
        r = run_experiment(h)
        if not isinstance(r, ExperimentResult) or type(r.falsified) is not bool:
            raise ContractError("typed experiment result required")
        sha(r.evidence)
        ratio(r.likelihood_if_true)
        ratio(r.likelihood_if_false)
        denominator = h.prior * r.likelihood_if_true + (1 - h.prior) * r.likelihood_if_false
        if denominator == 0:
            state, posterior = "INCONCLUSIVE", h.prior
        else:
            posterior = h.prior * r.likelihood_if_true / denominator
            state = "REFUTED" if r.falsified else "SUPPORTED"
        results.append(
            replace(h, posterior=posterior, state=state, evidence=h.evidence + (r.evidence,))
        )
    return tuple(results)
