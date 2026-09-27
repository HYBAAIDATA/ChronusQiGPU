"""Fail the release if a JavaScript/TypeScript mining backend reappears."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
FORBIDDEN = (
    re.compile(r"mining\.(?:subscribe|notify|submit)"),
    re.compile(r"\bStratum(?:Tcp)?Client\b"),
    re.compile(r"\bnet\.Socket\b"),
    re.compile(r"createHash\s*\(", re.IGNORECASE),
)
EXCLUDED_PARTS = {"node_modules", "dist", ".git", "tests", "test"}


def main() -> int:
    violations: list[str] = []
    for path in ROOT.rglob("*"):
        if path.suffix not in ACTIVE_EXTENSIONS or any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                violations.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")
    required = {
        "src/lib/api.ts": ROOT / "src/lib/api.ts",
        "src/App.tsx": ROOT / "src/App.tsx",
        "mla1517_platform_v3.4/python/control_api.py": ROOT / "mla1517_platform_v3.4/python/control_api.py",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        violations.extend(f"missing canonical API file: {name}" for name in missing)
    if violations:
        print("PYTHIA canonical backend gate: FAIL")
        print("\n".join(violations))
        return 1
    print("PYTHIA canonical backend gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
