"""Euclid / Salamander Isolated Trusted Repair Execution and Outcome Learning Engine.

Implements the verified 12-stage healing closed loop:
OBSERVE -> DIAGNOSE -> PROPOSE -> AUTHORIZE -> ISOLATE -> APPLY ->
VALIDATE -> PROBE OUTCOME -> COMPARE WITH BASELINE -> COMMIT/ROLLBACK ->
RECORD EVIDENCE -> LEARN FROM VERIFIED OUTCOME

Enforces:
- Clean temporary isolated workspace (no unisolated in-place edits called "sandboxes")
- Pre-change defect reproduction (defect MUST reproduce before repair is admitted)
- Post-change independent outcome probe (defect MUST be absent in candidate)
- External validator regression pass with digest binding
- Protected test and authority boundary exclusions
- Atomic publication with rollback on any failure
- Immutable repair receipt with cryptographic hashes
- Outcome-driven learning ledger (failed repairs preserved as learning evidence)
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class RepairAuthorizationError(PermissionError):
    """Raised when repair lacks valid authorization token or touches protected scope."""


class DefectReproductionError(ValueError):
    """Raised when defect cannot be independently reproduced on baseline."""


class RepairValidationError(RuntimeError):
    """Raised when candidate fails independent outcome probe or regression validator."""


@dataclass(frozen=True)
class RepairAttemptReceipt:
    """Cryptographically anchored receipt of a repair attempt."""

    receipt_id: str
    target_file: str
    baseline_sha256: str
    candidate_sha256: str
    status: str  # COMMITTED, ROLLED_BACK, REJECTED_UNAUTHORIZED, REJECTED_UNREPRODUCED
    pre_probe_defect_detected: bool
    post_probe_defect_cleared: bool
    validator_passed: bool
    timestamp: float
    duration_seconds: float
    reason: str
    receipt_sha256: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LearningOutcomeRecord:
    """Empirical outcome record used to update repair strategies."""

    record_id: str
    problem_signature: str
    issue_type: str
    target_path: str
    baseline_sha256: str
    candidate_sha256: str
    status: str
    pre_probe_reproduced: bool
    post_probe_cleared: bool
    validator_passed: bool
    timestamp: float
    duration_seconds: float
    confidence_delta: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RepairLearningLedger:
    """Records real repair outcomes to improve future repair ranking and prevent repeated mistakes."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path
        self._records: List[LearningOutcomeRecord] = []
        self._strategy_success_counts: Dict[str, int] = {}
        self._strategy_total_counts: Dict[str, int] = {}

    def record_outcome(
        self,
        *,
        problem_signature: str,
        issue_type: str,
        target_path: str,
        baseline_sha256: str,
        candidate_sha256: str,
        status: str,
        pre_probe_reproduced: bool,
        post_probe_cleared: bool,
        validator_passed: bool,
        duration_seconds: float,
    ) -> LearningOutcomeRecord:
        record_id = hashlib.sha256(
            f"{problem_signature}:{target_path}:{time.time()}:{status}".encode()
        ).hexdigest()[:16]

        success = status == "COMMITTED"
        confidence_delta = 0.1 if success else -0.15

        record = LearningOutcomeRecord(
            record_id=record_id,
            problem_signature=problem_signature,
            issue_type=issue_type,
            target_path=target_path,
            baseline_sha256=baseline_sha256,
            candidate_sha256=candidate_sha256,
            status=status,
            pre_probe_reproduced=pre_probe_reproduced,
            post_probe_cleared=post_probe_cleared,
            validator_passed=validator_passed,
            timestamp=time.time(),
            duration_seconds=duration_seconds,
            confidence_delta=confidence_delta,
        )
        self._records.append(record)

        # Update empirical strategy counts
        key = f"{issue_type}:{problem_signature}"
        self._strategy_total_counts[key] = self._strategy_total_counts.get(key, 0) + 1
        if success:
            self._strategy_success_counts[key] = self._strategy_success_counts.get(key, 0) + 1

        if self.storage_path:
            try:
                self.save()
            except Exception:
                pass

        return record

    def get_success_rate(self, issue_type: str, problem_signature: str) -> float:
        """Return empirical historical success rate in [0.0, 1.0]."""
        key = f"{issue_type}:{problem_signature}"
        total = self._strategy_total_counts.get(key, 0)
        if total == 0:
            return 0.5  # Neutral prior
        return self._strategy_success_counts.get(key, 0) / total

    def save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.as_dict() for r in self._records]
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self._records = [LearningOutcomeRecord(**item) for item in raw]
            for r in self._records:
                key = f"{r.issue_type}:{r.problem_signature}"
                self._strategy_total_counts[key] = self._strategy_total_counts.get(key, 0) + 1
                if r.status == "COMMITTED":
                    self._strategy_success_counts[key] = (
                        self._strategy_success_counts.get(key, 0) + 1
                    )
        except Exception:
            pass


class IsolatedRepairExecutor:
    """Executes code repairs inside a disposable temporary filesystem sandbox."""

    def __init__(
        self,
        repo_root: Path,
        *,
        learning_ledger: Optional[RepairLearningLedger] = None,
        authorized_tokens: Optional[Sequence[str]] = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.learning_ledger = learning_ledger or RepairLearningLedger()
        self.authorized_tokens = set(authorized_tokens or ["INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR"])
        self._attempt_history: List[RepairAttemptReceipt] = []

    def _is_scope_permitted(self, target_file: Path) -> bool:
        """Check that the target path is strictly within the allowed repair boundary."""
        target = target_file.resolve()
        try:
            rel = target.relative_to(self.repo_root)
        except ValueError:
            return False  # Path outside repository root

        rel_str = str(rel).replace("\\", "/")
        parts = rel.parts

        # 1. Tests are strictly protected from self-repair
        if (
            "tests" in parts
            or rel.name.startswith("test_")
            or rel.name.endswith("_test.py")
            or rel.name == "conftest.py"
        ):
            return False

        # 2. Authority files are protected
        if rel_str in (
            "OWNER_DECLARATIONS.md",
            "UNIVERSAL_PRINCIPLE_MAP.md",
            "AGENTS.md",
            "GEMINI.md",
        ):
            return False

        # 3. Only Python source files are admitted
        if target.suffix != ".py":
            return False

        return True

    def execute_closed_loop_repair(
        self,
        *,
        target_file: Path,
        replacement_code: str,
        defect_probe: Callable[[Path], bool],
        validator_fn: Callable[[str, str, Path], bool],
        authorization_token: str,
        issue_type: str = "ast_defect",
        problem_signature: str = "generic_repair",
    ) -> RepairAttemptReceipt:
        """Run the full 12-stage verified healing loop in an isolated workspace."""
        start_time = time.perf_counter()
        target = target_file.resolve()

        # Step 1: Authorization Gate
        if authorization_token not in self.authorized_tokens:
            duration = time.perf_counter() - start_time
            return self._record_attempt(
                target_file=str(target),
                baseline_sha="",
                candidate_sha="",
                status="REJECTED_UNAUTHORIZED",
                pre_probe=False,
                post_probe=False,
                val_passed=False,
                duration=duration,
                reason=f"Invalid authorization token '{authorization_token}'",
                issue_type=issue_type,
                signature=problem_signature,
            )

        # Step 2: Scope and Boundary Check
        if not self._is_scope_permitted(target):
            duration = time.perf_counter() - start_time
            return self._record_attempt(
                target_file=str(target),
                baseline_sha="",
                candidate_sha="",
                status="REJECTED_SCOPE_VIOLATION",
                pre_probe=False,
                post_probe=False,
                val_passed=False,
                duration=duration,
                reason="Target path is outside permitted repair scope or is a protected test/authority file",
                issue_type=issue_type,
                signature=problem_signature,
            )

        if not target.exists() or not target.is_file():
            duration = time.perf_counter() - start_time
            return self._record_attempt(
                target_file=str(target),
                baseline_sha="",
                candidate_sha="",
                status="REJECTED_FILE_NOT_FOUND",
                pre_probe=False,
                post_probe=False,
                val_passed=False,
                duration=duration,
                reason="Target file does not exist or is not a regular file",
                issue_type=issue_type,
                signature=problem_signature,
            )

        # Step 3: Baseline Snapshot
        baseline_bytes = target.read_bytes()
        baseline_sha = hashlib.sha256(baseline_bytes).hexdigest()

        # Step 4: Pre-Change Defect Reproduction
        # The probe MUST return True on baseline, confirming the defect is genuinely reproduced!
        try:
            pre_defect_detected = defect_probe(target)
        except Exception as exc:
            pre_defect_detected = False

        if not pre_defect_detected:
            duration = time.perf_counter() - start_time
            return self._record_attempt(
                target_file=str(target),
                baseline_sha=baseline_sha,
                candidate_sha="",
                status="REJECTED_UNREPRODUCED",
                pre_probe=False,
                post_probe=False,
                val_passed=False,
                duration=duration,
                reason="Target defect could not be reproduced on baseline; repair aborted to avoid false intervention",
                issue_type=issue_type,
                signature=problem_signature,
            )

        # Step 5: Syntax Validation of Candidate
        try:
            ast.parse(replacement_code, filename=str(target))
        except SyntaxError as syn_err:
            duration = time.perf_counter() - start_time
            return self._record_attempt(
                target_file=str(target),
                baseline_sha=baseline_sha,
                candidate_sha="",
                status="REJECTED_SYNTAX_ERROR",
                pre_probe=True,
                post_probe=False,
                val_passed=False,
                duration=duration,
                reason=f"Candidate code has syntax error: {syn_err}",
                issue_type=issue_type,
                signature=problem_signature,
            )

        candidate_bytes = replacement_code.encode("utf-8")
        candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()

        # Step 6: Isolated Workspace Creation
        with tempfile.TemporaryDirectory(prefix="salamander_isolated_") as sandbox_dir:
            sandbox_path = Path(sandbox_dir)
            sandboxed_file = sandbox_path / target.name
            sandboxed_file.write_bytes(candidate_bytes)

            # Step 7: Post-Change Independent Defect Probe in Isolation
            # The probe MUST return False on candidate, proving the defect is cleared!
            try:
                candidate_defect_detected = defect_probe(sandboxed_file)
            except Exception:
                candidate_defect_detected = True

            post_probe_cleared = not candidate_defect_detected
            if not post_probe_cleared:
                duration = time.perf_counter() - start_time
                return self._record_attempt(
                    target_file=str(target),
                    baseline_sha=baseline_sha,
                    candidate_sha=candidate_sha,
                    status="ROLLED_BACK",
                    pre_probe=True,
                    post_probe=False,
                    val_passed=False,
                    duration=duration,
                    reason="Independent defect probe still detected failure on candidate code in sandbox",
                    issue_type=issue_type,
                    signature=problem_signature,
                )

            # Step 8: Isolated Regression Validator Pass
            try:
                validator_passed = validator_fn(baseline_sha, candidate_sha, sandboxed_file)
            except Exception:
                validator_passed = False

            if not validator_passed:
                duration = time.perf_counter() - start_time
                return self._record_attempt(
                    target_file=str(target),
                    baseline_sha=baseline_sha,
                    candidate_sha=candidate_sha,
                    status="ROLLED_BACK",
                    pre_probe=True,
                    post_probe=True,
                    val_passed=False,
                    duration=duration,
                    reason="External regression validator failed or rejected the candidate in sandbox",
                    issue_type=issue_type,
                    signature=problem_signature,
                )

            # Step 9: Atomic Publication to Source Repository
            try:
                temp_swap = target.with_suffix(".tmp_heal")
                temp_swap.write_bytes(candidate_bytes)
                os.replace(temp_swap, target)
            except Exception as exc:
                duration = time.perf_counter() - start_time
                # Rollback if partial
                if temp_swap.exists():
                    try:
                        temp_swap.unlink()
                    except Exception:
                        pass
                return self._record_attempt(
                    target_file=str(target),
                    baseline_sha=baseline_sha,
                    candidate_sha=candidate_sha,
                    status="ROLLED_BACK",
                    pre_probe=True,
                    post_probe=True,
                    val_passed=True,
                    duration=duration,
                    reason=f"Atomic file publication failed: {exc}",
                    issue_type=issue_type,
                    signature=problem_signature,
                )

            # Step 10: Post-Publication Integrity Check
            published_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if published_sha != candidate_sha:
                # Rollback
                target.write_bytes(baseline_bytes)
                duration = time.perf_counter() - start_time
                return self._record_attempt(
                    target_file=str(target),
                    baseline_sha=baseline_sha,
                    candidate_sha=candidate_sha,
                    status="ROLLED_BACK",
                    pre_probe=True,
                    post_probe=True,
                    val_passed=True,
                    duration=duration,
                    reason="Post-publication digest mismatch; source reverted to baseline",
                    issue_type=issue_type,
                    signature=problem_signature,
                )

        # Step 11: Success Receipt and Learning Record
        duration = time.perf_counter() - start_time
        return self._record_attempt(
            target_file=str(target),
            baseline_sha=baseline_sha,
            candidate_sha=candidate_sha,
            status="COMMITTED",
            pre_probe=True,
            post_probe=True,
            val_passed=True,
            duration=duration,
            reason="Closed-loop verified: reproduced on baseline, cleared in sandbox, passed validator, published atomically",
            issue_type=issue_type,
            signature=problem_signature,
        )

    def _record_attempt(
        self,
        *,
        target_file: str,
        baseline_sha: str,
        candidate_sha: str,
        status: str,
        pre_probe: bool,
        post_probe: bool,
        val_passed: bool,
        duration: float,
        reason: str,
        issue_type: str,
        signature: str,
    ) -> RepairAttemptReceipt:
        now = time.time()
        receipt_id = hashlib.sha256(
            f"{target_file}:{baseline_sha}:{candidate_sha}:{status}:{now}".encode()
        ).hexdigest()[:16]

        payload = {
            "receipt_id": receipt_id,
            "target_file": target_file,
            "baseline_sha256": baseline_sha,
            "candidate_sha256": candidate_sha,
            "status": status,
            "pre_probe_defect_detected": pre_probe,
            "post_probe_defect_cleared": post_probe,
            "validator_passed": val_passed,
            "timestamp": now,
            "duration_seconds": round(duration, 4),
            "reason": reason,
        }
        receipt_sha256 = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        receipt = RepairAttemptReceipt(
            receipt_id=receipt_id,
            target_file=target_file,
            baseline_sha256=baseline_sha,
            candidate_sha256=candidate_sha,
            status=status,
            pre_probe_defect_detected=pre_probe,
            post_probe_defect_cleared=post_probe,
            validator_passed=val_passed,
            timestamp=now,
            duration_seconds=round(duration, 4),
            reason=reason,
            receipt_sha256=receipt_sha256,
        )
        self._attempt_history.append(receipt)

        # Update learning ledger with honest outcome
        self.learning_ledger.record_outcome(
            problem_signature=signature,
            issue_type=issue_type,
            target_path=target_file,
            baseline_sha256=baseline_sha,
            candidate_sha256=candidate_sha,
            status=status,
            pre_probe_reproduced=pre_probe,
            post_probe_cleared=post_probe,
            validator_passed=val_passed,
            duration_seconds=round(duration, 4),
        )

        return receipt

    def get_history(self) -> List[RepairAttemptReceipt]:
        return list(self._attempt_history)


__all__ = [
    "RepairAuthorizationError",
    "DefectReproductionError",
    "RepairValidationError",
    "RepairAttemptReceipt",
    "LearningOutcomeRecord",
    "RepairLearningLedger",
    "IsolatedRepairExecutor",
]
