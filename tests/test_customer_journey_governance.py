"""Content governance for customer-facing evaluation journeys.

These checks validate journey structure and bounded copy. They do not qualify
the software or establish security, deployment, or performance.
Run with: python -m unittest tests.test_customer_journey_governance -v
"""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "frontend" / "data" / "customer-journeys.json"
PAGE_PATH = ROOT / "frontend" / "app" / "journeys" / "page.tsx"
DOC_PATH = ROOT / "docs" / "HYPERSCALER_DATA_CONNECTOR_AND_USER_JOURNEYS.md"
README_PATH = ROOT / "README.md"
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


def _journey_text(journey):
    return " ".join(
        [journey["audience"], journey["summary"], *journey["customerRefusals"]]
        + [
            " ".join(
                [phase["name"], phase["decisionQuestion"], phase["exitCriteria"]]
                + phase["evidence"]
            )
            for phase in journey["phases"]
        ]
    )


class TestCustomerJourneyGovernance(unittest.TestCase):
    def test_exactly_three_distinct_customer_journeys(self):
        data = _load_data()
        self.assertEqual({journey["id"] for journey in data["journeys"]}, EXPECTED_JOURNEYS)
        self.assertEqual(data["releaseStatus"], "NOT RELEASE-QUALIFIED")

    def test_every_journey_has_procurement_security_and_technical_gates(self):
        for journey in _load_data()["journeys"]:
            available_gates = {
                gate for phase in journey["phases"] for gate in phase["gates"]
            }
            self.assertEqual(set(journey["mandatoryGates"]), REQUIRED_GATES)
            self.assertTrue(REQUIRED_GATES <= available_gates, journey["id"])

    def test_every_phase_has_question_evidence_exit_and_a_gate(self):
        for journey in _load_data()["journeys"]:
            self.assertTrue(journey["roles"])
            self.assertTrue(journey["phases"])
            for phase in journey["phases"]:
                with self.subTest(journey=journey["id"], phase=phase["id"]):
                    self.assertTrue(phase["name"].strip())
                    self.assertTrue(phase["gates"])
                    self.assertTrue(phase["decisionQuestion"].strip())
                    self.assertTrue(phase["evidence"])
                    self.assertTrue(all(item.strip() for item in phase["evidence"]))
                    self.assertTrue(phase["exitCriteria"].strip())

    def test_customer_visible_refusals_are_present_and_rendered(self):
        for journey in _load_data()["journeys"]:
            self.assertTrue(journey["customerRefusals"], journey["id"])
        page = PAGE_PATH.read_text(encoding="utf-8")
        self.assertIn("journey.customerRefusals.map", page)
        self.assertIn("Explicit limitations and refusals", page)

    def test_four_product_concepts_show_status_requirements_and_nonclaims(self):
        products = _load_data()["products"]
        self.assertEqual(
            {product["id"] for product in products},
            {"accelerator", "compression", "gpu-pool", "memory-tiering"},
        )
        for product in products:
            with self.subTest(product=product["id"]):
                self.assertTrue(product["scope"].strip())
                self.assertTrue(product["evidenceStatus"].strip())
                self.assertTrue(product["requiredEvidence"].strip())
                self.assertTrue(product["notClaimed"])
        page = PAGE_PATH.read_text(encoding="utf-8")
        self.assertIn("product.notClaimed.map", page)
        self.assertIn("Required before a claim", page)

    def test_product_specific_evidence_requirements_are_complete(self):
        products = {product["id"]: product for product in _load_data()["products"]}
        accelerator = products["accelerator"]["requiredEvidence"].lower()
        self.assertIn("source commit", accelerator)
        self.assertIn("hardware", accelerator)
        self.assertIn("raw output", accelerator)
        compression = products["compression"]["requiredEvidence"].lower()
        self.assertIn("ratio", compression)
        self.assertIn("verification", compression)
        self.assertIn("error metric", compression)
        capacity = products["gpu-pool"]["requiredEvidence"].lower()
        for term in ("ceiling", "supply source", "time-to-provision", "failure behavior", "remedies"):
            self.assertIn(term, capacity)
        memory = products["memory-tiering"]["requiredEvidence"].lower()
        for term in ("baseline failure", "successful run", "latency", "throughput"):
            self.assertIn(term, memory)

    def test_government_security_and_procurement_specifics(self):
        gov = next(j for j in _load_data()["journeys"] if j["id"] == "government")
        text = _journey_text(gov).lower()
        for term in ("sam.gov", "system security plan", "nist sp 800-53 rev. 5", "poa&m", "remediation date", "first 30 days", "quarterly"):
            self.assertIn(term, text)

    def test_enterprise_trial_security_and_contract_specifics(self):
        ent = next(j for j in _load_data()["journeys"] if j["id"] == "enterprise")
        text = _journey_text(ent).lower()
        for term in ("self-serve", "gpu-hour", "penetration-test report", "data-processing agreement", "software bill of materials", "baa", "insurance certificate", "export"):
            self.assertIn(term, text)

    def test_hyperscaler_benchmark_and_capacity_specifics(self):
        hyp = next(j for j in _load_data()["journeys"] if j["id"] == "hyperscaler")
        text = _journey_text(hyp).lower()
        for term in ("two pages", "p50", "p95", "p99", "variance", "n+1", "supply source", "failure modes"):
            self.assertIn(term, text)

    def test_seven_shared_trust_artifacts_show_status_and_evidence(self):
        artifacts = _load_data()["trustArtifacts"]
        self.assertEqual(len(artifacts), 7)
        for artifact in artifacts:
            with self.subTest(artifact=artifact["name"]):
                self.assertTrue(artifact["currentStatus"].strip())
                self.assertTrue(artifact["requiredEvidence"].strip())

    def test_customer_facing_copy_avoids_disallowed_and_unverified_speedup_claims(self):
        copy = "\n".join(path.read_text(encoding="utf-8") for path in (DATA_PATH, PAGE_PATH, DOC_PATH))
        for pattern in DISALLOWED_CLAIMS:
            with self.subTest(pattern=pattern.pattern):
                self.assertIsNone(pattern.search(copy))

    def test_document_console_and_readme_share_the_journey_source(self):
        page = PAGE_PATH.read_text(encoding="utf-8")
        doc = DOC_PATH.read_text(encoding="utf-8")
        readme = README_PATH.read_text(encoding="utf-8")
        self.assertIn("customer-journeys.json", page)
        self.assertIn("customer-journeys.json", doc)
        self.assertIn("docs/HYPERSCALER_DATA_CONNECTOR_AND_USER_JOURNEYS.md", readme)


if __name__ == "__main__":
    unittest.main()
