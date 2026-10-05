"""Executable production gates for cross-system shared data custody.

These tests exercise real subsystem implementations through the canonical
SystemDataPort adapters. A class existing is not evidence: each test performs
a real subsystem operation, observes the binding written to the one shared
THESEUS/OVID fabric, verifies it, and where meaningful reopens the lifecycle to
prove restart continuity.
"""

from __future__ import annotations

import time

import pytest

from aethel.enterprise.entangled_custody import CANONICAL_DATA_SYSTEMS
from aethel.enterprise.lifecycle import CompositionRoot
from aethel.enterprise.system_relations import (
    DEFAULT_PEERS,
    ProductionSystemRelations,
    SharedALHaras,
    SharedPythiaStore,
    SharedSalamander,
    SharedTOEBridge,
)

TEST_KEY = b"shared-system-relations-test-key-32b"


def _root(tmp_path):
    lifecycle = CompositionRoot(
        tmp_path / "shared-custody",
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    lifecycle.start()
    return lifecycle


def _bindings(lifecycle):
    return lifecycle.fabric.graph()["bindings"]


def _guardian(tmp_path):
    from al_haras.audit import HashChainAudit
    from al_haras.entitlements import SubscriptionAuthority
    from al_haras.guardian import ALHaras, GuardianPolicy

    authority = SubscriptionAuthority(
        {"k1": b"al-haras-production-organism-test-key"},
        issuer="test-issuer",
    )
    return ALHaras(
        authority,
        GuardianPolicy(version="production-organism-test-v1"),
        HashChainAudit(tmp_path / "al-haras-organism-audit.jsonl"),
    )


def test_relationship_map_covers_every_canonical_data_system():
    assert set(DEFAULT_PEERS) == set(CANONICAL_DATA_SYSTEMS)
    for owner, peers in DEFAULT_PEERS.items():
        assert owner not in peers
        assert set(peers) <= set(CANONICAL_DATA_SYSTEMS)


def test_pythia_real_store_uses_shared_custody_and_restores_from_it(tmp_path):
    from Intelligence.pythia_learning import PythiaLearning
    from Intelligence.pythia_memory import PythiaMemorySystem
    from Intelligence.pythia_store import PythiaStore

    lifecycle = _root(tmp_path)
    try:
        relations = ProductionSystemRelations(lifecycle)
        memory = PythiaMemorySystem()
        learner = PythiaLearning(n_units=32)
        raw = PythiaStore(
            memory,
            learner,
            store_dir=tmp_path / "pythia-local",
            autosave_every=1000,
        )
        shared = SharedPythiaStore(raw, relations.ports["pythia"])

        entry = shared.record_run("integration", {"verified_value": 17})
        path = shared.save()
        assert path.is_file()
        assert entry["kind"] == "integration"

        snapshots = [
            b for b in _bindings(lifecycle) if b["kind"] == "pythia_memory_snapshot"
        ]
        assert len(snapshots) == 1
        binding = snapshots[0]
        assert binding["source_system"] == "pythia"
        assert "kellogg" in binding["participants"]
        assert "toe" in binding["participants"]
        assert lifecycle.fabric.verify(binding["binding_id"])["passed"] is True

        memory2 = PythiaMemorySystem()
        learner2 = PythiaLearning(n_units=32)
        raw2 = PythiaStore(
            memory2,
            learner2,
            store_dir=tmp_path / "pythia-empty",
            autosave_every=1000,
        )
        shared2 = SharedPythiaStore(raw2, relations.ports["pythia"])
        assert shared2.load() is True
        assert raw2.journal.count() == 0
    finally:
        lifecycle.stop()


def test_toe_native_receipt_and_kellogg_tensor_enter_same_shared_graph(tmp_path):
    from toe.bridge import TOEBridge

    lifecycle = _root(tmp_path)
    try:
        relations = ProductionSystemRelations(lifecycle)
        toe = SharedTOEBridge(TOEBridge(), relations.ports["toe"])
        kellogg = relations.kellogg()

        state = kellogg.encode([1.0, 2.0, 3.0, 5.0], dim=32)
        assert state.dim == 32

        toe.raw.receipts.issue(
            "production_binding_probe",
            inputs={"values": [1, 2, 3, 5]},
            config={"owner": "toe"},
            output={"available": True},
            execution_evidence=toe.raw.execution_evidence(),
        )
        written = toe.flush_receipts()
        assert len(written) == 1

        graph = lifecycle.fabric.graph()
        systems = set(graph["systems"])
        assert {"toe", "kellogg", "pythia", "euclid"} <= systems
        for binding in written:
            assert lifecycle.fabric.verify(binding.binding_id)["passed"] is True
        assert lifecycle.fabric.verify(kellogg.last_binding.binding_id)["passed"] is True
    finally:
        lifecycle.stop()


def test_salamander_real_heal_result_is_custodied_under_salamander_authority(tmp_path):
    from Intelligence.salamander import SalamanderEngine

    lifecycle = _root(tmp_path)
    try:
        relations = ProductionSystemRelations(lifecycle)
        salamander = SharedSalamander(SalamanderEngine(), relations.ports["salamander"])
        proposal = salamander.heal("integration_probe", {"component": "test-component"})
        assert proposal is not None
        assert salamander.last_binding is not None
        binding = salamander.last_binding
        assert binding.source_system == "salamander"
        assert "al_haras" in binding.participants
        assert "euclid" in binding.participants
        assert lifecycle.fabric.verify(binding.binding_id)["passed"] is True
    finally:
        lifecycle.stop()


def test_al_haras_real_allowed_verdict_is_custodied_without_moving_authority(tmp_path):
    from al_haras.entitlements import SubscriptionClaims
    from al_haras.models import GuardianRequest

    lifecycle = _root(tmp_path)
    try:
        relations = ProductionSystemRelations(lifecycle)
        guardian = _guardian(tmp_path)
        shared = SharedALHaras(guardian, relations.ports["al_haras"])
        now = int(time.time())
        claims = SubscriptionClaims(
            subscription_id="sub-1",
            tenant_id="tenant-1",
            issuer="test-issuer",
            key_id="k1",
            capabilities=("hyba.security",),
            actors=("operator",),
            not_before=now - 1,
            expires_at=now + 300,
            jti="shared-relations-1",
        )
        token = guardian.authority.issue(claims)
        verdict = shared.evaluate(
            GuardianRequest(
                tenant_id="tenant-1",
                operation="security.evaluate",
                resource="integration",
                payload={"value": 1},
                actor="operator",
            ),
            subscription_token=token,
            now=now,
        )
        assert verdict.allowed is True
        assert shared.last_binding is not None
        assert shared.last_binding.source_system == "al_haras"
        assert lifecycle.fabric.verify(shared.last_binding.binding_id)["passed"] is True
    finally:
        lifecycle.stop()


def test_turing_real_pipeline_uses_shared_custody_not_private_theseus(tmp_path):
    from turing_universal_quantum_computer import Program
    from turing_universal_quantum_computer.pipeline import VQCRequest

    lifecycle = _root(tmp_path)
    try:
        relations = ProductionSystemRelations(lifecycle)
        turing = relations.turing()
        request = VQCRequest(
            program=Program(n_qubits=2).then("h", 0).then("cx", 0, 1),
            marginal_of=(0, 1),
            differential=True,
            custody=True,
            replay=True,
        )
        report = turing.run(request)
        assert report.verdict in {"PASS", "GATED"}
        assert {"program", "result", "witness", "report"} <= set(
            turing.last_bindings
        )

        for name, binding in turing.last_bindings.items():
            verdict = lifecycle.fabric.verify(binding.binding_id)
            assert verdict["passed"] is True, (name, verdict)
        assert turing.last_bindings["result"].parent_binding_ids == (
            turing.last_bindings["program"].binding_id,
        )
        assert turing.last_bindings["report"].source_system == "turing"
        assert "chronus" in turing.last_bindings["report"].participants
    finally:
        lifecycle.stop()


def test_binding_graph_and_cross_system_identity_survive_restart(tmp_path):
    state_dir = tmp_path / "restart-shared"
    first = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    first.start()
    try:
        relations = ProductionSystemRelations(first)
        binding = relations.ports["pythia"].put(
            "restart_probe",
            {"value": 42},
            share_with=(
                "toe",
                "kellogg",
                "euclid",
                "salamander",
                "al_haras",
                "turing",
            ),
        )
        binding_id = binding.binding_id
        expected = relations.ports["pythia"].read(binding_id)
    finally:
        first.stop()

    second = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    second.start()
    try:
        relations2 = ProductionSystemRelations(second)
        assert relations2.ports["toe"].read(binding_id) == expected
        assert relations2.ports["kellogg"].read(binding_id) == expected
        assert relations2.ports["turing"].read(binding_id) == expected
        assert second.fabric.verify(binding_id)["passed"] is True
        status = relations2.status()
        assert status["ready"] is True
        assert status["authority_preserved"] is True
    finally:
        second.stop()


def test_production_organism_is_single_startup_root_for_live_shared_systems(tmp_path):
    from aethel.enterprise.production_organism import ProductionOrganism

    organism = ProductionOrganism(
        tmp_path / "organism",
        hmac_key=TEST_KEY,
        guardian=_guardian(tmp_path),
        allow_insecure_dev_key=True,
    )
    try:
        organism.start()
        status = organism.status()
        assert status["ready"] is True
        assert status["shared_custody_ready"] is True
        assert status["authority_preserved"] is True
        assert all(status["bound_systems"].values())

        fabric = organism.lifecycle.fabric
        assert organism.intelligence.store.port.fabric is fabric
        assert organism.toe.port.fabric is fabric
        assert organism.salamander.port.fabric is fabric
        assert organism.al_haras.port.fabric is fabric
        assert organism.kellogg.port.fabric is fabric
        assert organism.turing.port.fabric is fabric
        assert organism.euclid.port.fabric is fabric

        organism.intelligence.store.record_run(
            "production_root_probe",
            {"verified": True},
        )
        organism.kellogg.encode([1.0, 1.0, 2.0, 3.0], dim=32)
        proposal = organism.salamander.heal(
            "timeout",
            {"component": "production-root-probe"},
        )
        assert proposal.applied is True

        graph = fabric.graph()
        sources = {item["source_system"] for item in graph["bindings"]}
        assert {"pythia", "kellogg", "salamander"} <= sources
        for item in graph["bindings"]:
            assert fabric.verify(item["binding_id"])["passed"] is True
    finally:
        organism.stop()


def test_production_organism_shutdown_closes_custody_when_final_snapshot_fails(
    tmp_path,
    monkeypatch,
):
    from aethel.enterprise.production_organism import ProductionOrganism

    organism = ProductionOrganism(
        tmp_path / "organism-stop-failure",
        hmac_key=TEST_KEY,
        guardian=_guardian(tmp_path),
        allow_insecure_dev_key=True,
    )
    organism.start()

    def fail_save():
        raise RuntimeError("final snapshot failed")

    monkeypatch.setattr(organism.intelligence.store, "save", fail_save)
    with pytest.raises(RuntimeError, match="final snapshot failed"):
        organism.stop()

    assert organism.lifecycle.readiness()["ready"] is False
    assert organism.status()["ready"] is False
