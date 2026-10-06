"""Production evidence gates for the canonical KELLOGG boundary."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from aethel.enterprise.lifecycle import CompositionRoot
from aethel.enterprise.system_relations import (
    ProductionSystemRelations,
    verify_kellogg_custody_boundary,
)
from kellogg.attest import AttestationError, attest, verify_attestation


TEST_KEY = b"kellogg-production-boundary-test-key"


def _root(path):
    root = CompositionRoot(
        path,
        hmac_key=TEST_KEY,
        allow_insecure_dev_key=True,
    )
    root.start()
    return root


def _read_json(port, binding):
    return json.loads(port.read(binding.binding_id).decode("utf-8"))


def test_attestation_replay_binds_computation_and_boundary_metadata():
    payload = {
        "schema": "kellogg.test-computation/v1",
        "steps": [{"operation": "encode"}, {"operation": "measure"}],
        "value": 17,
    }
    evidence = attest(
        payload,
        float_boundaries=("diagnostic display",),
        notes=("test evidence",),
    )
    assert evidence["schema"] == "kellogg.attestation/v1"
    assert len(evidence["attestation_digest"]) == 64
    assert verify_attestation(payload, evidence) is True

    tampered_payload = dict(payload)
    tampered_payload["value"] = 18
    with pytest.raises(AttestationError, match="digest"):
        verify_attestation(tampered_payload, evidence)

    forged_boundary = deepcopy(evidence)
    forged_boundary["boundary"]["float_boundaries"].append("undeclared crossing")
    with pytest.raises(AttestationError, match="envelope"):
        verify_attestation(payload, forged_boundary)

    overclaim = deepcopy(evidence)
    overclaim["boundary"]["theorem_proven"] = True
    with pytest.raises(AttestationError, match="theorem_proven"):
        verify_attestation(payload, overclaim)


def test_shared_kellogg_diagnostic_state_is_attested_and_semantically_replayed(tmp_path):
    lifecycle = _root(tmp_path / "diagnostic")
    try:
        kellogg = ProductionSystemRelations(lifecycle).kellogg()
        state = kellogg.encode([1.0, 2.0, 3.0, 5.0], dim=32)

        assert state.dim == 32
        assert set(kellogg.last_bindings) == {"input", "state", "attestation"}
        state_payload = _read_json(kellogg.port, kellogg.last_bindings["state"])
        evidence = _read_json(kellogg.port, kellogg.last_bindings["attestation"])

        assert state_payload["plane"] == "diagnostic"
        assert state_payload["exact"] is False
        assert state_payload["field"] == "IEEE-754 complex"
        assert evidence["boundary"]["float_boundaries"] == [
            "kellogg.quantum_tensor.encode_data_to_state"
        ]
        assert verify_attestation(state_payload, evidence) is True

        replay = kellogg.replay_latest()
        assert replay["passed"] is True
        assert replay["checks"]["float_boundary_declared"] is True
        assert replay["checks"]["normalization"] is True
        assert all(replay["custody"].values())
    finally:
        lifecycle.stop()


def test_shared_kellogg_exact_state_preserves_f4_without_float_roundtrip(tmp_path):
    lifecycle = _root(tmp_path / "exact")
    try:
        kellogg = ProductionSystemRelations(lifecycle).kellogg()
        state = kellogg.encode_exact({"job": "exact-proof"}, num_qubits=3)

        assert state.num_qubits == 3
        state_payload = _read_json(kellogg.port, kellogg.last_bindings["state"])
        evidence = _read_json(kellogg.port, kellogg.last_bindings["attestation"])

        assert state_payload["plane"] == "exact"
        assert state_payload["exact"] is True
        assert state_payload["field"] == "Q(sqrt(2)) + iQ(sqrt(2))"
        assert state_payload["amplitude_count"] == 8
        assert evidence["boundary"]["float_boundaries"] == []

        # Every exact F4 amplitude is four rational [numerator, denominator]
        # channels. No IEEE-754 projection is stored in the exact artefact.
        assert all(
            len(amplitude) == 4
            and all(
                isinstance(fraction, list)
                and len(fraction) == 2
                and all(isinstance(part, int) for part in fraction)
                for fraction in amplitude
            )
            for amplitude in state_payload["amplitudes"]
        )

        replay = kellogg.replay_latest()
        assert replay["passed"] is True
        assert replay["checks"]["exact_amplitudes_reconstruct"] is True
        assert replay["checks"]["state_commitment"] is True
        assert replay["checks"]["no_float_boundary_on_exact_plane"] is True
    finally:
        lifecycle.stop()


def test_kellogg_semantic_replay_rejects_individually_valid_foreign_attestation(tmp_path):
    lifecycle = _root(tmp_path / "cross-bind")
    try:
        kellogg = ProductionSystemRelations(lifecycle).kellogg()

        kellogg.encode_exact({"job": "first"}, num_qubits=3)
        first_input = _read_json(kellogg.port, kellogg.last_bindings["input"])
        first_state = _read_json(kellogg.port, kellogg.last_bindings["state"])

        kellogg.encode_exact({"job": "second"}, num_qubits=3)
        second_attestation = _read_json(
            kellogg.port,
            kellogg.last_bindings["attestation"],
        )

        report = verify_kellogg_custody_boundary(
            input_payload=first_input,
            state_payload=first_state,
            attestation_payload=second_attestation,
        )
        assert report["passed"] is False
        assert report["checks"]["attestation_verifies"] is False
    finally:
        lifecycle.stop()


def test_kellogg_exact_custody_semantics_survive_restart(tmp_path):
    state_dir = tmp_path / "restart"

    first = _root(state_dir)
    try:
        kellogg = ProductionSystemRelations(first).kellogg()
        kellogg.encode_exact({"restart": True}, num_qubits=3)
        first_report = kellogg.replay_latest()
        assert first_report["passed"] is True
    finally:
        first.stop()

    second = _root(state_dir)
    try:
        kellogg = ProductionSystemRelations(second).kellogg()
        replay = kellogg.replay_latest()
        assert replay["passed"] is True
        assert replay["plane"] == "exact"
        assert replay["checks"]["state_commitment"] is True
        assert all(replay["custody"].values())
    finally:
        second.stop()
