#!/usr/bin/env python3
"""RECORD ownership collision scanner for a directory of wheels.

Every installed distribution writes a RECORD of the files it owns. Two wheels
claiming the same site-packages path = namespace collision (the exact defect
the kellogg de-vendoring fixed). This scans wheel RECORDs directly — no install
needed — and reports any path owned by more than one distribution.

Usage: python3 record_collision_scan.py /tmp/pythia-dist [more wheels/dirs...]
Exit 0 = no collisions. Exit 2 = collisions found (details on stdout as JSON).
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


def iter_wheels(paths):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            yield from sorted(p.glob("*.whl"))
        elif p.suffix == ".whl":
            yield p


def record_paths(wheel: Path):
    with zipfile.ZipFile(wheel) as zf:
        recs = [n for n in zf.namelist() if n.endswith(".dist-info/RECORD")]
        if not recs:
            return None
        owned = set()
        for line in zf.read(recs[0]).decode("utf-8", "replace").splitlines():
            path = line.split(",", 1)[0].strip()
            # RECORD rows list the .dist-info files too; only payload paths collide.
            if path and ".dist-info/" not in path and not path.startswith("../"):
                owned.add(path)
        return owned


def main(argv):
    wheels = list(iter_wheels(argv[1:] or ["/tmp/pythia-dist"]))
    if not wheels:
        print(json.dumps({"error": "no wheels found", "scanned": argv[1:]}))
        return 1
    owners = {}
    missing = []
    for w in wheels:
        paths = record_paths(w)
        if paths is None:
            missing.append(w.name)
            continue
        dist = w.name.split("-")[0]
        for path in paths:
            owners.setdefault(path, set()).add(dist)
    collisions = {p: sorted(ds) for p, ds in owners.items() if len(ds) > 1}
    report = {
        "wheels": [w.name for w in wheels],
        "no_record": missing,
        "paths_scanned": len(owners),
        "collisions": collisions,
        "collision_count": len(collisions),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if collisions else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
