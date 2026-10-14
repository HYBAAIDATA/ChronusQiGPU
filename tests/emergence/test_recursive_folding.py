"""Unit tests for RecursiveFolding (Phi mechanism) and budgeted recursion."""

import pytest
from euclid.emergence.models.substrate import SubstrateProperties
from euclid.emergence.models.qualification import QualificationStatus
from euclid.emergence.substrate.executors import StandardSyncExecutor, AsyncIsolatedExecutor
from euclid.emergence.trusted_core.access_control import GovernanceToken
from euclid.emergence.trusted_core.qualification_service import EmergentQualificationService
from euclid.emergence.folding.recursive_folding import (
    RecursiveFolding,
    FROZEN_MAX_FOLD,
    FROZEN_MAX_FOLD_SIGNATURE,
    verify_frozen_max_fold,
)


class MockReflectiveAgent:
    def behavior_at(self, depth: int):
        return [f"reflective_synthesis_d{depth}", "evaluate_action"]


def test_frozen_max_fold_tampering_and_budgeting():
    # Verify valid signature passes
    assert verify_frozen_max_fold(FROZEN_MAX_FOLD, FROZEN_MAX_FOLD_SIGNATURE)

    # Tampered max_fold fails verification
    assert not verify_frozen_max_fold(10, FROZEN_MAX_FOLD_SIGNATURE)

    service = EmergentQualificationService()
    # Initializing with forged max_fold raises PermissionError
    with pytest.raises(PermissionError):
        RecursiveFolding(eq_service=service, max_fold=999, max_fold_signature="tampered_sig")


def test_recursive_folding_execution_and_qualification_routing():
    service = EmergentQualificationService()
    token = GovernanceToken.issue("assurance_officer", service.governance_secret_key)
    folding = RecursiveFolding(eq_service=service)

    prop_a = SubstrateProperties("sync", 5.0, "atomic", "vm", sandbox_id="box_a")
    prop_b = SubstrateProperties("async", 15.0, "batched", "container", sandbox_id="box_b")
    exec_a = StandardSyncExecutor(prop_a)
    exec_b = AsyncIsolatedExecutor(prop_b)

    agent = MockReflectiveAgent()

    # Run folding recursion starting at depth 1
    outcomes = list(folding.fold(
        agent=agent,
        depth=1,
        executor_A=exec_a,
        executor_B=exec_b,
        governance_token=token,
    ))

    # Should yield qualification outcomes up to MAX_FOLD
    assert len(outcomes) > 0
    assert len(outcomes) <= FROZEN_MAX_FOLD
    for outcome in outcomes:
        assert outcome.status in (QualificationStatus.QUALIFIED, QualificationStatus.REJECTED)
