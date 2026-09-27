"""One bind and one fail-closed check per protocol, and one bind per class."""

import sqlite3

import pytest

from toe.unified.catalog import CATALOG, DISPLACED_CLASSES
from toe.unified.connectors import ConnectorUnavailable, bind


def _first(protocol: str):
    return next(spec for spec in CATALOG if spec.protocol == protocol)


def _credentials(spec, database):
    entity = spec.entities[0]
    if spec.protocol == "jdbc":
        with sqlite3.connect(database) as conn:
            conn.execute("create table if not exists T (id integer)")
        return {"dsn": f"sqlite:{database}", "entities": {entity: "T"}}
    if spec.protocol in ("rest", "odata"):
        return {"transport": lambda spec, entity, mode: []}
    if spec.protocol == "kafka":
        return {"events": []}
    if spec.protocol == "sdk":
        return {"invoke": lambda spec, entity, mode: []}
    if spec.protocol == "opcua":
        return {"read": lambda spec, entity, mode: []}
    raise AssertionError(spec.protocol)


@pytest.mark.parametrize("protocol", ["jdbc", "rest", "odata", "kafka", "sdk", "opcua"])
def test_each_protocol_binds(protocol, tmp_path):
    spec = _first(protocol)
    bound = bind(spec.id, _credentials(spec, tmp_path / f"{protocol}.db"))
    extracted = bound.extract(spec.entities[0])
    assert extracted.rows == ()
    assert extracted.connector_id == spec.id


@pytest.mark.parametrize("protocol", ["jdbc", "rest", "odata", "kafka", "sdk", "opcua"])
def test_each_protocol_fails_closed(protocol):
    spec = _first(protocol)
    with pytest.raises(ConnectorUnavailable):
        bind(spec.id, {})


def test_each_displaced_class_binds(tmp_path):
    seen = set()
    for spec in CATALOG:
        if spec.category in seen:
            continue
        seen.add(spec.category)
        bound = bind(spec.id, _credentials(spec, tmp_path / f"{spec.category}.db"))
        assert bound.extract(spec.entities[0]).connector_id == spec.id
    assert seen == set(DISPLACED_CLASSES)
