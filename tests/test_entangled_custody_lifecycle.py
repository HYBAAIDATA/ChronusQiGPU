from __future__ import annotations

import json

import pytest

from aethel.enterprise.custody import compose
from aethel.enterprise.entangled_custody import (
    EntangledCustodyError,
    EntanglementBinding,
)
from aethel.enterprise.lifecycle import CompositionRoot
from aethel.enterprise.persistent_entangled_custody import (
    PersistentEntangledCustodyFabric,
)
from aethel.enterprise.records import OperationalRecord


TEST_KEY = b"entangled-lifecycle-test-key-32bytes"


@pytest.fixture()
def root(tmp_path):
    lifecycle = CompositionRoot(
        tmp_path / "organism-custody",
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    try:
        yield lifecycle
    finally:
        lifecycle.stop()


def test_shared_fabric_exists_before_consumers_start(root):
    observed = {}

    def start_consumer():
        observed["fabric"] = root.fabric
        observed["custody"] = root.custody
        observed["ready"] = root.fabric is not None and root.custody is not None

    root.register_consumer("pythia", start_consumer, lambda: None)
    custody = root.start()

    assert observed["ready"] is True
    assert observed["fabric"] is root.fabric
    assert observed["custody"] is custody
    assert root.fabric.custody is custody


def test_every_port_uses_same_fabric_and_same_theseus_custody(root):
    custody = root.start()
    pythia = root.data_port("pythia")
    turing = root.data_port("turing")
    salamander = root.data_port("salamander")
    al_haras = root.data_port("al_haras")

    assert pythia.fabric is turing.fabric is salamander.fabric is al_haras.fabric
    assert pythia.fabric is root.fabric
    assert root.fabric.custody is custody

    binding = pythia.put(
        "shared_observation",
        {"source": "pythia", "value": 17},
        share_with=("turing", "salamander", "al_haras"),
    )
    assert turing.read(binding.binding_id) == pythia.read(binding.binding_id)
    assert salamander.read(binding.binding_id) == pythia.read(binding.binding_id)
    assert al_haras.read(binding.binding_id) == pythia.read(binding.binding_id)


def test_readiness_reports_shared_entangled_custody(root):
    root.start()
    status = root.readiness()

    assert status["ready"] is True
    assert status["entangled_custody"]["theseus_owner"] == "theseus"
    assert status["entangled_custody"]["ovid_owner"] == "ovid"
    assert status["entangled_custody"]["restart_recoverable"] is True
    assert status["entangled_custody"]["restart_integrity_verified"] is True
    assert status["entangled_custody"]["bindings"] == 0


def test_data_port_fails_closed_before_start(tmp_path):
    lifecycle = CompositionRoot(
        tmp_path / "not-started",
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    with pytest.raises(RuntimeError, match="not started"):
        lifecycle.data_port("pythia")


def test_stop_releases_shared_references(root):
    root.start()
    root.stop()

    assert root.fabric is None
    assert root.custody is None
    assert root.readiness() == {"ready": False, "reason": "not_started"}


def test_binding_and_parent_lineage_survive_restart(tmp_path):
    state_dir = tmp_path / "restartable-custody"
    first = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    first.start()
    try:
        pythia = first.data_port("pythia")
        kellogg = first.data_port("kellogg")
        parent = kellogg.put(
            "tensor_state",
            {"basis": "golden", "values": [1, 1, 2, 3, 5]},
            share_with=("pythia", "toe"),
            evidence_state="PASS",
        )
        child = pythia.put(
            "intelligence_result",
            {"source": "kellogg", "confidence": 0.75},
            share_with=("kellogg", "toe"),
            parents=(parent.binding_id,),
            evidence_state="MEASURED",
        )
        child_bytes = pythia.read(child.binding_id)
        parent_id = parent.binding_id
        child_id = child.binding_id
    finally:
        first.stop()

    second = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    second.start()
    try:
        status = second.readiness()["entangled_custody"]
        assert status["bindings"] == 2
        assert status["restart_recoverable"] is True
        assert status["restart_integrity_verified"] is True

        pythia2 = second.data_port("pythia")
        assert pythia2.read(child_id) == child_bytes
        assert second.fabric.verify(parent_id)["passed"] is True
        verification = second.fabric.verify(child_id)
        assert verification["passed"] is True
        assert verification["parent_lineage"] is True
    finally:
        second.stop()


def _rewrite_record(
    state_dir,
    record_id: str,
    *,
    mutate_payload=None,
    mutate_meta=None,
    mutate_lineage=None,
) -> None:
    custody = compose(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    try:
        original = custody.get_record(record_id)
        payload_bytes = original.payload
        if mutate_payload is not None:
            payload = json.loads(original.payload.decode("utf-8"))
            mutate_payload(payload)
            payload_bytes = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")

        meta = dict(original.meta)
        if mutate_meta is not None:
            mutate_meta(meta)

        lineage = tuple(original.lineage)
        if mutate_lineage is not None:
            lineage = tuple(mutate_lineage(lineage))

        replacement = OperationalRecord(
            record_id=original.record_id,
            producer=original.producer,
            producer_version=original.producer_version,
            schema_version=original.schema_version,
            kind=original.kind,
            payload=payload_bytes,
            evidence_state=original.evidence_state,
            sequence=original.sequence + 1,
            epoch=original.epoch,
            lineage=lineage,
            correlation_ids=original.correlation_ids,
            dependencies=original.dependencies,
            meta=meta,
        )
        # This is a valid, freshly authenticated THESEUS write. Restart must
        # still reject it when the relationship semantics are false.
        custody.put_record(replacement)
    finally:
        custody.close()


def test_restart_rejects_validly_serialized_participant_identity_corruption(tmp_path):
    state_dir = tmp_path / "participant-corruption"
    first = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    first.start()
    try:
        binding = first.data_port("pythia").put(
            "shared_observation",
            {"value": 23},
            share_with=("toe",),
        )
        index_id = f"entangled-binding-{binding.binding_id}"
    finally:
        first.stop()

    _rewrite_record(
        state_dir,
        index_id,
        mutate_payload=lambda payload: payload.__setitem__("participants", ["pythia"]),
    )

    consumer_started = {"value": False}
    second = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    second.register_consumer(
        "pythia",
        lambda: consumer_started.__setitem__("value", True),
        lambda: None,
    )
    try:
        with pytest.raises(EntangledCustodyError, match="participant identity mismatch"):
            second.start()
        assert consumer_started["value"] is False
    finally:
        second.stop()


def test_restart_rejects_validly_serialized_content_digest_corruption(tmp_path):
    state_dir = tmp_path / "digest-corruption"
    first = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    first.start()
    try:
        binding = first.data_port("salamander").put(
            "healing_evidence",
            {"action": "requalify", "verified": True},
            share_with=("pythia", "al_haras"),
        )
        index_id = f"entangled-binding-{binding.binding_id}"
    finally:
        first.stop()

    _rewrite_record(
        state_dir,
        index_id,
        mutate_payload=lambda payload: payload.__setitem__("content_sha256", "0" * 64),
    )

    second = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    try:
        with pytest.raises(EntangledCustodyError, match="structural verification"):
            second.start()
    finally:
        second.stop()


def test_restart_rejects_authenticated_parent_edge_removal(tmp_path):
    state_dir = tmp_path / "parent-removal"
    first = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    first.start()
    try:
        parent = first.data_port("kellogg").put(
            "tensor_state",
            {"value": 3},
            share_with=("pythia",),
        )
        child = first.data_port("pythia").put(
            "derived_state",
            {"value": 5},
            share_with=("kellogg",),
            parents=(parent.binding_id,),
        )
        index_id = f"entangled-binding-{child.binding_id}"
    finally:
        first.stop()

    # Rewrite the index consistently with an empty parent declaration. The
    # underlying child/OVID records still retain the real parent and must win.
    _rewrite_record(
        state_dir,
        index_id,
        mutate_payload=lambda payload: payload.__setitem__("parent_binding_ids", []),
        mutate_lineage=lambda lineage: lineage[:2],
    )

    second = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    try:
        with pytest.raises(EntangledCustodyError, match="parent custody lineage mismatch"):
            second.start()
    finally:
        second.stop()


def test_restart_rejects_authenticated_source_rewrite_against_real_producer(tmp_path):
    state_dir = tmp_path / "source-rewrite"
    first = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    first.start()
    try:
        binding = first.data_port("pythia").put(
            "shared_observation",
            {"value": 29},
            share_with=("toe",),
        )
        index_id = f"entangled-binding-{binding.binding_id}"
        shared_id = binding.custody_record_id
        lineage_id = binding.ovid_lineage_record_id
    finally:
        first.stop()

    participants = ["euclid", "toe"]
    _rewrite_record(
        state_dir,
        index_id,
        mutate_payload=lambda payload: (
            payload.__setitem__("source_system", "euclid"),
            payload.__setitem__("participants", participants),
        ),
        mutate_meta=lambda meta: (
            meta.__setitem__("source_system", "euclid"),
            meta.__setitem__("participants", participants),
        ),
    )
    _rewrite_record(
        state_dir,
        shared_id,
        mutate_meta=lambda meta: (
            meta.__setitem__("source_system", "euclid"),
            meta.__setitem__("participants", participants),
        ),
    )
    _rewrite_record(
        state_dir,
        lineage_id,
        mutate_meta=lambda meta: (
            meta.__setitem__("source_system", "euclid"),
            meta.__setitem__("participants", participants),
        ),
    )

    second = CompositionRoot(
        state_dir,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    try:
        with pytest.raises(EntangledCustodyError, match="producer/source identity mismatch"):
            second.start()
    finally:
        second.stop()


def test_parent_graph_validation_handles_deep_valid_lineage_without_recursion():
    bindings: dict[str, EntanglementBinding] = {}
    previous: str | None = None
    for index in range(1500):
        binding_id = f"binding-{index}"
        bindings[binding_id] = EntanglementBinding(
            binding_id=binding_id,
            source_system="pythia",
            participants=("pythia",),
            kind="test",
            custody_record_id=f"record-{index}",
            ovid_lineage_record_id=f"lineage-record-{index}",
            ovid_lineage_id=f"lineage-{index}",
            content_sha256="0" * 64,
            parent_binding_ids=() if previous is None else (previous,),
            created_at=0.0,
        )
        previous = binding_id

    PersistentEntangledCustodyFabric._validate_parent_graph(bindings)


def test_parent_graph_validation_still_rejects_cycles():
    bindings = {
        "a": EntanglementBinding(
            binding_id="a",
            source_system="pythia",
            participants=("pythia",),
            kind="test",
            custody_record_id="record-a",
            ovid_lineage_record_id="lineage-record-a",
            ovid_lineage_id="lineage-a",
            content_sha256="0" * 64,
            parent_binding_ids=("b",),
            created_at=0.0,
        ),
        "b": EntanglementBinding(
            binding_id="b",
            source_system="pythia",
            participants=("pythia",),
            kind="test",
            custody_record_id="record-b",
            ovid_lineage_record_id="lineage-record-b",
            ovid_lineage_id="lineage-b",
            content_sha256="0" * 64,
            parent_binding_ids=("a",),
            created_at=0.0,
        ),
    }
    with pytest.raises(EntangledCustodyError, match="cycle"):
        PersistentEntangledCustodyFabric._validate_parent_graph(bindings)
