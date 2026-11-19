"""scripts/ci/audit_manifests.py — audit every qualification manifest in the tree.

Runs the manifest auditor over the committed manifest set and reports one
aggregate number: how many manifests carry a blocking finding.

The set is the root qualification manifest plus every file in manifests/.
A file in that directory that cannot be parsed is itself a defect: it is
catalogued as a manifest but is not one, so it is reported and counted.

Exit codes: 0 no blocking findings, 2 one or more blocking findings, 1 the
manifest set could not be located.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_manifest  # noqa: E402  (sibling module, path set above)

ROOT = Path(__file__).resolve().parents[2]
ROOT_MANIFEST = ROOT / "manifests" / "historical" / "PRODUCTION_QUALIFIED.json"
MANIFEST_DIR = ROOT / "manifests"


def manifest_paths(root: Path = ROOT) -> list[Path]:
    """Return the manifest set: the root manifest then manifests/*.json."""
    paths: list[Path] = []
    if ROOT_MANIFEST.exists():
        paths.append(ROOT_MANIFEST)
    if MANIFEST_DIR.is_dir():
        paths.extend(sorted(MANIFEST_DIR.glob("*.json")))
    return paths


def audit_file(path: Path) -> tuple[int, list[str], list[str]]:
    """Return (blocking count, blocking findings, notes) for one file."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return 1, [f"cannot be read as a manifest: {exc}"], []
    if not isinstance(doc, dict):
        return 1, ["manifest is not a JSON object"], []

    relative = path.relative_to(ROOT).as_posix()
    blocking = audit_manifest.blocking_findings(doc, relative)
    catalogued = audit_manifest.findings(doc)
    notes: list[str] = []
    if catalogued and not blocking:
        notes.append(
            f"{len(catalogued)} finding(s) catalogued as historical "
            "(not blocking)"
        )
    return len(blocking), blocking, notes


def main(argv: list[str] | None = None) -> int:
    del argv
    paths = manifest_paths()
    if not paths:
        print("no qualification manifests found", file=sys.stderr)
        return 1

    total = 0
    for path in paths:
        blocking, details, notes = audit_file(path)
        total += blocking
        label = path.relative_to(ROOT).as_posix()
        print(f"--- {label}: {blocking} blocking finding(s)")
        for detail in details:
            print(f"    FAIL {detail}")
        for note in notes:
            print(f"    {note}")

    print(f"TOTAL blocking findings: {total}")
    return 2 if total else 0


if __name__ == "__main__":
    sys.exit(main())
