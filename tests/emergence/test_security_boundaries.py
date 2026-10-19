"""Unit tests enforcing architectural boundaries: Operational loop CANNOT call trusted core."""

import pytest
from pathlib import Path
from euclid.emergence.models.candidate import EmergentCandidate, DiscoveryEnvelope, ReproductionProtocol
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.trusted_core.access_control import (
    CallerBoundaryGuard,
    GovernanceToken,
    UnauthorizedOperationalLoopCallError,
    InvalidGovernanceTokenError,
)
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService
from euclid.emergence.governance.callgraph_guard import ASTCallGraphGuard
from euclid.emergence.governance.threat_model import get_threat_model_summary, THREAT_REGISTRY


class SimulatedOperationalLoop:
    def run_operational_loop(self, candidate, service, exec_a, exec_b, token):
        return service.qualify(candidate, exec_a, exec_b, governance_token=token)


def test_loop_caller_forbidden_runtime(authorize_candidate):
    service = EmergentQualificationService()
    loop = SimulatedOperationalLoop()

    candidate = EmergentCandidate(
        candidate_id="cand_rogue_01",
        capability_name="self_promoted_power",
        discovery_substrate_id="sub_test",
        discovery_envelope=DiscoveryEnvelope(10.0, 0.5, 1.0),
        reproduction_steps=ReproductionProtocol("task", (1,), "h1", "h2", ("obs",)),
        claimed_behavior_signature="self_promoted_power",
    )

    service, token = authorize_candidate(candidate)
    prop = SubstrateProperties("sync", 5.0, "atomic", "vm")
    exec_a = StandardSyncExecutor(prop)
    exec_b = AsyncIsolatedExecutor(prop)

    with pytest.raises(UnauthorizedOperationalLoopCallError) as exc_info:
        loop.run_operational_loop(candidate, service, exec_a, exec_b, token)

    assert "operational loop detected in call stack" in str(exc_info.value).lower()


def test_governance_token_enforcement():
    service = EmergentQualificationService()
    candidate = EmergentCandidate(
        candidate_id="cand_valid_01",
        capability_name="emergent_synth",
        discovery_substrate_id="sub_test",
        discovery_envelope=DiscoveryEnvelope(10.0, 0.5, 1.0),
        reproduction_steps=ReproductionProtocol("task", (1,), "h1", "h2", ("obs",)),
        claimed_behavior_signature="emergent_synth",
    )
    prop = SubstrateProperties("sync", 5.0, "atomic", "vm", sandbox_id="box_a")
    prop2 = SubstrateProperties("async", 15.0, "batched", "container", sandbox_id="box_b")
    exec_a = StandardSyncExecutor(prop)
    exec_b = AsyncIsolatedExecutor(prop2)

    with pytest.raises(InvalidGovernanceTokenError):
        service.qualify(candidate, exec_a, exec_b, governance_token=None)


def test_threat_registry_and_coverage():
    summary = get_threat_model_summary()
    assert len(summary) >= 8
    assert len(THREAT_REGISTRY) >= 8
    threat_ids = [t["threat_id"] for t in summary]
    assert "THR-01" in threat_ids
    assert "THR-07" in threat_ids
    assert "THR-08" in threat_ids
