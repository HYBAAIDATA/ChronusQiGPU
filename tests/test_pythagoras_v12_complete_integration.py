"""End-to-end contract tests for the complete PYTHAGORAS v12 drop-in integration."""

from __future__ import annotations

from pathlib import Path

import pythagoras
from pythagoras.adapter import PythagorasEngineAdapter
from pythagoras.agents.manifold import AgentID
from pythagoras.agents.orchestrator import MultiAgentEntangledOrchestrator
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core.primitives import ASTPrimitives
from pythagoras.core.tononi_penrose import TononiPenroseSubstrate
from pythagoras.enterprise.roi_governance import EnterpriseROIGovernanceEngine
from pythagoras.healing import RepositoryHealingOrchestrator


SAMPLE = """\
def transform(values: list[int]) -> list[int]:
    output: list[int] = []
    for value in values:
        output.append(value * 2)
    return output
"""


def test_complete_v12_surface_is_exported_and_superseded_engine_is_absent():
    assert pythagoras.__version__ == "12.0.0"
    assert hasattr(pythagoras, "PythagorasEngineAdapter")
    assert hasattr(pythagoras, "MultiAgentEntangledOrchestrator")
    assert hasattr(pythagoras, "RepositoryHealingOrchestrator")
    package_root = Path(pythagoras.__file__).resolve().parent
    assert not (package_root / "engine").exists()


def test_v12_metric_reports_measured_features_and_fails_closed():
    calculator = PhiResonanceCalculator()
    measured = calculator.extract_features(SAMPLE)
    assert measured["parse_valid"] is True
    assert measured["node_count"] > 0
    invalid = calculator.extract_features("def broken(")
    assert invalid == {
        "parse_valid": False,
        "node_count": 0,
        "depth": 0,
        "annotation_density": 0.0,
        "function_count": 0,
        "statement_count": 0,
        "phi_score": 0.1000,
    }


def test_v12_primitive_vocabulary_is_available():
    names = {name for name, _ in ASTPrimitives.get_all_operators()}
    assert names == {
        "ADD:AnnAssign",
        "NON_LOCAL:function_split_refactor",
        "MUTATE:rename_variable",
        "MUTATE:swap_binary_operator",
        "MUTATE:inject_docstring",
        "MUTATE:dead_code_branch",
        "MUTATE:list_comprehension",
    }


def test_tononi_penrose_output_cannot_pose_as_physical_mining_evidence():
    result = TononiPenroseSubstrate.calculate_integrated_information(20, 40, 5)
    assert result["evidence_class"] == "MODELED"
    assert result["physical_measurement"] is False


def test_roi_model_is_not_invented_without_explicit_coefficients():
    result = EnterpriseROIGovernanceEngine.calculate_technical_debt_reduction(
        total_evaluations=10,
        valid_evaluations=8,
        initial_phi=0.5,
        final_phi=0.6,
        wall_time_ms=12.0,
    )
    assert result["validity_survival_ratio"] == 0.8
    assert result["economic_model_applied"] is False
    assert result["estimated_dev_hours_saved"] is None
    assert result["estimated_dollar_value_roi"] is None


def test_adapter_exposes_full_analysis_evolution_and_snapshot(tmp_path):
    state = tmp_path / "pythagoras-session.json"
    adapter = PythagorasEngineAdapter(persistent_repo_path=str(state))
    analysis = adapter.analyze("sample.py", SAMPLE)
    assert len(analysis["11d_projection"]) == 11
    assert analysis["euclid_intelligence"]["owner"] == "EUCLID_REPO_INTELLIGENCE"

    result = adapter.evolve("sample.py", SAMPLE, generations=0, seed=7)
    assert result["target"] == "sample.py"
    assert result["engine"] == "PYTHAGORAS_CURRENT_META_EVOLUTION"
    assert result["candidate_gate"]["runtime_gate"] == "NOT_RUN"
    assert state.exists()

    primitive = adapter.commit_primitive(
        "ADD:AnnAssign",
        "shipped operator",
        origin_target="integration-test",
    )
    assert primitive["active"] is True
    assert "ADD:AnnAssign" in adapter.snapshot()["repository_summary"]["primitives_detail"]


def test_multi_agent_cycle_records_all_four_agent_roles():
    orchestrator = MultiAgentEntangledOrchestrator()
    result = orchestrator.run_multi_agent_cycle(
        [{"name": "sample.py", "code_str": SAMPLE}],
        generations=0,
    )
    assert "sample.py" in result["session_results"]
    projections = result["manifold_snapshot"]["agent_11d_projections"]
    assert AgentID.EUCLID.value in projections
    assert AgentID.SALAMANDER.value in projections
    assert AgentID.AL_HARAS.value in projections
    assert AgentID.PYTHIA.value in projections


def test_healing_bridge_never_writes_tests_or_unverified_candidates(tmp_path, monkeypatch):
    source = tmp_path / "module.py"
    source.write_text("x = 1\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    test_file = tests / "test_module.py"
    test_file.write_text("def test_x(): assert True\n", encoding="utf-8")

    bridge = RepositoryHealingOrchestrator(tmp_path, verify_cmd=None)

    def fake_evolve(*args, **kwargs):
        return {"final_code": "x = 2\n"}

    def fake_invariants(*args, **kwargs):
        return {"syntax_compilation_invariant": True}

    monkeypatch.setattr(bridge.adapter, "evolve", fake_evolve)
    monkeypatch.setattr(bridge.adapter, "verify_property_invariants", fake_invariants)
    result = bridge.optimize_file("module.py")
    assert result["status"] == "PROPOSED_AWAITING_VERIFICATION_COMMAND"
    assert source.read_text(encoding="utf-8") == "x = 1\n"

    try:
        bridge.optimize_file("tests/test_module.py")
    except ValueError as exc:
        assert "never auto-writes test files" in str(exc)
    else:
        raise AssertionError("test files must not be eligible for healing writes")
