from fractions import Fraction as F
import pytest
from chronus.agent.metacognition import MetacognitivePolicy, metacognitive_review


@pytest.mark.parametrize(
    "updates,expected",
    [
        ({"capability_available": False}, "CREATE_CAPABILITY"),
        ({"contradictory": True}, "SEEK_INDEPENDENT_REVIEW"),
        ({"understanding": F(0)}, "REFRAME_PROBLEM"),
        ({"no_progress": 4}, "GATHER_INFORMATION"),
    ],
)
def test_impasse_responses(updates, expected):
    args = dict(
        understanding=F(1),
        strategy_fit=F(1),
        no_progress=0,
        contradictory=False,
        capability_available=True,
        policy=MetacognitivePolicy(F(1, 2), F(1, 2), 3),
    )
    args.update(updates)
    assert metacognitive_review(**args) == expected
