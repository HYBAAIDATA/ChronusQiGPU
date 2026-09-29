from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import threading

from al_haras import (
    ALHaras,
    AuditIntegrityError,
    GuardianPolicy,
    GuardianRequest,
    HashChainAudit,
    SubscriptionAuthority,
    SubscriptionClaims,
)
from al_haras.runtime import GuardianAPI
from al_haras.settings import ALHarasSettings


KEY = b"k" * 32
NOW = 1_800_000_000


def claims(**changes):
    values = {
        "subscription_id": "sub-001",
        "tenant_id": "tenant-a",
        "issuer": "hyba-subscriptions",
        "key_id": "k1",
        "capabilities": ("hyba.security",),
        "actors": ("user-1",),
        "not_before": NOW - 10,
        "expires_at": NOW + 100,
        "max_payload_bytes": 4096,
    }
    values.update(changes)
    return SubscriptionClaims(**values)


def make_guardian():
    authority = SubscriptionAuthority({"k1": KEY}, "hyba-subscriptions")
    audit = HashChainAudit()
    guardian = ALHaras(
        authority,
        GuardianPolicy(version="test-policy", max_payload_bytes=4096),
        audit,
    )
    return guardian, authority, audit


def request(tenant_id="tenant-a"):
    return GuardianRequest(
        tenant_id=tenant_id,
        operation="security.evaluate",
        resource="container/client-data",
        payload={"sensitive": "never persisted"},
        actor="user-1",
    )


def test_valid_subscription_allows_and_audits_hash_only():
    guardian, authority, audit = make_guardian()
    verdict = guardian.evaluate(
        request(),
        subscription_token=authority.issue(claims()),
        now=NOW,
    )
    assert verdict.allowed
    assert HashChainAudit.verify(audit.records)
    assert "never persisted" not in str(audit.records)
    assert audit.records[0]["event"]["payload_hash"] == verdict.payload_hash


def test_wrong_tenant_fails_closed():
    guardian, authority, _ = make_guardian()
    verdict = guardian.evaluate(
        request("tenant-b"),
        subscription_token=authority.issue(claims()),
        now=NOW,
    )
    assert not verdict.allowed
    assert "tenant mismatch" in verdict.reason


def test_expired_subscription_fails_closed():
    guardian, authority, _ = make_guardian()
    token = authority.issue(claims(expires_at=NOW))
    assert not guardian.evaluate(request(), subscription_token=token, now=NOW).allowed


def test_tampered_audit_chain_is_detected():
    guardian, authority, audit = make_guardian()
    guardian.evaluate(request(), subscription_token=authority.issue(claims()), now=NOW)
    records = [copy.deepcopy(item) for item in audit.records]
    records[0]["event"]["allowed"] = False
    assert not HashChainAudit.verify(records)


def test_api_routes_unsubscribed_user_to_subscription():
    guardian, _, _ = make_guardian()
    settings = ALHarasSettings(
        issuer="hyba-subscriptions",
        keyring={"k1": KEY},
        audit_path=__import__("pathlib").Path("/tmp/al-haras-test.jsonl"),
    )
    api = GuardianAPI(guardian, settings)
    status, payload = api.evaluate(
        headers={"x-hyba-tenant": "tenant-a", "x-hyba-actor": "user-1"},
        body={
            "operation": "security.evaluate",
            "resource": "container/client-data",
            "payload": {},
        },
        now=NOW,
    )
    assert status == 402
    assert payload["reason"].startswith("SUBSCRIPTION_DENIED:")
    assert payload["evidence_id"]


def test_intelligence_provider_is_bound_into_evidence():
    guardian, authority, _ = make_guardian()
    settings = ALHarasSettings(
        issuer="hyba-subscriptions",
        keyring={"k1": KEY},
        audit_path=__import__("pathlib").Path("/tmp/al-haras-test.jsonl"),
    )
    api = GuardianAPI(
        guardian,
        settings,
        evidence_provider=lambda observation: {"source": "toe", "state": observation},
    )
    status, payload = api.evaluate(
        headers={
            "authorization": f"Bearer {authority.issue(claims())}",
            "x-hyba-tenant": "tenant-a",
            "x-hyba-actor": "user-1",
        },
        body={
            "operation": "security.evaluate",
            "resource": "container/client-data",
            "payload": {"value": 1},
            "observation": {"value": 1},
        },
        now=NOW,
    )
    assert status == 200
    assert payload["intelligence_evidence_hash"]


def _api_with_provider(provider, audit=None):
    authority = SubscriptionAuthority({"k1": KEY}, "hyba-subscriptions")
    guardian = ALHaras(
        authority,
        GuardianPolicy(version="test-policy", max_payload_bytes=4096),
        audit or HashChainAudit(),
    )
    settings = ALHarasSettings(
        issuer="hyba-subscriptions",
        keyring={"k1": KEY},
        audit_path=Path("/tmp/al-haras-test.jsonl"),
    )
    return GuardianAPI(guardian, settings, evidence_provider=provider), authority, guardian.audit


def _api_body():
    return {
        "operation": "security.evaluate",
        "resource": "container/client-data",
        "payload": {"value": 1},
        "observation": {"value": 1},
    }


def _api_headers(token, tenant="tenant-a", actor="user-1"):
    return {
        "authorization": f"Bearer {token}",
        "x-hyba-tenant": tenant,
        "x-hyba-actor": actor,
    }


def test_invalid_subscription_never_invokes_intelligence():
    calls = []
    api, _, audit = _api_with_provider(lambda value: calls.append(value) or value)
    status, _ = api.evaluate(
        headers=_api_headers("invalid"),
        body=_api_body(),
        now=NOW,
    )
    assert status == 403
    assert calls == []
    assert len(audit.records) == 1


def test_expired_subscription_never_invokes_intelligence():
    calls = []
    api, authority, _ = _api_with_provider(lambda value: calls.append(value) or value)
    token = authority.issue(claims(expires_at=NOW))
    status, _ = api.evaluate(
        headers=_api_headers(token),
        body=_api_body(),
        now=NOW,
    )
    assert status == 403
    assert calls == []


def test_wrong_tenant_never_invokes_intelligence():
    calls = []
    api, authority, _ = _api_with_provider(lambda value: calls.append(value) or value)
    status, _ = api.evaluate(
        headers=_api_headers(authority.issue(claims()), tenant="tenant-b"),
        body=_api_body(),
        now=NOW,
    )
    assert status == 403
    assert calls == []


def test_actor_identity_requires_entitled_identity():
    calls = []
    api, authority, audit = _api_with_provider(lambda value: calls.append(value) or value)
    status, payload = api.evaluate(
        headers=_api_headers(authority.issue(claims()), actor="ceo"),
        body=_api_body(),
        now=NOW,
    )
    assert status == 403
    assert calls == []
    assert "actor identity not entitled" in payload["reason"]
    assert audit.records[-1]["event"]["actor"] == "ceo"


def test_intelligence_failure_creates_denial_receipt():
    def fail(_):
        raise RuntimeError("offline")

    api, authority, audit = _api_with_provider(fail)
    status, payload = api.evaluate(
        headers=_api_headers(authority.issue(claims())),
        body=_api_body(),
        now=NOW,
    )
    assert status == 503
    assert payload["reason"] == "INTELLIGENCE_UNAVAILABLE:RuntimeError"
    assert payload["evidence_id"]
    assert audit.records[-1]["event"]["allowed"] is False


def test_audit_chain_resumes_after_process_restart():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "audit.jsonl"
        first = HashChainAudit(path)
        record_a = first.append({"decision": "A"})
        second = HashChainAudit(path)
        record_b = second.append({"decision": "B"})
        records = second.records
        assert len(records) == 2
        assert record_b["previous_hash"] == record_a["record_hash"]
        assert HashChainAudit.verify(records)


def test_corrupt_existing_audit_prevents_startup():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "audit.jsonl"
        audit = HashChainAudit(path)
        audit.append({"decision": "A"})
        record = json.loads(path.read_text().strip())
        record["event"]["decision"] = "CORRUPTED"
        path.write_text(json.dumps(record) + "\n")
        try:
            HashChainAudit(path)
        except AuditIntegrityError:
            pass
        else:
            raise AssertionError("corrupt audit must prevent startup")


def test_parallel_writer_cannot_fork_chain():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "audit.jsonl"
        writers = (HashChainAudit(path), HashChainAudit(path))
        barrier = threading.Barrier(2)

        def write(index):
            barrier.wait()
            for sequence in range(20):
                writers[index].append({"writer": index, "sequence": sequence})

        threads = [threading.Thread(target=write, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        records = HashChainAudit(path).records
        assert len(records) == 40
        assert HashChainAudit.verify(records)
