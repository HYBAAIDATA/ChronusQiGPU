"""Unit tests for the in-process distributed systems bookkeeping module.

Covers ClusterOrchestrator, ConsensusProtocol, HealthCheckService, and
FailureInjectionEngine.
"""

import pytest

from chronus.distributed import (
    ClusterOrchestrator,
    ClusterState,
    ConsensusProtocol,
    FailureInjectionEngine,
    FailureType,
    HealthCheckResult,
    HealthCheckService,
    NodeStatus,
)


# ---------------------------------------------------------------------------
# ClusterOrchestrator
# ---------------------------------------------------------------------------


def _orchestrator(cluster_size=3):
    return ClusterOrchestrator(cluster_size=cluster_size)


def test_orchestrator_starts_initializing():
    orch = _orchestrator()
    assert orch.get_cluster_state() == ClusterState.INITIALIZING
    assert orch.get_all_nodes() == []


def test_register_node_transitions_state():
    orch = _orchestrator(cluster_size=2)
    orch.register_node("host-a", "us-east")
    assert orch.get_cluster_state() == ClusterState.DEGRADED
    orch.register_node("host-b", "eu-west")
    assert orch.get_cluster_state() == ClusterState.HEALTHY


def test_register_node_returns_unique_ids():
    orch = _orchestrator(cluster_size=10)
    ids = {orch.register_node(f"host-{i}", "us-east") for i in range(5)}
    assert len(ids) == 5


def test_assign_workload_requires_active_node():
    orch = _orchestrator()
    assert orch.assign_workload("w-0") is None


def test_assign_workload_least_loaded_node():
    orch = _orchestrator(cluster_size=2)
    n1 = orch.register_node("host-a", "us-east")
    n2 = orch.register_node("host-b", "us-east")
    first = orch.assign_workload("w-1")
    second = orch.assign_workload("w-2")
    assert first in (n1, n2)
    assert second in (n1, n2)
    assert first != second  # least-loaded scheduling balances the pair


def test_assign_workload_prefers_region():
    orch = _orchestrator(cluster_size=3)
    orch.register_node("host-a", "us-east")
    eu = orch.register_node("host-b", "eu-west")
    for i in range(4):
        assert orch.assign_workload(f"w-{i}", preferred_region="eu-west") == eu


def test_assign_workload_falls_back_when_region_missing():
    orch = _orchestrator(cluster_size=2)
    orch.register_node("host-a", "us-east")
    node = orch.assign_workload("w-1", preferred_region="ap-south")
    assert node is not None


def test_assign_workload_respects_capacity():
    orch = _orchestrator(cluster_size=2)
    orch.register_node("host-a", "us-east", capacity=1)
    n2 = orch.register_node("host-b", "us-east", capacity=1)
    assert orch.assign_workload("w-1") is not None
    assert orch.assign_workload("w-2") is not None
    assert orch.assign_workload("w-3") is None  # all nodes at capacity
    assert orch.get_node(n2).workloads_assigned == 1


def test_complete_workload_releases_capacity():
    orch = _orchestrator(cluster_size=1)
    orch.register_node("host-a", "us-east", capacity=1)
    assert orch.assign_workload("w-1") is not None
    assert orch.assign_workload("w-2") is None
    assert orch.complete_workload("w-1", result={"ok": True}) is True
    assert orch.assign_workload("w-3") is not None
    assignment = orch.get_workload_assignment("w-1")
    assert assignment.status == "COMPLETED"
    assert assignment.result == {"ok": True}


def test_fail_workload_releases_capacity():
    orch = _orchestrator(cluster_size=1)
    orch.register_node("host-a", "us-east", capacity=1)
    orch.assign_workload("w-1")
    assert orch.fail_workload("w-1") is True
    assert orch.get_workload_assignment("w-1").status == "FAILED"
    assert orch.assign_workload("w-2") is not None


def test_complete_unknown_workload_returns_false():
    orch = _orchestrator()
    assert orch.complete_workload("missing") is False
    assert orch.fail_workload("missing") is False


def test_heartbeat_updates_node_status():
    orch = _orchestrator(cluster_size=1)
    node_id = orch.register_node("host-a", "us-east")
    node = orch.get_node(node_id)
    node.status = "DRAINING"
    assert orch.heartbeat(node_id) is True
    assert orch.get_node(node_id).status == "ACTIVE"
    assert orch.heartbeat("no-such-node") is False


def test_get_stats_tracks_workload_counters():
    orch = _orchestrator(cluster_size=1)
    orch.register_node("host-a", "us-east")
    orch.assign_workload("w-1")
    orch.assign_workload("w-2")
    orch.complete_workload("w-1")
    orch.fail_workload("w-2")
    stats = orch.get_stats()
    assert stats["total_workloads"] == 2
    assert stats["completed_workloads"] == 1
    assert stats["failed_workloads"] == 1
    assert stats["active_nodes"] == 1
    assert stats["cluster_state"] == "HEALTHY"


def test_node_info_to_dict_roundtrip():
    orch = _orchestrator(cluster_size=1)
    node_id = orch.register_node("host-a", "us-east", capacity=7)
    data = orch.get_node(node_id).to_dict()
    assert data["node_id"] == node_id
    assert data["hostname"] == "host-a"
    assert data["capacity"] == 7
    assert data["last_heartbeat"] is not None


# ---------------------------------------------------------------------------
# ConsensusProtocol
# ---------------------------------------------------------------------------


def test_consensus_propose_and_approve_quorum():
    c = ConsensusProtocol(quorum_size=2)
    assert c.propose("p1", {"action": "scale"}, "node-1") is True
    assert c.is_decided("p1") is False
    assert c.vote("p1", "node-1", True) is True
    assert c.is_decided("p1") is False
    c.vote("p1", "node-2", True)
    assert c.is_decided("p1") is True
    assert c.get_proposal_result("p1") is True


def test_consensus_rejection_quorum():
    c = ConsensusProtocol(quorum_size=2)
    c.propose("p1", {"action": "scale"}, "node-1")
    c.vote("p1", "node-1", False)
    c.vote("p1", "node-2", False)
    assert c.is_decided("p1") is True
    assert c.get_proposal_result("p1") is False


def test_consensus_duplicate_proposal_rejected():
    c = ConsensusProtocol()
    assert c.propose("p1", {}, "node-1") is True
    assert c.propose("p1", {}, "node-2") is False


def test_consensus_vote_on_unknown_proposal():
    c = ConsensusProtocol()
    assert c.vote("ghost", "node-1", True) is False


def test_consensus_no_votes_after_decision():
    c = ConsensusProtocol(quorum_size=1)
    c.propose("p1", {}, "node-1")
    c.vote("p1", "node-1", True)
    assert c.is_decided("p1") is True
    assert c.vote("p1", "node-2", True) is False


def test_consensus_undecided_result_is_none():
    c = ConsensusProtocol(quorum_size=3)
    c.propose("p1", {}, "node-1")
    c.vote("p1", "node-1", True)
    assert c.get_proposal_result("p1") is None


# ---------------------------------------------------------------------------
# HealthCheckService
# ---------------------------------------------------------------------------


def _healthy(component="comp"):
    return HealthCheckResult(
        component=component, status=NodeStatus.HEALTHY, latency_ms=1.0
    )


def _failing(component="comp"):
    return HealthCheckResult(
        component=component, status=NodeStatus.UNHEALTHY, latency_ms=99.0
    )


def test_health_service_registers_and_runs_check():
    svc = HealthCheckService()
    svc.register_check("db", lambda: _healthy("db"))
    result = svc.run_check("db")
    assert result.status == NodeStatus.HEALTHY


def test_health_service_unknown_component_raises():
    svc = HealthCheckService()
    with pytest.raises(KeyError):
        svc.run_check("ghost")


def test_health_service_unhealthy_after_threshold():
    svc = HealthCheckService(unhealthy_threshold=3)
    svc.register_check("db", lambda: _failing("db"))
    svc.run_check("db")
    svc.run_check("db")
    assert svc.get_component_status("db") != NodeStatus.UNHEALTHY
    svc.run_check("db")
    assert svc.get_component_status("db") == NodeStatus.UNHEALTHY
    assert svc.get_unhealthy_components() == ["db"]
    assert svc.is_cluster_healthy() is False


def test_health_service_recovery_after_threshold():
    svc = HealthCheckService(unhealthy_threshold=2, recovery_threshold=2)
    state = {"healthy": False}
    svc.register_check(
        "db", lambda: _healthy("db") if state["healthy"] else _failing("db")
    )
    svc.run_check("db")
    svc.run_check("db")
    assert svc.get_component_status("db") == NodeStatus.UNHEALTHY
    state["healthy"] = True
    svc.run_check("db")
    svc.run_check("db")
    assert svc.get_component_status("db") == NodeStatus.HEALTHY
    assert svc.is_cluster_healthy() is True


def test_health_service_run_all_checks():
    svc = HealthCheckService()
    svc.register_check("a", lambda: _healthy("a"))
    svc.register_check("b", lambda: _healthy("b"))
    results = svc.run_all_checks()
    assert set(results) == {"a", "b"}
    # One healthy check each is below the default recovery_threshold, so
    # components remain UNKNOWN until the threshold is met.
    assert svc.is_cluster_healthy() is False
    svc.run_all_checks()
    stats = svc.get_stats()
    assert stats["registered_components"] == 2
    assert stats["total_checks"] == 4
    assert stats["cluster_healthy"] is True


def test_health_result_to_dict():
    result = HealthCheckResult(
        component="x", status=NodeStatus.DEGRADED, latency_ms=2.5, message="slow"
    )
    data = result.to_dict()
    assert data["component"] == "x"
    assert data["status"] == "DEGRADED"
    assert data["latency_ms"] == 2.5


# ---------------------------------------------------------------------------
# FailureInjectionEngine
# ---------------------------------------------------------------------------


def test_failure_injection_lifecycle():
    engine = FailureInjectionEngine(seed=42)
    fid = engine.inject_failure(FailureType.PROCESS_CRASH, "node-1", 30.0, 0.9)
    assert fid != ""
    assert engine.is_target_affected("node-1") is True
    assert engine.is_target_affected("node-2") is False
    assert len(engine.get_active_failures()) == 1
    assert engine.recover_failure(fid) is True
    assert engine.is_target_affected("node-1") is False
    assert len(engine.get_active_failures()) == 0


def test_failure_injection_disabled_engine():
    engine = FailureInjectionEngine(enabled=False)
    assert engine.inject_failure(FailureType.DISK_FAILURE, "node-1") == ""
    assert engine.get_stats()["total_injections"] == 0


def test_failure_recover_unknown_id():
    engine = FailureInjectionEngine()
    assert engine.recover_failure("no-such-failure") is False


def test_failure_history_persists_after_recovery():
    engine = FailureInjectionEngine(seed=1)
    fid = engine.inject_failure(FailureType.NETWORK_PARTITION, "node-1")
    engine.recover_failure(fid)
    history = engine.get_failure_history()
    assert len(history) == 1
    assert history[0]["failure_id"] == fid
    assert history[0]["failure_type"] == "NETWORK_PARTITION"


def test_failure_stats_report_all_types():
    engine = FailureInjectionEngine()
    stats = engine.get_stats()
    assert set(stats["failure_types"]) == {t.name for t in FailureType}
    engine.inject_failure(FailureType.POWER_LOSS, "node-9")
    engine.inject_failure(FailureType.CPU_EXHAUSTION, "node-9")
    stats = engine.get_stats()
    assert stats["total_injections"] == 2
    assert stats["active_failures"] == 2
