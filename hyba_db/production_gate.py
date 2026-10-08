"""Installed production gate for the storage and ontology projection.

This command validates the current database, content-addressed storage root and
THESEUS custody together. It never upgrades missing evidence into a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .rebuild import projection_fingerprint, restore_projection_from_custody
from .store import OntologyStore
from .theseus_custody import TheseusFileCustody


def evaluate(
    *,
    db_path: str | Path,
    storage_root: str | Path,
    tenant_id: str,
    integrity_key: bytes,
    custody_root: str | Path,
    custody_key: bytes,
) -> dict[str, Any]:
    custody = TheseusFileCustody(custody_root, hmac_key=custody_key)
    with OntologyStore(db_path, integrity_key, custody=custody) as store:
        metadata = {
            row["key"]: row["value"]
            for row in store._db.execute("SELECT key,value FROM metadata")
        }
        sqlite_integrity = str(store._db.execute("PRAGMA integrity_check").fetchone()[0])
        journal_mode = str(store._db.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        synchronous = int(store._db.execute("PRAGMA synchronous").fetchone()[0])
        foreign_keys = int(store._db.execute("PRAGMA foreign_keys").fetchone()[0])
        verification = store.verify_database(
            tenant_id, storage_roots={tenant_id: str(storage_root)}
        )
        knowledge = store.knowledge.verify(tenant_id)
        ovid_index = store.ovid.verify(tenant_id)
        file_plane = store.files.verify_database(tenant_id)
        stats = store.files.stats(tenant_id)
        tenant_custody = custody.open_tenant(tenant_id)
        custody_health = tenant_custody.health()
        custody_replay = tenant_custody.verify_replay()
        pending_revalidation = tenant_custody.pending_revalidation()
        tenant_manifest_id = f"tenant_projection.{tenant_id}"
        tenant_manifest_verified = custody.verify(tenant_id, tenant_manifest_id)
        baseline_fingerprint = projection_fingerprint(store, tenant_id)
        base_checks = {
            "schema_v3": metadata.get("schema_version") == str(store.SCHEMA_VERSION),
            "sqlite_integrity": sqlite_integrity == "ok",
            "wal_enabled": journal_mode == "wal",
            "synchronous_full": synchronous == 2,
            "foreign_keys_enabled": foreign_keys == 1,
            "database_verified": verification.passed,
            "file_plane_verified": bool(file_plane.get("passed")),
            "mining_chain_verified": verification.mining_chain_ok,
            "knowledge_projection_verified": bool(knowledge.get("passed")),
            "ovid_data_index_verified": bool(ovid_index.get("passed")),
            "tenant_identity_custodied": tenant_manifest_verified,
            "storage_reconciled": verification.reconciliation_ok,
            "custody_ready": bool(custody_health.get("ready")),
            "custody_not_degraded": not bool(custody_health.get("degraded")),
            "custody_replay_verified": bool(custody_replay.get("match")),
            "producer_revalidation_complete": not bool(pending_revalidation),
        }
        base_report = {
            "database_errors": list(verification.errors),
            "knowledge_errors": list(knowledge.get("errors", ())),
            "ovid_index": ovid_index,
            "file_errors": list(file_plane.get("errors", ())),
            "custody_health": custody_health,
            "custody_replay": custody_replay,
            "pending_producer_revalidation": pending_revalidation,
            "stats": stats["tenants"].get(tenant_id, {}),
        }

    rebuild_report: dict[str, Any]
    rebuild_errors: list[str] = []
    rebuilt_fingerprint: dict[str, Any] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="hyba-db-rebuild-gate-") as directory:
            rebuilt_custody = TheseusFileCustody(custody_root, hmac_key=custody_key)
            with OntologyStore(
                Path(directory) / "ontology.db",
                integrity_key,
                custody=rebuilt_custody,
            ) as rebuilt:
                rebuild_report = restore_projection_from_custody(
                    rebuilt,
                    tenant_id,
                    storage_root,
                )
                rebuilt_verification = rebuilt.verify_database(
                    tenant_id,
                    storage_roots={tenant_id: str(storage_root)},
                )
                rebuilt_fingerprint = projection_fingerprint(rebuilt, tenant_id)
                if not rebuilt_verification.passed:
                    rebuild_errors.extend(rebuilt_verification.errors)
    except Exception as exc:
        rebuild_report = {
            "schema": "hyba.database-rebuild/v1",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        rebuild_errors.append(rebuild_report["error"])

    destructive_match = (
        bool(rebuild_report.get("passed"))
        and rebuilt_fingerprint is not None
        and rebuilt_fingerprint == baseline_fingerprint
        and not rebuild_errors
    )
    checks = {
        **base_checks,
        "destructive_projection_rebuild": destructive_match,
    }
    return {
        "schema": "hyba.storage-database-production-gate/v2",
        "tenant_id": tenant_id,
        "passed": all(checks.values()),
        "checks": checks,
        **base_report,
        "destructive_rebuild": {
            "passed": destructive_match,
            "report": rebuild_report,
            "errors": rebuild_errors,
            "fingerprint_match": (
                rebuilt_fingerprint == baseline_fingerprint
                if rebuilt_fingerprint is not None
                else False
            ),
        },
        "claim_boundary": {
            "live_pool": "UNAVAILABLE",
            "physical_hardware": "UNAVAILABLE",
            "fleet": "UNAVAILABLE",
            "performance": "UNAVAILABLE",
            "accepted_share": "UNAVAILABLE",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--custody-root", required=True)
    parser.add_argument("--integrity-key-hex", default=None)
    parser.add_argument("--custody-key-hex", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    integrity_hex = args.integrity_key_hex or os.environ.get("HYBA_INTEGRITY_KEY_HEX", "")
    custody_hex = args.custody_key_hex or os.environ.get("THESEUS_CUSTODY_KEY_HEX", "")
    try:
        integrity_key = bytes.fromhex(integrity_hex)
        custody_key = bytes.fromhex(custody_hex)
    except ValueError as exc:
        parser.error(f"keys must be hexadecimal: {exc}")
    if len(integrity_key) < 32 or len(custody_key) < 32:
        parser.error("integrity and custody keys must each contain at least 32 bytes")

    report = evaluate(
        db_path=args.db,
        storage_root=args.root,
        tenant_id=args.tenant,
        integrity_key=integrity_key,
        custody_root=args.custody_root,
        custody_key=custody_key,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
