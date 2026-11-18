#!/usr/bin/env python3
"""Machine-validated definitive capability manifest.

Runs against capabilities/definitive_manifest.json and fails (nonzero exit,
first failing assertion) if the manifest does not validate against its own
JSON schema, or any row claims a status its evidence fields cannot support
(the "no claim without a named passing test" gate).

Usage:
    pytest -q tests/test_definitive_manifest.py
    python tests/test_definitive_manifest.py --render   # renders docs/definitive-manifest.md
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "capabilities" / "definitive_manifest.json"
SCHEMA = REPO_ROOT / "capabilities" / "definitive_manifest.schema.json"
DOC = REPO_ROOT / "docs" / "definitive-manifest.md"

# disposition -> evidence fields that must be present for an honest claim
REQUIRED_EVIDENCE_BY_STATUS = {
    "IMPLEMENTED_ALL": ["results"],
    "IMPLEMENTED_EVIDENCE_PENDING": ["results"],
    "EVIDENCE_GATED": ["missing"],
    "HELD": ["missing"],
    "PROVENANCE": [],
    "SUPERSEDED": [],
    "RE-VERIFIED": ["results"],
    "NOT-REPRODUCED": [],
}
DIAGNOSTICS = []


def _check_row(row, path):
    row_id = row.get("id", "<no id>")
    disposition = row.get("disposition")
    evidence = row.get("evidence")
    results = evidence.get("results") if isinstance(evidence, dict) else None
    claimed_status = row.get("status")

    if disposition is None:
        DIAGNOSTICS.append(f"{path}: row {row_id} has no 'disposition'")
        return
    allowed = REQUIRED_EVIDENCE_BY_STATUS.get(disposition)
    if allowed is None:
        DIAGNOSTICS.append(f"{path}: row {row_id} disposition '{disposition}' is not allowed")
        return
    if claimed_status is not None and claimed_status not in allowed:
        DIAGNOSTICS.append(f"{path}: row {row_id} claims status '{claimed_status}' "
                           f"but disposition '{disposition}' supports only {allowed}")
    if disposition == "PROVENANCE":
        # provenance must never upgrade a current claim (withdrawn 100%-qualified dossier)
        if results:
            DIAGNOSTICS.append(f"{path}: row {row_id} is PROVENANCE but carries results")
        return
    if disposition == "SUPERSEDED":
        if results:
            DIAGNOSTICS.append(f"{path}: row {row_id} is SUPERSEDED but carries results")
        return
    if results:
        if not isinstance(results, list) or not results:
            DIAGNOSTICS.append(f"{path}: row {row_id} has status {disposition} "
                               f"but no executed test results")
            return
        if disposition == "HELD":
            passed = [r for r in results if isinstance(r, dict) and r.get("status") == "PASS"]
            if passed:
                DIAGNOSTICS.append(f"{path}: row {row_id} is HELD but {len(passed)} test(s) PASS")
        elif disposition == "IMPLEMENTED_EVIDENCE_PENDING":
            open_tests = [r for r in results if isinstance(r, dict)
                          and r.get("status") in ("OPEN", "UNRESOLVED")]
            if not open_tests:
                DIAGNOSTICS.append(f"{path}: row {row_id} evidence-pending but no OPEN/UNRESOLVED result")
    if disposition in ("EVIDENCE_GATED", "HELD") and not (
            isinstance(evidence, dict) and evidence.get("missing")):
        DIAGNOSTICS.append(f"{path}: row {row_id} disposition '{disposition}' requires 'missing' evidence")


def validate():
    errors = []
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot read manifest: {exc}"]
    if not isinstance(manifest, dict) or "rows" not in manifest:
        return ["manifest root must be an object with a 'rows' array"]
    rows = manifest["rows"]
    if not isinstance(rows, list) or not rows:
        return ["'rows' must be a non-empty array"]
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"rows[{i}]: row is not an object")
            continue
        _check_row(row, f"rows[{i}]")
    return errors


def render_doc():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lines = [
        "# Chronus definitive capability manifest",
        "",
        f"- Generated: {manifest.get('generated', 'unknown')}",
        f"- Baseline: `{manifest.get('baseline', {}).get('sha')}` "
        f"({manifest.get('baseline', {}).get('branch') or '?'}, "
        f"dirty={manifest.get('baseline', {}).get('dirty', 'unknown')})",
        f"- Provenance rule: {manifest.get('provenance_rule', 'n/a')}",
        f"- Mandatory gates: {', '.join(manifest.get('mandatory_gates', []))}",
        "",
        "## Front matter (findings)",
        "",
        "| Finding | Content |",
        "| --- | --- |",
    ]
    for f in manifest.get("findings", []):
        lines.append(f"| {f.get('id')} | {f.get('summary')} |")
    lines += [
        "",
        "## Row inventory",
        "",
        "| id | namespace | disposition | status | missing |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in manifest.get("rows", []):
        missing = row.get("evidence", {}).get("missing") or []
        lines.append(f"| {row.get('id')} | {row.get('namespace')} | {row.get('disposition')} | "
                     f"{row.get('status')} | {', '.join(missing) or 'none'} |")
    return "\n".join(lines) + "\n"


def main():
    render = "--render" in sys.argv
    errors = validate()
    if render:
        DOC.write_text(render_doc(), encoding="utf-8")
        print(f"rendered {DOC}")
    if errors:
        print("DEFINITIVE MANIFEST VALIDATION FAILED")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("DEFINITIVE MANIFEST VALIDATION OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
