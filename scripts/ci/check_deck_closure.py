"""Validate a restricted taxonomy and deterministic text export.

The private deck, website and annex remain outside this public repository.
This gate checks an explicitly supplied inventory; format-specific extraction
and independent coverage review remain required for a final deck.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")


def verify_binding(root, row, revision):
    commit, path, digest = (row[k] for k in ("source_commit", "artifact_path", "artifact_sha256"))
    if not SHA.fullmatch(commit) or not DIGEST.fullmatch(digest):
        raise ValueError("full source commit and digest required")
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts or ":" in path:
        raise ValueError("invalid evidence path")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, revision],
                   cwd=root, check=True, capture_output=True)
    raw = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=root)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("artifact digest mismatch")
    if row["status"] == "MEASURED" and commit != revision:
        raise ValueError("measured evidence has not been rerun at reviewed revision")


def validate_taxonomy(document, root, revision):
    rows = document["figures"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty claim inventory required")
    ids = set()
    for row in rows:
        cid = row["id"]
        if not isinstance(cid, str) or not cid or cid in ids:
            raise ValueError("invalid or duplicate claim ID")
        ids.add(cid)
        if row["status"] not in {"MEASURED", "SPECIFIED", "REMOVED"}:
            raise ValueError("unknown claim status")
        for key in ("figure", "exhibit", "meaning_one_liner", "execution_mode"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError(f"missing {key}")
        if row["status"] != "REMOVED":
            verify_binding(root, row, revision)
        if row["status"] == "SPECIFIED" and "(design rating)" not in row["figure"]:
            raise ValueError("specified figure lacks design rating")
    return ids


def render(document):
    rows = document["figures"]
    by_id = {r["id"]: r for r in rows}
    lines = []
    for row in rows:
        if row["status"] == "REMOVED":
            continue
        text = row["figure"] + " — " + row["meaning_one_liner"]
        if row["id"] in {"fold-multiple", "fold-occupancy"}:
            paired_id = "fold-occupancy" if row["id"] == "fold-multiple" else "fold-multiple"
            paired = by_id.get(paired_id)
            if not paired or paired["status"] == "REMOVED":
                raise ValueError("fold ratio requires paired disclosed quantity")
            text += "; " + paired["figure"] + " — " + paired["meaning_one_liner"]
        if re.search(r"\b(?:2,500|2500)\s+qubits\b|\b5,200\s+FLOPS\b", text, re.I):
            raise ValueError("unscoped qubit or ambiguous FLOPS claim")
        lines.append(f'{row["id"]}: {text} [{row["status"]}; {row["execution_mode"]}]')
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--taxonomy", type=Path, required=True)
    p.add_argument("--rendered", type=Path, required=True)
    a = p.parse_args()
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        doc = json.loads(a.taxonomy.read_text())
        ids = validate_taxonomy(doc, ROOT, revision)
        if a.rendered.read_text() != render(doc):
            raise ValueError("rendered figures differ from taxonomy")
        print(json.dumps({"taxonomy_rows": len(ids), "figure_export": "PASS",
                          "coverage": "INDEPENDENT_REVIEW_REQUIRED", "production": "NOT_ASSESSED"}))
        return 0
    except (OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"figure_export": "FAIL", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
