#!/usr/bin/env python3
"""CI grep-gate: banned mechanism tokens must not appear on external surfaces.

Internal math, execution, tests, and audit ledgers keep full provenance.
This gate only scans customer-visible prefixes defined in chronus.core.seal.
"""

from __future__ import annotations

import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from chronus.core.seal import (  # noqa: E402
    EXTERNAL_SURFACE_PREFIXES,
    find_banned_tokens,
    is_external_surface,
)

# Binary / generated assets that are not customer-readable copy.
SKIP_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".map",
    ".lock",
)


def tracked_files() -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    return [item.decode("utf-8", "surrogateescape") for item in raw if item]


def _read_source_text(path: Path) -> str:
    """Decode an in-scope source file; never silently skip undecodable text."""
    if path.suffix == ".py":
        with path.open("rb") as handle:
            encoding, _ = tokenize.detect_encoding(handle.readline)
        return path.read_bytes().decode(encoding)
    # Non-Python external surfaces are UTF-8; fail closed on decode errors.
    return path.read_text(encoding="utf-8")


def main() -> int:
    violations: list[tuple[str, str]] = []
    scanned = 0
    for rel in tracked_files():
        if not is_external_surface(rel):
            continue
        if rel.endswith(SKIP_SUFFIXES):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = _read_source_text(path)
        except (UnicodeDecodeError, LookupError, SyntaxError) as exc:
            print(
                f"Mechanism seal gate FAILED: cannot decode external surface {rel}: {exc}",
                file=sys.stderr,
            )
            return 1
        scanned += 1
        hits = find_banned_tokens(text)
        if hits:
            violations.append((rel, ", ".join(hits)))

    if violations:
        print("Mechanism seal gate FAILED on external surfaces:", file=sys.stderr)
        for rel, hits in violations:
            print(f"  {rel}: {hits}", file=sys.stderr)
        print(
            f"Scanned {scanned} files under {EXTERNAL_SURFACE_PREFIXES}",
            file=sys.stderr,
        )
        return 1
    print(
        f"Mechanism seal gate OK ({scanned} external files; prefixes={EXTERNAL_SURFACE_PREFIXES})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
