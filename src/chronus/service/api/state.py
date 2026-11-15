"""Process-shared API state.

SQLite is the default for local or single-node deployments and coordinates
multiple workers through immediate transactions. Tests may select the explicit
memory backend with ``CHRONUS_API_STATE_BACKEND=memory``. PostgreSQL remains the
horizontal scaling path; this module makes no distributed-SQLite claim.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_TABLES = ("workloads", "nodes", "receipts")
_RECORD_SQL = {
    "workloads": {
        "read": "SELECT record_json FROM api_workloads WHERE record_id = ?",
        "all": "SELECT record_json FROM api_workloads",
        "write": (
            "INSERT INTO api_workloads "
            "(record_id, tenant_id, state, created_at, record_json) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(record_id) DO UPDATE SET "
            "tenant_id=excluded.tenant_id, state=excluded.state, "
            "created_at=excluded.created_at, record_json=excluded.record_json"
        ),
        "clear": "DELETE FROM api_workloads",
    },
    "nodes": {
        "read": "SELECT record_json FROM api_nodes WHERE record_id = ?",
        "all": "SELECT record_json FROM api_nodes",
        "write": (
            "INSERT INTO api_nodes "
            "(record_id, tenant_id, state, created_at, record_json) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(record_id) DO UPDATE SET "
            "tenant_id=excluded.tenant_id, state=excluded.state, "
            "created_at=excluded.created_at, record_json=excluded.record_json"
        ),
        "clear": "DELETE FROM api_nodes",
    },
    "receipts": {
        "read": "SELECT record_json FROM api_receipts WHERE record_id = ?",
        "all": "SELECT record_json FROM api_receipts",
        "write": (
            "INSERT INTO api_receipts "
            "(record_id, tenant_id, state, created_at, record_json) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(record_id) DO UPDATE SET "
            "tenant_id=excluded.tenant_id, state=excluded.state, "
            "created_at=excluded.created_at, record_json=excluded.record_json"
        ),
        "clear": "DELETE FROM api_receipts",
    },
}
_BACKENDS = frozenset({"memory", "sqlite"})
_MEMORY: dict[str, dict] = {
    "workloads": {},
    "nodes": {},
    "receipts": {},
    "idempotency": {},
}
_RATE_HITS: dict[str, list[float]] = {}
_MEMORY_LOCK = threading.RLock()
# Schema setup is a first-use operation, never part of concurrent requests.
_SCHEMA_LOCK = threading.Lock()
# Guard against a live file replacement at an already-initialised path.
_INITIALIZED_DB: dict[str, tuple[int, int]] = {}
_SCHEMA_OBJECTS = frozenset(
    {f"api_{name}" for name in _TABLES}
    | {f"api_{name}_tenant_created" for name in _TABLES}
    | {"api_idempotency", "api_idempotency_expires", "api_rate_limits"}
)
_RECORD_LAYOUT = (
    ("record_id", "TEXT", 0, 1),
    ("tenant_id", "TEXT", 0, 0),
    ("state", "TEXT", 0, 0),
    ("created_at", "TEXT", 0, 0),
    ("record_json", "TEXT", 1, 0),
)
_SCHEMA_LAYOUTS = {
    "PRAGMA table_info(api_workloads)": _RECORD_LAYOUT,
    "PRAGMA table_info(api_nodes)": _RECORD_LAYOUT,
    "PRAGMA table_info(api_receipts)": _RECORD_LAYOUT,
    "PRAGMA table_info(api_idempotency)": (
        ("tenant_id", "TEXT", 1, 1),
        ("key", "TEXT", 1, 2),
        ("body_hash", "TEXT", 1, 0),
        ("status", "INTEGER", 1, 0),
        ("body_json", "TEXT", 1, 0),
        ("headers_json", "TEXT", 1, 0),
        ("expires", "REAL", 1, 0),
    ),
    "PRAGMA table_info(api_rate_limits)": (
        ("key", "TEXT", 0, 1),
        ("window_start", "INTEGER", 1, 0),
        ("count", "INTEGER", 1, 0),
    ),
}
_SCHEMA_INDEXES = {
    "PRAGMA index_info(api_workloads_tenant_created)": (
        "tenant_id", "created_at", "record_id"
    ),
    "PRAGMA index_info(api_nodes_tenant_created)": (
        "tenant_id", "created_at", "record_id"
    ),
    "PRAGMA index_info(api_receipts_tenant_created)": (
        "tenant_id", "created_at", "record_id"
    ),
    "PRAGMA index_info(api_idempotency_expires)": ("expires",),
}


def _schema_valid(conn: sqlite3.Connection) -> bool:
    """Validate the exact API schema, not just the names of its objects."""
    objects = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        )
    }
    if not _SCHEMA_OBJECTS.issubset(objects):
        return False
    for pragma, expected in _SCHEMA_LAYOUTS.items():
        actual = tuple(
            (row[1], row[2].upper(), row[3], row[5])
            for row in conn.execute(pragma)
        )
        if actual != expected:
            return False
    for pragma, expected in _SCHEMA_INDEXES.items():
        actual = tuple(row[2] for row in conn.execute(pragma))
        if actual != expected:
            return False
    return True


def backend() -> str:
    value = os.getenv("CHRONUS_API_STATE_BACKEND", "sqlite").strip().lower()
    if value not in _BACKENDS:
        raise RuntimeError(
            "CHRONUS_API_STATE_BACKEND must be one of: "
            + ", ".join(sorted(_BACKENDS))
        )
    return value


def is_sqlite() -> bool:
    return backend() == "sqlite"


def database_path() -> str:
    return os.getenv("CHRONUS_API_DB_PATH", "data/chronus-api.sqlite3")


def _connect() -> sqlite3.Connection:
    path = database_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # Detect an unexpected replacement while SQLite is opening the file.
    # Path identity alone cannot substitute for independent durable custody.
    try:
        before_stat = os.stat(path)
        before_identity = (before_stat.st_dev, before_stat.st_ino)
    except FileNotFoundError:
        before_identity = None
    connection = sqlite3.connect(path, timeout=30.0, isolation_level=None)
    try:
        # Set timeout before any schema / journal negotiation.
        connection.execute("PRAGMA busy_timeout=30000")
        with _SCHEMA_LOCK:
            metadata = os.stat(path)
            identity = (metadata.st_dev, metadata.st_ino)
            if before_identity is not None and identity != before_identity:
                raise RuntimeError(
                    "SQLite database changed while opening; recovery verification required"
                )
            prior_identity = _INITIALIZED_DB.get(path)
            if prior_identity is not None and prior_identity != identity:
                raise RuntimeError(
                    "SQLite database replaced at an initialized path; "
                    "recovery verification required before serving requests"
                )
            if prior_identity is None:
                # Restarting a process must not recreate tables in an existing
                # incomplete database. Only a newly created file is bootstrapped.
                if before_identity is not None and not _schema_valid(connection):
                    raise RuntimeError(
                        "SQLite schema missing or invalid in existing database; "
                        "recovery verification required before serving requests"
                    )
                mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                if mode.lower() != "wal":
                    connection.execute("PRAGMA journal_mode=WAL")
                if before_identity is None:
                for table in _TABLES:
                    connection.execute(
                        f"CREATE TABLE IF NOT EXISTS api_{table} ("
                        "record_id TEXT PRIMARY KEY, tenant_id TEXT, state TEXT, "
                        "created_at TEXT, record_json TEXT NOT NULL)"
                    )
                    connection.execute(
                        f"CREATE INDEX IF NOT EXISTS api_{table}_tenant_created "
                        f"ON api_{table} (tenant_id, created_at, record_id)"
                    )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS api_idempotency ("
                    "tenant_id TEXT NOT NULL, key TEXT NOT NULL, body_hash TEXT NOT NULL, "
                    "status INTEGER NOT NULL, body_json TEXT NOT NULL, headers_json TEXT NOT NULL, "
                    "expires REAL NOT NULL, PRIMARY KEY (tenant_id, key))"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS api_idempotency_expires "
                    "ON api_idempotency (expires)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS api_rate_limits ("
                    "key TEXT PRIMARY KEY, window_start INTEGER NOT NULL, count INTEGER NOT NULL)"
                )
                if not _schema_valid(connection):
                    raise RuntimeError(
                        "SQLite schema invalid after initialization; "
                        "recovery verification required before serving requests"
                    )
                _INITIALIZED_DB[path] = identity
            else:
                if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                    raise RuntimeError("SQLite journal mode changed; recovery verification required")
                if not _schema_valid(connection):
                    raise RuntimeError(
                        "SQLite schema changed after initialization; "
                        "recovery verification required before serving requests"
                    )
            after_stat = os.stat(path)
            if identity != (after_stat.st_dev, after_stat.st_ino):
                raise RuntimeError(
                    "SQLite database replaced during initialization; recovery verification required"
                )
        return connection
    except Exception:
        connection.close()
        raise

@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    if not is_sqlite():
        raise RuntimeError("SQL connection requested for the memory backend")
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


@contextmanager
def atomic() -> Iterator[sqlite3.Connection | None]:
    """Serialise a state change for either configured backend."""
    if is_sqlite():
        with transaction() as conn:
            yield conn
        return
    with _MEMORY_LOCK:
        yield None


def read_record(
    table: str,
    record_id: str,
    conn: sqlite3.Connection | None = None,
) -> dict | None:
    if table not in _TABLES:
        raise ValueError(f"unknown record table {table!r}")
    if not is_sqlite():
        with _MEMORY_LOCK:
            record = _MEMORY[table].get(record_id)
            return dict(record) if record is not None else None
    own = conn is None
    conn = conn or _connect()
    try:
        row = conn.execute(
            _RECORD_SQL[table]["read"],
            (record_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        if own:
            conn.close()


def all_records(table: str) -> list[dict]:
    if table not in _TABLES:
        raise ValueError(f"unknown record table {table!r}")
    if not is_sqlite():
        with _MEMORY_LOCK:
            return [dict(record) for record in _MEMORY[table].values()]
    with connection() as conn:
        rows = conn.execute(_RECORD_SQL[table]["all"]).fetchall()
    return [json.loads(row[0]) for row in rows]


def write_record(
    table: str,
    record: dict,
    conn: sqlite3.Connection | None = None,
) -> None:
    if table not in _TABLES:
        raise ValueError(f"unknown record table {table!r}")
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id:
        raise ValueError("state records need a non-empty string id")
    if not is_sqlite():
        with _MEMORY_LOCK:
            _MEMORY[table][record_id] = dict(record)
        return
    own = conn is None
    conn = conn or _connect()
    try:
        conn.execute(
            _RECORD_SQL[table]["write"],
            (
                record_id,
                record.get("tenant_id"),
                record.get("state"),
                record.get("created_at"),
                json.dumps(record, separators=(",", ":"), sort_keys=True),
            ),
        )
    finally:
        if own:
            conn.close()


def clear_records(table: str) -> None:
    if table not in _TABLES:
        raise ValueError(f"unknown record table {table!r}")
    if not is_sqlite():
        with _MEMORY_LOCK:
            _MEMORY[table].clear()
        return
    with connection() as conn:
        conn.execute(_RECORD_SQL[table]["clear"])


def get_idempotency(
    tenant_id: str,
    key: str,
    conn: sqlite3.Connection | None = None,
) -> dict | None:
    if not is_sqlite():
        with _MEMORY_LOCK:
            record = _MEMORY["idempotency"].get((tenant_id, key))
            return dict(record) if record is not None else None
    own = conn is None
    conn = conn or _connect()
    try:
        row = conn.execute(
            "SELECT body_hash, status, body_json, headers_json, expires "
            "FROM api_idempotency WHERE tenant_id = ? AND key = ?",
            (tenant_id, key),
        ).fetchone()
    finally:
        if own:
            conn.close()
    if row is None:
        return None
    return {
        "body_hash": row[0],
        "status": row[1],
        "body": json.loads(row[2]),
        "headers": json.loads(row[3]),
        "expires": row[4],
    }


def put_idempotency(
    tenant_id: str,
    key: str,
    record: dict,
    conn: sqlite3.Connection | None = None,
) -> None:
    if not is_sqlite():
        with _MEMORY_LOCK:
            _MEMORY["idempotency"][(tenant_id, key)] = dict(record)
        return
    own = conn is None
    conn = conn or _connect()
    try:
        conn.execute(
            "INSERT INTO api_idempotency "
            "(tenant_id, key, body_hash, status, body_json, headers_json, expires) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(tenant_id, key) DO UPDATE SET "
            "body_hash=excluded.body_hash, status=excluded.status, "
            "body_json=excluded.body_json, headers_json=excluded.headers_json, "
            "expires=excluded.expires",
            (
                tenant_id,
                key,
                record["body_hash"],
                record["status"],
                json.dumps(record["body"], separators=(",", ":"), sort_keys=True),
                json.dumps(record["headers"], separators=(",", ":"), sort_keys=True),
                record["expires"],
            ),
        )
    finally:
        if own:
            conn.close()


def delete_idempotency(
    tenant_id: str,
    key: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    if not is_sqlite():
        with _MEMORY_LOCK:
            _MEMORY["idempotency"].pop((tenant_id, key), None)
        return
    own = conn is None
    conn = conn or _connect()
    try:
        conn.execute(
            "DELETE FROM api_idempotency WHERE tenant_id = ? AND key = ?",
            (tenant_id, key),
        )
    finally:
        if own:
            conn.close()


def reset_idempotency() -> None:
    if not is_sqlite():
        with _MEMORY_LOCK:
            _MEMORY["idempotency"].clear()
        return
    with connection() as conn:
        conn.execute("DELETE FROM api_idempotency")


def reset_rate_limit() -> None:
    with _MEMORY_LOCK:
        _RATE_HITS.clear()
    if is_sqlite():
        with connection() as conn:
            conn.execute("DELETE FROM api_rate_limits")


def rate_hit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Atomically consume one request slot; return allowed and retry delay."""
    if limit < 1 or window_seconds < 1:
        raise ValueError("rate limit and window must be positive")
    now = time.time()
    if not is_sqlite():
        with _MEMORY_LOCK:
            hits = _RATE_HITS.setdefault(key, [])
            hits[:] = [stamp for stamp in hits if now - stamp <= window_seconds]
            if len(hits) >= limit:
                return False, max(1, int(window_seconds - (now - hits[0])))
            hits.append(now)
            if len(_RATE_HITS) > 10_000:
                stale = [item for item, values in _RATE_HITS.items() if not values]
                for item in stale[:5_000]:
                    _RATE_HITS.pop(item, None)
            return True, 0

    window_start = int(now // window_seconds)
    with transaction() as conn:
        conn.execute(
            "DELETE FROM api_rate_limits WHERE window_start < ?",
            (window_start - 1,),
        )
        row = conn.execute(
            "SELECT window_start, count FROM api_rate_limits WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None or row[0] != window_start:
            conn.execute(
                "INSERT INTO api_rate_limits (key, window_start, count) VALUES (?, ?, 1) "
                "ON CONFLICT(key) DO UPDATE SET window_start=excluded.window_start, count=1",
                (key, window_start),
            )
            return True, 0
        if row[1] >= limit:
            retry = max(1, int((window_start + 1) * window_seconds - now))
            return False, retry
        conn.execute(
            "UPDATE api_rate_limits SET count = count + 1 WHERE key = ?",
            (key,),
        )
        return True, 0


def check_state() -> None:
    """Readiness probe for the configured state backend."""
    if is_sqlite():
        try:
            with connection() as conn:
                conn.execute("SELECT 1").fetchone()
        except sqlite3.Error as exc:
            raise RuntimeError("configured API state is unavailable") from exc
