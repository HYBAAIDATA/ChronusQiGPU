"""Failure-modes-first: every mode has a named truth agent AND a covering
test before the corresponding code may be considered done.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from hyba.operating_model.roles import AGENT, repo_root

DOC_PATH = "docs/failure_modes.json"
TEST_FILE = "tests/test_operating_model.py"

# mode id -> owner agent name; test name convention test_mode_<id>
FAILURE_MODES = [
    ("float_leak_in_gap_kernel", "precision_sentinel"),
    ("hmac_key_reuse", "security_verifier"),
    ("replay_across_cycle_boundary", "security_verifier"),
    ("integer_overflow_at_L20", "math_verifier"),
    ("nondeterministic_dict_iteration", "precision_sentinel"),
    ("retarget_thrash_hardware", "auditor"),
    ("goal_stack_starvation", "auditor"),
    ("folded_ratio_lies", "precision_sentinel"),
    ("non_cptp_measurement_path", "quantum_checker"),
    ("pin_violated_somewhere", "pin_verifier"),
]


def _owner_ok(owner: str) -> bool:
    return owner in AGENT.values()


def _test_exists_for(mode: str, root: Path) -> bool:
    test_file = root / TEST_FILE
    if not test_file.is_file():
        return False
    src = test_file.read_text(encoding="utf-8")
    return re.search(rf"def\s+test_\w*{re.escape(mode)}\w*\s*\(", src) is not None


def write_failure_modes(root: Optional[Path] = None, *, write: bool = True) -> Dict[str, Any]:
    root = repo_root() if root is None else Path(root)
    modes = []
    for mode, owner in FAILURE_MODES:
        assert _owner_ok(owner), f"failure mode {mode} has no truth-agent owner"
        assert _test_exists_for(mode, root), f"failure mode {mode} has no covering test"
        modes.append({"mode": mode, "owner": owner,
                      "test": f"{TEST_FILE}::test_mode_{mode}"})
    doc = {
        "modes": modes,
        "each_has_a_test": True,
        "each_has_an_owner_truth_agent": True,
        "theorem_proven": False,
    }
    if write:
        out = root / DOC_PATH
        out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def failure_modes_documented(root: Optional[Path] = None) -> bool:
    root = repo_root() if root is None else Path(root)
    doc = root / DOC_PATH
    if not doc.is_file():
        return False
    try:
        stored = json.loads(doc.read_text(encoding="utf-8"))
    except Exception:
        return False
    stored_modes = {m["mode"] for m in stored.get("modes", [])}
    return stored_modes == {m for m, _ in FAILURE_MODES} and all(
        _test_exists_for(m, root) for m, _ in FAILURE_MODES
    )
