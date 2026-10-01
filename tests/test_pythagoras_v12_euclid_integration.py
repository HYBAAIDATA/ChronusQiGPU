from pythagoras.adapter import PythagorasEngineAdapter
from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator


def test_euclid_is_intelligence_owner():
    result = EuclidIntelligenceEngine().compute_intelligence_scale("x = 1")
    assert result["owner"] == "EUCLID_REPO_INTELLIGENCE"


def test_lucas_recurrence():
    calc = LucasSequenceCalculator()
    for n in range(2, 31):
        assert calc.exact_lucas(n) == calc.exact_lucas(n - 1) + calc.exact_lucas(n - 2)


def test_invalid_candidate_fails_closed():
    result = PythagorasEngineAdapter().evaluate_candidate("def broken(")
    assert result["parse_valid"] is False
    assert result["euclid_intelligence_score"] == 0.0
