#!/usr/bin/env python3
"""Check HYBA's internal wheels before they are stored anywhere.

Usage: python scripts/ci/check_wheels.py DIST_DIR [DIST_DIR ...]

Each directory must hold exactly one wheel. The check fails when:
- a wheel lacks the "Private :: Do Not Upload" classifier, which makes the
  public package index refuse an accidental upload;
- two wheels ship the same top-level package, so installing both would
  overwrite files and uninstalling one would break the other;
- a shipped Python module does not compile;
- a wheel carries working files (logs, patches, coverage data, caches).
"""

from __future__ import annotations

import sys
import zipfile
from email.parser import HeaderParser
from pathlib import Path, PurePosixPath

PRIVATE = "Private :: Do Not Upload"
FORBIDDEN_SUFFIXES = (".log", ".patch", ".pyc", ".orig", ".rej")
FORBIDDEN_PARTS = ("__pycache__", ".pytest_cache", ".supervisor")


def inspect(wheel: Path) -> tuple[str, set[str], list[str]]:
    """Return the distribution name, its top-level names and any problems."""
    problems: list[str] = []
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        meta_name = next((n for n in names if n.endswith(".dist-info/METADATA")), None)
        if meta_name is None:
            return wheel.name, set(), [f"{wheel.name}: no METADATA"]
        meta = HeaderParser().parsestr(archive.read(meta_name).decode("utf-8"))
        dist = meta.get("Name", wheel.name)
        if PRIVATE not in (meta.get_all("Classifier") or []):
            problems.append(f"{dist}: missing classifier '{PRIVATE}'")
        tops: set[str] = set()
        for name in names:
            if name.endswith("/"):
                continue
            path = PurePosixPath(name)
            first = path.parts[0]
            if not first.endswith((".dist-info", ".data")):
                tops.add(first[:-3] if first.endswith(".py") else first)
            if (
                path.suffix in FORBIDDEN_SUFFIXES
                or path.name.startswith(".coverage")
                or any(part in FORBIDDEN_PARTS for part in path.parts)
            ):
                problems.append(f"{dist}: working file shipped: {name}")
            if path.suffix == ".py":
                try:
                    compile(archive.read(name), name, "exec", dont_inherit=True)
                except SyntaxError as error:
                    problems.append(f"{dist}: {name} does not compile: {error.msg} (line {error.lineno})")
    return dist, tops, problems


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    owners: dict[str, str] = {}
    problems: list[str] = []
    for directory in argv:
        wheels = sorted(Path(directory).glob("*.whl"))
        if len(wheels) != 1:
            problems.append(f"{directory}: expected exactly one wheel, found {len(wheels)}")
            continue
        dist, tops, found = inspect(wheels[0])
        problems.extend(found)
        for top in sorted(tops):
            if top in owners:
                problems.append(f"top-level '{top}' is shipped by both {owners[top]} and {dist}")
            else:
                owners[top] = dist
        print(f"{dist}: {wheels[0].name}; top-level: {', '.join(sorted(tops))}")
    if problems:
        print("\n".join("FAIL " + problem for problem in problems))
        return 1
    print("Wheel checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
