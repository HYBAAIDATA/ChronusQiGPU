#!/usr/bin/env python3
"""Validate the checked-in canonical storage taxonomy.

The manifest is JSON syntax, which is a strict subset of YAML and keeps the
bootstrap validator dependency-free in clean environments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ALLOWED = {
    "DURABLE_AUTHORITY",
    "DURABLE_ADAPTER",
    "DURABLE_EVIDENCE",
    "SNAPSHOT",
    "TRANSFORM_ARTIFACT",
    "REPORT",
    "MANIFEST",
    "PACKAGE",
    "CACHE",
    "EPHEMERAL",
    "LEGACY",
    "EXPERIMENTAL",
}
REQUIRED = {
    "id",
    "owner_subsystem",
    "implementation_path",
    "backend",
    "tenant_semantics",
    "authoritative",
    "class",
    "custody_required",
    "retention",
    "replay",
    "reconcile",
    "may_delete",
    "may_rebuild",
}


def validate(path: Path) -> dict:
    errors = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"passed": False, "errors": [f"invalid JSON/YAML-compatible manifest: {exc}"]}
    if doc.get("schema") != "pythia.storage-registry/v1":
        errors.append("schema must be pythia.storage-registry/v1")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        entries = []
    ids = set()
    for i, entry in enumerate(entries):
        missing = sorted(REQUIRED - set(entry))
        if missing:
            errors.append(f"entry {i} missing {missing}")
        if entry.get("id") in ids:
            errors.append(f"duplicate id {entry.get('id')}")
        ids.add(entry.get("id"))
        if entry.get("class") not in ALLOWED:
            errors.append(f"{entry.get('id')}: invalid class {entry.get('class')}")
        if not isinstance(entry.get("tenant_semantics"), str) or not entry.get("tenant_semantics"):
            errors.append(f"{entry.get('id')}: tenant semantics required")
    return {
        "schema": doc.get("schema"),
        "entries": len(entries),
        "passed": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="governance/storage_registry.yaml")
    args = parser.parse_args()
    result = validate(Path(args.path))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
