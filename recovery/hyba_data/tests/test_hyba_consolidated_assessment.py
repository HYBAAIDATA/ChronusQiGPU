from hermes.offerings.national_security import NationalSecurityOffering


class FakeTOEAdapter:
    def __init__(self):
        self.calls = []

    def assess(self, observation, *, tenant_id, purpose):
        self.calls.append((observation, tenant_id, purpose))
        return {
            "schema": "hyba.toe_assessment/v1",
            "status": "available",
            "recommendation_only": True,
            "action_authorized": False,
            "toe_response": {"ok": True, "receipt": {"receipt_id": "toe-r1"}},
        }


class FakeSalamanderAdapter:
    def observe(self, observations, *, tenant_id, policy_id):
        return {
            "schema": "hyba.salamander_observation/v1",
            "status": "available",
            "decision_id": "sal-r1",
            "health_state": "HEALTHY",
            "action_authorized": False,
            "actuation_performed": False,
        }


class FakeMathAPI:
    def __init__(self):
        self.calls = []

    def run(self, operation, payload):
        self.calls.append((operation, payload))
        return {"status": "available", "proof_claim": False}


def test_combined_assessment_coordinates_toe_and_salamander_without_math_or_actuation():
    toe = FakeTOEAdapter()
    math_api = FakeMathAPI()
    offering = NationalSecurityOffering(
        toe_adapter=toe,
        salamander_adapter=FakeSalamanderAdapter(),
        millennium_api=math_api,
    )
    result = offering.assess_operational_state(
        {"event_id": "e-1", "summary": "synthetic"},
        [{"subsystem": "api", "dimension": "health", "availability": "NOT_MEASURED"}],
        tenant_id="tenant-a",
        purpose="defensive-resilience",
    )
    assert result["schema"] == "hyba.national_security_assessment/v1"
    assert result["status"] == "available"
    assert result["assessment_id"]
    assert result["mathematical_probe_invoked"] is False
    assert result["recommendation_only"] is True
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False
    assert len(toe.calls) == 1
    assert math_api.calls == []


def test_combined_assessment_degrades_if_either_dependency_is_unavailable():
    offering = NationalSecurityOffering(
        toe_adapter=FakeTOEAdapter(),
        salamander_adapter=type("Unavailable", (), {
            "observe": lambda self, observations, *, tenant_id, policy_id: {
                "status": "unavailable", "action_authorized": False,
                "actuation_performed": False,
            }
        })(),
    )
    result = offering.assess_operational_state(
        {"event_id": "e-2"},
        [{"subsystem": "api", "dimension": "health", "availability": "NOT_MEASURED"}],
        tenant_id="tenant-a",
        purpose="defensive-resilience",
    )
    assert result["status"] == "degraded"
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False
