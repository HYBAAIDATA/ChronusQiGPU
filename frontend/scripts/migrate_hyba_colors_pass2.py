#!/usr/bin/env python3
"""Pass 2: residual Stripe/blurple leftovers after first HYBA migration."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS: list[tuple[str, str]] = [
    ("rgba(99,91,255,", "rgba(0,102,178,"),
    ("rgba(99, 91, 255,", "rgba(0, 102, 178,"),
    ("rgba(10,37,64,", "rgba(0,33,71,"),
    ("rgba(10, 37, 64,", "rgba(0, 33, 71,"),
    ("#b4233c", "var(--hyba-danger)"),
    ("#B4233C", "var(--hyba-danger)"),
    ("#9aa8b8", "var(--hyba-silver)"),
    ("#9AA8B8", "var(--hyba-silver)"),
    ("#7c3aed", "var(--hyba-hypothesis)"),
    ("#7C3AED", "var(--hyba-hypothesis)"),
    ("rgba(124,58,237,", "rgba(91,33,182,"),
    ("rgba(124, 58, 237,", "rgba(91, 33, 182,"),
    ("#05070a", "var(--hyba-cream)"),
    ("#e7edf5", "var(--hyba-oxford)"),
    ("#635bff", "var(--hyba-primary)"),
    ("#0a2540", "var(--hyba-oxford)"),
    ("#f5f7fa", "var(--hyba-cream)"),
]


def main() -> None:
    changed = []
    for path in list((ROOT / "src").rglob("*")) + [ROOT / "index.html"]:
        if not path.is_file():
            continue
        if path.suffix not in {".tsx", ".ts", ".css", ".html"}:
            continue
        raw = path.read_text(encoding="utf-8")
        new = raw
        for a, b in REPLACEMENTS:
            new = new.replace(a, b)
        if new != raw:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(ROOT)))
    print(f"pass2 updated {len(changed)}")
    for c in changed:
        print(" ", c)


if __name__ == "__main__":
    main()
