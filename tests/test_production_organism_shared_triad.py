from __future__ import annotations

import time

from aethel.enterprise.production_organism import ProductionOrganism

TEST_KEY = b"production-organism-shared-triad-key"


def _guardian(tmp_path):
    from al_haras.audit import HashChainAudit
    from al_haras.entitlements import SubscriptionAuthority
    from al_haras.guardian import (
        DEFAULT_ALLOWED_OPERATIONS,
        ALHaras,
        GuardianPolicy,
    )

    authority = SubscriptionAuthority(
        {"k1": b"production-organism-guardian-key-32b"},
        issuer="production-test-issuer",
    )
    policy = GuardianPolicy(
        version="production-organism-shared-triad-v1",
        allowed_operations=DEFAULT_ALLOWED_OPERATIONS
        | frozenset({"triad.put", "triad.get", "triad.fold", "triad.verify"}),
    )
    return ALHaras(
        authority,
        policy,
        HashChainAudit(tmp_path / "al-haras-shared-triad.jsonl"),
    )


def _token(guardian, now: int) -> str:
    from al_haras.entitlements import SubscriptionClaims

    claims = SubscriptionClaims(
        subscription_id="production-organism-sub",
        tenant_id="production-tenant",
        issuer="production-test-issuer",
        key_id="k1",
        capabilities=("hyba.security",),
        actors=("operator",),
        not_before=now - 1,
        expires_at=now + 300,
        jti="production-organism-shared-triad-token",
    )
    return guardian.authority.issue(claims)


def test_governed_euclid_triad_uses_same_shared_theseus_ovid_fabric(tmp_path):
    guardian = _guardian(tmp_path)
    organism = ProductionOrganism(
        tmp_path / "organism",
        hmac_key=TEST_KEY,
        guardian=guardian,
        allow_insecure_dev_key=True,
    )
    try:
        organism.start()
        status = organism.status()
        assert status["ready"] is True
        assert status["euclid_private_triad_opened"] is False
        assert status["bound_systems"]["theseus_ovid"] is True

        now = int(time.time())
        result = organism.euclid.dispatch_specialist(
            "triad",
            {"operation": "put", "payload_utf8": "shared-custody-proof"},
            tenant_id="production-tenant",
            actor="operator",
            subscription_token=_token(guardian, now),
        )
        assert result["allowed"] is True
        assert result["result"]["owner"] == "THESEUS"
        binding_id = result["result"]["binding_id"]

        fabric = organism.lifecycle.fabric
        verdict = fabric.verify(binding_id)
        assert verdict["passed"] is True
        binding = next(
            item for item in fabric.graph()["bindings"] if item["binding_id"] == binding_id
        )
        assert binding["source_system"] == "euclid"
        assert "pythia" in binding["participants"]
        assert "turing" in binding["participants"]
        assert "kellogg" in binding["participants"]

        # AL HARAS made the governed admission decision and its own verdict is
        # also retained on the same shared fabric under AL HARAS authority.
        assert any(
            item["source_system"] == "al_haras"
            and item["kind"] == "al_haras_evaluate"
            for item in fabric.graph()["bindings"]
        )
    finally:
        organism.stop()
