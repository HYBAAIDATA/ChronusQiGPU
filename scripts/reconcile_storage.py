#!/usr/bin/env python3
"""Reconcile a tenant's content-addressed file plane against hyba_db."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--root", required=True); ap.add_argument("--tenant", required=True); ap.add_argument("--integrity-key-hex", default=None); ap.add_argument("--custody-record-id", default=None)
    args=ap.parse_args()
    key=bytes.fromhex(args.integrity_key_hex or os.environ.get("HYBA_INTEGRITY_KEY_HEX", ""))
    if len(key)<32: print(json.dumps({"passed":False,"error":"integrity key must contain at least 32 bytes"})); return 2
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hyba_db.store import OntologyStore
    with OntologyStore(args.db, key) as store:
        report, artifact = store.files.reconcile_and_record(args.tenant, args.root, custody_record_id=args.custody_record_id)
        output=report.to_dict(); output["artifact_registered"]=artifact is not None
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if report.passed else 1
if __name__ == "__main__": raise SystemExit(main())
