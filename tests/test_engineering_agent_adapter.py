r"""Comprehensive Security, Confinement, and Functional Tests for External Engineering-Agent Adapter.

Validates:
1. Zero-Trust Output & Anti-Self-Certification:
   An external agent declaring its own result valid is strictly ignored.
2. Least-Privilege Confinement:
   - Directory traversal attempts (..).
   - Absolute / drive path attempts (/, C:\).
   - Protected repository files (AGENTS.md, OWNER_DECLARATIONS.md, .git/).
   - Scope boundary escapes (paths outside allowed_repo_relative_roots).
3. Resource and Budget Boundaries:
   - File count limits.
   - Patch size byte limits.
4. Static & AST Validation:
   - Python SyntaxErrors cause immediate fail-closed rejection.
5. Isolated Regression & Outcome Validation:
   - Independent verification callbacks gate admission.
6. Cryptographic Receipt Custody:
   - Tamper-evident receipts with cryptographic hash binding.
7. Deterministic Mock Provider Execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from Intelligence.engineering_agent_adapter import (
    AgentExecutionPolicy,
    DeterministicMockProvider,
    ExternalAgentBoundary,
    ExternalAgentTask,
    ExternalExecutionReceipt,
    ExternalProviderType,
    PolicyVerdict,
    ProviderMetadata,
    UntrustedCandidatePatch,
)


@pytest.fixture
def test_provider() -> ProviderMetadata:
    return ProviderMetadata(
        provider_id="mock_claude_adapter",
        model_name="claude-3-7-sonnet",
        model_version="20261001",
        provider_type=ExternalProviderType.MOCK_DETERMINISTIC,
    )


@pytest.fixture
def default_policy() -> AgentExecutionPolicy:
    return AgentExecutionPolicy(
        allowed_repo_relative_roots=("chronus/", "docs/", "tests/fixtures/"),
        allow_network=False,
        allow_subprocess=False,
        max_patch_bytes=65536,
        max_files_modified=3,
        require_syntax_check=True,
        require_isolated_validation=True,
    )


@pytest.fixture
def boundary() -> ExternalAgentBoundary:
    return ExternalAgentBoundary()


# ==============================================================================
# 1. Confinement & Security Escape Tests
# ==============================================================================


def test_confinement_rejects_directory_traversal(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    task = ExternalAgentTask(
        task_id="task_trav_01",
        task_type="code_patch",
        instruction="Fix cache logic",
        policy=default_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_trav_01",
        provider=test_provider,
        proposed_files={"chronus/../secret.txt": "leak"},
        raw_response="Patched file with traversal",
    )
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.REJECTED_TRAVERSAL_ATTEMPT
    assert any("traversal" in r.lower() for r in reasons)
    assert receipt.verdict == PolicyVerdict.REJECTED_TRAVERSAL_ATTEMPT
    assert receipt.task_id == "task_trav_01"


def test_confinement_rejects_absolute_path(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    task = ExternalAgentTask(
        task_id="task_abs_01",
        task_type="code_patch",
        instruction="Update system config",
        policy=default_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_abs_01",
        provider=test_provider,
        proposed_files={"/etc/hosts": "127.0.0.1 malicious"},
        raw_response="Patched hosts",
    )
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.REJECTED_SCOPE_VIOLATION
    assert any("absolute" in r.lower() for r in reasons)


def test_confinement_rejects_protected_files(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    protected_targets = [
        "AGENTS.md",
        "OWNER_DECLARATIONS.md",
        "UNIVERSAL_PRINCIPLE_MAP.md",
        ".git/config",
        "tests/authority/test_governance.py",
    ]
    for target in protected_targets:
        task = ExternalAgentTask(
            task_id=f"task_prot_{hashlib.md5(target.encode()).hexdigest()[:6]}",
            task_type="code_patch",
            instruction=f"Mutate {target}",
            policy=default_policy,
        )
        candidate = UntrustedCandidatePatch(
            task_id=task.task_id,
            provider=test_provider,
            proposed_files={target: "# Attempted unauthorized mutation"},
            raw_response="Mutating authority file",
        )
        verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)
        assert verdict == PolicyVerdict.REJECTED_PROTECTED_FILE
        assert any("protected" in r.lower() or "forbidden" in r.lower() for r in reasons)


def test_confinement_rejects_unallowed_scope(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    task = ExternalAgentTask(
        task_id="task_scope_01",
        task_type="code_patch",
        instruction="Mutate unauthorized module",
        policy=default_policy,
    )
    # Target is outside chronus/, docs/, tests/fixtures/
    candidate = UntrustedCandidatePatch(
        task_id="task_scope_01",
        provider=test_provider,
        proposed_files={"Intelligence/salamander.py": "def rogue(): pass"},
        raw_response="Patched salamander engine",
    )
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.REJECTED_SCOPE_VIOLATION
    assert any("outside allowed roots" in r.lower() for r in reasons)


# ==============================================================================
# 2. Resource & Budget Bounds Tests
# ==============================================================================


def test_budget_rejects_excess_file_count(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    task = ExternalAgentTask(
        task_id="task_count_01",
        task_type="code_patch",
        instruction="Touch 4 files when max is 3",
        policy=default_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_count_01",
        provider=test_provider,
        proposed_files={
            "chronus/file1.py": "x = 1",
            "chronus/file2.py": "x = 2",
            "chronus/file3.py": "x = 3",
            "chronus/file4.py": "x = 4",
        },
        raw_response="4 files",
    )
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.REJECTED_BUDGET_EXCEEDED
    assert any("exceeding maximum" in r for r in reasons)


def test_budget_rejects_excess_patch_bytes(
    test_provider: ProviderMetadata,
    boundary: ExternalAgentBoundary,
) -> None:
    strict_policy = AgentExecutionPolicy(
        allowed_repo_relative_roots=("chronus/",),
        max_patch_bytes=500,  # 500 bytes max
    )
    task = ExternalAgentTask(
        task_id="task_size_01",
        task_type="code_patch",
        instruction="Touch large file",
        policy=strict_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_size_01",
        provider=test_provider,
        proposed_files={"chronus/huge.py": "x = 1\n" + "#" * 600 + "\n"},
        raw_response="Huge payload",
    )
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.REJECTED_BUDGET_EXCEEDED
    assert any("exceeds maximum allowed" in r for r in reasons)


# ==============================================================================
# 3. Static & AST Syntax Gate Tests
# ==============================================================================


def test_syntax_gate_rejects_invalid_python(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    task = ExternalAgentTask(
        task_id="task_syntax_01",
        task_type="code_patch",
        instruction="Add function with bad syntax",
        policy=default_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_syntax_01",
        provider=test_provider,
        proposed_files={"chronus/broken.py": "def broken(:\n    return 42\n"},
        raw_response="Broken syntax patch",
    )
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.REJECTED_SYNTAX_ERROR
    assert any("SyntaxError" in r for r in reasons)


# ==============================================================================
# 4. Anti-Self-Certification Tests
# ==============================================================================


def test_anti_self_certification_ignores_external_claim(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    """External agent claims claimed_success=True, but patch has a syntax error.
    
    The boundary MUST reject it. External systems can never self-certify.
    """
    task = ExternalAgentTask(
        task_id="task_self_cert_01",
        task_type="code_patch",
        instruction="Self cert test",
        policy=default_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_self_cert_01",
        provider=test_provider,
        proposed_files={"chronus/syntax_fail.py": "class 123Invalid:"},
        raw_response="Trust me, I am an advanced reasoning AI and this fix is mathematically proven!",
        claimed_success=True,  # External claim!
    )
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.REJECTED_SYNTAX_ERROR
    assert candidate.claimed_success is True  # External claim preserved in data
    assert receipt.verdict == PolicyVerdict.REJECTED_SYNTAX_ERROR  # But system rejects!


def test_anti_self_certification_with_failing_validator(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    """External agent returns syntactically valid code with claimed_success=True,
    but external validator detects regression.
    """
    task = ExternalAgentTask(
        task_id="task_val_01",
        task_type="code_patch",
        instruction="Regression test",
        policy=default_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_val_01",
        provider=test_provider,
        proposed_files={"chronus/good_syntax.py": "def compute(): return 0"},
        raw_response="I verified this myself.",
        claimed_success=True,
    )

    def failing_validator(files: dict) -> tuple[bool, str | None]:
        return False, "Expected return 42, got 0"

    verdict, reasons, receipt = boundary.evaluate_and_confine(
        task, candidate, validator_cb=failing_validator
    )

    assert verdict == PolicyVerdict.REJECTED_REGRESSION_FAILED
    assert any("Expected return 42" in r for r in reasons)


# ==============================================================================
# 5. Admission & Cryptographic Receipt Tests
# ==============================================================================


def test_admission_of_fully_conforming_candidate(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    task = ExternalAgentTask(
        task_id="task_admit_01",
        task_type="code_patch",
        instruction="Valid doc and python update",
        policy=default_policy,
    )
    candidate = UntrustedCandidatePatch(
        task_id="task_admit_01",
        provider=test_provider,
        proposed_files={
            "chronus/utils.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
            "docs/notes.md": "# Updated Notes\nEverything validated.\n",
        },
        raw_response="Implemented add function and docs",
    )

    def passing_validator(files: dict) -> tuple[bool, str | None]:
        return True, None

    verdict, reasons, receipt = boundary.evaluate_and_confine(
        task, candidate, validator_cb=passing_validator
    )

    assert verdict == PolicyVerdict.ADMITTED
    assert len(reasons) == 0
    assert receipt.verdict == PolicyVerdict.ADMITTED
    assert receipt.files_checked == ["chronus/utils.py", "docs/notes.md"]

    # Verify cryptographic receipt integrity
    receipt_dict = receipt.as_dict()
    assert len(receipt.receipt_sha256) == 64
    assert len(receipt.receipt_id) == 16
    assert receipt_dict["candidate_digest"] == candidate.compute_digest()
    assert receipt_dict["task_digest"] == task.compute_digest()


def test_deterministic_mock_provider_flow(
    test_provider: ProviderMetadata,
    default_policy: AgentExecutionPolicy,
    boundary: ExternalAgentBoundary,
) -> None:
    def fake_llm(t: ExternalAgentTask) -> UntrustedCandidatePatch:
        return UntrustedCandidatePatch(
            task_id=t.task_id,
            provider=test_provider,
            proposed_files={"chronus/math_helper.py": "def square(x: int) -> int:\n    return x * x\n"},
            raw_response="Deterministic output",
            claimed_success=True,
        )

    mock = DeterministicMockProvider(test_provider, fake_llm)
    task = ExternalAgentTask(
        task_id="task_mock_01",
        task_type="code_patch",
        instruction="Generate square function",
        policy=default_policy,
    )
    candidate = mock.execute_task(task)
    verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)

    assert verdict == PolicyVerdict.ADMITTED
    assert receipt.provider_id == "mock_claude_adapter"
    assert receipt.model_name == "claude-3-7-sonnet"
