"""Single registration owner for the existing conjecture-tracking capability.

Used by Salamander composition and explicit minimal research compositions. This
is proof-state bookkeeping and numerical evidence, never theorem certification.
"""
from .capability_fabric import (
    CapabilityManifest, CapabilityPermissions, CapabilityRegistry,
    DeterminismClass, ExecutionProfile, ResourceBudget, SideEffectClass,
)
from .mathematical_research import MathematicalProofTracker


def register_proof_capability(registry: CapabilityRegistry, tracker: MathematicalProofTracker):
    """Bind a real tracker to an existing registry; create no competing owner."""
    if not isinstance(registry, CapabilityRegistry) or not isinstance(tracker, MathematicalProofTracker):
        raise TypeError("canonical registry and proof tracker are required")

    def execute(*, action="get", conjecture_id, **kwargs):
        if action == "register":
            return tracker.register_conjecture(
                conjecture_id, kwargs["domain"], kwargs["statement"],
                kwargs.get("assumptions"), kwargs.get("unresolved_steps"),
            ).as_dict()
        if action == "get":
            conjecture = tracker.get_conjecture(conjecture_id)
            if conjecture is None:
                raise KeyError(f"Conjecture '{conjecture_id}' not found")
            return conjecture.as_dict()
        if action == "experiment":
            return tracker.record_numerical_experiment(
                conjecture_id, kwargs["experiment_name"], kwargs["parameters"],
                kwargs["results"], kwargs["consistent"],
            )
        raise ValueError(f"Unknown proof action: '{action}'")

    registry.register(CapabilityManifest(
        capability_id="proof-conjecture", version="1.1.0",
        source_provenance="Intelligence/mathematical_research.py",
        description="Conjecture bookkeeping and numerical evidence; not certification",
        permissions=CapabilityPermissions(allowed_profiles=(
            ExecutionProfile.INTERNAL_RESEARCH, ExecutionProfile.SHARED_RESTRICTED)),
        resource_budget=ResourceBudget(), supported_operations=("register", "get", "experiment"),
        determinism=DeterminismClass.DETERMINISTIC, side_effects=SideEffectClass.READ_ONLY,
        verification_strategy="proof_state_bookkeeping_not_theorem_certification",
        input_schema={"type": "object", "required": ["conjecture_id"],
            "additionalProperties": False, "properties": {
                "action": {"type": "string", "enum": ["register", "get", "experiment"]},
                "conjecture_id": {"type": "string", "minLength": 1},
                "domain": {"type": "string", "minLength": 1},
                "statement": {"type": "string", "minLength": 1},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "unresolved_steps": {"type": "array", "items": {"type": "string"}},
                "experiment_name": {"type": "string", "minLength": 1},
                "parameters": {"type": "object"}, "results": {"type": "object"},
                "consistent": {"type": "boolean"},
            }}, output_schema={"type": "object"},
    ), execute)
