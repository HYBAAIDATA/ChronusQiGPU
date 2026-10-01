"""End-to-end repository contract for PYTHAGORAS v12.2."""
from pythagoras.adapter import PythagorasEngineAdapter

SAMPLE = "def transform(values):\n    return [value * 2 for value in values]\n"


def test_adapter_analysis_evolution_and_persistence(tmp_path):
    state = tmp_path / "pythagoras-session.json"
    adapter = PythagorasEngineAdapter(persistent_repo_path=str(state))
    analysis = adapter.analyze("sample.py", SAMPLE)
    assert len(analysis["11d_projection"]) == 11
    assert analysis["euclid_intelligence"]["owner"] == "EUCLID_REPO_INTELLIGENCE"
    result = adapter.evolve("sample.py", SAMPLE, generations=0, seed=7)
    assert result["target"] == "sample.py"
    assert result["best_euclid_intelligence"] >= result["initial_euclid_intelligence"]
    assert state.exists()
