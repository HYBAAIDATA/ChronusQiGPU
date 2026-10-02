"""Mutation-detecting verification gate for proposal-only self-healing."""
from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .contracts import domain_hash


def _tree_hash(roots: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*.py") if path.is_file())
    for path in sorted(files, key=lambda value: str(value)):
        digest.update(str(path).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class SelfHealingEvidence:
    before_hash: str
    after_hash: str
    mutation_detected: bool
    diagnosis_completed: bool
    proposals: int
    repairs_applied: int
    passed: bool
    generated_at: float
    evidence_hash: str


def verify_proposal_only_self_healing(
    run_diagnosis: Callable[[], Mapping[str, Any]],
    protected_roots: Iterable[str | Path],
) -> SelfHealingEvidence:
    roots = [Path(path) for path in protected_roots]
    before = _tree_hash(roots)
    report = dict(run_diagnosis())
    after = _tree_hash(roots)
    proposals = int(report.get("proposals", 0))
    applied = int(report.get("repairs_applied", 0))
    completed = bool(report.get("diagnosis_completed", False))
    base = {
        "before_hash": before,
        "after_hash": after,
        "mutation_detected": before != after,
        "diagnosis_completed": completed,
        "proposals": proposals,
        "repairs_applied": applied,
        "passed": completed and before == after and applied == 0,
        "generated_at": time.time(),
    }
    return SelfHealingEvidence(
        **base,
        evidence_hash=domain_hash("euclid.self-healing-evidence.v1", base),
    )


__all__ = ["SelfHealingEvidence", "verify_proposal_only_self_healing"]