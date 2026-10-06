from toe.golden_unified import GoldenUnifiedTheory
from toe.system import TOESystem


def test_unified_observation_is_digest_bound_and_evidence_scoped():
    theory = GoldenUnifiedTheory()
    observation = theory.compile(
        {"revenue": [1.0, 2.0], "cost": [0.5, 0.75]},
        goal="business_intelligence",
    )
    assert observation.foundation_digest == theory.foundation.digest
    assert observation.theory_digest == theory.theory_digest
    assert "data_ml_bi" in observation.admitted_theories
    report = theory.report()
    assert report["verified"] is True
    assert report["open_problem_solution_claimed"] is False
    assert report["physical_theory_of_everything_claimed"] is False


def test_unresolved_disagreement_is_not_collapsed():
    theory = GoldenUnifiedTheory()
    result = theory.collapse(
        [
            {"surface": "surface_a", "answer": "left"},
            {"surface": "surface_b", "answer": "right"},
        ]
    )
    assert result.status == "DISAGREEMENT"
    assert result.collapsed is False
    assert result.answer is None


def test_declared_authority_can_resolve_without_averaging():
    theory = GoldenUnifiedTheory()
    result = theory.collapse(
        [
            {"surface": "associational_predictor", "answer": "hold"},
            {"surface": "causal_interventional", "answer": "act"},
        ],
        problem_type="interventional",
    )
    assert result.status == "DISAGREEMENT"
    assert result.collapsed is True
    assert result.answer == "act"
    assert "authority[interventional]" in result.reason


def test_toe_system_records_unified_foundation_on_every_new_decision():
    system = TOESystem()
    observation = system.unify_observation([1, 2, 3], goal="analytics")
    assert observation.foundation_digest == system.foundation.digest
    assert system.verify_provenance()
    record = system.provenance_ledger[-1]
    assert record.parameters["_unified_theory_digest"] == system.foundation.digest
    assert record.parameters["theory_digest"] == system.golden_unified.theory_digest
