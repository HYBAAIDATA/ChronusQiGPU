from dataclasses import replace
from conftest import H
from chronus.agent.abstraction import Abstraction, AbstractionState as S, discover_abstractions


def test_support_is_independent_and_falsifiable():
    a = Abstraction("a", "rule", "scope", ("same", "same"), (H, H), (), True)
    assert discover_abstractions((a,), minimum_groups=2)[0].state == S.CANDIDATE
    a = replace(a, support_groups=("one", "two"))
    assert discover_abstractions((a,), minimum_groups=2)[0].state == S.ESTABLISHED
    assert (
        discover_abstractions((replace(a, counterexamples=("case",)),), minimum_groups=2)[0].state
        == S.CONTESTED
    )
