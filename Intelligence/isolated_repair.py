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
import math
import os
import shutil
import tempfile
import time
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class RepairAuthorizationError(PermissionError):
    """Raised when repair lacks valid authorization token or touches protected scope."""


class DefectReproductionError(ValueError):
    """Raised when defect cannot be independently reproduced on baseline."""


class RepairValidationError(RuntimeError):
    """Raised when candidate fails independent outcome probe or regression validator."""


class RepairEvidencePersistenceError(RepairValidationError):
    """Outcome custody failed; source_restored is observation, not crash atomicity."""

    def __init__(self, *, source_restored: bool) -> None:
        self.source_restored = source_restored
        super().__init__("Repair evidence persistence failed; " + (
            "baseline restored and read back" if source_restored else
            "source state uncertain: operator reconciliation required; do not retry"))


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
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self._lock = threading.RLock()
        self._records: List[LearningOutcomeRecord] = []
        self._strategy_success_counts: Dict[Tuple[str, str], int] = {}
        self._strategy_total_counts: Dict[Tuple[str, str], int] = {}

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
        self._validate_record(record)
        with self._lock:
            # Do not acknowledge a durable write that failed. Persist the proposed
            # snapshot before making it visible to readers of this instance.
            proposed = [*self._records, record]
            if self.storage_path is not None:
                self._persist(proposed)
            self._records = proposed
            self._recount()
        return record

    def _recount(self) -> None:
        self._strategy_success_counts = {}
        self._strategy_total_counts = {}
        for record in self._records:
            key = (record.issue_type, record.problem_signature)
            self._strategy_total_counts[key] = self._strategy_total_counts.get(key, 0) + 1
            if record.status == "COMMITTED":
                self._strategy_success_counts[key] = self._strategy_success_counts.get(key, 0) + 1

    @staticmethod
    def _validate_record(record: LearningOutcomeRecord) -> None:
        for name in ("record_id", "problem_signature", "issue_type", "target_path", "status"):
            value = getattr(record, name)
            if type(value) is not str or not value:
                raise ValueError("repair outcome requires nonempty " + name)
        for name in ("baseline_sha256", "candidate_sha256"):
            if type(getattr(record, name)) is not str:
                raise ValueError("repair artifact digests must be strings")
        for name in ("pre_probe_reproduced", "post_probe_cleared", "validator_passed"):
            if type(getattr(record, name)) is not bool:
                raise ValueError("repair evidence flags must be booleans")
        for name in ("timestamp", "duration_seconds", "confidence_delta"):
            value = getattr(record, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("repair outcome requires finite " + name)
        if record.duration_seconds < 0:
            raise ValueError("repair duration cannot be negative")
        if record.status == "COMMITTED" and not (
            record.pre_probe_reproduced and record.post_probe_cleared and record.validator_passed
        ):
            raise ValueError("committed outcome requires all recorded verification flags")

    def outcome_statistics(self, issue_type: str, problem_signature: str) -> Dict[str, Any]:
        """Observation-only statistics; not reward authority or certification.

        COMMITTED flags are locally recorded assertions, not independently
        authenticated evidence. An empty population has no empirical rate.
        """
        with self._lock:
            key = (issue_type, problem_signature)
            total = self._strategy_total_counts.get(key, 0)
            successes = self._strategy_success_counts.get(key, 0)
            return {"issue_type": issue_type, "problem_signature": problem_signature,
                    "sample_count": total, "committed_count": successes,
                    "empirical_success_rate": successes / total if total else None,
                    "evidence_class": "LOCAL_REPAIR_OUTCOMES" if total else "NO_OBSERVATIONS",
                    "independently_qualified": False}

    def get_success_rate(self, issue_type: str, problem_signature: str) -> float:
        """Legacy ranking API: 0.5 is an unobserved prior, not an empirical rate.

        New callers should use outcome_statistics() to distinguish no evidence.
        """
        rate = self.outcome_statistics(issue_type, problem_signature)["empirical_success_rate"]
        return 0.5 if rate is None else rate

    def _persist(self, records: List[LearningOutcomeRecord]) -> None:
        """Atomic local snapshot replacement; single writer process per path.

        No cross-process locking, signature, rollback protection or OVID custody
        is implied by this compatibility ledger. It is not a second learner.
        """
        path = self.storage_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".repair-outcomes-", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump([r.as_dict() for r in records], handle, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def save(self) -> None:
        with self._lock:
            self._persist(self._records)

    def load(self) -> None:
        """Validate completely before replacing state; repeated loads are idempotent."""
        with self._lock:
            if self.storage_path is None or not self.storage_path.exists():
                return
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if type(raw) is not list:
                raise ValueError("repair ledger must be a JSON array")
            proposed = [LearningOutcomeRecord(**item) for item in raw]
            ids = set()
            for record in proposed:
                self._validate_record(record)
                if record.record_id in ids:
                    raise ValueError("duplicate repair outcome identity")
                ids.add(record.record_id)
            self._records = proposed
            self._recount()



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
        if learning_ledger is not None and not isinstance(learning_ledger, RepairLearningLedger):
            raise TypeError("existing RepairLearningLedger required")
        self.learning_ledger = learning_ledger if learning_ledger is not None else RepairLearningLedger()
        # Explicit host configuration only. A public default string is not authority.
        supplied = () if authorized_tokens is None else authorized_tokens
        if isinstance(supplied, (str, bytes)):
            raise ValueError("authorized_tokens must be a collection, not a token string")
        supplied = tuple(supplied)
        if any(type(t) is not str or not t for t in supplied):
            raise ValueError("authorized_tokens must contain explicit nonempty host tokens")
        self.authorized_tokens = frozenset(supplied)
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
                reason="Repair authorization denied",
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

        # Step 11: Do not acknowledge publication without its outcome custody.
        # This is best-effort synchronous recovery, not a cross-owner crash
        # transaction or an OS/process boundary.
        duration = time.perf_counter() - start_time
        try:
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
        except Exception as evidence_error:
            restored = False
            rollback_path = None
            try:
                # Never intentionally overwrite an observed third-party change.
                if hashlib.sha256(target.read_bytes()).hexdigest() == candidate_sha:
                    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".repair-recovery-",
                                                     delete=False) as recovery:
                        rollback_path = Path(recovery.name)
                        recovery.write(baseline_bytes)
                        recovery.flush()
                        os.fsync(recovery.fileno())
                    os.replace(rollback_path, target)
                    restored = hashlib.sha256(target.read_bytes()).hexdigest() == baseline_sha
            except Exception:
                restored = False
            finally:
                if rollback_path is not None and rollback_path.exists():
                    try:
                        rollback_path.unlink()
                    except OSError:
                        pass
            raise RepairEvidencePersistenceError(source_restored=restored) from evidence_error

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
        # A local success history must not precede the required ledger write.
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

        self._attempt_history.append(receipt)
        return receipt

    def get_history(self) -> List[RepairAttemptReceipt]:
        return list(self._attempt_history)


__all__ = [
    "RepairAuthorizationError",
    "DefectReproductionError",
    "RepairValidationError",
    "RepairEvidencePersistenceError",
    "RepairAttemptReceipt",
    "LearningOutcomeRecord",
    "RepairLearningLedger",
    "IsolatedRepairExecutor",
]
