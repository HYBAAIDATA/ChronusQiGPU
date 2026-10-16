from chronus.agent.epistemic import classify_epistemic_state, EpistemicState


def test_unknown_not_knowledge():
    assert classify_epistemic_state() == EpistemicState.CANNOT_ESTABLISH
    assert classify_epistemic_state(valid_derivation=True) == EpistemicState.INFERS
