from types import SimpleNamespace

from hermes.offerings.salamander_platform_adapter import SalamanderPlatformAdapter


class FakeControlPlane:
    def __init__(self):
        self.calls = []

    def observe(self, observations, *, policy_id):
        self.calls.append((observations, policy_id))
        return SimpleNamespace(
            state=SimpleNamespace(value="HEALTHY"),
            decision_id="decision-123",
            reasons=(),
        )


def test_missing_control_plane_fails_closed_without_actuation():
    result = SalamanderPlatformAdapter().observe(
        [{"subsystem": "api", "dimension": "latency", "availability": "MEASURED", "value": 10}],
        tenant_id="tenant-a",
    )
    assert result["status"] == "unavailable"
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False


def test_observations_are_converted_to_canonical_typed_contract():
    control_plane = FakeControlPlane()
    adapter = SalamanderPlatformAdapter(control_plane)
    result = adapter.observe(
        [{
            "subsystem": "api",
            "dimension": "latency",
            "availability": "MEASURED",
            "value": 10.0,
            "unit": "ms",
            "source": "synthetic-test",
            "observed_at_ns": 123,
            "confidence": 0.9,
        }],
        tenant_id="tenant-a",
        policy_id="test-policy",
    )
    assert result["status"] == "available"
    assert result["health_state"] == "HEALTHY"
    assert result["decision_id"] == "decision-123"
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False
    observations, policy_id = control_plane.calls[0]
    assert observations[0].tenant_id == "tenant-a"
    assert observations[0].availability.value == "MEASURED"
    assert observations[0].value == 10.0
    assert policy_id == "test-policy"


def test_unavailable_observation_cannot_smuggle_a_value():
    adapter = SalamanderPlatformAdapter(FakeControlPlane())
    result = adapter.observe(
        [{
            "subsystem": "api",
            "dimension": "latency",
            "availability": "UNAVAILABLE",
            "value": 10.0,
        }],
        tenant_id="tenant-a",
    )
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "invalid_observation"


def test_invalid_tenant_is_rejected_before_control_plane_call():
    control_plane = FakeControlPlane()
    result = SalamanderPlatformAdapter(control_plane).observe(
        [{"subsystem": "api", "dimension": "health", "availability": "NOT_MEASURED"}],
        tenant_id=" ",
    )
    assert result["status"] == "unavailable"
    assert result["error"]["code"] == "invalid_tenant"
    assert control_plane.calls == []


class BaselineControlPlane(FakeControlPlane):
    def regression(self, metric, measured):
        if metric != "api.latency_ms":
            raise RuntimeError("baseline unavailable")
        return measured > 200.0


def test_salamander_bridge_reports_configured_baseline_regression_without_actuation():
    result = SalamanderPlatformAdapter(BaselineControlPlane()).observe(
        [{
            "subsystem": "api",
            "dimension": "latency",
            "availability": "MEASURED",
            "value": 350.0,
            "metric_key": "api.latency_ms",
        }],
        tenant_id="tenant-a",
    )
    assert result["status"] == "available"
    assert result["anomaly_status"] == "detected"
    assert result["anomalies"] == [{
        "metric_key": "api.latency_ms",
        "status": "anomaly",
    }]
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False


def test_salamander_bridge_does_not_call_missing_baseline_healthy():
    result = SalamanderPlatformAdapter(BaselineControlPlane()).observe(
        [{
            "subsystem": "api",
            "dimension": "latency",
            "availability": "MEASURED",
            "value": 350.0,
            "metric_key": "unknown.metric",
        }],
        tenant_id="tenant-a",
    )
    assert result["status"] == "available"
    assert result["anomaly_status"] == "unavailable"
    assert result["baseline_checks"][0]["status"] == "unavailable"
