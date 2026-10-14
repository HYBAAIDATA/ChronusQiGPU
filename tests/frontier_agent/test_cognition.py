from dataclasses import replace
from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError


def test_cognition_digest_changes_with_framing(wired):
    r, o, c, p, a = wired
    other = replace(c, representation=replace(c.representation, unknowns=("new unknown",)))
    assert other.fingerprint != c.fingerprint
    with pytest.raises(ContractError):
        r.run(o, other, p)


def test_initialise_runs_governed_selector(wired):
    from chronus.agent.cognition import initialise_cognition
    from chronus.agent.strategy import (
        TaskCharacterisation,
        SelectorPolicy,
        Strategy,
        ReasoningStrategy as S,
    )
    from chronus.agent.trust import TrustLevel

    r, o, c, p, a = wired
    state = initialise_cognition(
        o,
        (),
        extractor=lambda *_: c.representation,
        confidence_floor=F(1, 2),
        registry=(Strategy(S.TOOL_USE, 1, F(1), (), (), 2, True),),
        characterisation=TaskCharacterisation(
            r.task_class.key, F(1), F(0), "REVERSIBLE", "LOCAL", 10, (), (), F(1)
        ),
        authority=TrustLevel.OBSERVE,
        selector_policy=SelectorPolicy(F(1, 4), F(1, 2), F(1, 2), F(0), 10, 10, 1, F(1, 2)),
        statistics=(),
        verify_statistics=lambda *_: False,
        now=100,
        ledger=r.audit,
    )
    assert state.strategy.mode == "STOP"
