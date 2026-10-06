#!/usr/bin/env python3
"""Reconcile a tenant's content-addressed file plane against hyba_db.

Exit 0 only when the reconciliation reports zero unresolved production
violations; exit 1 on unresolved violations; exit 2 on invocation errors.
The machine-readable report is emitted to stdout (or --out) and, when THESEUS
custody is wired, registered as a custodied artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the ontology store SQLite file")
    parser.add_argument("--root", required=True, help="Declared content-addressed storage root")
    parser.add_argument("--tenant", required=True, help="Tenant id to reconcile")
    parser.add_argument("--integrity-key-hex", default=None)
    parser.add_argument(
        "--custody-root", default=None, help="THESEUS custody root (verifies custody ids)"
    )
    parser.add_argument("--custody-key-hex", default=None)
    parser.add_argument("--out", default=None, help="Write the JSON report to this path as well")
    args = parser.parse_args()

    key_hex = args.integrity_key_hex or os.environ.get("HYBA_INTEGRITY_KEY_HEX", "")
    key = bytes.fromhex(key_hex) if key_hex else b""
    if len(key) < 32:
        print(
            json.dumps({"passed": False, "error": "integrity key must contain at least 32 bytes"})
        )
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hyba_db.store import OntologyStore
    from hyba_db.theseus_custody import TheseusFileCustody

    custody = None
    custody_key_hex = args.custody_key_hex or os.environ.get("THESEUS_CUSTODY_KEY_HEX", "")
    if args.custody_root:
        if not custody_key_hex:
            print(json.dumps({"passed": False, "error": "custody root requires --custody-key-hex"}))
            return 2
        custody = TheseusFileCustody(args.custody_root, hmac_key=bytes.fromhex(custody_key_hex))

    with OntologyStore(args.db, key, custody=custody) as store:
        report, artifact = store.files.reconcile_and_record(args.tenant, args.root)
        output = report.to_dict()
        output["artifact_registered"] = artifact is not None
        text = json.dumps(output, indent=2, sort_keys=True)
        print(text)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
