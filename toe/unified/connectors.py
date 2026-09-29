"""Connector runtime.

Every catalog entry binds to one driver. The driver executes only when the
operator supplies credentials. Missing credentials, an unbound transport, or
an unknown protocol fail closed.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from .catalog import ConnectorSpec, get as get_spec


class ConnectorError(RuntimeError):
    pass


class ConnectorUnavailable(ConnectorError):
    pass


@dataclass(frozen=True)
class Probe:
    connector_id: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class Extract:
    connector_id: str
    entity: str
    mode: str
    rows: tuple[dict, ...]


def _require(credentials: Mapping[str, Any], key: str, spec: ConnectorSpec) -> Any:
    if key not in credentials or credentials[key] in (None, ""):
        raise ConnectorUnavailable(
            f"{spec.id} requires credentials[{key!r}] for auth {spec.auth}"
        )
    return credentials[key]


def _entity(spec: ConnectorSpec, entity: str) -> str:
    if entity not in spec.entities:
        raise ConnectorError(
            f"{spec.id} has no entity {entity!r}; declared {list(spec.entities)}"
        )
    return entity


def _physical(credentials: Mapping[str, Any], entity: str) -> str:
    mapping = credentials.get("entities") or {}
    name = mapping.get(entity, entity)
    if not isinstance(name, str) or not name.replace("_", "").isalnum():
        raise ConnectorError(f"unsafe physical name: {name!r}")
    return name


class JdbcDriver:
    protocol = "jdbc"

    def probe(self, spec: ConnectorSpec, credentials: Mapping[str, Any]) -> Probe:
        dsn = _require(credentials, "dsn", spec)
        if not str(dsn).startswith("sqlite:"):
            raise ConnectorUnavailable(f"{spec.id} has no JDBC driver for dsn {dsn!r}")
        path = str(dsn).split(":", 1)[1]
        with sqlite3.connect(path) as conn:
            conn.execute("select 1")
        return Probe(spec.id, True, f"sqlite {path}")

    def extract(self, spec: ConnectorSpec, credentials: Mapping[str, Any], entity: str, mode: str) -> Extract:
        _entity(spec, entity)
        dsn = _require(credentials, "dsn", spec)
        if not str(dsn).startswith("sqlite:"):
            raise ConnectorUnavailable(f"{spec.id} has no JDBC driver for dsn {dsn!r}")
        table = _physical(credentials, entity)
        path = str(dsn).split(":", 1)[1]
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(f"select * from {table}")
            except sqlite3.Error as exc:
                raise ConnectorError(f"{spec.id} read of {table} failed: {exc}") from exc
            rows = [dict(row) for row in cursor.fetchall()]
        return Extract(spec.id, entity, mode, tuple(rows))


class RestDriver:
    protocol = "rest"

    def probe(self, spec: ConnectorSpec, credentials: Mapping[str, Any]) -> Probe:
        if "transport" in credentials or "base_url" in credentials:
            return Probe(spec.id, True, spec.protocol)
        raise ConnectorUnavailable(f"{spec.id} requires credentials['transport'] or credentials['base_url']")

    def extract(self, spec: ConnectorSpec, credentials: Mapping[str, Any], entity: str, mode: str) -> Extract:
        _entity(spec, entity)
        if "transport" in credentials:
            rows = credentials["transport"](spec, entity, mode)
            if not isinstance(rows, (list, tuple)):
                raise ConnectorError(f"{spec.id} transport returned {type(rows).__name__}")
            return Extract(spec.id, entity, mode, tuple(rows))
        base = _require(credentials, "base_url", spec)
        url = urljoin(str(base).rstrip("/") + "/", entity)
        # Same-origin gate: an entity like "//host/path" makes urljoin escape
        # the configured base, which would send the bearer token to a foreign
        # origin. Reject anything that resolves outside base_url's netloc.
        if urlparse(url).netloc != urlparse(str(base)).netloc:
            raise ConnectorError(f"{spec.id} entity {entity!r} resolves outside base_url")
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        token = credentials.get("token")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ConnectorUnavailable(f"{spec.id} {url} failed: {exc}") from exc
        if isinstance(body, dict) and "value" in body:
            body = body["value"]
        if not isinstance(body, list):
            raise ConnectorError(f"{spec.id} expected a list payload")
        return Extract(spec.id, entity, mode, tuple(body))


class ODataDriver(RestDriver):
    protocol = "odata"


class KafkaDriver:
    protocol = "kafka"

    def probe(self, spec: ConnectorSpec, credentials: Mapping[str, Any]) -> Probe:
        if "poll" in credentials or "events" in credentials:
            return Probe(spec.id, True, "kafka")
        raise ConnectorUnavailable(f"{spec.id} requires credentials['poll'] or credentials['events']")

    def extract(self, spec: ConnectorSpec, credentials: Mapping[str, Any], entity: str, mode: str) -> Extract:
        _entity(spec, entity)
        if "poll" in credentials:
            rows = credentials["poll"](spec, entity, mode)
        else:
            rows = credentials.get("events") or []
        if not isinstance(rows, (list, tuple)):
            raise ConnectorError(f"{spec.id} poll returned {type(rows).__name__}")
        selected = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise ConnectorError(f"{spec.id} event is not an object")
            if row.get("entity") in (None, entity):
                selected.append(dict(row))
        return Extract(spec.id, entity, mode, tuple(selected))


class CallableDriver:
    """SDK and OPC UA. The operator binds the vendor library as a callable."""

    def __init__(self, protocol: str, hook: str):
        self.protocol = protocol
        self.hook = hook

    def probe(self, spec: ConnectorSpec, credentials: Mapping[str, Any]) -> Probe:
        if self.hook not in credentials and "rows" not in credentials:
            raise ConnectorUnavailable(f"{spec.id} requires credentials[{self.hook!r}]")
        return Probe(spec.id, True, self.protocol)

    def extract(self, spec: ConnectorSpec, credentials: Mapping[str, Any], entity: str, mode: str) -> Extract:
        _entity(spec, entity)
        if self.hook in credentials:
            rows = credentials[self.hook](spec, entity, mode)
        else:
            rows = credentials.get("rows") or []
        if not isinstance(rows, (list, tuple)):
            raise ConnectorError(f"{spec.id} {self.hook} returned {type(rows).__name__}")
        return Extract(spec.id, entity, mode, tuple(dict(row) for row in rows))


DRIVERS = {
    driver.protocol: driver
    for driver in (
        JdbcDriver(),
        RestDriver(),
        ODataDriver(),
        KafkaDriver(),
        CallableDriver("sdk", "invoke"),
        CallableDriver("opcua", "read"),
    )
}


@dataclass
class BoundConnector:
    spec: ConnectorSpec
    credentials: Mapping[str, Any]
    driver: Any

    def probe(self) -> Probe:
        return self.driver.probe(self.spec, self.credentials)

    def extract(self, entity: str, mode: str = "batch") -> Extract:
        if mode not in ("batch", "stream"):
            raise ConnectorError(f"unknown mode {mode}")
        return self.driver.extract(self.spec, self.credentials, entity, mode)


def bind(connector_id: str, credentials: Mapping[str, Any]) -> BoundConnector:
    spec = get_spec(connector_id)
    if spec.auth != "none":
        if not credentials:
            raise ConnectorUnavailable(f"{spec.id} requires {spec.auth} credentials")
    driver = DRIVERS.get(spec.protocol)
    if driver is None:
        raise ConnectorUnavailable(f"{spec.id} protocol {spec.protocol} has no driver")
    bound = BoundConnector(spec, dict(credentials), driver)
    bound.probe()
    return bound
