#!/usr/bin/env python3
"""Mining capability check. Reports present/absent with file:line; exit 1 on any absent.

Present means a pattern matched. It does not mean the pattern is correct.
Hits in the mock-pool demo (chronus_master_end_to_end_engine.py) count as
present here; read the hit before treating it as a shipped capability.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = {
    ".git", "recovery_merge", "archive", "port-review", "__pycache__", "dist", "build",
    # Third-party code must never satisfy a check (pandas matched the 10**18 literal).
    ".venv", "venv", "site-packages", "node_modules", ".tox",
}

CHECKS = {
    "version_rolling_negotiate": r"version[-_]rolling",
    "version_rolling_mask": r"version_bits|version_mask|vb_mask",
    "nonce_range_partition": r"nonce_(?:range|partition|split)",
    "gpu_nonce_offset": r"(?:gpu|opencl).{0,40}nonce|nonce.{0,40}(?:gpu|opencl)",
    # The shipped cap is named HASHRATE_CAP_EH_S / process_cap, not written as 10**18.
    "budget_cap_1ehs": r"1\s*(?:\*\*\s*)?10\s*\*\*\s*18|1_000_000_000_000_000_000|HASHRATE_CAP_EH_S|process_cap",
    "set_difficulty": r"set_difficulty",
    "clean_jobs_stale": r"clean_jobs",
    "canonical_le_target": r"from_bytes\([^)]*['\"]little['\"]",
    "opencl_known_answer": r"known[_ ]answer",
    "opencl_eligibility_gate": r"(?:eligible|readiness|self[_ ]test)",
    "share_submit": r"mining\.submit|submit_share",
    # Word boundary: a bare "asic" matches "basic".
    "asic_feature_flag": r"\basic\b",
}


def scan() -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {k: [] for k in CHECKS}
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP for part in path.relative_to(ROOT).parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue  # the pattern table would otherwise satisfy every check
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for name, pattern in CHECKS.items():
            for lineno, line in enumerate(text.splitlines(), 1):
                if re.search(pattern, line, re.IGNORECASE):
                    hits[name].append(f"{rel}:{lineno}")
                    break
    return hits


def main() -> int:
    hits = scan()
    absent = [k for k, v in hits.items() if not v]
    for name in CHECKS:
        where = hits[name][0] if hits[name] else "-- ABSENT --"
        print(f"{'ok  ' if hits[name] else 'MISS'} {name:28} {where}  ({len(hits[name])} files)")
    print(f"\n{len(CHECKS) - len(absent)}/{len(CHECKS)} present")
    if absent:
        print("absent: " + ", ".join(absent))
    return 1 if absent else 0


if __name__ == "__main__":
    sys.exit(main())
