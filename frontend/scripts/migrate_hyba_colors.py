#!/usr/bin/env python3
"""One-shot HYBA colour migration: hard-coded hex/rgba → institutional tokens.

Semantic rules:
  - #635bff / blurple rgba → primary (actions) or prize only where explicitly prize
  - #0a2540 ink → oxford
  - muted greys → slate/grey/silver
  - green/red status kept as success/danger
Does not invent hashrate claims; pure class-string rewrite.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"

# Order matters: longer / more specific first.
REPLACEMENTS: list[tuple[str, str]] = [
    # ── Blurple / Stripe leftovers → McKinsey primary (actions & chrome) ──
    ("#635bff", "var(--hyba-primary)"),
    ("#635BFF", "var(--hyba-primary)"),
    ("rgba(99,91,255,0.5)", "rgba(0,102,178,0.5)"),
    ("rgba(99,91,255,0.50)", "rgba(0,102,178,0.5)"),
    ("rgba(99,91,255,0.4)", "rgba(0,102,178,0.4)"),
    ("rgba(99,91,255,0.40)", "rgba(0,102,178,0.4)"),
    ("rgba(99,91,255,0.35)", "rgba(0,102,178,0.35)"),
    ("rgba(99,91,255,0.18)", "rgba(0,102,178,0.18)"),
    ("rgba(99,91,255,0.12)", "rgba(0,102,178,0.12)"),
    ("rgba(99,91,255,0.10)", "rgba(0,102,178,0.10)"),
    ("rgba(99,91,255,0.1)", "rgba(0,102,178,0.10)"),
    ("rgba(99,91,255,0.08)", "rgba(0,102,178,0.08)"),
    ("rgba(99, 91, 255,", "rgba(0, 102, 178,"),
    # Tailwind arbitrary with spaces stripped variants already covered

    # ── Ink / canvas (old Stripe fintech) ──
    ("#0a2540", "var(--hyba-oxford)"),
    ("#0A2540", "var(--hyba-oxford)"),
    ("#f5f7fa", "var(--hyba-cream)"),
    ("#f7f9fc", "var(--hyba-sand-light)"),
    ("#ffffff", "var(--hyba-white)"),
    ("#FFFFFF", "var(--hyba-white)"),

    # ── Muted hierarchy ──
    ("#42566f", "var(--hyba-slate)"),
    ("#42566F", "var(--hyba-slate)"),
    ("#6b7c93", "var(--hyba-grey)"),
    ("#6B7C93", "var(--hyba-grey)"),
    ("#8898aa", "var(--hyba-silver)"),
    ("#8898AA", "var(--hyba-silver)"),
    ("#718096", "var(--hyba-grey)"),

    # ── Secondary blues already close to law ──
    ("#2563eb", "var(--hyba-primary)"),
    ("#2563EB", "var(--hyba-primary)"),
    ("rgba(37,99,235,0.35)", "rgba(0,102,178,0.35)"),
    ("rgba(37,99,235,0.08)", "rgba(0,102,178,0.08)"),
    ("rgba(37, 99, 235,", "rgba(0, 102, 178,"),

    # ── Oxford hairlines (old 10,37,64 ≈ #0a2540) ──
    ("rgba(10,37,64,0.18)", "rgba(0,33,71,0.18)"),
    ("rgba(10,37,64,0.25)", "rgba(0,33,71,0.25)"),
    ("rgba(10,37,64,0.12)", "rgba(0,33,71,0.12)"),
    ("rgba(10,37,64,0.10)", "rgba(0,33,71,0.10)"),
    ("rgba(10,37,64,0.1)", "rgba(0,33,71,0.10)"),
    ("rgba(10,37,64,0.08)", "rgba(0,33,71,0.08)"),
    ("rgba(10,37,64,0.06)", "rgba(0,33,71,0.06)"),
    ("rgba(10,37,64,0.04)", "rgba(0,33,71,0.04)"),
    ("rgba(10, 37, 64,", "rgba(0, 33, 71,"),
    ("rgba(107,124,147,0.35)", "rgba(113,128,150,0.35)"),
    ("rgba(107,124,147,0.08)", "rgba(113,128,150,0.08)"),
    ("rgba(107, 124, 147,", "rgba(113, 128, 150,"),

    # ── Status greens / reds / amber (ops, not brand chrome) ──
    ("#067647", "var(--hyba-success-ink)"),
    ("#047857", "var(--hyba-success)"),
    ("#df1b41", "var(--hyba-danger-bright)"),
    ("#DF1B41", "var(--hyba-danger-bright)"),
    ("#b42318", "var(--hyba-danger)"),
    ("#B42318", "var(--hyba-danger)"),
    ("#b45309", "var(--hyba-orange-dark)"),
    ("#B45309", "var(--hyba-orange-dark)"),
    ("#d97706", "var(--hyba-orange-dark)"),
    ("#5b21b6", "var(--hyba-hypothesis)"),
    ("#5B21B6", "var(--hyba-hypothesis)"),
    ("rgba(91,33,182,0.35)", "rgba(91,33,182,0.35)"),
    ("rgba(91,33,182,0.08)", "rgba(91,33,182,0.08)"),
    ("rgba(180,83,9,0.35)", "rgba(200,90,16,0.35)"),
    ("rgba(180,83,9,0.08)", "rgba(232,108,30,0.08)"),
    ("rgba(180, 83, 9,", "rgba(200, 90, 16,"),

    # ── Amber/warn soft fills often used with b45309 ──
    ("rgba(245,158,11,0.15)", "rgba(232,108,30,0.12)"),
    ("rgba(245,158,11,0.10)", "rgba(232,108,30,0.10)"),
]


def migrate_text(text: str) -> str:
    out = text
    for old, new in REPLACEMENTS:
        out = out.replace(old, new)
    return out


def main() -> None:
    changed: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if path.suffix not in {".tsx", ".ts", ".css"}:
            continue
        if "node_modules" in path.parts:
            continue
        # index.css is already canonical — still run replace for any leftover pythia hex in comments only ok
        raw = path.read_text(encoding="utf-8")
        new = migrate_text(raw)
        if new != raw:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(ROOT)))
    print(f"updated {len(changed)} files")
    for c in changed:
        print(f"  {c}")


if __name__ == "__main__":
    main()
