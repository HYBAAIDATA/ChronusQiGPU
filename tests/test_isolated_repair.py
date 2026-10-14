"""Tests for Euclid / Salamander Isolated Trusted Repair and Learning Engine.

Validates the complete 12-stage closed-loop repair protocol:
1. Authorization token enforcement.
2. Scope confinement (rejection of tests, authority files, non-python, and out-of-tree paths).
3. Pre-change defect reproduction (refusal to act if defect cannot be reproduced on baseline).
4. Candidate AST syntax validation.
5. Sandbox isolation (defect probe and regression validator evaluated in disposable temporary environment).
6. Sandbox rollback on probe failure or validator rejection (baseline on disk left untouched).
7. Atomic publication with post-publication digest integrity check.
8. Outcome-driven learning ledger recording empirical successes and failures.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from Intelligence.isolated_repair import (
    IsolatedRepairExecutor,
    RepairLearningLedger,
)


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary sandbox repository structure."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "core_engine").mkdir()
    (repo / "tests").mkdir()
    (repo / "Intelligence").mkdir()

    # Create dummy source file
    sample = repo / "core_engine" / "sample_module.py"
    sample.write_text("def compute():\n    return 42\n", encoding="utf-8")

    # Create authority files
    (repo / "OWNER_DECLARATIONS.md").write_text("# Owner Declarations\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("# Agents Rules\n", encoding="utf-8")

    # Create test file
    (repo / "tests" / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    return repo


def test_authorization_token_enforcement(temp_repo: Path) -> None:
    """Repairs without authorized tokens are rejected without touching files."""
    executor = IsolatedRepairExecutor(temp_repo)
    target = temp_repo / "core_engine" / "sample_module.py"
    initial_content = target.read_text(encoding="utf-8")

    receipt = executor.execute_closed_loop_repair(
        target_file=target,
        replacement_code="def compute(): return 100\n",
        defect_probe=lambda p: True,
        validator_fn=lambda b, c, p: True,
        authorization_token="INVALID_TOKEN",
    )

    assert receipt.status == "REJECTED_UNAUTHORIZED"
    assert target.read_text(encoding="utf-8") == initial_content
    assert "Invalid authorization token" in receipt.reason


def test_scope_confinement_protections(temp_repo: Path) -> None:
    """Scope checks strictly protect tests, authority docs, and non-python paths."""
    executor = IsolatedRepairExecutor(temp_repo)
    auth_token = "INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR"

    # 1. Protected test file
    test_file = temp_repo / "tests" / "test_sample.py"
    r1 = executor.execute_closed_loop_repair(
        target_file=test_file,
        replacement_code="# mutated\n",
        defect_probe=lambda p: True,
        validator_fn=lambda b, c, p: True,
        authorization_token=auth_token,
    )
    assert r1.status == "REJECTED_SCOPE_VIOLATION"

    # 2. Protected authority file
    auth_file = temp_repo / "OWNER_DECLARATIONS.md"
    r2 = executor.execute_closed_loop_repair(
        target_file=auth_file,
        replacement_code="# mutated\n",
        defect_probe=lambda p: True,
        validator_fn=lambda b, c, p: True,
        authorization_token=auth_token,
    )
    assert r2.status == "REJECTED_SCOPE_VIOLATION"

    # 3. Non-python file
    doc_file = temp_repo / "README.md"
    doc_file.write_text("docs", encoding="utf-8")
    r3 = executor.execute_closed_loop_repair(
        target_file=doc_file,
        replacement_code="mutated",
        defect_probe=lambda p: True,
        validator_fn=lambda b, c, p: True,
        authorization_token=auth_token,
    )
    assert r3.status == "REJECTED_SCOPE_VIOLATION"

    # 4. Out of repo path
    outside_file = temp_repo.parent / "outside.py"
    outside_file.write_text("x = 1\n", encoding="utf-8")
    r4 = executor.execute_closed_loop_repair(
        target_file=outside_file,
        replacement_code="x = 2\n",
        defect_probe=lambda p: True,
        validator_fn=lambda b, c, p: True,
        authorization_token=auth_token,
    )
    assert r4.status == "REJECTED_SCOPE_VIOLATION"


def test_pre_change_defect_reproduction_requirement(temp_repo: Path) -> None:
    """If the defect cannot be reproduced on baseline, the repair is refused."""
    executor = IsolatedRepairExecutor(temp_repo)
    target = temp_repo / "core_engine" / "sample_module.py"
    initial_content = target.read_text(encoding="utf-8")
    auth_token = "INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR"

    # Probe returns False (no defect detected on baseline)
    receipt = executor.execute_closed_loop_repair(
        target_file=target,
        replacement_code="def compute(): return 999\n",
        defect_probe=lambda p: False,
        validator_fn=lambda b, c, p: True,
        authorization_token=auth_token,
    )

    assert receipt.status == "REJECTED_UNREPRODUCED"
    assert target.read_text(encoding="utf-8") == initial_content
    assert "could not be reproduced on baseline" in receipt.reason


def test_syntax_validation_of_candidate(temp_repo: Path) -> None:
    """Candidate code with syntax errors is rejected before sandbox evaluation."""
    executor = IsolatedRepairExecutor(temp_repo)
    target = temp_repo / "core_engine" / "sample_module.py"
    initial_content = target.read_text(encoding="utf-8")
    auth_token = "INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR"

    receipt = executor.execute_closed_loop_repair(
        target_file=target,
        replacement_code="def broken_syntax(:\n",
        defect_probe=lambda p: True,
        validator_fn=lambda b, c, p: True,
        authorization_token=auth_token,
    )

    assert receipt.status == "REJECTED_SYNTAX_ERROR"
    assert target.read_text(encoding="utf-8") == initial_content
    assert "Syntax error" in receipt.reason or "syntax error" in receipt.reason


def test_sandbox_probe_failure_rollback(temp_repo: Path) -> None:
    """If candidate still exhibits the defect in sandbox, rollback occurs and baseline is untouched."""
    executor = IsolatedRepairExecutor(temp_repo)
    target = temp_repo / "core_engine" / "sample_module.py"
    initial_content = target.read_text(encoding="utf-8")
    auth_token = "INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR"

    # Probe returns True on baseline AND still True on candidate
    receipt = executor.execute_closed_loop_repair(
        target_file=target,
        replacement_code="def compute(): return 0\n",
        defect_probe=lambda p: True,
        validator_fn=lambda b, c, p: True,
        authorization_token=auth_token,
        issue_type="ast_defect",
        problem_signature="sig_test_probe_fail",
    )

    assert receipt.status == "ROLLED_BACK"
    assert receipt.pre_probe_defect_detected is True
    assert receipt.post_probe_defect_cleared is False
    assert target.read_text(encoding="utf-8") == initial_content
    assert "still detected failure on candidate code" in receipt.reason


def test_validator_failure_rollback(temp_repo: Path) -> None:
    """If external regression validator rejects candidate, target file remains untouched."""
    executor = IsolatedRepairExecutor(temp_repo)
    target = temp_repo / "core_engine" / "sample_module.py"
    initial_content = target.read_text(encoding="utf-8")
    auth_token = "INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR"

    # Probe: True on baseline, False on candidate
    def _probe(p: Path) -> bool:
        return "42" in p.read_text(encoding="utf-8")

    # Validator rejects candidate
    def _rejecting_validator(b: str, c: str, p: Path) -> bool:
        return False

    receipt = executor.execute_closed_loop_repair(
        target_file=target,
        replacement_code="def compute(): return 100\n",
        defect_probe=_probe,
        validator_fn=_rejecting_validator,
        authorization_token=auth_token,
        issue_type="regression_test",
        problem_signature="sig_val_fail",
    )

    assert receipt.status == "ROLLED_BACK"
    assert receipt.pre_probe_defect_detected is True
    assert receipt.post_probe_defect_cleared is True
    assert receipt.validator_passed is False
    assert target.read_text(encoding="utf-8") == initial_content


def test_successful_closed_loop_repair_and_atomic_publication(temp_repo: Path) -> None:
    """Full 12-stage verified healing loop succeeds, publishes atomically, and records learning."""
    ledger_path = temp_repo / "Intelligence" / "repair_ledger.json"
    ledger = RepairLearningLedger(storage_path=ledger_path)
    executor = IsolatedRepairExecutor(temp_repo, learning_ledger=ledger)
    target = temp_repo / "core_engine" / "sample_module.py"
    auth_token = "INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR"

    # Defect: presence of "42"
    def _probe(p: Path) -> bool:
        return "42" in p.read_text(encoding="utf-8")

    # Validator: candidate is valid python and does not equal baseline
    def _validator(b: str, c: str, p: Path) -> bool:
        return b != c and p.name == "sample_module.py"

    replacement = "def compute():\n    return 100\n"
    receipt = executor.execute_closed_loop_repair(
        target_file=target,
        replacement_code=replacement,
        defect_probe=_probe,
        validator_fn=_validator,
        authorization_token=auth_token,
        issue_type="magic_constant",
        problem_signature="replace_42_with_100",
    )

    assert receipt.status == "COMMITTED"
    assert receipt.pre_probe_defect_detected is True
    assert receipt.post_probe_defect_cleared is True
    assert receipt.validator_passed is True
    assert target.read_text(encoding="utf-8") == replacement

    # Check learning ledger
    rate = ledger.get_success_rate("magic_constant", "replace_42_with_100")
    assert rate == 1.0
    assert ledger_path.exists()

    # Load ledger from disk and verify persistence
    new_ledger = RepairLearningLedger(storage_path=ledger_path)
    new_ledger.load()
    assert new_ledger.get_success_rate("magic_constant", "replace_42_with_100") == 1.0
