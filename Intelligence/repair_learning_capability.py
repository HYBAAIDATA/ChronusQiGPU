"""Shared registration owner for observation-only repair-outcome queries.

Consumes the existing host-owned ledger. Does not create an executor, learner,
RewardAuthority, store, rights grant, or signing authority.
"""
from .capability_fabric import (
    CapabilityManifest, CapabilityPermissions, CapabilityRegistry,
    DeterminismClass, ExecutionProfile, ResourceBudget, SideEffectClass,
)
from .isolated_repair import RepairLearningLedger


def register_repair_learning_capability(registry, ledger):
    if not isinstance(registry, CapabilityRegistry) or not isinstance(ledger, RepairLearningLedger):
        raise TypeError("existing canonical registry and repair ledger are required")
    def query(*, issue_type="ast_defect", problem_signature="generic_repair"):
        return ledger.outcome_statistics(issue_type, problem_signature)
    registry.register(CapabilityManifest(
        capability_id="repair-learning-query", version="1.1.0",
        source_provenance="Intelligence/isolated_repair.py",
        description="Observation-only local repair statistics; not calibrated trust or reward",
        permissions=CapabilityPermissions(allowed_profiles=(
            ExecutionProfile.INTERNAL_RESEARCH, ExecutionProfile.SHARED_RESTRICTED)),
        resource_budget=ResourceBudget(), supported_operations=("query",),
        determinism=DeterminismClass.DETERMINISTIC, side_effects=SideEffectClass.READ_ONLY,
        verification_strategy="local_outcome_counts_not_independent_assurance",
        input_schema={"type": "object", "additionalProperties": False, "properties": {
            "issue_type": {"type": "string", "minLength": 1, "maxLength": 256},
            "problem_signature": {"type": "string", "minLength": 1, "maxLength": 256}}},
        output_schema={"type": "object", "additionalProperties": False,
            "required": ["issue_type", "problem_signature", "sample_count", "committed_count",
                         "empirical_success_rate", "evidence_class", "independently_qualified"],
            "properties": {
                "issue_type": {"type": "string"}, "problem_signature": {"type": "string"},
                "sample_count": {"type": "integer", "minimum": 0},
                "committed_count": {"type": "integer", "minimum": 0},
                "empirical_success_rate": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                "evidence_class": {"type": "string", "enum": ["LOCAL_REPAIR_OUTCOMES", "NO_OBSERVATIONS"]},
                "independently_qualified": {"type": "boolean", "enum": [False]}}},
    ), query)
