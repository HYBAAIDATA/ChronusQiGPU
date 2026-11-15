#!/usr/bin/env python3
"""Merge gate: temporary, diagnostic or scratch workflows must never reach main."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKERS = re.compile(r"temporary|not for merge|do not merge|never merge|scratch", re.IGNORECASE)


def offenders(root: Path = ROOT) -> list[str]:
    found = []
    for workflow in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        head = workflow.read_text(encoding="utf-8", errors="replace").splitlines()[:15]
        header = [line for line in head if line.startswith(("name:", "#"))]
        if (
            workflow.name.startswith("zz-")
            or "diagnostic" in workflow.name.lower()
            or any(MARKERS.search(line) for line in header)
        ):
            found.append(workflow.name)
    return found


if __name__ == "__main__":
    bad = offenders()
    if bad:
        print("Remove temporary workflows before merge: " + ", ".join(bad))
        sys.exit(1)
    print("No temporary workflows present.")
