"""Build-time vendoring for the consumer bundle.

Stages the sibling substrate sources into ``src/`` so the wheel is
self-contained (the sibling distributions are not yet published):

- ``aethel``            — THESEUS storage/custody  (repo root ``aethel/``)
- ``hyba_db``           — OVID data organisation    (repo root ``hyba_db/``)
- ``chronos_one_igpu``  — CHRONOS ONE iGPU fabric   (``chronus/packages/chronos-one-igpu/src``)

Then builds the wheel via ``python -m build``. Staged trees are gitignored
build artifacts — never edit them in place; edit the upstream sources.

Usage::

    python build_bundle.py            # stage + build wheel/sdist into dist/
    python build_bundle.py --stage    # stage only (for local test runs)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

BUNDLED = {
    "aethel": (REPO / "aethel", "hyba-theseus-storage"),
    "hyba_db": (REPO / "hyba_db", "hyba-ovid-data-organisation"),
    "chronus": (
        REPO / "chronus",
        "hyba-chronus-igpu",
    ),
}

_SKIP = {".venv", "dist", "build", "node_modules", "__pycache__", ".git"}


def _ignore(_dir: str, names: list) -> set:
    return {
        n for n in names
        if n in _SKIP or n.endswith((".pyc", ".pyo", ".egg-info"))
    }


def stage(src: Path) -> dict:
    src.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "pythia.consumer.bundle/1", "staged_at": int(time.time()), "products": []}
    for name, (origin, distribution) in BUNDLED.items():
        dest = src / name
        if dest.exists():
            shutil.rmtree(dest)
        if not origin.is_dir():
            raise SystemExit(f"missing bundle source: {origin}")
        shutil.copytree(origin, dest, ignore=_ignore)
        digest = hashlib.sha256(
            b"".join(
                hashlib.sha256(p.read_bytes()).digest()
                for p in sorted(dest.rglob("*")) if p.is_file()
            )
        ).hexdigest()
        manifest["products"].append({
            "namespace": name,
            "distribution": distribution,
            "origin": str(origin.relative_to(REPO)),
            "tree_sha256": digest,
        })
        print(f"staged {name:18s} <- {origin.relative_to(REPO)}  ({digest[:12]})")
    (src / "pythia_consumer" / "bundled_products.json").write_text(
        json.dumps(manifest, indent=1) + "\n"
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", action="store_true", help="stage sources only; do not build")
    ap.add_argument("--out", default="dist", help="build output directory")
    args = ap.parse_args()

    stage(HERE / "src")
    if args.stage:
        return 0
    return subprocess.call(
        [sys.executable, "-m", "build", "--outdir", args.out], cwd=HERE
    )


if __name__ == "__main__":
    raise SystemExit(main())
