"""Restart reattaches external authority; checkpoints never grant authority."""
from __future__ import annotations

import time

import pytest

from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
from euclid.contracts import Health
from euclid.runtime import EuclidRuntime
from salamander.control_plane import FailClosed


def authority():
    issuer = SubscriptionAuthority({"restart-test": b"restart-fixture-key-not-production"}, "restart-tests")
    guardian = ALHaras(issuer, GuardianPolicy(
        version="restart-tests/1", allowed_operations=frozenset({
            "turing.capability-matrix", "salamander.requalify",
        }),
    ), HashChainAudit())
    now = int(time.time())
    token = issuer.issue(SubscriptionClaims(
        subscription_id="test-restart", tenant_id="tenant-test", issuer="restart-tests",
        key_id="restart-test", capabilities=("hyba.security",), actors=("test-operator",),
        not_before=now - 10, expires_at=now + 600, max_payload_bytes=65536,
    ))
    return guardian, token


def dispatch(runtime, token=None):
    return runtime.dispatch_specialist(
        "turing", {"operation": "capability-matrix"}, tenant_id="tenant-test",
        actor="test-operator", subscription_token=token,
    )


@pytest.mark.parametrize("custodied", [False, True])
def test_restored_runtime_requires_reattached_authority(tmp_path, custodied):
    from aethel.enterprise.custody import EnterpriseCustody

    guardian, token = authority()
    root = tmp_path / "runtime"
    first = EuclidRuntime.production(creator_id="tenant-test", state_dir=root,
        guardian=guardian, subscription_token_provider=lambda tenant, actor: token)
    custody = EnterpriseCustody(tmp_path / "custody", hmac_key=b"restore-custody-fixture-key-32bytes")
    try:
        assert dispatch(first, token)["allowed"] is True
        if custodied:
            checkpoint = first.save_to_custody(custody)["record_id"]
        else:
            checkpoint = tmp_path / "checkpoint.json"
            first.save(checkpoint)
            assert token not in checkpoint.read_text()
        first.close()
        def restore(**kwargs):
            if custodied:
                return EuclidRuntime.restore_from_custody(custody, checkpoint, state_dir=root, **kwargs)
            return EuclidRuntime.restore(checkpoint, state_dir=root, **kwargs)

        closed = restore()
        try:
            assert dispatch(closed, token)["allowed"] is False
            with pytest.raises(FailClosed):
                closed.heal_organ("chronus", reason="restart test", actor="test-operator")
        finally:
            closed.close()
        resumed = restore(guardian=guardian, subscription_token_provider=lambda tenant, actor: token)
        try:
            assert dispatch(resumed)["allowed"] is False
            assert dispatch(resumed, token)["allowed"] is True
            resumed.registry.get("chronus").health = Health.DEGRADED
            repair = resumed.heal_organ("chronus", reason="bounded restart requalification", actor="test-operator")
            assert repair.verified is True
            assert resumed.registry.get("chronus").health is Health.HEALTHY
            assert token not in str(resumed.snapshot())
        finally:
            resumed.close()
    finally:
        first.close()
        custody.close()
