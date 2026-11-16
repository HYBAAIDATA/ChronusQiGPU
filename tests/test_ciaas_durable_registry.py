"""Restart and custody-failure coverage for the existing CIaaSStore.

Uses a real local THESEUS/WAL database, not an external runtime deployment.
"""

import sqlite3

import pytest

from chronus.service.ciaas_store import CIaaSStore, ChronusCapacityEntitlement
from chronus.storage.durable import DurableTheseusService
from chronus.storage.theseus import StorageIntegrityError


def test_registry_replays_updates_and_removals_across_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("CHRONUS_ENV", raising=False)
    db = str(tmp_path / "ciaas-theseus.sqlite3")
    first = CIaaSStore(durable_path=db)
    assert first.list_tenants() == []  # No reference personas in durable mode.
    profile = first.onboard_tenant(
        tenant_id="tenant-persistent-a",
        organization_name="Durability Test Only",
        admin_email="example@example.invalid",
        sovereign_profile_enabled=False,
    )
    assert first.get_tenant(profile.tenant_id) is not None

    restarted = CIaaSStore(durable_path=db)
    assert restarted.get_tenant(profile.tenant_id).organization_name == (
        "Durability Test Only"
    )
    original = restarted.get_tenant(profile.tenant_id)
    updated = restarted.update_cce(
        profile.tenant_id,
        ChronusCapacityEntitlement(concurrency_limit=16),
    )
    assert updated.cce.concurrency_limit == 16
    assert original.cce.concurrency_limit != updated.cce.concurrency_limit

    recovered = CIaaSStore(durable_path=db)
    assert recovered.get_tenant(profile.tenant_id).cce.concurrency_limit == 16
    recovered.remove_tenant(profile.tenant_id)
    assert CIaaSStore(durable_path=db).get_tenant(profile.tenant_id) is None

    custody = DurableTheseusService(db)
    assert custody.verify_journal_continuity("chronus-ciaas-registry")
    assert len(custody.get_journal("chronus-ciaas-registry")) == 3


def test_registry_refuses_tampered_custody(tmp_path, monkeypatch):
    monkeypatch.delenv("CHRONUS_ENV", raising=False)
    db = str(tmp_path / "tamper.sqlite3")
    store = CIaaSStore(durable_path=db)
    store.onboard_tenant(
        tenant_id="tenant-tamper",
        organization_name="Test Only",
        admin_email="test@example.invalid",
    )
    with sqlite3.connect(db) as con:
        con.execute("UPDATE objects SET payload = X'626164' WHERE 1=1")
        con.commit()
    with pytest.raises(StorageIntegrityError):
        CIaaSStore(durable_path=db)


def test_registry_mutation_fails_before_memory_update_if_custody_unavailable(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("CHRONUS_ENV", raising=False)
    store = CIaaSStore(durable_path=str(tmp_path / "fail.sqlite3"))
    def unavailable(*args, **kwargs):
        raise RuntimeError("durable custody is unavailable")
    monkeypatch.setattr(store._custody, "append_journal_event", unavailable)
    with pytest.raises(RuntimeError, match="durable custody"):
        store.onboard_tenant(
            tenant_id="tenant-no-custody",
            organization_name="Test Only",
            admin_email="test@example.invalid",
        )
    assert store.get_tenant("tenant-no-custody") is None


def test_production_must_configure_durable_registry(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENV", "production")
    monkeypatch.delenv("CHRONUS_CIAAS_DURABLE_PATH", raising=False)
    with pytest.raises(RuntimeError, match="CHRONUS_CIAAS_DURABLE_PATH"):
        CIaaSStore()

def test_settlement_uses_exact_integer_cents_for_large_amounts():
    store = CIaaSStore(durable_path=None)  # Reference arithmetic only.
    result = store.calculate_hermiten_settlement(
        "nonexistent-reference-tenant",
        counterfactual_cost=9007199254740993,
        actual_cost=0,
        incremental_cost=0,
    )
    assert result.counterfactual_cost_usd == "9007199254740993.00"
    assert result.chronus_value_share_usd == "2251799813685248.25"
    assert result.settlement_status == "CALCULATED_UNVERIFIED"
    assert result.proof_certificate is None
    with pytest.raises(ValueError):
        store.calculate_hermiten_settlement("any", counterfactual_cost=-1)
