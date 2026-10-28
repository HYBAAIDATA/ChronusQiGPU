from __future__ import annotations

import time

import pytest

from hyba_mcp.control_plane import ControlPlane
from hyba_mcp.server import HybaMCPServer, TOOLS


def _arguments(lease_id: str) -> dict:
    return {
        "enabled": True,
        "metrics": {"vram_utilization": 0.9, "error_rate": 0.0, "throughput": 100.0},
        "baseline_throughput": 100.0,
        "lease_id": lease_id,
        "optimization": {
            "parameter": "batch_size",
            "previous_value": 4.0,
            "current_value": 5.0,
            "minimum": 1.0,
            "maximum": 10.0,
            "previous_cuop": 5.0,
            "current_cuop": 6.0,
        },
        "budget": {"max_steps": 1, "max_seconds": 1.0},
    }


def _server(tmp_path, *, enabled=True, identity="trusted-operator"):
    calls = []

    def authorizer(caller, capability, arguments):
        calls.append((caller, capability, arguments))
        if capability in {"security.verify_authority", "salamander.optimise"}:
            return {
                "allowed": True,
                "audit_record": {"expires_at": time.time() + 120.0},
            }
        return False

    plane = ControlPlane(
        authorizer=authorizer,
        audit_path=tmp_path / "mcp-audit.jsonl" if tmp_path is not None else None,
    )
    server = HybaMCPServer(
        control_plane=plane,
        identity_provider=lambda: identity,
        salamander_enabled=enabled,
    )
    return server, calls


def _lease(server):
    response = server.execute_tool(
        "invoke_skill",
        {
            "skill_id": "security.verify_authority",
            "arguments": {
                "identity": "untrusted-argument-identity",
                "capability": "salamander.optimise",
                "lease_duration": 60,
            },
        },
    )
    assert response["ok"] is True
    return response["authority_lease"]["lease_id"]


def test_tools_are_registered_on_the_existing_mcp_server():
    assert {"salamander_diagnose", "salamander_propose", "salamander_optimise"} <= TOOLS.keys()


def test_salamander_tools_are_disabled_without_both_opt_ins():
    server, _ = _server(None, enabled=False)
    result = server.execute_tool(
        "salamander_diagnose",
        {
            "enabled": True,
            "metrics": {"vram_utilization": 0.9, "error_rate": 0.0, "throughput": 1.0},
            "baseline_throughput": 1.0,
        },
    )
    assert result == {"enabled": False, "status": "disabled", "theorem_proven": False}

    server, _ = _server(None)
    result = server.execute_tool(
        "salamander_propose", {"enabled": False, "fault_type": "timeout", "details": {}}
    )
    assert result["status"] == "disabled"


@pytest.mark.parametrize(
    ("metrics", "expected_action"),
    [
        (
            {"vram_utilization": 0.85, "error_rate": 0.1, "throughput": 100.0},
            "none",
        ),
        (
            {"vram_utilization": 0.86, "error_rate": 0.0, "throughput": 100.0},
            "reduce_load",
        ),
        (
            {"vram_utilization": 0.0, "error_rate": 0.11, "throughput": 100.0},
            "circuit_break",
        ),
        (
            {"vram_utilization": 0.0, "error_rate": 0.0, "throughput": 0.0},
            "recalibrate",
        ),
    ],
)
def test_diagnose_is_quiet_at_bounds_and_reports_homeostasis_breaches(
    tmp_path, metrics, expected_action
):
    server, _ = _server(tmp_path)
    result = server.execute_tool(
        "salamander_diagnose",
        {"enabled": True, "metrics": metrics, "baseline_throughput": 100.0},
    )
    assert result["report"]["action"] == expected_action
    assert result["triggered"] is (expected_action != "none")
    assert result["theorem_proven"] is False


def test_propose_uses_diagnosis_only_and_never_applies():
    server = HybaMCPServer(salamander_enabled=True)
    result = server.execute_tool(
        "salamander_propose",
        {"enabled": True, "fault_type": "timeout", "details": {"component": "worker"}},
    )
    assert result["proposal"]["proposed_action"] == "reduce_batch_size"
    assert result["proposal"]["applied"] is False
    assert result["applied"] is False
    assert result["executed"] is False


def test_authority_lease_uses_trusted_identity_and_optimizer_is_advisory(tmp_path):
    server, calls = _server(tmp_path)
    lease_id = _lease(server)
    assert all(caller == "trusted-operator" for caller, _, _ in calls)
    assert calls[-1][1] == "salamander.optimise"

    result = server.execute_tool("salamander_optimise", _arguments(lease_id))
    recommendation = result["recommendation"]
    assert result["status"] == "recommended"
    assert result["applied"] is False
    assert result["evidence_class"] == "caller_supplied_unverified_telemetry"
    assert 1.0 <= recommendation["suggested_value"] <= 10.0
    assert recommendation["steps"] == 1
    assert result["audit_record"]["event"] == "salamander_optimise"
    assert server.control_plane.audit.verify() is True


def test_authority_lease_is_single_use_and_identity_bound(tmp_path):
    server, _ = _server(tmp_path)
    lease_id = _lease(server)
    assert (
        server.execute_tool("salamander_optimise", _arguments(lease_id))["status"] == "recommended"
    )
    second = server.execute_tool("salamander_optimise", _arguments(lease_id))
    assert second["status"] == "denied"
    assert second["reason"] == "authority_lease_invalid"

    server, _ = _server(tmp_path / "second")
    lease_id = _lease(server)
    server.identity_provider = lambda: "different-operator"
    result = server.execute_tool("salamander_optimise", _arguments(lease_id))
    assert result["reason"] == "authority_lease_invalid"


def test_expired_lease_and_non_breach_do_not_optimize(tmp_path):
    server, _ = _server(tmp_path)
    lease_id = _lease(server)
    server.salamander_tools._leases[lease_id]["expires_mono"] = 0.0
    expired = server.execute_tool("salamander_optimise", _arguments(lease_id))
    assert expired["reason"] == "authority_lease_expired"

    lease_id = _lease(server)
    args = _arguments(lease_id)
    args["metrics"]["vram_utilization"] = 0.0
    quiet = server.execute_tool("salamander_optimise", args)
    assert quiet["status"] == "quiet"
    assert quiet["recommendation"] is None


def test_optimizer_enforces_rate_limit_and_circuit_breaker(tmp_path):
    server, _ = _server(tmp_path)
    first_lease = _lease(server)
    assert (
        server.execute_tool("salamander_optimise", _arguments(first_lease))["status"]
        == "recommended"
    )

    second_lease = _lease(server)
    limited = server.execute_tool("salamander_optimise", _arguments(second_lease))
    assert limited["reason"] == "rate_limit_exceeded"

    server, _ = _server(tmp_path / "breaker")
    lease_id = _lease(server)
    server.salamander_tools._get_circuit_breaker().state = "OPEN"
    blocked = server.execute_tool("salamander_optimise", _arguments(lease_id))
    assert blocked["reason"] == "circuit_breaker_open"


def test_optimizer_rejects_budget_above_one_step(tmp_path):
    server, _ = _server(tmp_path)
    args = _arguments(_lease(server))
    args["budget"]["max_steps"] = 2
    with pytest.raises(ValueError, match="max_steps"):
        server.execute_tool("salamander_optimise", args)
