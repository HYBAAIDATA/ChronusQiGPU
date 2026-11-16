"""Shared qualification transcript and sticky-class store.

Backed by SQLite so API replicas that share the database file observe the same
suspension/reset state. Process restart retains evidence under the configured
path. Transcript signatures use the durable qualification signer (see
``chronus.qualification.signing``), not the process-local API receipt key.
Set ``CHRONUS_QUALIFICATION_DB_PATH`` to override the default location.

Writers use ``BEGIN IMMEDIATE`` so reset and remember serialize across
processes. ``remember`` never lets a clean result replace a stored suspension;
``clear_class`` deletes only the exact row it read so a concurrent suspension
cannot be wiped by a stale reset.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from chronus.qualification.harness import QualificationResult
from chronus.qualification.tiers import Tier, TierContract

_LOCK = Lock()


def _db_path() -> str:
    configured = os.getenv("CHRONUS_QUALIFICATION_DB_PATH")
    if configured:
        return configured
    workload = os.getenv("CHRONUS_WORKLOAD_DB_PATH", "data/chronus-workloads.sqlite3")
    parent = Path(workload).parent
    return str(parent / "chronus-qualification.sqlite3")


@contextmanager
def _connect(*, exclusive: bool = False) -> Iterator[sqlite3.Connection]:
    path = _db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None → autocommit; we manage BEGIN/COMMIT explicitly so
    # writers can take BEGIN IMMEDIATE and hold it across SELECT+DELETE.
    connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transcripts (
                evidence_hash TEXT PRIMARY KEY,
                transcript_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS class_state (
                workload_class TEXT PRIMARY KEY,
                result_json TEXT NOT NULL
            )
            """
        )
        connection.execute("BEGIN IMMEDIATE" if exclusive else "BEGIN")
        yield connection
        connection.execute("COMMIT")
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        connection.close()


def _serialize_result(result: QualificationResult) -> str:
    payload = {
        "tier": result.tier.value,
        "evidence_hash": result.evidence_hash,
        "audit_transcript": result.audit_transcript,
        "public_view": result.public_view,
        "economics": result.economics,
        "contract": {
            "tier": result.contract.tier.value,
            "tier_contract_version": result.contract.tier_contract_version,
            "residual_bound_by_size": [
                [int(size), bound] for size, bound in result.contract.residual_bound_by_size
            ],
            "qualification_evidence_hash": result.contract.qualification_evidence_hash,
            "suspended": result.contract.suspended,
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _deserialize_result(raw: str) -> QualificationResult:
    payload = json.loads(raw)
    contract_raw = payload["contract"]
    contract = TierContract(
        tier=Tier(contract_raw["tier"]),
        tier_contract_version=contract_raw["tier_contract_version"],
        residual_bound_by_size=tuple(
            (int(size), str(bound))
            for size, bound in contract_raw["residual_bound_by_size"]
        ),
        qualification_evidence_hash=contract_raw["qualification_evidence_hash"],
        suspended=bool(contract_raw["suspended"]),
    )
    return QualificationResult(
        tier=Tier(payload["tier"]),
        contract=contract,
        evidence_hash=payload["evidence_hash"],
        audit_transcript=dict(payload["audit_transcript"]),
        public_view=dict(payload["public_view"]),
        economics=dict(payload["economics"]),
    )


def _is_suspended_result(result: QualificationResult) -> bool:
    return bool(result.contract.suspended or result.tier == Tier.SUSPENDED)


def remember(result: QualificationResult) -> bool:
    """Persist the qualification transcript and, when allowed, the class row.

    Always stores the audit transcript by evidence hash. The class row is
    updated inside the same exclusive write transaction unless a sticky
    suspension is already stored and the incoming result is not suspended —
    that prevents a later clean qualify from clearing a concurrent suspension
    without an operator reset.

    Returns True when the class row was written/updated.
    """
    workload_class = str(result.audit_transcript.get("workload_class", ""))
    serialized = _serialize_result(result)
    transcript_json = json.dumps(
        result.audit_transcript, sort_keys=True, separators=(",", ":")
    )
    incoming_suspended = _is_suspended_result(result)
    class_updated = False
    with _LOCK:
        with _connect(exclusive=True) as connection:
            connection.execute(
                """
                INSERT INTO transcripts (evidence_hash, transcript_json)
                VALUES (?, ?)
                ON CONFLICT(evidence_hash) DO UPDATE SET
                    transcript_json=excluded.transcript_json
                """,
                (result.evidence_hash, transcript_json),
            )
            row = connection.execute(
                "SELECT result_json FROM class_state WHERE workload_class = ?",
                (workload_class,),
            ).fetchone()
            if row is not None and not incoming_suspended:
                existing = _deserialize_result(row[0])
                if _is_suspended_result(existing):
                    return False
            connection.execute(
                """
                INSERT INTO class_state (workload_class, result_json)
                VALUES (?, ?)
                ON CONFLICT(workload_class) DO UPDATE SET
                    result_json=excluded.result_json
                """,
                (workload_class, serialized),
            )
            class_updated = True
    return class_updated


def recall_by_class(workload_class: str) -> QualificationResult | None:
    with _LOCK:
        with _connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM class_state WHERE workload_class = ?",
                (workload_class,),
            ).fetchone()
    if row is None:
        return None
    return _deserialize_result(row[0])


def recall_by_hash(evidence_hash: str) -> dict[str, Any] | None:
    with _LOCK:
        with _connect() as connection:
            row = connection.execute(
                "SELECT transcript_json FROM transcripts WHERE evidence_hash = ?",
                (evidence_hash,),
            ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def clear_class(workload_class: str) -> dict[str, Any] | None:
    """Clear sticky class state after operator review.

    Preserves the prior audit transcript under its evidence hash so suspension
    evidence remains inspectable after the class is allowed to re-qualify.

    Deletion is conditioned on the exact ``result_json`` that was read inside
    an exclusive write transaction. If another writer replaced the class state
    before the delete, the newer row is left intact and this returns
    ``cleared=False``.
    """
    with _LOCK:
        with _connect(exclusive=True) as connection:
            row = connection.execute(
                "SELECT result_json FROM class_state WHERE workload_class = ?",
                (workload_class,),
            ).fetchone()
            if row is None:
                return None
            prior = _deserialize_result(row[0])
            connection.execute(
                """
                INSERT INTO transcripts (evidence_hash, transcript_json)
                VALUES (?, ?)
                ON CONFLICT(evidence_hash) DO UPDATE SET
                    transcript_json=excluded.transcript_json
                """,
                (
                    prior.evidence_hash,
                    json.dumps(
                        prior.audit_transcript, sort_keys=True, separators=(",", ":")
                    ),
                ),
            )
            deleted = connection.execute(
                """
                DELETE FROM class_state
                WHERE workload_class = ? AND result_json = ?
                """,
                (workload_class, row[0]),
            )
            cleared = deleted.rowcount == 1
    return {
        "workload_class": workload_class,
        "preserved_evidence_hash": prior.evidence_hash,
        "was_suspended": bool(
            prior.contract.suspended or prior.tier == Tier.SUSPENDED
        ),
        "cleared": cleared,
    }


def clear() -> None:
    """Test helper — drop all qualification state and transcripts."""
    with _LOCK:
        with _connect(exclusive=True) as connection:
            connection.execute("DELETE FROM class_state")
            connection.execute("DELETE FROM transcripts")
