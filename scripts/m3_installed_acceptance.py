#!/usr/bin/env python3
"""§20.17 installed-artifact acceptance gate.

Self-contained: provisions a THESEUS custody + hyba_db plane in a temp dir
via the *installed* package, drives put→custody→link→reconcile→stats, and
exits non-zero on any failure. Run from outside the checkout against the
installed wheel:

    python scripts/m3_installed_acceptance.py
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import hyba_db  # noqa: F401  — must import from the installed artifact


def main() -> int:
    from hyba_db.models import Quota
    from hyba_db.ovid_transform import OvidTransformPlane
    from hyba_db.store import OntologyStore
    from hyba_db.theseus_custody import TheseusFileCustody

    work = Path(tempfile.mkdtemp(prefix="m3_installed_"))
    custody = TheseusFileCustody(work / "custody", hmac_key=os.urandom(32))
    store = OntologyStore(work / "store.db", os.urandom(32), custody=custody)
    client = store.provision_client(
        "m3-installed-gate", Quota(max_records=10**6, max_blob_bytes=10**8)
    )
    root = work / "cas"
    obj, version = store.files.put_file(
        client.tenant_id,
        root,
        logical_name="installed-gate.json",
        file_class="durable_evidence",
        semantic_owner="chronus",
        domain="mining:installed-gate",
        content=b'{"gate":"installed-artifact"}',
        producer="chronus",
        links=(("external:installed-gate", "v1", "describes"),),
    )
    lineage = OvidTransformPlane(store.files).fold_into(client.tenant_id, root, version)
    report = store.files.reconcile_files(client.tenant_id, root)
    status = store.files.stats(client.tenant_id, root=root)["tenants"][client.tenant_id]["status"]
    out = {
        "gate": "m3-installed-artifact",
        "hyba_db_origin": hyba_db.__file__,
        "file_object_id": obj,
        "file_version_id": version,
        "ovid_equivalent": lineage["equivalence"]["equivalent"],
        "reconcile_passed": report.passed,
        "unresolved": list(report.unresolved),
        "status": status,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    store.close()
    custody.close()
    ok = report.passed and lineage["equivalence"]["equivalent"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
