"""Cognition combines explicit framing with authority-gated metacognitive selection."""

from dataclasses import dataclass
from ._contracts import digest
from .representation import represent_problem
from .strategy import select_reasoning_strategy


@dataclass(frozen=True)
class CognitiveState:
    representation: object
    strategy: object

    @property
    def fingerprint(self):
        return digest(self)


def initialise_cognition(
    objective,
    context,
    *,
    extractor,
    confidence_floor,
    registry,
    characterisation,
    authority,
    selector_policy,
    statistics,
    verify_statistics,
    now,
    ledger
):
    representation = represent_problem(
        objective, context, extractor=extractor, confidence_floor=confidence_floor
    )
    strategy = select_reasoning_strategy(
        registry,
        characterisation,
        authority=authority,
        policy=selector_policy,
        statistics=statistics,
        verify_statistics=verify_statistics,
        now=now,
        ledger=ledger,
    )
    return CognitiveState(representation, strategy)
