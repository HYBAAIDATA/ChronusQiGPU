"""Production drift gate (item 6.2).

Enforces that:
1. Every contract double carries a traceability link to the production component it stands in for.
2. Every contract double carries an explicit TODO-gate.
3. Merge/production release is prevented while a production-path implementation is pending.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def audit_contract_double(cls: Any) -> List[str]:
    """Audit a class representing a contract double for traceability and TODO-gate."""
    issues = []
    if not getattr(cls, "__contract_double__", False):
        return issues

    target = getattr(cls, "__production_target__", None)
    if not target or not isinstance(target, str):
        issues.append(f"{cls.__name__} missing __production_target__ traceability link")

    todo_gate = getattr(cls, "__todo_gate__", None)
    if not todo_gate or not isinstance(todo_gate, str) or "TODO-GATE" not in todo_gate:
        issues.append(f"{cls.__name__} missing explicit TODO-gate in __todo_gate__")

    return issues


def check_production_merge_blocker(
    contract_doubles: List[Any], target_env: str = "production"
) -> Tuple[bool, str]:
    """Assert that contract doubles prevent merge to production while production paths are missing."""
    if target_env.lower() in ("production", "prod", "main_release"):
        blocked = [
            f"{cls.__name__} ({getattr(cls, '__todo_gate__', 'unresolved')})"
            for cls in contract_doubles
            if getattr(cls, "__contract_double__", False)
        ]
        if blocked:
            return False, f"Merge blocked by active TODO-gates: {'; '.join(blocked)}"
    return True, "OK for local/test validation"


if __name__ == "__main__":
    from tests.frontier_agent.conftest import FileAdapter

    issues = audit_contract_double(FileAdapter)
    if issues:
        print(f"[FAIL] Contract double audit failed: {issues}")
        sys.exit(1)
    print("[PASS] Contract double traceability and TODO-gates verified.")
    sys.exit(0)
