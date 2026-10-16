"""Provider-Neutral External Engineering-Agent Adapter Boundary.

Extends Euclid / Salamander Capability Fabric with a secure policy-gated
adapter for external reasoning, coding, and repair providers.

Key Architecture Invariants:
1. Zero-Trust Output: All external outputs are 'untrusted candidate outputs'.
2. No Self-Certification: An external agent claiming success is untrusted;
   success is determined solely by external deterministic verification,
   confinement bounds, AST validation, reproduction probes, and regression tests.
3. Strict Confinement: File paths, network access, subprocesses, budgets,
   and execution times are bounded by explicit least-privilege policy.
4. Cryptographic Proof: Every interaction produces an immutable,
   tamper-evident execution receipt recording task, provider, raw response,
   digests, policy evaluation, and verdict.
5. Fail-Closed: Ambiguous requests, unauthorized paths, or syntax violations
   halt immediately with explicit rejection receipts.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from Intelligence.capability_fabric import (
    AuthorizationDenied,
    CapabilityExecutionReceipt,
    CapabilityManifest,
    CapabilityPermissions,
    DeterminismClass,
    ExecutionProfile,
    ResourceBudget,
    SideEffectClass,
)


class ExternalProviderType(str, Enum):
    """Known or generic external provider class."""

    MOCK_DETERMINISTIC = "mock_deterministic"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    LOCAL_OLLAMA = "local_ollama"
    CUSTOM_HTTP = "custom_http"


class PolicyVerdict(str, Enum):
    """Evaluation verdict for an untrusted external candidate."""

    ADMITTED = "ADMITTED"
    REJECTED_SCOPE_VIOLATION = "REJECTED_SCOPE_VIOLATION"
    REJECTED_TRAVERSAL_ATTEMPT = "REJECTED_TRAVERSAL_ATTEMPT"
    REJECTED_PROTECTED_FILE = "REJECTED_PROTECTED_FILE"
    REJECTED_BUDGET_EXCEEDED = "REJECTED_BUDGET_EXCEEDED"
    REJECTED_SYNTAX_ERROR = "REJECTED_SYNTAX_ERROR"
    REJECTED_PROBE_FAILED = "REJECTED_PROBE_FAILED"
    REJECTED_REGRESSION_FAILED = "REJECTED_REGRESSION_FAILED"
    REJECTED_UNAUTHORIZED = "REJECTED_UNAUTHORIZED"
    REJECTED_TIMEOUT = "REJECTED_TIMEOUT"


@dataclass(frozen=True)
class ProviderMetadata:
    """Metadata describing the external engineering or reasoning provider."""

    provider_id: str
    model_name: str
    model_version: str
    provider_type: ExternalProviderType = ExternalProviderType.MOCK_DETERMINISTIC
    endpoint_url: Optional[str] = None
    declared_capabilities: Tuple[str, ...] = ("code_patch",)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "provider_type": self.provider_type.value,
            "endpoint_url": self.endpoint_url,
            "declared_capabilities": list(self.declared_capabilities),
        }


@dataclass(frozen=True)
class AgentExecutionPolicy:
    """Least-privilege policy boundary for external agent execution."""

    allowed_repo_relative_roots: Tuple[str, ...] = ("chronus/", "docs/", "tests/fixtures/")
    forbidden_path_substrings: Tuple[str, ...] = (
        ".git/",
        ".github/",
        "AGENTS.md",
        "OWNER_DECLARATIONS.md",
        "UNIVERSAL_PRINCIPLE_MAP.md",
        "tests/authority/",
        "reports/EUCLID_CAPABILITY_MANIFEST.json",
    )
    allow_network: bool = False
    allow_subprocess: bool = False
    max_timeout_seconds: float = 30.0
    max_patch_bytes: int = 131072  # 128 KB
    max_files_modified: int = 5
    require_syntax_check: bool = True
    require_isolated_validation: bool = True

    def validate_target_path(self, repo_relative_path: str) -> Tuple[bool, Optional[str]]:
        """Verify that a relative path conforms strictly to allowed boundaries."""
        clean_path = repo_relative_path.replace("\\", "/").strip()

        # 1. Deny absolute or drive paths
        if clean_path.startswith("/") or (len(clean_path) > 1 and clean_path[1] == ":"):
            return False, f"Absolute path prohibited: {clean_path}"

        # 2. Deny directory traversal
        posix = PurePosixPath(clean_path)
        if ".." in posix.parts:
            return False, f"Directory traversal attempt prohibited: {clean_path}"

        # 3. Deny forbidden critical / authority paths
        for forbidden in self.forbidden_path_substrings:
            if forbidden.endswith("/"):
                if forbidden.rstrip("/") in posix.parts or clean_path.startswith(forbidden):
                    return False, f"Access to forbidden scope prohibited: {clean_path} matches {forbidden}"
            else:
                if forbidden in clean_path:
                    return False, f"Access to protected file prohibited: {clean_path}"

        # 4. Must be under one of the allowed relative roots (if roots are configured)
        if self.allowed_repo_relative_roots:
            is_under_allowed = False
            for root in self.allowed_repo_relative_roots:
                clean_root = root.rstrip("/") + "/"
                if clean_path.startswith(clean_root) or clean_path == root.rstrip("/"):
                    is_under_allowed = True
                    break
            if not is_under_allowed:
                return False, f"Path {clean_path} outside allowed roots {self.allowed_repo_relative_roots}"

        return True, None


@dataclass(frozen=True)
class ExternalAgentTask:
    """Explicitly specified engineering task handed to an external provider."""

    task_id: str
    task_type: str  # e.g., "code_patch", "refactor", "diagnostics"
    instruction: str
    context_files: Dict[str, str] = field(default_factory=dict)
    policy: AgentExecutionPolicy = field(default_factory=AgentExecutionPolicy)

    def compute_digest(self) -> str:
        data = {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "instruction": self.instruction,
            "context_files": self.context_files,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class UntrustedCandidatePatch:
    """Candidate output produced by an external provider, treated as untrusted."""

    task_id: str
    provider: ProviderMetadata
    proposed_files: Dict[str, str]  # repo_relative_path -> proposed_full_content
    raw_response: str
    claimed_success: bool = False
    provider_evidence: Dict[str, Any] = field(default_factory=dict)
    generation_duration_seconds: float = 0.0

    def compute_digest(self) -> str:
        data = {
            "task_id": self.task_id,
            "provider": self.provider.as_dict(),
            "proposed_files": self.proposed_files,
            "raw_response": self.raw_response,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ExternalExecutionReceipt:
    """Cryptographic audit receipt for external agent invocation and policy evaluation."""

    receipt_id: str
    task_id: str
    provider_id: str
    model_name: str
    task_digest: str
    candidate_digest: str
    verdict: PolicyVerdict
    rejection_reasons: List[str]
    timestamp: float
    duration_seconds: float
    files_checked: List[str]
    receipt_sha256: str

    @classmethod
    def create(
        cls,
        *,
        task: ExternalAgentTask,
        candidate: Optional[UntrustedCandidatePatch],
        verdict: PolicyVerdict,
        rejection_reasons: List[str],
        duration_seconds: float,
        files_checked: Optional[List[str]] = None,
    ) -> ExternalExecutionReceipt:
        now = time.time()
        task_digest = task.compute_digest()
        candidate_digest = candidate.compute_digest() if candidate else "none"
        provider_id = candidate.provider.provider_id if candidate else "unknown"
        model_name = candidate.provider.model_name if candidate else "unknown"
        files_checked_list = files_checked or []

        raw_id_str = f"{task.task_id}:{provider_id}:{verdict.value}:{now}"
        receipt_id = hashlib.sha256(raw_id_str.encode()).hexdigest()[:16]

        payload = {
            "receipt_id": receipt_id,
            "task_id": task.task_id,
            "provider_id": provider_id,
            "model_name": model_name,
            "task_digest": task_digest,
            "candidate_digest": candidate_digest,
            "verdict": verdict.value,
            "rejection_reasons": rejection_reasons,
            "timestamp": now,
            "duration_seconds": duration_seconds,
            "files_checked": files_checked_list,
        }
        receipt_sha256 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

        return cls(
            receipt_id=receipt_id,
            task_id=task.task_id,
            provider_id=provider_id,
            model_name=model_name,
            task_digest=task_digest,
            candidate_digest=candidate_digest,
            verdict=verdict,
            rejection_reasons=rejection_reasons,
            timestamp=now,
            duration_seconds=duration_seconds,
            files_checked=files_checked_list,
            receipt_sha256=receipt_sha256,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "task_digest": self.task_digest,
            "candidate_digest": self.candidate_digest,
            "verdict": self.verdict.value,
            "rejection_reasons": self.rejection_reasons,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "files_checked": self.files_checked,
            "receipt_sha256": self.receipt_sha256,
        }


class ExternalAgentBoundary:
    """Rigorous gatekeeper mediating all external engineering interactions."""

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or Path.cwd()

    def evaluate_and_confine(
        self,
        task: ExternalAgentTask,
        candidate: UntrustedCandidatePatch,
        validator_cb: Optional[Callable[[Dict[str, str]], Tuple[bool, Optional[str]]]] = None,
    ) -> Tuple[PolicyVerdict, List[str], ExternalExecutionReceipt]:
        """Evaluate an untrusted candidate against the task policy.
        
        Zero-trust principle: candidate.claimed_success is ignored.
        """
        t_start = time.perf_counter()
        reasons: List[str] = []
        files_checked = list(candidate.proposed_files.keys())

        # 1. Budget Checks: File count
        if len(candidate.proposed_files) > task.policy.max_files_modified:
            reasons.append(
                f"Candidate modifies {len(candidate.proposed_files)} files, exceeding maximum {task.policy.max_files_modified}"
            )
            receipt = ExternalExecutionReceipt.create(
                task=task,
                candidate=candidate,
                verdict=PolicyVerdict.REJECTED_BUDGET_EXCEEDED,
                rejection_reasons=reasons,
                duration_seconds=time.perf_counter() - t_start,
                files_checked=files_checked,
            )
            return PolicyVerdict.REJECTED_BUDGET_EXCEEDED, reasons, receipt

        # 2. Budget Checks: Total patch bytes
        total_bytes = sum(len(content.encode("utf-8")) for content in candidate.proposed_files.values())
        if total_bytes > task.policy.max_patch_bytes:
            reasons.append(
                f"Candidate size {total_bytes} bytes exceeds maximum allowed {task.policy.max_patch_bytes} bytes"
            )
            receipt = ExternalExecutionReceipt.create(
                task=task,
                candidate=candidate,
                verdict=PolicyVerdict.REJECTED_BUDGET_EXCEEDED,
                rejection_reasons=reasons,
                duration_seconds=time.perf_counter() - t_start,
                files_checked=files_checked,
            )
            return PolicyVerdict.REJECTED_BUDGET_EXCEEDED, reasons, receipt

        # 3. Path and Scope Checks
        for path_key in candidate.proposed_files.keys():
            valid, err = task.policy.validate_target_path(path_key)
            if not valid:
                reasons.append(err or f"Invalid path {path_key}")
                # Determine specific verdict
                if "traversal" in (err or "").lower():
                    v = PolicyVerdict.REJECTED_TRAVERSAL_ATTEMPT
                elif "protected" in (err or "").lower() or "forbidden" in (err or "").lower():
                    v = PolicyVerdict.REJECTED_PROTECTED_FILE
                else:
                    v = PolicyVerdict.REJECTED_SCOPE_VIOLATION

                receipt = ExternalExecutionReceipt.create(
                    task=task,
                    candidate=candidate,
                    verdict=v,
                    rejection_reasons=reasons,
                    duration_seconds=time.perf_counter() - t_start,
                    files_checked=files_checked,
                )
                return v, reasons, receipt

        # 4. Syntax and AST Validation for Python files
        if task.policy.require_syntax_check:
            for path_key, content in candidate.proposed_files.items():
                if path_key.endswith(".py"):
                    try:
                        ast.parse(content, filename=path_key)
                    except SyntaxError as e:
                        reasons.append(f"SyntaxError in {path_key}: {e.msg} at line {e.lineno}")
                        receipt = ExternalExecutionReceipt.create(
                            task=task,
                            candidate=candidate,
                            verdict=PolicyVerdict.REJECTED_SYNTAX_ERROR,
                            rejection_reasons=reasons,
                            duration_seconds=time.perf_counter() - t_start,
                            files_checked=files_checked,
                        )
                        return PolicyVerdict.REJECTED_SYNTAX_ERROR, reasons, receipt

        # 5. Domain / Isolated Validation Callback
        if task.policy.require_isolated_validation and validator_cb:
            try:
                passed, val_err = validator_cb(candidate.proposed_files)
                if not passed:
                    reasons.append(val_err or "Isolated validation failed")
                    receipt = ExternalExecutionReceipt.create(
                        task=task,
                        candidate=candidate,
                        verdict=PolicyVerdict.REJECTED_REGRESSION_FAILED,
                        rejection_reasons=reasons,
                        duration_seconds=time.perf_counter() - t_start,
                        files_checked=files_checked,
                    )
                    return PolicyVerdict.REJECTED_REGRESSION_FAILED, reasons, receipt
            except Exception as e:
                reasons.append(f"Exception during isolated validation: {e}")
                receipt = ExternalExecutionReceipt.create(
                    task=task,
                    candidate=candidate,
                    verdict=PolicyVerdict.REJECTED_REGRESSION_FAILED,
                    rejection_reasons=reasons,
                    duration_seconds=time.perf_counter() - t_start,
                    files_checked=files_checked,
                )
                return PolicyVerdict.REJECTED_REGRESSION_FAILED, reasons, receipt

        # All checks passed! Admitted as candidate for publication or execution
        duration = round(time.perf_counter() - t_start, 4)
        receipt = ExternalExecutionReceipt.create(
            task=task,
            candidate=candidate,
            verdict=PolicyVerdict.ADMITTED,
            rejection_reasons=[],
            duration_seconds=duration,
            files_checked=files_checked,
        )
        return PolicyVerdict.ADMITTED, [], receipt


class DeterministicMockProvider:
    """Deterministic fake provider used for security and protocol testing."""

    def __init__(
        self,
        metadata: ProviderMetadata,
        response_generator: Callable[[ExternalAgentTask], UntrustedCandidatePatch],
    ) -> None:
        self.metadata = metadata
        self.response_generator = response_generator

    def execute_task(self, task: ExternalAgentTask) -> UntrustedCandidatePatch:
        return self.response_generator(task)
