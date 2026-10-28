from hermes.offerings.national_security import NationalSecurityOffering


class FakeSalamanderAdapter:
    def __init__(self):
        self.calls = []

    def observe(self, observations, *, tenant_id, policy_id):
        self.calls.append((observations, tenant_id, policy_id))
        return {
            "schema": "hyba.salamander_observation/v1",
            "status": "available",
            "health_state": "HEALTHY",
            "action_authorized": False,
            "actuation_performed": False,
        }


def test_national_security_offering_routes_health_to_salamander_and_audits_status():
    adapter = FakeSalamanderAdapter()
    offering = NationalSecurityOffering(salamander_adapter=adapter)
    result = offering.observe_with_salamander(
        [{"subsystem": "api", "dimension": "health", "availability": "NOT_MEASURED"}],
        tenant_id="tenant-a",
        policy_id="smoke-policy",
    )
    assert result["status"] == "available"
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False
    assert result["hyba_audit_integrity"] is True
    assert adapter.calls[0][1:] == ("tenant-a", "smoke-policy")


def test_unconfigured_salamander_is_reported_instead_of_claiming_health():
    offering = NationalSecurityOffering()
    result = offering.observe_with_salamander(
        [{"subsystem": "api", "dimension": "health", "availability": "NOT_MEASURED"}],
        tenant_id="tenant-a",
    )
    assert result["status"] == "unavailable"
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False
