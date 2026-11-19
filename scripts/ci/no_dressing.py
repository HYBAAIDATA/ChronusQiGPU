#!/usr/bin/env python3
"""Exact-path wording audit. A token match is a review trigger, not semantic proof.

Usage: python scripts/ci/no_dressing.py [--json] [--baseline] [--write-baseline]
Exit 0: no findings, 2: findings, 1: configuration or I/O error.
Only explicitly reviewed exceptions suppress findings; 'pending' never does.

--baseline is a ratchet over recorded historical debt, not an exception: findings
already listed in scripts/ci/dressing_baseline.json (matched on category, path,
token and a digest of the line text, never on line number) are reported as baselined and do not
fail; any new finding still fails. Entries that no longer occur are reported as
resolved so the baseline can be shrunk with --write-baseline. The baseline must
only shrink: --write-baseline refuses (exit 2) when any finding is not already
recorded, so it can remove resolved debt but never admit new wording.
"""
from __future__ import annotations

import collections
import hashlib
import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = Path("scripts/ci/dressing_policy.json")
BASELINE = Path("scripts/ci/dressing_baseline.json")
BASELINE_SCHEMA = "chronus.dressing-baseline/1"
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
            matches = list(root.glob(path_glob))
            paths = set()
            for match in matches:
                paths.update(match.rglob("*")) if match.is_dir() else paths.add(match)
            for path in sorted(paths):
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
                            # Baseline identity uses the complete line, never the
                            # truncated display preview.
                            "line_sha256_16": hashlib.sha256(
                                line.strip().encode("utf-8")).hexdigest()[:16],
                        })
    return sorted(findings, key=lambda f: (f["path"], f["line"], f["category"], f["word"]))


def _key(f: dict) -> tuple[str, str, str, str]:
    # The complete line is stored as a digest so the baseline never repeats the
    # wording (other gates, e.g. check_forbidden_claims.py, scan every tracked file).
    return (f["category"], f["path"], f["word"].casefold(), f["line_sha256_16"])


def baseline_document(findings: list[dict]) -> dict:
    counts = collections.Counter(_key(f) for f in findings)
    return {
        "schema": BASELINE_SCHEMA,
        "description": "Historical no_dressing findings recorded as debt (ratchet). "
                       "Shrink only; never add entries to admit new wording.",
        "entries": [
            {"category": c, "path": p, "word": w, "line_sha256_16": t, "count": n}
            for (c, p, w, t), n in sorted(counts.items())
        ],
    }


def _budget(document: dict) -> collections.Counter:
    if document.get("schema") != BASELINE_SCHEMA or not isinstance(document.get("entries"), list):
        raise ValueError("unsupported or missing dressing baseline schema/entries")
    budget: collections.Counter = collections.Counter()
    for e in document["entries"]:
        if not isinstance(e, dict) or not isinstance(e.get("count"), int) or e["count"] < 1:
            raise ValueError(f"invalid baseline entry: {e!r}")
        budget[(e["category"], e["path"], str(e["word"]).casefold(), e["line_sha256_16"])] += e["count"]
    return budget


def apply_baseline(findings: list[dict], document: dict) -> tuple[list[dict], int, int]:
    """Return (new findings, baselined count, resolved count)."""
    budget = _budget(document)
    new, baselined = [], 0
    for f in findings:
        k = _key(f)
        if budget[k] > 0:
            budget[k] -= 1
            baselined += 1
        else:
            new.append(f)
    return new, baselined, sum(n for n in budget.values() if n > 0)


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a not in {"--json", "--baseline", "--write-baseline"} for a in args):
        print("usage: no_dressing.py [--json] [--baseline] [--write-baseline]", file=sys.stderr)
        return 1
    try:
        findings = scan(root, json.loads((root / POLICY).read_text(encoding="utf-8")))
        if "--write-baseline" in args:
            # Shrink-only: an existing baseline may lose entries, never gain them.
            # Only the very first baseline (no file yet) may be created from scratch.
            if (root / BASELINE).exists():
                new, _, _ = apply_baseline(
                    findings, json.loads((root / BASELINE).read_text(encoding="utf-8")))
                if new:
                    for f in new:
                        print(f"not in baseline: {f['category']}: {f['path']}:{f['line']}: "
                              f"{f['word']!r}", file=sys.stderr)
                    print(f"refusing to grow the baseline with {len(new)} new findings",
                          file=sys.stderr)
                    return 2
            (root / BASELINE).write_text(
                json.dumps(baseline_document(findings), indent=2) + "\n", encoding="utf-8")
            print(f"wrote {len(findings)} findings to {BASELINE.as_posix()}", file=sys.stderr)
            return 0
        if "--baseline" in args:
            findings, baselined, resolved = apply_baseline(
                findings, json.loads((root / BASELINE).read_text(encoding="utf-8")))
            print(f"{baselined} baselined findings; {resolved} baseline entries resolved"
                  + (" (run --write-baseline to shrink)" if resolved else ""), file=sys.stderr)
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
