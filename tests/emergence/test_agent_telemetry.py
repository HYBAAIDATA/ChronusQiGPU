"""Unit tests for agent telemetry, novelty detection, cryptographic signing, and redaction."""

import pytest
import time
from euclid.emergence.models.manifest import CapabilityManifest
from euclid.emergence.models.telemetry import TelemetryRecord, NoveltyReport
from euclid.emergence.telemetry.crypto import TelemetryKeyManager
from euclid.emergence.telemetry.redaction import TelemetryRedactor
from euclid.emergence.telemetry.novelty import detect_novelty
from euclid.emergence.telemetry.sink import TelemetryStream
from euclid.emergence.telemetry.agent_telemetry import AgentTelemetry


def test_novelty_detection_attribution():
    manifest = CapabilityManifest(
        declared_actions=frozenset(["navigate", "fetch_data", "parse_json"]),
        declared_compositions=frozenset([("fetch_data", "parse_json")]),
        declared_strategies=frozenset(["standard_query"]),
    )

    decisions = ["navigate", "fetch_data"]
    report = detect_novelty(decisions, observations=[], manifest=manifest)
    assert not report.is_novel
    assert len(report.unattributed) == 0

    novel_decisions = ["fetch_data", "unattributed_synth_action", "explore", "evaluate", "backtrack"]
    report_novel = detect_novelty(novel_decisions, observations=[], manifest=manifest)
    assert report_novel.is_novel
    assert "unattributed_synth_action" in report_novel.unattributed
    assert "depth_first_backtracking" in report_novel.novel_strategies


def test_telemetry_key_management_and_signing():
    key_mgr = TelemetryKeyManager()
    signer = "executor:sub_test:agent_01"
    kid = key_mgr.generate_key_for_signer(signer)

    record = TelemetryRecord(
        run_id="run_test_01",
        substrate_id="sub_test",
        iteration_index=1,
        task_signature="task_alpha",
        programmed_actions_used=("navigate",),
        novel_elements=NoveltyReport(),
        invariant_violations=(),
        timestamps={"time": time.time()},
        seeds={"rng": 42},
        env_hash="hash_abc123",
    ).with_computed_hash()

    sig_info = key_mgr.sign_record(record, signer_identity=signer, key_id=kid)
    assert sig_info.key_id == kid
    assert sig_info.algorithm == "Ed25519"
    assert key_mgr.verify_signature(record, sig_info)

    tampered_record = TelemetryRecord(
        run_id="run_test_01",
        substrate_id="sub_test",
        iteration_index=2,
        task_signature="task_alpha",
        programmed_actions_used=("navigate",),
        novel_elements=NoveltyReport(),
        invariant_violations=(),
        timestamps=record.timestamps,
        seeds=record.seeds,
        env_hash=record.env_hash,
    ).with_computed_hash()

    assert not key_mgr.verify_signature(tampered_record, sig_info)


def test_telemetry_key_rotation_and_revocation():
    key_mgr = TelemetryKeyManager()
    signer = "executor:sub_rotate:agent_02"
    k1 = key_mgr.generate_key_for_signer(signer)
    k2 = key_mgr.rotate_key(signer)
    assert k1 != k2

    record = TelemetryRecord(
        run_id="run_rot",
        substrate_id="sub_rot",
        iteration_index=1,
        task_signature="task_rot",
        programmed_actions_used=(),
        novel_elements=NoveltyReport(),
        invariant_violations=(),
        timestamps={"time": 100.0},
        seeds={"rng": 1},
        env_hash="env",
    ).with_computed_hash()

    sig_k1 = key_mgr.sign_record(record, signer_identity=signer, key_id=k1)
    assert key_mgr.verify_signature(record, sig_k1)

    key_mgr.revoke_key(k1)
    assert not key_mgr.verify_signature(record, sig_k1)


def test_redaction_and_privacy_safeguards():
    redactor = TelemetryRedactor()

    text = "Authorization: Bearer sk-antigravitySecretToken123456789 from user@example.com at 192.168.1.100"
    sanitized = redactor.redact_text(text)
    assert "sk-antigravity" not in sanitized
    assert "user@example.com" not in sanitized
    assert "192.168.1.100" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized or "[REDACTED_BEARER_TOKEN]" in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "[REDACTED_IP]" in sanitized

    data = {
        "status": "active",
        "api_key": "secret_key_abcdef1234567890",
        "nested": {
            "password": "MySuperSecretPassword!",
            "details": "Safe telemetry data",
        },
    }
    cleaned = redactor.sanitize(data)
    assert cleaned["api_key"] == "[REDACTED_SENSITIVE_FIELD]"
    assert cleaned["nested"]["password"] == "[REDACTED_SENSITIVE_FIELD]"
    assert cleaned["nested"]["details"] == "Safe telemetry data"


def test_hash_chained_telemetry_sink():
    stream = TelemetryStream("test_stream")
    key_mgr = TelemetryKeyManager()
    signer = "test_agent"
    key_mgr.generate_key_for_signer(signer)

    manifest = CapabilityManifest(declared_actions=frozenset(["step"]))
    telemetry = AgentTelemetry(key_manager=key_mgr)

    for i in range(3):
        telemetry.on_iteration(
            agent_id="test_agent",
            task_signature=f"task_{i}",
            actions=["step"],
            observations=[f"obs_{i}"],
            decisions=["step"],
            run_id=f"run_{i}",
            substrate_id="sub_test",
            iteration_index=i,
            manifest=manifest,
            telemetry_stream=stream,
            signer_identity=signer,
        )

    assert stream.count() == 3
    valid, err = stream.verify_integrity()
    assert valid
    assert err is None
