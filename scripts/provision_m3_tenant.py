#!/usr/bin/env python3
"""Explicit one-time tenant admission for the strict PYTHIA mining custody plane.

No pool connection, mining or publication. Names and quotas are operator-owned.
Private integrity/custody keys are read from the environment and NEVER logged.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re

from hyba_db.models import Quota
from hyba_db.store import OntologyStore
from hyba_db.theseus_custody import TheseusFileCustody


def namespace_for(explicit: str) -> str:
    value = re.sub(r"[^a-z0-9-]", "-", explicit.strip().lower())
    return re.sub(r"-{2,}", "-", value).strip("-")[:63]


def provision(*, tenant: str, max_records: int, max_bytes: int,
              approved: bool = False) -> str:
    if not approved:
        raise ValueError("explicit --approve-tenant required")
    if not 1 <= max_records <= 10**9 or not 1 <= max_bytes <= 10**12:
        raise ValueError("bounded max-records and max-bytes required")
    selected = namespace_for(tenant)
    if len(selected) < 3:
        raise ValueError("tenant namespace must be at least three characters")
    if selected != namespace_for(os.getenv("PYTHIA_STORAGE_TENANT", "")):
        raise ValueError("tenant must equal canonical PYTHIA_STORAGE_TENANT")
    db = os.getenv("PYTHIA_STORAGE_DB", "").strip()
    cas_root = os.getenv("PYTHIA_STORAGE_ROOT", "").strip()
    custody_root = os.getenv("PYTHIA_STORAGE_CUSTODY_ROOT", "").strip()
    integrity = os.getenv("PYTHIA_STORAGE_INTEGRITY_KEY_HEX", "").strip()
    custody_key = os.getenv("PYTHIA_STORAGE_CUSTODY_KEY_HEX", "").strip()
    if not all((db, cas_root, custody_root, integrity, custody_key)):
        raise ValueError("all PYTHIA_STORAGE_* custody, root and key variables required")
    if not os.getenv("PYTHIA_M3_ACTOR", "").strip():
        raise ValueError("PYTHIA_M3_ACTOR required for administrative admission")
    if not os.getenv("PYTHIA_M3_AL_HARAS_TOKEN", "").strip():
        raise ValueError("PYTHIA_M3_AL_HARAS_TOKEN required")
    if not os.getenv("PYTHIA_M3_REQUIRED", "").strip().lower() in {"1", "true", "yes", "on"}:
        raise ValueError("PYTHIA_M3_REQUIRED=1 required")
    if len(bytes.fromhex(integrity)) < 32 or len(bytes.fromhex(custody_key)) < 32:
        raise ValueError("separate 32+ byte integrity and custody keys required")
    # All file/custody paths are chosen by the operator; never use temp storage.
    Path(cas_root).mkdir(parents=True, exist_ok=True)
    custody = TheseusFileCustody(
        root=custody_root, hmac_key=bytes.fromhex(custody_key)
    )
    store = OntologyStore(db, bytes.fromhex(integrity), custody=custody)
    try:
        existing = store._db.execute(
            "SELECT tenant_id,max_records,max_blob_bytes FROM tenants WHERE namespace=?",
            (selected,),
        ).fetchone()
        if existing is not None:
            if int(existing["max_records"]) != max_records or int(existing["max_blob_bytes"]) != max_bytes:
                raise ValueError("existing tenant quota differs: refuse implicit quota change")
            tenant_id = str(existing["tenant_id"])
        else:
            client = store.provision_client(
                selected,
                Quota(max_records=max_records, max_blob_bytes=max_bytes),
                issuer="m3-operator-approved-admission",
            )
            tenant_id = client.tenant_id
        if not store.files.verify_database(tenant_id).get("passed"):
            raise RuntimeError("custody projection integrity verification failed")
        if not custody.verify(tenant_id, f"tenant_projection.{tenant_id}"):
            raise RuntimeError("THESEUS tenant manifest not durably verified")
        return tenant_id
    finally:
        store.close()
        custody.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--max-records", type=int, default=1000000)
    parser.add_argument("--max-bytes", type=int, default=10000000000)
    parser.add_argument("--approve-tenant", action="store_true",
                        help="Authorised operator acknowledges durable admission")
    args = parser.parse_args(argv)
    tid = provision(tenant=args.tenant, max_records=args.max_records,
                    max_bytes=args.max_bytes, approved=args.approve_tenant)
    print("THESEUS tenant manifest verified; tenant_id=" + tid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
