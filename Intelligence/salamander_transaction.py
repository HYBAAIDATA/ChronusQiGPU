"""Fail-closed, single-file repair transactions.

A validator is trusted infrastructure, not candidate code. It must execute baseline
and candidate regression tests outside this process in an OS-enforced sandbox.
No validator is installed by default; local exec/subprocess is not a sandbox.
Transactions serialize cooperating writers and detect intervening content changes.
They do not provide multi-file atomicity or protection from hostile local writers.
"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


def source_digest(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    candidate_digest: str
    baseline_digest: str
    tests_run: int
    isolated: bool
    reason: str


class RepairValidator(Protocol):
    def validate(self, relative_path: Path, baseline: bytes, candidate: bytes) -> ValidationResult:
        """Validate both versions in an externally enforced isolation boundary."""
        ...


@dataclass(frozen=True)
class RepairResult:
    status: str
    reason: str

    @property
    def committed(self) -> bool:
        return self.status == "COMMITTED"


class RepairTransaction:
    """Validate before publication; discard failed candidates without live writes."""

    def __init__(self, repo_root: Path, validator: RepairValidator | None = None):
        self.repo_root = repo_root.resolve()
        self.validator = validator

    def apply(self, target: Path, baseline: bytes, candidate: bytes) -> RepairResult:
        lock_path = None
        lock_fd = None
        staged_path = None
        try:
            target = target.absolute()
            relative = target.relative_to(self.repo_root)
            if target.resolve() != target or any(
                part.is_symlink() for part in (target, *target.parents)
            ):
                return RepairResult("REJECTED", "Symlink targets are not writable")
            if relative.parts[0] not in ("Intelligence", "core_engine", "pythagoras"):
                return RepairResult("REJECTED", "Target is outside repair scope")
            if target.suffix != ".py" or not target.is_file():
                return RepairResult("REJECTED", "Target must be an existing Python file")
            if candidate == baseline:
                return RepairResult("NO_CHANGE", "Candidate is unchanged")
            # Compilation checks syntax without executing candidate code.
            compile(candidate, str(relative), "exec", dont_inherit=True)
            if self.validator is None:
                return RepairResult("BLOCKED", "No isolated regression validator configured")
            lock_path = target.with_name(target.name + ".salamander.lock")
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                return RepairResult("CONFLICT", "Repair lock already exists")
            if target.read_bytes() != baseline:
                return RepairResult("CONFLICT", "Source changed since proposal")
            verdict = self.validator.validate(relative, baseline, candidate)
            if not (
                isinstance(verdict, ValidationResult)
                and verdict.passed is True
                and verdict.isolated is True
                and type(verdict.tests_run) is int
                and verdict.tests_run > 0
                and verdict.candidate_digest == source_digest(candidate)
                and verdict.baseline_digest == source_digest(baseline)
            ):
                return RepairResult("REJECTED", "Missing or failed bound regression evidence")
            fd, name = tempfile.mkstemp(prefix=".salamander-", dir=target.parent)
            staged_path = Path(name)
            with os.fdopen(fd, "wb") as staged:
                staged.write(candidate)
                staged.flush()
                os.fsync(staged.fileno())
            os.chmod(staged_path, stat.S_IMODE(target.stat().st_mode))
            if target.read_bytes() != baseline:
                return RepairResult("CONFLICT", "Source changed during validation")
            os.replace(staged_path, target)
            staged_path = None
            return RepairResult("COMMITTED", "Validated candidate atomically published")
        except (OSError, ValueError, SyntaxError, TypeError) as exc:
            return RepairResult("REJECTED", str(exc))
        except Exception as exc:
            return RepairResult("REJECTED", f"Validator failed: {type(exc).__name__}: {exc}")
        finally:
            if staged_path is not None:
                staged_path.unlink(missing_ok=True)
            if lock_fd is not None:
                os.close(lock_fd)
                lock_path.unlink(missing_ok=True)
