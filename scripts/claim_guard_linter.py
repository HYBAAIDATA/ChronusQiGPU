"""Claim guard documentation linter enforcing the EUCLID no-claims clause (6.5).

Enforces:
- No AGI/ASI operational claims
- No scientific model superiority claims
- No Millennium prize proof claims
- No quantum speedup or quantum supremacy claims
- No unauthorized merge/release/deployment authorizations
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

PROHIBITED_PATTERNS = [
    (
        r"(?<!no\s)(?<!not\s)(?<!zero\s)(?<!neither\s)\b(?:AGI|ASI)\s+(?:achieved|operational|demonstrated|realized)\b",
        "AGI/ASI operational claim",
    ),
    (
        r"(?<!no\s)(?<!not\s)(?<!zero\s)\b(?:model\s+)?superiority\s+(?:proven|demonstrated|achieved|established)\b",
        "Scientific model superiority claim",
    ),
    (
        r"(?<!no\s)(?<!not\s)\b(?:Millennium\s+Prize|Riemann\s+Hypothesis|P\s*vs\s*NP)\s+(?:is\s+)?(?:solved|proven|settled)\b",
        "Prize-proof / Millennium problem claim",
    ),
    (
        r"(?<!no\s)(?<!not\s)(?<!without\s)\bquantum\s+(?:speedup|supremacy|advantage)\s+(?:achieved|proven|demonstrated)\b",
        "Quantum speedup / quantum supremacy claim",
    ),
    (
        r"(?<!no\s)(?<!not\s)(?<!without\s)\b(?:authorized|approved)\s+for\s+(?:main\s+merge|production\s+release|production\s+deployment)\b",
        "Unauthorized merge/release/deployment authorization claim",
    ),
]


def check_content(content: str) -> List[Tuple[int, str, str]]:
    """Scan content line-by-line for prohibited claim statements.

    Returns list of (line_number, line_snippet, violation_description).
    """
    violations = []
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        # Ignore markdown blockquotes or explicit disclaimer markers
        stripped = line.strip().lower()
        if stripped.startswith("no ") or stripped.startswith("> no ") or "no-claims" in stripped:
            continue
        for pattern, desc in PROHIBITED_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append((idx, line.strip(), desc))
    return violations


def lint_file(file_path: Path) -> List[Tuple[int, str, str]]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    return check_content(text)


def lint_docs(target_dir: Path) -> int:
    all_violations = 0
    for path in target_dir.rglob("*.md"):
        violations = lint_file(path)
        if violations:
            all_violations += len(violations)
            print(f"[FAIL] {path}:")
            for line_no, snippet, desc in violations:
                print(f"  Line {line_no}: [{desc}] {snippet}")
    return 0 if all_violations == 0 else 1


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs")
    sys.exit(lint_docs(target))
