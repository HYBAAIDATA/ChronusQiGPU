"""Fail-closed claims for the local-loopback mining rehearsal API.

This test does not connect to external pools or qualify mining production.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from chronus.execution import master_e2e_engine
from chronus.service.routers import mining_admin

pytestmark = pytest.mark.simulated


def test_local_rehearsal_never_claims_pool_acceptance(monkeypatch):
    calls = []

    async def local_fixture():
        calls.append("loopback")

    monkeypatch.setattr(master_e2e_engine, "execute_master_end_to_end", local_fixture)
    result = asyncio.run(
        mining_admin.simulate_patroclus_session(
            mining_admin.SimulatePatroclusRequest(),
            tenant_id="test-tenant",
        )
    )
    assert calls == ["loopback"]
    assert result["status"] == "REHEARSAL_COMPLETED"
    assert result["evidence_class"] == "LOCAL_LOOPBACK_FIXTURE"
    assert result["transport"] == "127.0.0.1"
    assert result["live_pool_acceptance"] == "UNAVAILABLE"
    assert result["pool_acknowledgements"] == []
    assert result["production_qualified"] is False
    assert result["decision_points"] == []
    assert "external pool" in result["message"].lower()


def test_rehearsal_rejects_caller_pool_overrides(monkeypatch):
    async def must_not_run():
        raise AssertionError("untrusted pool selection reached the runner")

    monkeypatch.setattr(master_e2e_engine, "execute_master_end_to_end", must_not_run)
    for pools in ([], ["stratum+tcp://untrusted.invalid:3333"]):
        with pytest.raises(HTTPException) as caught:
            asyncio.run(
                mining_admin.simulate_patroclus_session(
                    mining_admin.SimulatePatroclusRequest(pools=pools),
                    tenant_id="test-tenant",
                )
            )
        assert caught.value.status_code == 422


def test_rehearsal_failure_is_not_promoted_and_internal_error_is_redacted(monkeypatch):
    async def fail():
        raise RuntimeError("private fixture diagnostic")

    monkeypatch.setattr(master_e2e_engine, "execute_master_end_to_end", fail)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(
            mining_admin.simulate_patroclus_session(
                mining_admin.SimulatePatroclusRequest(),
                tenant_id="test-tenant",
            )
        )
    assert caught.value.status_code == 500
    assert "private fixture diagnostic" not in caught.value.detail
    assert "no production evidence" in caught.value.detail.lower()


def test_rejected_fixture_releases_ports_for_next_rehearsal(monkeypatch):
    original_validate = master_e2e_engine.LocalStratumTestServer.validate_share

    def deny_share(self, params):
        return False

    monkeypatch.setattr(
        master_e2e_engine.LocalStratumTestServer, "validate_share", deny_share
    )
    with pytest.raises(RuntimeError, match="rejected mining.submit"):
        asyncio.run(master_e2e_engine.execute_master_end_to_end())

    # The first failed rehearsal must not leave a loopback listener bound.
    monkeypatch.setattr(
        master_e2e_engine.LocalStratumTestServer, "validate_share", original_validate
    )
    asyncio.run(master_e2e_engine.execute_master_end_to_end())
