from dataclasses import replace
from conftest import H
from chronus.agent.perception import (
    confirm_action_effect,
    assess_causality,
    CausalEvidence,
    ObservationChannel,
)


def test_temporal_matching_not_causal_proof(wired):
    r, o, c, p, a = wired
    pre = a.observe()
    a.path.write_text("after")
    post = a.observe()
    assert confirm_action_effect("a", pre, post, "after").judgement == "CONSISTENT_WITH_CAUSATION"
    assert (
        assess_causality("a", pre, post, "after", CausalEvidence((H,), (), ())).judgement
        == "CONFIRMED"
    )
    assert (
        assess_causality(
            "a", pre, post, "after", CausalEvidence((), (), ("other cause",))
        ).judgement
        == "CONFOUNDED"
    )
    assert (
        confirm_action_effect(
            "a", pre, replace(post, channel=ObservationChannel.INFERRED), "after"
        ).judgement
        == "NOT_CONFIRMED"
    )
