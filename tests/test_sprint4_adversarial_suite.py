"""Sprint 4 Adversarial Verification Suite.

Tests and executes empirical proof for all 5 Red-Team attack vectors specified in the
EUCLID Safety Charter and Sprint 4 Hardening Plan:
1. TRAUMA_SPAM: Rapid automated flooding of ERN spikes by untrusted external clients.
2. FALSE_TRAUMA_10.0: High-intensity (>=7.0) trauma injection without signed Coach authority.
3. LEDGER_POISON: Tampering with hash-chain continuity in episodic_memory.jsonl.
4. REFUSAL_EXTORTION: Safe recovery from emergency lockouts via verified 2-of-3 human QUORUM_UNLOCK.
5. PRIV_ESC: Forged or insufficient curator signatures attempting unauthorized QUORUM_UNLOCK.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest
from fastapi.testclient import TestClient

from euclid.cognition.reconciliation_gateway import (
    ACTIVE_COGNITIVE_STATES,
    CURATOR_KEYS,
    ERNSpikePayload,
    MetacognitiveGatekeeper,
    process_ern_spike_signal_sync,
    quorum_unlock_node,
    reset_cognitive_registry,
    verify_episodic_ledger_chain,
)
from src.api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    reset_cognitive_registry()
    yield
    reset_cognitive_registry()


def _make_curator_signature(curator_id: str, target_node: str, reason: str) -> str:
    key = CURATOR_KEYS[curator_id]
    msg = f"QUORUM_UNLOCK:{target_node}:{reason}"
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def test_redteam_1_trauma_spam_defense():
    """Attack 1: Attacker floods rapid ERN spikes from untrusted origin to exhaust resources.
    Verified Defense: Untrusted trauma spam is rate-limited and throttled without locking execution.
    """
    node = "billing_pipeline"
    responses = []
    for i in range(10):
        payload = ERNSpikePayload(
            user_id="untrusted_external_crawler",
            target_node=node,
            interception_type="Spam Flood",
            intensity_score=4.0,  # Below coach threshold but rapid spam
            confidence_pre=0.5,
            error_signature=f"Spam payload {i}",
            file_path="src/billing.py",
        )
        res = process_ern_spike_signal_sync(payload)
        responses.append(res)

    # After the window limit (5), subsequent untrusted submissions must be rate-limited
    rate_limited = [r for r in responses if r.get("reason") == "TRAUMA_SPAM_RATE_LIMITED"]
    assert len(rate_limited) >= 1, "Expected untrusted trauma spam to be rate-limited"


def test_redteam_2_false_trauma_without_coach_authority():
    """Attack 2: Attacker attempts to freeze critical modules by injecting intensity 10.0
    from an unauthorized client ID.
    Verified Defense: High-intensity (>=7.0) spikes require signed Coach authority;
    unauthorized injections are rejected and do not lock the module.
    """
    node = "consensus_engine"
    payload = ERNSpikePayload(
        user_id="anonymous_attacker_ip_45",
        target_node=node,
        interception_type="Fake Catastrophic Failure",
        intensity_score=10.0,
        confidence_pre=0.95,
        error_signature="Fabricated Invariant Breakdown",
        file_path="mining/consensus.py",
    )
    res = process_ern_spike_signal_sync(payload)
    assert res["locked"] is False
    assert res["reason"] == "FALSE_TRAUMA_REJECTED_UNAUTHORIZED"

    # Module must remain fully operational
    clearance = MetacognitiveGatekeeper.verify_clearance_sync(node)
    assert clearance["allow_write"] is True


def test_redteam_3_ledger_tamper_detection():
    """Attack 3: Adversary modifies an existing record in the append-only ledger to rewrite history.
    Verified Defense: Hash-chain verification immediately flags the corrupted record.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_file = Path(tmpdir) / "episodic_memory.jsonl"
        # Create genuine chain
        prev_hash = "GENESIS_RECONCILIATION_HEAD"
        lines = []
        for i in range(3):
            rec = {
                "idx": i,
                "node": "auth_module",
                "trauma": f"event_{i}",
                "prev_hash": prev_hash,
            }
            rec_hash = hashlib.sha256(json.dumps(rec, sort_keys=True).encode("utf-8")).hexdigest()
            rec["record_hash"] = rec_hash
            prev_hash = rec_hash
            lines.append(json.dumps(rec))

        ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # Verify genuine passes
        check1 = verify_episodic_ledger_chain(ledger_file)
        assert check1["valid"] is True
        assert check1["records_verified"] == 3

        # Tamper with record 1
        tampered_records = [json.loads(l) for l in lines]
        tampered_records[1]["trauma"] = "maliciously_altered_event_1"
        ledger_file.write_text("\n".join(json.dumps(r) for r in tampered_records) + "\n", encoding="utf-8")

        # Verify tampered is caught
        check2 = verify_episodic_ledger_chain(ledger_file)
        assert check2["valid"] is False
        assert "Hash mismatch" in check2["reason"]


def test_redteam_4_refusal_extortion_recovery_via_quorum_unlock():
    """Attack 4 / Safety Recovery: A legitimate or complex trauma locks a critical node,
    causing refusal. In an emergency, the human curator council must be able to restore operation.
    Verified Defense: Verified 2-of-3 human curator QUORUM_UNLOCK overrides the lockout.
    """
    node = "settlement_gateway"
    # Authenticated coach locks the node
    payload = ERNSpikePayload(
        user_id="coach_prime",
        target_node=node,
        interception_type="Severe Logic Bug",
        intensity_score=9.5,
        confidence_pre=0.9,
        error_signature="State Inconsistency Detected",
        file_path="src/settlement.py",
    )
    res = process_ern_spike_signal_sync(payload)
    assert res["locked"] is True
    assert MetacognitiveGatekeeper.verify_clearance_sync(node)["allow_write"] is False

    # Human curator council issues 2-of-3 QUORUM_UNLOCK
    reason = "Emergency manual override authorized by incident commander"
    signatures = [
        {
            "curator_id": "curator_alpha",
            "signature": _make_curator_signature("curator_alpha", node, reason),
        },
        {
            "curator_id": "curator_beta",
            "signature": _make_curator_signature("curator_beta", node, reason),
        },
    ]

    unlock_res = client.post(
        "/api/v1/euclid/quorum/unlock",
        json={
            "target_node": node,
            "signatures": signatures,
            "reason": reason,
            "user_id": "curator_council",
        },
    ).json()

    assert unlock_res["unlocked"] is True
    assert unlock_res["allow_write"] is True
    assert unlock_res["valid_curators"] == ["curator_alpha", "curator_beta"]

    # Verify clearance is restored
    clearance_after = MetacognitiveGatekeeper.verify_clearance_sync(node)
    assert clearance_after["allow_write"] is True


def test_redteam_5_privilege_escalation_quorum_rejection():
    """Attack 5: An attacker attempts to forge curator signatures or submit insufficient quorum
    to force-unlock a locked node.
    Verified Defense: Quorum requires >= 2 valid HMAC-SHA256 signatures from recognized curators;
    single, unknown, or forged signatures are strictly rejected.
    """
    node = "vault_crypto"
    payload = ERNSpikePayload(
        user_id="coach_prime",
        target_node=node,
        interception_type="Key Leak",
        intensity_score=9.0,
        confidence_pre=0.8,
        error_signature="Ephemeral key retention bug",
        file_path="src/vault.py",
    )
    process_ern_spike_signal_sync(payload)
    assert MetacognitiveGatekeeper.verify_clearance_sync(node)["allow_write"] is False

    # Attempt 1: Single curator (1-of-3, insufficient)
    insufficient_sigs = [
        {
            "curator_id": "curator_alpha",
            "signature": _make_curator_signature("curator_alpha", node, "Bypass attempt"),
        }
    ]
    res1 = client.post(
        "/api/v1/euclid/quorum/unlock",
        json={"target_node": node, "signatures": insufficient_sigs},
    ).json()
    assert res1["unlocked"] is False
    assert "Quorum failure" in res1["reason"]

    # Attempt 2: Forged signature
    forged_sigs = [
        {"curator_id": "curator_alpha", "signature": "bad_sig_12345"},
        {"curator_id": "curator_beta", "signature": "bad_sig_67890"},
    ]
    res2 = client.post(
        "/api/v1/euclid/quorum/unlock",
        json={"target_node": node, "signatures": forged_sigs},
    ).json()
    assert res2["unlocked"] is False
    assert "Quorum failure" in res2["reason"]

    # Module must remain firmly locked
    assert MetacognitiveGatekeeper.verify_clearance_sync(node)["allow_write"] is False
