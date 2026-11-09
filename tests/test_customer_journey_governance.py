"""Content governance for customer-facing evaluation journeys.

These checks validate the journey data and its bounded claims; they do not
qualify the software or establish security, deployment, or performance.
"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "frontend" / "data" / "customer-journeys.json"
EXPECTED_JOURNEYS = {"government", "enterprise", "hyperscaler"}
REQUIRED_GATES = {"procurement", "security", "technical_evaluation"}
DISALLOWED_CLAIMS = (
    re.compile(r"\binfinite\b", re.IGNORECASE),
    re.compile(r"\bunlimited\b", re.IGNORECASE),
    re.compile(r"\bexponential\b", re.IGNORECASE),
    re.compile(r"\b100\s*x\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*x\b", re.IGNORECASE),
)


def _load_data():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_journey_set_and_required_approval_paths():
    journeys = _load_data()["journeys"]
    assert {journey["id"] for journey in journeys} == EXPECTED_JOURNEYS

    for journey in journeys:
        available_gates = {
            gate for phase in journey["phases"] for gate in phase["gates"]
        }
        assert set(journey["mandatoryGates"]) == REQUIRED_GATES
        assert REQUIRED_GATES <= available_gates


def test_every_phase_has_a_question_evidence_and_exit_gate():
    for journey in _load_data()["journeys"]:
        assert journey["roles"]
        assert journey["phases"]
        for phase in journey["phases"]:
            assert phase["name"].strip()
            assert phase["decisionQuestion"].strip()
            assert phase["evidence"]
            assert all(item.strip() for item in phase["evidence"])
            assert phase["exitCriteria"].strip()


def test_four_product_concepts_are_explicitly_evidence_gated():
    products = _load_data()["products"]
    assert {product["id"] for product in products} == {
        "accelerator",
        "compression",
        "gpu-pool",
        "memory-tiering",
    }
    for product in products:
        assert product["scope"].strip()
        assert product["evidenceStatus"].strip()
        assert product["requiredEvidence"].strip()


def test_shared_trust_artifacts_have_status_and_evidence_requirements():
    artifacts = _load_data()["trustArtifacts"]
    assert len(artifacts) == 7
    for artifact in artifacts:
        assert artifact["name"].strip()
        assert artifact["currentStatus"].strip()
        assert artifact["requiredEvidence"].strip()


def test_customer_facing_data_has_no_unbounded_or_unverified_speedup_claims():
    rendered_data = DATA_PATH.read_text(encoding="utf-8")
    for pattern in DISALLOWED_CLAIMS:
        assert pattern.search(rendered_data) is None, pattern.pattern
