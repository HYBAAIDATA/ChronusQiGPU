from pythagoras.adapter import PythagorasEngineAdapter
from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator


def test_euclid_is_intelligence_owner():
    result = EuclidIntelligenceEngine().compute_intelligence_scale("x = 1")
    assert result["owner"] == "EUCLID_REPO_INTELLIGENCE"
    assert result["scaling_formula"] == "Intelligence = L_n * 20^(phi * t_p)"


def test_lucas_recurrence():
    calc = LucasSequenceCalculator()
    for n in range(2, 31):
        assert calc.exact_lucas(n) == calc.exact_lucas(n - 1) + calc.exact_lucas(n - 2)


def test_adapter_uses_existing_pythagoras_substrate():
    adapter = PythagorasEngineAdapter()
    result = adapter.analyze("sample.py", "def sample():\n    return 1\n")
    assert result["domain"] == "code"
    assert result["euclid_intelligence"]["owner"] == "EUCLID_REPO_INTELLIGENCE"


def test_invalid_candidate_fails_closed():
    result = PythagorasEngineAdapter().evaluate_candidate("def broken(")
    assert result["parse_valid"] is False
    assert result["euclid_intelligence_score"] == 0.0


def test_property_invariants_are_exposed_at_host_boundary():
    adapter = PythagorasEngineAdapter()
    original = "def f(x):\n    return x\n"
    mutated = original + "\ny: int = 1\n"
    result = adapter.verify_property_invariants(original, mutated)
    assert result["non_degeneracy_invariant"] is True
    assert result["lucas_recurrence_invariant"] is True
    assert result["syntax_compilation_invariant"] is True
