#!/usr/bin/env python3
"""Validate the checked-in canonical storage taxonomy.

The manifest is JSON syntax, which is a strict subset of YAML and keeps the
bootstrap validator dependency-free in clean environments.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ALLOWED = {"DURABLE_AUTHORITY","DURABLE_ADAPTER","DURABLE_EVIDENCE","SNAPSHOT","TRANSFORM_ARTIFACT","REPORT","MANIFEST","PACKAGE","CACHE","EPHEMERAL","LEGACY","EXPERIMENTAL"}
REQUIRED = {"id","owner_subsystem","implementation_path","backend","tenant_semantics","authoritative","class","custody_required","retention","replay","reconcile","may_delete","may_rebuild"}

def validate(path: Path) -> dict:
    errors=[]
    try: doc=json.loads(path.read_text())
    except Exception as exc: return {"passed":False,"errors":[f"invalid JSON/YAML-compatible manifest: {exc}"]}
    if doc.get("schema") != "pythia.storage-registry/v1": errors.append("schema must be pythia.storage-registry/v1")
    entries=doc.get("entries")
    if not isinstance(entries,list) or not entries: errors.append("entries must be a non-empty list"); entries=[]
    ids=set()
    for i,e in enumerate(entries):
        missing=sorted(REQUIRED-set(e))
        if missing: errors.append(f"entry {i} missing {missing}")
        if e.get("id") in ids: errors.append(f"duplicate id {e.get('id')}")
        ids.add(e.get("id"))
        if e.get("class") not in ALLOWED: errors.append(f"{e.get('id')}: invalid class {e.get('class')}")
        if not isinstance(e.get("tenant_semantics"),str) or not e.get("tenant_semantics"): errors.append(f"{e.get('id')}: tenant semantics required")
    return {"schema":doc.get("schema"),"entries":len(entries),"passed":not errors,"errors":errors}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("path", nargs="?", default="governance/storage_registry.yaml")
    result=validate(Path(ap.parse_args().path)); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["passed"] else 1
if __name__ == "__main__": sys.exit(main())
