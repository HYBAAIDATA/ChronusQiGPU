"""Evidence categories rather than self-promoted knowledge claims."""

from enum import Enum


class EpistemicState(Enum):
    KNOWS = "knows"
    INFERS = "infers"
    SUSPECTS = "suspects"
    CANNOT_ESTABLISH = "cannot_establish"


def classify_epistemic_state(*, direct_evidence=False, valid_derivation=False, weak_signal=False):
    if direct_evidence:
        return EpistemicState.KNOWS
    if valid_derivation:
        return EpistemicState.INFERS
    if weak_signal:
        return EpistemicState.SUSPECTS
    return EpistemicState.CANNOT_ESTABLISH


def calibrate_uncertainty(claim):
    state = classify_epistemic_state(
        direct_evidence=bool(claim.observation_refs), valid_derivation=bool(claim.derivation_refs)
    )
    return state, (
        "not established by current evidence"
        if state is EpistemicState.CANNOT_ESTABLISH
        else state.value
    )
