"""Adversarial regressions for authorized Salamander actuation (F->A).

QC contract: the canonical EUCLID->SALAMANDER healing route must compose
through ``salamander.authority.build_authorized_control_plane`` bound to an
evidence-bearing AL HARAS verdict plus an out-of-band subscription-token
provider, and must refuse before any handler invocation when authorization
is absent.  ``salamander.authority`` lands when Agent F's branch merges; the
authorized-path tests inject a test double for that module (production code
still calls the canonical constructor by name — no bypass).
"""

from __future__ import annotations

import sys
import types

import pytest

from euclid.contracts import Health
from euclid.runtime import EuclidRuntime
from salamander.control_plane import (
    ActionRegistry,
    AutonomicControlPlane,
    EvidenceLedger,
    FailClosed,
)


def _authorized_module(plane_fn):
    module = types.ModuleType("salamander.authority")
    module.build_authorized_control_plane = plane_fn
    return module


def _spy_execute(rt):
    calls = []
    original = rt.autonomic.execute

    def wrapped(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    rt.autonomic.execute = wrapped
    return calls


def _real_authorized_plane(**kwargs):
    """Test double: F's constructor shape, real plane behaviour."""
    return AutonomicControlPlane(
        registry=kwargs["registry"], ledger=kwargs["ledger"]
    )


def test_no_guardian_actuation_refused_before_handler(tmp_path):
    rt = EuclidRuntime.production(creator_id="c", state_dir=tmp_path)
    try:
        calls = _spy_execute(rt)
        with pytest.raises(FailClosed):
            rt.heal_organ("chronus", reason="degraded", actor="ops-1")
        assert calls == []
        assert "guardian" in rt._actuation_reason
        assert any(
            r.kind == "salamander-actuation-unavailable" for r in rt.evidence.records
        )
    finally:
        rt.close()


def test_guardian_without_token_provider_refused(tmp_path):
    rt = EuclidRuntime.production(
        creator_id="c", state_dir=tmp_path, guardian=object()
    )
    try:
        calls = _spy_execute(rt)
        with pytest.raises(FailClosed):
            rt.heal_organ("chronus", reason="degraded", actor="ops-1")
        assert calls == []
        assert "token provider" in rt._actuation_reason
    finally:
        rt.close()


def test_missing_actor_refused_before_handler(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "salamander.authority", _authorized_module(_real_authorized_plane)
    )
    rt = EuclidRuntime.production(
        creator_id="c",
        state_dir=tmp_path,
        guardian=object(),
        subscription_token_provider=lambda tenant, actor: "tok",
    )
    try:
        calls = _spy_execute(rt)
        for bad in (None, "", "   "):
            with pytest.raises(FailClosed):
                rt.heal_organ("chronus", reason="degraded", actor=bad)
        assert calls == []
    finally:
        rt.close()


def test_authorized_heal_executes_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "salamander.authority", _authorized_module(_real_authorized_plane)
    )
    rt = EuclidRuntime.production(
        creator_id="c",
        state_dir=tmp_path,
        guardian=object(),
        subscription_token_provider=lambda tenant, actor: "tok",
    )
    try:
        rt.registry.get("chronus").health = Health.DEGRADED
        result = rt.heal_organ("chronus", reason="injected", actor="ops-1")
        assert result.verified
        assert rt.registry.get("chronus").health is Health.HEALTHY
        assert any(
            r.kind == "heal-attempt" and r.payload.get("actor") == "ops-1"
            for r in rt.evidence.records
        )
    finally:
        rt.close()


def test_constructor_refusal_leaves_actuation_unavailable(tmp_path, monkeypatch):
    def refusing(**kwargs):
        raise PermissionError("invalid subscription credential")

    monkeypatch.setitem(
        sys.modules, "salamander.authority", _authorized_module(refusing)
    )
    rt = EuclidRuntime.production(
        creator_id="c",
        state_dir=tmp_path,
        guardian=object(),
        subscription_token_provider=lambda tenant, actor: "tok",
    )
    try:
        calls = _spy_execute(rt)
        with pytest.raises(FailClosed):
            rt.heal_organ("chronus", reason="degraded", actor="ops-1")
        assert calls == []
        assert "unavailable" in rt._actuation_reason
    finally:
        rt.close()


def test_token_never_enters_evidence_or_payload(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "salamander.authority", _authorized_module(_real_authorized_plane)
    )
    sentinel = "SENTINEL-SECRET-TOKEN-9f3a"
    captured = []

    def provider(tenant, actor):
        return sentinel

    monkeypatch.setitem(
        sys.modules,
        "salamander.authority",
        _authorized_module(_real_authorized_plane),
    )
    rt = EuclidRuntime.production(
        creator_id="c",
        state_dir=tmp_path,
        guardian=object(),
        subscription_token_provider=provider,
    )
    try:
        rt.registry.get("chronus").health = Health.DEGRADED
        rt.heal_organ("chronus", reason="injected", actor="ops-1")
        for record in rt.evidence.records:
            assert sentinel not in str(record.payload)
        for request_record in rt.autonomic.ledger.records:
            assert sentinel not in str(request_record)
    finally:
        rt.close()
