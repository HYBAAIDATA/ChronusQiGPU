"""Host-approved JSON adapter to the existing source-bound review implementation.

The client selects an approved review identifier, never a root, path list,
callback or policy. Registration does not confer EUCLID dispatch authority.
"""
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .capability_fabric import (
    CapabilityManifest, CapabilityPermissions, CapabilityRegistry,
    DeterminismClass, ExecutionProfile, ResourceBudget, SideEffectClass,
)
from .repository_review import ReviewPolicy, ReviewRejected, review_repository


def register_repository_review_capability(
    registry: CapabilityRegistry, *, repo_root: Path,
    approved_policies: Mapping[str, ReviewPolicy] | None = None,
):
    if not isinstance(registry, CapabilityRegistry):
        raise TypeError("existing CapabilityRegistry required")
    if not isinstance(repo_root, Path):
        raise TypeError("host-owned repository Path required")
    root = repo_root.absolute()
    policies = dict(approved_policies or {})
    for name, policy in policies.items():
        if type(name) is not str or not name or type(policy) is not ReviewPolicy:
            raise TypeError("named host-approved ReviewPolicy values required")
        # Revalidate the immutable contract, including values changed through
        # object.__setattr__ before registration. Retain no host mapping alias.
        policies[name] = ReviewPolicy(policy.expected_files, policy.max_file_bytes,
                                      policy.max_total_bytes, policy.max_findings)
    policies = MappingProxyType(policies)

    def execute(*, review_id):
        if review_id not in policies:
            raise ReviewRejected("review identifier is not host-approved")
        return review_repository(repo_root=root, policy=policies[review_id])

    registry.register(CapabilityManifest(
        capability_id="repository-review", version="1.1.0",
        source_provenance="Intelligence/repository_review.py",
        description="Host-approved bounded source review; not a semantic security verdict",
        permissions=CapabilityPermissions(allowed_profiles=tuple(ExecutionProfile)),
        resource_budget=ResourceBudget(), supported_operations=("review",),
        determinism=DeterminismClass.DETERMINISTIC, side_effects=SideEffectClass.READ_ONLY,
        verification_strategy="host_policy_and_source_digest_binding_not_certification",
        enabled=bool(policies),
        input_schema={"type": "object", "required": ["review_id"],
                      "additionalProperties": False,
                      "properties": {"review_id": {"type": "string", "minLength": 1}}},
        output_schema={"type": "object", "required": ["status", "files", "receipt_sha256"],
                       "properties": {"status": {"type": "string"},
                                      "files": {"type": "array", "items": {"type": "object"}},
                                      "receipt_sha256": {"type": "string", "minLength": 64}}},
    ), execute)
