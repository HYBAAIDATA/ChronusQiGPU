#!/usr/bin/env python3
"""Exact-path wording audit. A token match is a review trigger, not semantic proof.

Usage: python scripts/ci/no_dressing.py [--json]
Exit 0: no findings, 2: findings, 1: configuration or I/O error.
Only explicitly reviewed exceptions suppress findings; 'pending' never does.
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = Path("scripts/ci/dressing_policy.json")
SKIP = frozenset({".git", "node_modules", "__pycache__", ".venv", "archive", "vendor"})
EXTENSIONS = frozenset({".py", ".md", ".ts", ".tsx"})


def matcher(words: list[str]) -> re.Pattern[str]:
    if not words or any(not isinstance(w, str) or not w.strip() for w in words):
        raise ValueError("word list must contain nonempty strings")
    parts = []
    for word in sorted(words, key=len, reverse=True):
        if word.casefold() == "simulat":  # Intentional stem: simulate, simulated, simulation.
            parts.append(r"\bsimulat\w*")
        elif word.endswith("("):
            parts.append(r"(?<!\w)" + re.escape(word))
        else:
            parts.append(r"(?<!\w)" + re.escape(word) + r"(?!\w)")
    return re.compile("|".join(parts), re.IGNORECASE)


def allowed(relative: str, word: str, allow: list[dict]) -> bool:
    """Wildcard path plus exact token; pending/unreviewed exceptions never activate."""
    return any(
        entry["word"].casefold() == word.casefold()
        and fnmatch.fnmatchcase(relative, entry["path"])
        and str(entry.get("reason", "")).strip()
        and str(entry.get("reviewer", "")).strip().casefold() not in {"", "pending"}
        for entry in allow
    )


def scan(root: Path, policy: dict) -> list[dict]:
    if policy.get("schema") != "chronus.dressing/1" or not isinstance(policy.get("categories"), dict):
        raise ValueError("unsupported or missing dressing policy schema/categories")
    allow = policy.get("allow", [])
    if not isinstance(allow, list) or any(
        not isinstance(e, dict) or not isinstance(e.get("word"), str)
        or not isinstance(e.get("path"), str) or not isinstance(e.get("reason"), str)
        or not isinstance(e.get("reviewer"), str)
        for e in allow
    ):
        raise ValueError("allow entries require path, word, reason and reviewer")
    findings: list[dict] = []
    for category, rule in policy["categories"].items():
        if not isinstance(rule, dict) or not rule.get("paths"):
            raise ValueError(f"{category}: missing paths")
        pattern = matcher(rule["words"])
        exempt = rule.get("exempt", [])
        seen: set[Path] = set()
        for path_glob in rule["paths"]:
            for path in sorted(root.glob(path_glob)):
                if not path.is_file() or path.suffix not in EXTENSIONS or path in seen:
                    continue
                seen.add(path)
                relative = path.relative_to(root).as_posix()
                if any(part in SKIP for part in path.relative_to(root).parts):
                    continue
                if any(fnmatch.fnmatchcase(relative, e) for e in exempt):
                    continue
                for number, line in enumerate(
                    path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    for hit in pattern.finditer(line):
                        if allowed(relative, hit.group(), allow):
                            continue
                        findings.append({
                            "category": category, "path": relative, "line": number,
                            "word": hit.group(), "text": line.strip()[:100],
                        })
    return sorted(findings, key=lambda f: (f["path"], f["line"], f["category"], f["word"]))


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a not in {"--json"} for a in args):
        print("usage: no_dressing.py [--json]", file=sys.stderr)
        return 1
    try:
        findings = scan(root, json.loads((root / POLICY).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"dressing policy scan failed: {exc}", file=sys.stderr)
        return 1
    if "--json" in args:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['category']}: {f['path']}:{f['line']}: {f['word']!r} — {f['text']}")
    print(f"{len(findings)} findings", file=sys.stderr)
    return 2 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
