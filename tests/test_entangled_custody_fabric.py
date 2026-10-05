from __future__ import annotations

import json

import pytest

from aethel.enterprise import compose
from aethel.enterprise.entangled_custody import (
    CANONICAL_DATA_SYSTEMS,
    EntangledAccessError,
    EntangledCustodyFabric,
)


@pytest.fixture()
def fabric(tmp_path):
    custody = compose(
        tmp_path / "shared-custody",
        hmac_key=b"entangled-custody-test-key-32bytes",
        allow_insecure_dev_key=True,
    )
    try:
        yield EntangledCustodyFabric(custody)
    finally:
        custody.close()


def test_all_declared_memory_data_systems_share_one_theseus_record(fabric):
    participants = sorted(CANONICAL_DATA_SYSTEMS)
    binding = fabric.put(
        "pythia",
        "intelligence_observation",
        {"job": "real-job", "confidence": 0.625, "state": "observed"},
        participants=participants,
        evidence_state="MEASURED",
    )

    # Entanglement is shared identity, not N copied private records.
    record_ids = set()
    payloads = set()
    for system in participants:
        record = fabric.record(binding.binding_id, consumer=system)
        record_ids.add(record.record_id)
        payloads.add(record.payload)

    assert record_ids == {binding.custody_record_id}
    assert len(payloads) == 1
    assert fabric.verify(binding.binding_id)["passed"] is True


def test_nonparticipant_cannot_consume_shared_binding(fabric):
    binding = fabric.put(
        "pythia",
        "private_learning_event",
        {"reward": 0.2},
        participants=("pythia", "toe"),
    )
    with pytest.raises(EntangledAccessError):
        fabric.read(binding.binding_id, consumer="turing")


def test_derived_data_binds_parent_theseus_and_ovid_lineage(fabric):
    parent = fabric.put(
        "kellogg",
        "tensor_state",
        {"coefficients": [1, 0, 1], "field": "Z[phi]"},
        participants=("kellogg", "pythia", "toe"),
        evidence_state="PASS",
    )
    child = fabric.put(
        "toe",
        "causal_result",
        {"available": True, "source": "kellogg"},
        participants=("toe", "pythia", "kellogg"),
        parents=(parent.binding_id,),
        evidence_state="MEASURED",
    )

    child_record = fabric.record(child.binding_id, consumer="pythia")
    lineage_record = fabric.custody.get_record(child.ovid_lineage_record_id)
    lineage = json.loads(lineage_record.payload.decode("utf-8"))

    assert parent.custody_record_id in child_record.lineage
    assert parent.ovid_lineage_id in lineage["parent_ids"]
    assert fabric.verify(child.binding_id) == {
        "schema": "aethel.entangled-custody.verify/1",
        "binding_id": child.binding_id,
        "passed": True,
        "payload_digest": True,
        "shared_identity": True,
        "ovid_lineage": True,
        "parent_lineage": True,
        "participants": list(child.participants),
        "custody_record_id": child.custody_record_id,
        "ovid_lineage_record_id": child.ovid_lineage_record_id,
    }


def test_kellogg_identity_is_preserved_while_existing_tensor_contract_is_honoured(fabric):
    binding = fabric.put(
        "kellogg",
        "exact_tensor_evidence",
        b"kellogg-evidence",
        participants=("kellogg", "pythia"),
        evidence_state="PASS",
    )
    record = fabric.record(binding.binding_id, consumer="kellogg")

    # Existing THESEUS producer registry still spells this producer "tensor".
    # The architectural identity is not lost: Kellogg is explicit in metadata.
    assert record.producer == "tensor"
    assert record.meta["source_system"] == "kellogg"
    assert set(record.meta["participants"]) == {"kellogg", "pythia"}


def test_system_ports_share_parent_lineage_without_copying(fabric):
    salamander = fabric.port("salamander")
    al_haras = fabric.port("al_haras")
    turing = fabric.port("turing")

    health = salamander.put(
        "health_decision",
        {"status": "DEGRADED", "reason": "lane fault"},
        share_with=("al_haras", "turing"),
    )
    governance = al_haras.put(
        "governance_decision",
        {"allowed": True, "reason": "bounded recovery"},
        share_with=("salamander", "turing"),
        parents=(health.binding_id,),
    )

    assert turing.read(health.binding_id) == salamander.read(health.binding_id)
    assert turing.read(governance.binding_id) == al_haras.read(governance.binding_id)
    assert fabric.verify(governance.binding_id)["parent_lineage"] is True


def test_sink_is_a_real_shared_custody_writer(fabric):
    seen_before = fabric.status()["bindings"]
    sink = fabric.port("salamander").sink(
        "autonomic_evidence",
        share_with=("pythia", "al_haras"),
        evidence_state="PASS",
    )
    sink({"action": "requalify", "verified": True})

    assert fabric.status()["bindings"] == seen_before + 1
    graph = fabric.graph()
    assert {"al_haras", "pythia", "salamander"} <= set(graph["systems"])
    assert any(
        {edge["left"], edge["right"]} == {"pythia", "salamander"}
        for edge in graph["edges"]
    )
