"""Fail-closed due-diligence index validator. Private documents stay private."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {"corporate", "financials", "technical_evidence", "contracts", "compliance", "people", "disputes"}
PLACEHOLDER = re.compile(r"\b(?:TBD|TODO|PLACEHOLDER|XXXX)\b|<Name", re.I)
REQUIRED_ROLES = {"support", "dispute", "security", "maintainer", "qc"}


def index_room(room: Path, manifest: dict) -> dict:
    """Validate actual files, digests and named roles from an explicit inventory."""
    room = room.resolve(strict=True)
    folders = manifest["folders"]
    if set(folders) != REQUIRED:
        raise ValueError("required data-room categories differ")
    index = {}
    seen = set()
    for category, items in sorted(folders.items()):
        if not isinstance(items, list) or not items:
            raise ValueError(f"missing category {category}")
        records = []
        for item in items:
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != category:
                raise ValueError("invalid category-scoped path")
            path = (room / relative).resolve(strict=True)
            if not path.is_relative_to(room) or not path.is_file() or path in seen:
                raise ValueError("file outside room, missing or duplicated")
            seen.add(path)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if not raw or item["sha256"] != digest:
                raise ValueError("empty or digest-mismatched file")
            if path.suffix.lower() in {".md", ".txt", ".json", ".csv"}:
                if PLACEHOLDER.search(raw.decode("utf-8")):
                    raise ValueError(f"placeholder content: {relative}")
            if not item.get("owner") or PLACEHOLDER.search(item["owner"]):
                raise ValueError("named owner required")
            records.append({"path": relative.as_posix(), "sha256": digest, "owner": item["owner"]})
        index[category] = records
    actual = {p.resolve() for category in REQUIRED for p in (room / category).rglob("*") if p.is_file()}
    if actual != seen:
        raise ValueError("unindexed room files")
    names = manifest["named_roster"]
    if set(names) != REQUIRED_ROLES:
        raise ValueError("five accountable roles required")
    for role, entry in names.items():
        if not entry["name"].strip() or PLACEHOLDER.search(entry["name"]) or not entry.get("consent_evidence"):
            raise ValueError(f"named and consented human required for {role}")
        # Consent proof is an actual indexed artifact, not a string assertion.
        if entry["consent_evidence"] not in {r["sha256"] for r in index["people"]}:
            raise ValueError(f"missing indexed consent artifact for {role}")
    if names["qc"]["name"].strip().casefold() == names["maintainer"]["name"].strip().casefold():
        raise ValueError("maintainer cannot self-certify independent QC")
    return index


def tests():
    with tempfile.TemporaryDirectory() as d:
        xml = Path(d) / "tests.xml"
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "-o", "addopts=",
                            "tests/test_bookings.py", "tests/test_rider.py", "tests/test_dual_ledger.py",
                            f"--junitxml={xml}"], cwd=ROOT)
        if p.returncode or not xml.exists():
            return False
        cases = list(ET.parse(xml).getroot().iter("testcase"))
        return bool(cases) and all(not any(c.find(tag) is not None for tag in ("failure", "error", "skipped")) for c in cases)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--room", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--period-end", required=True)
    a = p.parse_args()
    try:
        period = date.fromisoformat(a.period_end)
        m = json.loads(a.manifest.read_text())
        index = index_room(a.room, m)
        policy = (ROOT / "docs/accounting/REVREC_POLICY.md").read_text()
        if not all(f"Step {i}" in policy for i in range(1, 6)) or "606-10-32" not in policy:
            raise ValueError("revenue policy step/citation missing")
        if not m.get("accountant_approval_sha256") in {r["sha256"] for r in index["financials"]}:
            raise ValueError("external accountant approval artifact missing")
        cost = m["closed_period_economics"]
        if cost["period_end"] != period.isoformat() or cost["source_sha256"] not in {r["sha256"] for r in index["financials"]}:
            raise ValueError("actual closed-period economics evidence missing")
        if not tests():
            raise ValueError("focused accounting tests failed or skipped")
        print(json.dumps({"index": index, "receipt_tests": "PASS", "data_room_index": "PASS",
                          "scope": "technical validation only; external due diligence not certified"}))
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"data_room_index": "FAIL", "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
