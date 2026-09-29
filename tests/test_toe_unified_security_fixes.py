"""Regression pins for the unified-platform review findings (QUANTUMDATA2 PR #9)."""

from __future__ import annotations

import dataclasses
import time
import urllib.request

import pytest

from toe.unified.bi import QueryError
from toe.unified.catalog import CATALOG
from toe.unified.connectors import ConnectorError, RestDriver
from toe.unified.data_layer import UnifiedDataLayer, _matches
from toe.unified.monitor import HealthMonitor
from toe.unified.security import AccessDenied, SecurityModel


def _rest_spec(*entities: str):
    specs = CATALOG.values() if isinstance(CATALOG, dict) else CATALOG
    spec = next(s for s in specs if s.protocol == "rest")
    return dataclasses.replace(spec, entities=entities)


def test_grant_cannot_self_escalate_once_roles_exist():
    sec = SecurityModel()
    sec.enforced = True
    sec.grant("root", "admin")  # bootstrap window: empty table
    with pytest.raises(AccessDenied):
        sec.grant("mallory", "admin")  # anonymous after bootstrap
    sec.authenticate("root")
    sec.grant("eve", "reader")
    sec.authenticate("eve")
    with pytest.raises(AccessDenied):
        sec.grant("eve", "admin")
    sec.authenticate("root")
    sec.grant("bob", "analyst")


@pytest.mark.parametrize("entity", ["//evil.example/steal", "https://evil.example/steal"])
def test_rest_entity_cannot_escape_base_origin(monkeypatch, entity):
    def _no_network(*_a, **_k):
        raise AssertionError("request must not leave base_url's origin")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    spec = _rest_spec(entity)
    creds = {"base_url": "https://api.vendor.example/v1", "token": "secret"}
    with pytest.raises(ConnectorError, match="outside base_url"):
        RestDriver().extract(spec, creds, entity, "batch")


def test_monitor_loop_survives_a_raising_tick():
    calls = {"n": 0}

    def tick():
        calls["n"] += 1
        raise RuntimeError("boom")

    mon = HealthMonitor(tick, interval=0.01)
    mon.start()
    try:
        deadline = time.time() + 2.0
        while calls["n"] < 3 and time.time() < deadline:
            time.sleep(0.01)
    finally:
        mon._stop.set()
    assert calls["n"] >= 3
    assert mon.errors >= 3
    assert mon.last_error == "RuntimeError: boom"


def test_ordered_filter_with_non_numeric_bound_is_a_query_error():
    with pytest.raises(QueryError):
        _matches({"n": 3}, (("n", ">", "three"),))


def test_batch_null_rate_counts_duplicate_payloads():
    layer = UnifiedDataLayer()
    op = {"operator_digest": "d", "operator_kind": "k"}
    layer.ingest("s", "e", [{"a": 1}], **op)
    second = layer.ingest("s", "e", [{"a": 1}, {"a": None}], **op)
    assert second.duplicates == 1
    assert layer.batch_null_rate(second.batch_id) == 0.5
