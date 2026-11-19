"""Fail a release whose tag does not carry the single-source Chronus version.

The version is declared once, as ``chronus.__version__`` in src/chronus/__init__.py.
A release tag must be ``v<version>`` or ``v<version>-<suffix>`` (for example
``v37.0.0.dev0-internal``). The built wheel and sdist names must carry the same
version.

Usage: python scripts/ci/check_release_version.py --tag v37.0.0.dev0 [--dist dist]
Exit codes: 0 consistent, 1 mismatch, 2 bad input.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECLARATION = re.compile(r'^__version__ = "([^"]+)"\s*$', re.M)


def declared_version(root: Path = ROOT) -> str:
    match = DECLARATION.search((root / "src" / "chronus" / "__init__.py").read_text(encoding="utf-8"))
    if not match:
        raise ValueError("chronus.__version__ is not declared as a plain string literal")
    return match.group(1)


def check(tag: str, version: str, dist: Path | None = None) -> list[str]:
    problems = []
    tag = tag.removeprefix("refs/tags/")
    if not (tag == f"v{version}" or tag.startswith(f"v{version}-")):
        problems.append(f"tag {tag!r} does not carry chronus.__version__ {version!r} (expected 'v{version}' or 'v{version}-<suffix>')")
    if dist is not None:
        expected = {f"hyba_chronus-{version}-py3-none-any.whl", f"hyba_chronus-{version}.tar.gz"}
        present = {p.name for p in dist.iterdir() if p.is_file()}
        for name in sorted(expected - present):
            problems.append(f"expected artifact {name} is missing from {dist}")
        for name in sorted(present - expected):
            problems.append(f"unexpected file {name} in {dist} (only the exact {version} wheel and sdist may be published)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--dist", type=Path)
    args = ap.parse_args(argv)
    try:
        version = declared_version()
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    problems = check(args.tag, version, args.dist)
    for p in problems:
        print(f"FAIL: {p}", file=sys.stderr)
    if not problems:
        print(f"release version consistent: {version}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
