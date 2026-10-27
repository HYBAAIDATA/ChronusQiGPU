"""Contract, governance, and sandbox regressions for the HYBA MCP skills."""

from __future__ import annotations

import itertools
import json
import multiprocessing
import sys
import types
from dataclasses import dataclass

import pytest

from hyba_mcp.control_plane import AuditTrail, ControlPlane, SandboxConfig
from hyba_mcp.server import HybaMCPServer, TOOLS
from hyba_mcp.skills import SKILL_MODULES, get_skill_module
from hyba_mcp.skills.common import validate_schema


def _allow(identity: str, capability: str, arguments: dict) -> dict:
    return {
        "allowed": True,
        "reason": "test policy admitted",
        "audit_record": {"identity": identity, "capability": capability},
    }


def _append_audit_after_start(path, start, event) -> None:
    start.wait(5)
    AuditTrail(path).append({"event": event})


def _fake_toe(monkeypatch, *, causal=None, trajectory=None, mining=None) -> None:
    class FakeOrchestrator:
        def toe_explain_causality(self, data):
            return causal

        def toe_predict_trajectory(self, data):
            return trajectory

        def toe_guide_mining(self, header, target, context):
            return mining

    intelligence = types.ModuleType("Intelligence.orchestrator")
    intelligence.IntelligenceOrchestrator = FakeOrchestrator
    bridge = types.ModuleType("toe.bridge")
    bridge.TOEBridge = type("TOEBridge", (), {})
    monkeypatch.setitem(sys.modules, "Intelligence.orchestrator", intelligence)
    monkeypatch.setitem(sys.modules, "toe.bridge", bridge)


@pytest.mark.parametrize("skill_id", list(SKILL_MODULES))
def test_each_registered_skill_has_a_complete_contract(skill_id):
    module = get_skill_module(skill_id)
    assert module.SKILL_ID == skill_id
    assert module.INPUT_SCHEMA["type"] == "object"
    assert module.OUTPUT_SCHEMA["type"] == "object"
    assert module.INPUT_SCHEMA["required"]
    assert module.SOURCE
    assert module.EXAMPLES
    assert module.LIMITATIONS


@pytest.mark.parametrize("skill_id", list(SKILL_MODULES))
def test_each_skill_example_matches_its_advertised_contract(skill_id):
    module = get_skill_module(skill_id)
    for example in module.EXAMPLES:
        assert validate_schema(example["input"], module.INPUT_SCHEMA) == []
        assert validate_schema(example["output"], module.OUTPUT_SCHEMA) == []


@pytest.mark.parametrize(
    ("skill_id", "arguments"),
    [
        ("proof.emergence_verify", {"spectral_gap": 1}),
        ("reasoning.causal_explain", {"data": {}}),
        ("healing.propose_repair", {"telemetry": {}}),
        ("security.verify_authority", {"identity": "agent"}),
        ("adaptation.trajectory_predict", {"state_data": {}}),
        ("mining.guidance", {"header": [], "target": []}),
    ],
)
def test_each_skill_rejects_missing_required_inputs(skill_id, arguments):
    assert not ControlPlane().validate_inputs(skill_id, arguments)["valid"]


@pytest.mark.parametrize(
    ("skill_id", "arguments", "extra"),
    [
        (
            "proof.emergence_verify",
            {"spectral_gap": 1, "betti_1": 1, "phi_resonance": 1},
            "ignored",
        ),
        ("reasoning.causal_explain", {"data": {}, "query": "why"}, "ignored"),
        ("healing.propose_repair", {"telemetry": {}, "fault_type": "timeout"}, "ignored"),
        (
            "security.verify_authority",
            {"identity": "x", "capability": "y", "lease_duration": 1},
            "ignored",
        ),
        ("adaptation.trajectory_predict", {"state_data": {}, "horizon": 1}, "ignored"),
        ("mining.guidance", {"header": [], "target": [], "context": {}}, "ignored"),
    ],
)
def test_each_skill_rejects_uncontracted_fields(skill_id, arguments, extra):
    arguments["unexpected"] = extra
    assert not ControlPlane().validate_inputs(skill_id, arguments)["valid"]


@pytest.mark.parametrize("bits", list(itertools.product((False, True), repeat=3)))
def test_emergence_criterion_truth_table_is_exact(bits):
    from hyba_mcp.skills.emergence_verify import run

    gap = 1.0 if bits[0] else 0.0
    betti = 1.0 if bits[1] else 0.0
    resonance = 0.6 if bits[2] else 0.5
    result = run(gap, betti, resonance)
    assert result["emerged"] is all(bits)
    assert result["confidence"] == (1.0 if all(bits) else 0.0)
    assert result["diagnostics"]["emerged"] is all(bits)


@pytest.mark.parametrize(
    ("task", "constraints", "expected"),
    [
        (
            {"candidates": ["proof.emergence_verify", "security.verify_authority"]},
            {},
            "proof.emergence_verify",
        ),
        (
            {"candidates": ["mining.guidance", "healing.propose_repair"]},
            {},
            "healing.propose_repair",
        ),
        ({"skill_id": "adaptation.trajectory_predict"}, {"max_cost": 4}, None),
        ({"skill_id": "mining.guidance"}, {"max_risk": 0.2}, None),
        ({"skill_id": "reasoning.causal_explain"}, {"max_seconds": 5}, None),
        (
            {"skill_id": "security.verify_authority"},
            {"max_cost": 1, "max_risk": 0.05},
            "security.verify_authority",
        ),
    ],
)
def test_router_honors_explicit_candidates_and_budgets(task, constraints, expected):
    selected, _, _ = ControlPlane().route_task(task, constraints)
    assert selected == expected


def test_router_chooses_cheapest_competent_candidate():
    selected, cost, risk = ControlPlane().route_task(
        {"candidates": ["mining.guidance", "healing.propose_repair", "proof.emergence_verify"]}
    )
    assert (selected, cost, risk) == ("proof.emergence_verify", 1, 0.05)


def test_router_accepts_explicit_fallback_chain_candidates():
    selected, _, _ = ControlPlane().route_task(
        {"fallback_chain": ["mining.guidance", "healing.propose_repair"]},
        {"max_cost": 2},
    )
    assert selected == "healing.propose_repair"


def test_emergence_rejects_non_finite_and_boolean_values():
    errors = validate_schema(
        {"spectral_gap": float("nan"), "betti_1": True, "phi_resonance": 1.0},
        get_skill_module("proof.emergence_verify").INPUT_SCHEMA,
    )
    assert len(errors) == 2


def test_emergence_source_module_reports_actual_threshold_diagnostics():
    from hyba_mcp.skills.emergence_verify import run

    result = run(0.01, 1, 0.51)
    assert result["emerged"]
    assert result["diagnostics"]["delta_ok"]
    assert result["confidence_measure"].startswith("binary predicate")


def test_emergence_benchmark_claim_is_disclosed_not_certified():
    module = get_skill_module("proof.emergence_verify")
    assert any("dataset" in limitation for limitation in module.LIMITATIONS)


def test_causal_skill_calls_orchestrator_contract_and_marks_query_scope(monkeypatch):
    analysis = types.SimpleNamespace(
        available=True,
        confidence=0.75,
        key_factors=[("load", 0.8)],
        factor_weights={"load": 0.8},
        as_dict=lambda: {"diagnostics": {"ranking_basis": "expectation_magnitude"}},
    )
    _fake_toe(monkeypatch, causal=analysis)
    from hyba_mcp.skills.causal_explain import run

    result = run({"load": 0.8}, "why is load high?")
    assert result["factors"] == [{"factor": "load", "weight": 0.8}]
    assert result["query_context"] == "why is load high?"
    assert any("not interpreted" in value for value in result["limitations"])


def test_causal_skill_fails_closed_when_source_reports_unavailable(monkeypatch):
    analysis = types.SimpleNamespace(available=False, confidence=0.0, as_dict=lambda: {})
    _fake_toe(monkeypatch, causal=analysis)
    from hyba_mcp.skills.causal_explain import run

    with pytest.raises(RuntimeError, match="unavailable"):
        run({}, "why?")


def test_repair_skill_calls_only_diagnosis_and_never_executes(monkeypatch):
    @dataclass
    class Proposal:
        proposal_id: str = "p1"
        target: str = "engine"
        issue_type: str = "timeout"
        description: str = "timeout"
        proposed_action: str = "reduce_batch_size"
        is_safe: bool = True
        applied: bool = True
        timestamp: float = 1.0

    class SelfRepairEngine:
        def diagnose(self, fault_type, details):
            assert fault_type == "timeout"
            assert details["component"] == "engine"
            return Proposal()

    module = types.ModuleType("Intelligence.salamander")
    module.SelfRepairEngine = SelfRepairEngine
    monkeypatch.setitem(sys.modules, "Intelligence.salamander", module)
    from hyba_mcp.skills.propose_repair import run

    result = run({"component": "engine"}, "timeout")
    assert result["executed"] is False
    assert result["proposal"]["applied"] is False
    assert result["risk_score"] == 0.0


def test_unknown_repair_fault_is_advisory_and_high_risk(monkeypatch):
    @dataclass
    class Proposal:
        proposal_id: str = "p2"
        target: str = "engine"
        issue_type: str = "unclassified"
        description: str = "unknown"
        proposed_action: str = "log_and_escalate"
        is_safe: bool = False
        applied: bool = False
        timestamp: float = 1.0

    class SelfRepairEngine:
        def diagnose(self, fault_type, details):
            return Proposal()

    module = types.ModuleType("Intelligence.salamander")
    module.SelfRepairEngine = SelfRepairEngine
    monkeypatch.setitem(sys.modules, "Intelligence.salamander", module)
    from hyba_mcp.skills.propose_repair import run

    result = run({}, "unknown")
    assert result["executed"] is False
    assert result["risk_score"] == 1.0


def test_authority_skill_denies_without_configured_adapter():
    from hyba_mcp.skills.verify_authority import run

    result = run("agent", "proof.emergence_verify", 30)
    assert result["allowed"] is False
    assert "unavailable" in result["reason"]


def test_authority_skill_uses_explicit_authorizer():
    from hyba_mcp.skills.verify_authority import run

    result = run("agent", "proof.emergence_verify", 30, authorizer=_allow)
    assert result["allowed"] is True
    assert result["audit_record"]["allowed"] is True


def test_authority_skill_closes_on_adapter_exception():
    from hyba_mcp.skills.verify_authority import run

    def broken(*args):
        raise OSError("policy service unavailable")

    with pytest.raises(RuntimeError, match="failed closed"):
        run("agent", "capability", 10, authorizer=broken)


def test_trajectory_skill_uses_requested_prefix_and_fidelity_uncertainty(monkeypatch):
    forecast = types.SimpleNamespace(
        available=True,
        confidence=0.8,
        diagnostics={"energies": [1, 2, 3, 4, 5, 6]},
        intervention_points=[{"time": 1}, {"time": 4}],
    )
    _fake_toe(monkeypatch, trajectory=forecast)
    from hyba_mcp.skills.trajectory_predict import run

    result = run({"x": 1}, 3)
    assert result["trajectory"] == [1, 2, 3]
    assert result["uncertainty"] == pytest.approx(0.2)
    assert result["intervention_points"] == [{"time": 1}]


def test_mining_skill_does_not_invent_expected_value(monkeypatch):
    _fake_toe(monkeypatch, mining={"confidence": 0.8, "available": True})
    from hyba_mcp.skills.mining_guidance import run

    result = run(b"header", b"target", {})
    assert result["expected_value"] is None
    assert result["advisory_only"] is True
    assert result["search_space"]["ordering_advice"] == "not provided by this endpoint"


def test_mining_json_schema_bounds_byte_values():
    result = ControlPlane().validate_inputs(
        "mining.guidance",
        {"header": [256], "target": [], "context": {}},
    )
    assert not result["valid"]


def test_permission_denied_by_default_and_audited(tmp_path):
    control = ControlPlane(audit_path=tmp_path / "audit.jsonl")
    allowed, reason, record = control.check_permission("agent", "proof.emergence_verify", {})
    assert not allowed
    assert "unavailable" in reason
    assert record["event"] == "permission_decision"
    assert control.audit.verify()


def test_allow_requires_durable_audit():
    control = ControlPlane(authorizer=_allow)
    allowed, reason, _ = control.check_permission("agent", "proof.emergence_verify", {})
    assert not allowed
    assert "durable audit" in reason


def test_permission_audit_is_hash_chained_and_reloadable(tmp_path):
    path = tmp_path / "audit.jsonl"
    control = ControlPlane(authorizer=_allow, audit_path=path)
    allowed, _, record = control.check_permission(
        "agent", "proof.emergence_verify", {"spectral_gap": 1}
    )
    assert allowed and record["record_hash"]
    restored = AuditTrail(path)
    assert restored.verify()
    assert len(restored.records()) == 1


def test_stale_audit_instances_append_to_current_verified_tail(tmp_path):
    path = tmp_path / "audit.jsonl"
    first = AuditTrail(path)
    second = AuditTrail(path)
    first_record = first.append({"event": "first"})
    second_record = second.append({"event": "second"})
    assert second_record["sequence"] == 2
    assert second_record["previous_hash"] == first_record["record_hash"]
    assert AuditTrail(path).verify()


def test_concurrent_processes_serialize_audit_appends(tmp_path):
    context = multiprocessing.get_context("spawn")
    path = str(tmp_path / "audit.jsonl")
    start = context.Event()
    processes = [
        context.Process(target=_append_audit_after_start, args=(path, start, event))
        for event in ("first", "second")
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
    assert all(process.exitcode == 0 for process in processes)
    trail = AuditTrail(path)
    records = trail.records()
    assert [record["sequence"] for record in records] == [1, 2]
    assert {record["event"] for record in records} == {"first", "second"}
    assert trail.verify()


def test_audit_persistence_failure_poison_trail_and_denies_future_checks(monkeypatch, tmp_path):
    authorizer_calls = []
    control = ControlPlane(
        authorizer=lambda *args: authorizer_calls.append(args) or True,
        audit_path=tmp_path / "audit.jsonl",
    )

    def fail_fsync(_fd):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr("hyba_mcp.control_plane.os.fsync", fail_fsync)
    first = control.check_permission("agent", "proof.emergence_verify", {})
    second = control.check_permission("agent", "proof.emergence_verify", {})
    assert not first[0] and not second[0]
    assert "audit persistence failed" in first[1]
    assert len(authorizer_calls) == 1
    assert not control.audit.healthy


def test_audit_chain_detects_tampering(tmp_path):
    path = tmp_path / "audit.jsonl"
    trail = AuditTrail(path)
    trail.append({"event": "test"})
    record = json.loads(path.read_text())
    record["event"] = "changed"
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        AuditTrail(path)


def test_permission_callback_exception_fails_closed(tmp_path):
    def broken(*args):
        raise RuntimeError("unavailable")

    control = ControlPlane(authorizer=broken, audit_path=tmp_path / "audit.jsonl")
    allowed, reason, _ = control.check_permission("agent", "proof.emergence_verify", {})
    assert not allowed
    assert "failed closed" in reason


def test_oversized_permission_payload_is_hashed_and_denied(tmp_path):
    called = False

    def authorizer(*args):
        nonlocal called
        called = True
        return True

    control = ControlPlane(authorizer=authorizer, audit_path=tmp_path / "audit.jsonl")
    allowed, reason, record = control.check_permission(
        "agent",
        "reasoning.causal_explain",
        {"data": {"payload": "x" * 1_100_000}, "query": "why"},
    )
    assert not allowed
    assert not called
    assert "audit payload limit" in reason
    assert record["inputs"]["truncated"]
    assert len(record["inputs"]["sha256"]) == 64


def test_outcome_tracker_flags_repeated_regression(tmp_path):
    control = ControlPlane(audit_path=tmp_path / "audit.jsonl")
    for _ in range(5):
        summary = control.record_outcome(
            "proof.emergence_verify", {}, {"confidence": 0.9}, 0.2, False
        )
    assert summary["observations"] == 5
    assert summary["regression_detected"]
    assert summary["mean_brier_score"] == pytest.approx(0.81)


def test_outcome_tracker_rejects_invalid_latency():
    with pytest.raises(ValueError, match="latency"):
        ControlPlane().record_outcome("proof.emergence_verify", {}, {}, -1, False)


def test_sandbox_validation_fails_closed_on_invalid_limits():
    control = ControlPlane()
    result = control.execute_skill(
        "proof.emergence_verify",
        {"spectral_gap": 1, "betti_1": 1, "phi_resonance": 1},
        SandboxConfig(timeout_seconds=0),
    )
    assert not result["ok"]


def test_sandbox_timeout_is_enforced():
    control = ControlPlane()
    result = control.execute_skill(
        "proof.emergence_verify",
        {"spectral_gap": 1, "betti_1": 1, "phi_resonance": 1},
        SandboxConfig(timeout_seconds=0.001),
    )
    assert not result["ok"]
    assert result["error"]["code"] == "timeout"


def test_sandbox_executes_a_registered_skill_successfully():
    result = ControlPlane().execute_skill(
        "proof.emergence_verify",
        {"spectral_gap": 1, "betti_1": 1, "phi_resonance": 1},
    )
    assert result["ok"]
    assert result["result"]["emerged"] is True


def test_sandbox_uses_registered_skills_only():
    result = ControlPlane().execute_skill("os.system", {"command": "echo unsafe"})
    assert not result["ok"]
    assert result["error"]["code"] == "invalid_input"


def test_invoke_skill_enforces_permission_and_records_denial(tmp_path):
    server = HybaMCPServer(
        control_plane=ControlPlane(
            authorizer=lambda *args: False, audit_path=tmp_path / "audit.jsonl"
        )
    )
    result = server.control_plane.invoke_skill(
        "agent",
        "proof.emergence_verify",
        {"spectral_gap": 1, "betti_1": 1, "phi_resonance": 1},
    )
    assert result["error"]["code"] == "permission_denied"
    assert server.control_plane.audit.verify()


def test_invoke_skill_checks_budget_before_authority(tmp_path):
    control = ControlPlane(authorizer=_allow, audit_path=tmp_path / "audit.jsonl")
    result = control.invoke_skill(
        "agent",
        "mining.guidance",
        {"header": [], "target": [], "context": {}},
        options={"constraints": {"max_cost": 1}},
    )
    assert result["error"]["code"] == "budget_exceeded"


def test_authority_invocation_is_audited_without_execution_subprocess(tmp_path):
    control = ControlPlane(authorizer=_allow, audit_path=tmp_path / "audit.jsonl")
    result = control.invoke_skill(
        "caller",
        "security.verify_authority",
        {"identity": "subject", "capability": "proof.emergence_verify", "lease_duration": 30},
    )
    assert result["ok"]
    assert result["result"]["allowed"]
    assert control.audit.verify()
    assert all(record["identity"] == "caller" for record in control.audit.records())


def test_mcp_lists_old_tools_and_new_skill_tools():
    server = HybaMCPServer()
    response = server.handle_request({"id": 1, "method": "tools/list", "params": {}})
    tools = {item["name"] for item in response["result"]["tools"]}
    exact_tools = {
        "lucas",
        "fibonacci",
        "cassini",
        "zeckendorf",
        "ladder_verify",
        "ladder_capacity",
        "largest_feasible_tile",
        "sha256d_verify",
        "scale_intelligence",
    }
    assert exact_tools <= tools
    assert {
        "discover_skills",
        "get_skill",
        "invoke_skill",
        "validate_inputs",
        "evaluate_skill_outcome",
    } <= tools
    assert all(name in tools for name in TOOLS)


def test_mcp_discover_and_get_skill_contracts():
    server = HybaMCPServer()
    discovered = server.execute_tool("discover_skills", {})["skills"]
    assert len(discovered) == 6
    skill = server.execute_tool("get_skill", {"skill_id": "healing.propose_repair"})
    assert skill["source"].endswith("diagnose(failure_type, details)")
    assert skill["examples"]


def test_mcp_validate_inputs_exposes_preflight_errors():
    server = HybaMCPServer()
    result = server.execute_tool(
        "validate_inputs", {"skill_id": "proof.emergence_verify", "arguments": {}}
    )
    assert not result["valid"]
    assert result["errors"]


def test_mcp_invocation_without_identity_is_denied():
    server = HybaMCPServer()
    result = server.execute_tool(
        "invoke_skill",
        {
            "skill_id": "proof.emergence_verify",
            "arguments": {"spectral_gap": 1, "betti_1": 1, "phi_resonance": 1},
        },
    )
    assert not result["ok"]
    assert result["error"]["code"] == "permission_denied"


def test_mcp_cannot_assert_identity_in_tool_options(tmp_path):
    authorizer_calls = []
    server = HybaMCPServer(
        control_plane=ControlPlane(
            authorizer=lambda *args: authorizer_calls.append(args) or True,
            audit_path=tmp_path / "audit.jsonl",
        )
    )
    result = server.execute_tool(
        "invoke_skill",
        {
            "skill_id": "proof.emergence_verify",
            "arguments": {"spectral_gap": 1, "betti_1": 1, "phi_resonance": 1},
            "options": {"identity": "claimed-admin"},
        },
    )
    assert not result["ok"]
    assert result["error"]["code"] == "permission_denied"
    assert not authorizer_calls


def test_mcp_uses_host_supplied_trusted_identity(tmp_path):
    observed_identities = []

    def authorizer(identity, capability, arguments):
        observed_identities.append(identity)
        return _allow(identity, capability, arguments)

    server = HybaMCPServer(
        control_plane=ControlPlane(authorizer=authorizer, audit_path=tmp_path / "audit.jsonl"),
        identity_provider=lambda: "verified-host-user",
    )
    result = server.execute_tool(
        "invoke_skill",
        {
            "skill_id": "security.verify_authority",
            "arguments": {
                "identity": "subject",
                "capability": "proof.emergence_verify",
                "lease_duration": 30,
            },
            "options": {"identity": "untrusted-tool-user"},
        },
    )
    assert result["ok"]
    assert observed_identities[0] == "verified-host-user"
    assert all(
        record["identity"] == "verified-host-user"
        for record in server.control_plane.audit.records()
    )


def test_skill_tools_remain_separate_from_existing_exact_math_tools():
    assert (
        len(
            [
                name
                for name in TOOLS
                if name
                not in {
                    "discover_skills",
                    "get_skill",
                    "invoke_skill",
                    "validate_inputs",
                    "evaluate_skill_outcome",
                }
            ]
        )
        == 9
    )


def test_server_reports_skill_layer_version_two():
    assert HybaMCPServer().version == "2.0.0"
