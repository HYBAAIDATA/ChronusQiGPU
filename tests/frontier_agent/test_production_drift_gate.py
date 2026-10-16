"""Tests for double-vs-real drift gate and traceability (item 6.2)."""

from scripts.assert_production_drift_gate import (
    audit_contract_double,
    check_production_merge_blocker,
)
from tests.frontier_agent.conftest import FileAdapter


def test_file_adapter_carries_traceability_and_todo_gate():
    """Verify that FileAdapter carries production traceability link and TODO-gate."""
    issues = audit_contract_double(FileAdapter)
    assert len(issues) == 0, f"FileAdapter drift issues: {issues}"
    assert (
        FileAdapter.__production_target__ == "chronus.capabilities.storage.ProductionStorageAdapter"
    )
    assert "TODO-GATE" in FileAdapter.__todo_gate__


def test_untraceable_double_is_rejected():
    class IncompleteDouble:
        __contract_double__ = True

    issues = audit_contract_double(IncompleteDouble)
    assert len(issues) == 2
    assert any("missing __production_target__" in msg for msg in issues)
    assert any("missing explicit TODO-gate" in msg for msg in issues)


def test_todo_gate_prevents_production_merge():
    """Assert that unresolved TODO-gates on contract doubles prevent production merge."""
    allowed, reason = check_production_merge_blocker([FileAdapter], target_env="production")
    assert allowed is False
    assert "Merge blocked by active TODO-gates" in reason
    assert "FileAdapter" in reason

    # Local validation environment is allowed
    local_allowed, local_reason = check_production_merge_blocker(
        [FileAdapter], target_env="local_contract_testing"
    )
    assert local_allowed is True
