"""Independent support/counterexample/held-out gates for candidate abstractions."""

from dataclasses import dataclass, replace
from enum import Enum
from ._contracts import ContractError, integer, sha


class AbstractionState(Enum):
    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    ESTABLISHED = "established"
    CONTESTED = "contested"
    RETRACTED = "retracted"


@dataclass(frozen=True)
class Abstraction:
    id: str
    statement: str
    scope: str
    support_groups: tuple[str, ...]
    evidence: tuple[str, ...]
    counterexamples: tuple[str, ...]
    heldout_improved: bool
    state: AbstractionState = AbstractionState.CANDIDATE


def discover_abstractions(candidates, *, minimum_groups):
    integer(minimum_groups, minimum=2)
    if type(candidates) is not tuple or len(candidates) > 256:
        raise ContractError("bounded abstraction candidates required")
    results = []
    for c in candidates:
        for ref in c.evidence:
            sha(ref)
        state = AbstractionState.CANDIDATE
        if c.counterexamples:
            state = AbstractionState.CONTESTED
        elif len(set(c.support_groups)) >= minimum_groups and len(c.evidence) >= minimum_groups:
            state = (
                AbstractionState.ESTABLISHED
                if c.heldout_improved is True
                else AbstractionState.SUPPORTED
            )
        results.append(replace(c, state=state))
    return tuple(results)
