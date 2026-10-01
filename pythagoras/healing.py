"""Repository-healing bridge between PYTHAGORAS v12 and Salamander.

PYTHAGORAS proposes and evaluates source candidates. Salamander is the only
component in this bridge that writes them to disk, and it does so through its
existing backup, verification and rollback transaction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .adapter import PythagorasEngineAdapter


class RepositoryHealingOrchestrator:
    """Run v12 evolution and hand verified candidates to Salamander."""

    def __init__(
        self,
        repo_root: Path | str,
        verify_cmd: Optional[str],
        persistent_repo_path: Optional[str] = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.verify_cmd = verify_cmd
        self.adapter = PythagorasEngineAdapter(
            persistent_repo_path=persistent_repo_path,
        )

    def _resolve_target(self, relative_path: str | Path) -> Path:
        target = (self.repo_root / relative_path).resolve()
        if target != self.repo_root and self.repo_root not in target.parents:
            raise ValueError("target must remain inside repo_root")
        if target.suffix != ".py":
            raise ValueError("repository healing currently accepts Python source only")
        if "tests" in target.relative_to(self.repo_root).parts:
            raise ValueError("repository healing never auto-writes test files")
        return target

    def optimize_file(
        self,
        relative_path: str | Path,
        generations: int = 20,
        seed: int = 42,
    ) -> Dict[str, Any]:
        target = self._resolve_target(relative_path)
        if not target.exists():
            raise FileNotFoundError(target)

        original = target.read_text(encoding="utf-8")
        evolution = self.adapter.evolve(
            str(target.relative_to(self.repo_root)),
            original,
            generations=generations,
            seed=seed,
        )
        candidate = str(evolution["final_code"])
        invariants = self.adapter.verify_property_invariants(original, candidate)

        result: Dict[str, Any] = {
            "target": str(target.relative_to(self.repo_root)),
            "candidate_changed": candidate != original,
            "invariants": invariants,
            "evolution": evolution,
            "applied": False,
            "status": "NO_CHANGE" if candidate == original else "PROPOSED",
        }
        if candidate == original:
            return result
        if not invariants["syntax_compilation_invariant"]:
            result["status"] = "REJECTED_STATIC_GATE"
            return result
        if not self.verify_cmd:
            result["status"] = "PROPOSED_AWAITING_VERIFICATION_COMMAND"
            return result

        from Intelligence.salamander_agentic import SalamanderAgenticOptimizer

        salamander = SalamanderAgenticOptimizer(
            repo_root=self.repo_root,
            verify_cmd=self.verify_cmd,
        )
        success, message = salamander.apply_repair_sandboxed(
            target_file=target,
            replacement=candidate,
            test_cmd=self.verify_cmd,
        )
        result["applied"] = success
        result["status"] = "APPLIED" if success else "ROLLED_BACK"
        result["salamander_result"] = message
        result["post_apply_analysis"] = self.adapter.analyze(
            str(target.relative_to(self.repo_root)),
            target.read_text(encoding="utf-8"),
        )
        return result

    def optimize_files(
        self,
        relative_paths: Iterable[str | Path],
        generations: int = 20,
        seed: int = 42,
    ) -> List[Dict[str, Any]]:
        return [
            self.optimize_file(path, generations=generations, seed=seed + index)
            for index, path in enumerate(relative_paths)
        ]
