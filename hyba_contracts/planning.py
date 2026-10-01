"""Sequential contract pipeline C3/C4: AuthorizedQuery and ExecutionPlan.

The spec's backbone: a query is authorized against a PolicyContext BEFORE
planning, and an ExecutionPlan binds the authorized query to a fold family,
operator contract and backend certificate before PRIME-DB sees it. Every
rejection happens at planning time with a recorded reason — never partial,
never silent.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from .types import BackendCertificate
from .types import EnterprisePolicyContext
from .types import FoldContract
from .types import FoldMode
from .types import OperatorContract
from .types import canonical_hash


class PlanningRejected(ValueError):
    """A request was rejected at planning time. ``reasons`` is the full,
    non-empty list of contract violations — one rejection, every reason."""

    def __init__(self, reasons: tuple[str, ...]):
        self.reasons = tuple(reasons)
        super().__init__("; ".join(self.reasons))


@dataclass(frozen=True)
class QueryBudget:
    """C3 budget envelope — enforced before execution, not after."""

    bytes_moved: int | None = None
    latency_ms: float | None = None
    cost: float | None = None
    energy_joules: float | None = None
    proof_bytes: int | None = None

    def validate(self):
        for name in ("bytes_moved", "latency_ms", "cost", "energy_joules", "proof_bytes"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"budget.{name} must be non-negative")


@dataclass(frozen=True)
class QueryRequest:
    """The caller's raw query, in the structured form policy can judge."""

    statement: str
    operators: tuple[str, ...]
    exactness_mode: str
    residency: tuple[str, ...]
    reconstruction: bool = False
    export: bool = False
    estimated: QueryBudget = field(default_factory=QueryBudget)


@dataclass(frozen=True)
class AuthorizedQuery:
    """C3 transport: Policy Engine -> Query Planner.

    Only exists once every policy check has passed — it cannot be built
    around a rejected request.
    """

    query: QueryRequest
    policy_context: EnterprisePolicyContext
    allowed_backends: tuple[str, ...]
    allowed_exactness_modes: tuple[str, ...]
    allowed_operators: tuple[str, ...]
    budget: QueryBudget
    residency_constraint: tuple[str, ...]
    reconstruction_permitted: bool
    export_permitted: bool

    def validate(self):
        if not self.allowed_backends:
            raise ValueError("authorized query requires at least one allowed backend")
        if not self.allowed_exactness_modes:
            raise ValueError("authorized query requires allowed exactness modes")
        if not self.residency_constraint:
            raise ValueError("authorized query requires a residency constraint")
        self.budget.validate()

    def hash(self) -> str:
        return canonical_hash(self)


def _over_budget(estimated: QueryBudget, budget: QueryBudget) -> list[str]:
    over = []
    for name in ("bytes_moved", "latency_ms", "cost", "energy_joules", "proof_bytes"):
        est = getattr(estimated, name)
        cap = getattr(budget, name)
        if est is not None and cap is not None and est > cap:
            over.append(f"budget.{name} {est} exceeds {cap}")
    return over


def authorize_query(
    query: QueryRequest,
    *,
    policy_context: EnterprisePolicyContext,
    allowed_backends: tuple[str, ...],
    allowed_exactness_modes: tuple[str, ...],
    allowed_operators: tuple[str, ...],
    budget: QueryBudget,
    residency_constraint: tuple[str, ...],
    reconstruction_permitted: bool,
    export_permitted: bool,
) -> AuthorizedQuery:
    """C3 admission: reject at planning time or return the authorized query."""
    reasons: list[str] = []
    denied_operators = sorted(set(query.operators) - set(allowed_operators))
    if denied_operators:
        reasons.append(f"operators not allowed: {','.join(denied_operators)}")
    if query.exactness_mode not in allowed_exactness_modes:
        reasons.append(f"exactness mode not allowed: {query.exactness_mode}")
    out_of_residency = sorted(set(query.residency) - set(residency_constraint))
    if out_of_residency:
        reasons.append(f"residency outside constraint: {','.join(out_of_residency)}")
    if query.reconstruction and not reconstruction_permitted:
        reasons.append("reconstruction requested but policy denies it")
    if query.export and not export_permitted:
        reasons.append("export requested but policy denies it")
    reasons.extend(_over_budget(query.estimated, budget))
    if reasons:
        raise PlanningRejected(tuple(reasons))
    authorized = AuthorizedQuery(
        query=query,
        policy_context=policy_context,
        allowed_backends=allowed_backends,
        allowed_exactness_modes=allowed_exactness_modes,
        allowed_operators=allowed_operators,
        budget=budget,
        residency_constraint=residency_constraint,
        reconstruction_permitted=reconstruction_permitted,
        export_permitted=export_permitted,
    )
    authorized.validate()
    return authorized


@dataclass(frozen=True)
class FallbackPolicy:
    permitted: bool
    marked: bool

    def validate(self):
        if self.permitted and not self.marked:
            raise ValueError("permitted fallback must be marked")


@dataclass(frozen=True)
class ExecutionPlan:
    """C4 transport: Query Planner -> PRIME-DB."""

    plan_id: str
    query: AuthorizedQuery
    object_ids: tuple[str, ...]
    fold_family: str
    operator: str
    operator_mode: FoldMode
    backend_target: str
    exactness_mode: str
    residual_budget: int
    movement_budget: int
    proof_requirement: str
    policy_context: EnterprisePolicyContext
    fallback_policy: FallbackPolicy

    def validate(self):
        self.fallback_policy.validate()
        if not self.object_ids:
            raise ValueError("execution plan requires object ids")
        if not self.proof_requirement:
            raise ValueError("execution plan requires a proof requirement")

    def hash(self) -> str:
        return canonical_hash(self)


def build_execution_plan(
    *,
    plan_id: str,
    query: AuthorizedQuery,
    object_ids: tuple[str, ...],
    fold_contract: FoldContract,
    operator_contract: OperatorContract,
    backend: BackendCertificate,
    operator_mode: FoldMode,
    residual_budget: int,
    movement_budget: int,
    proof_requirement: str,
    fallback_policy: FallbackPolicy,
) -> ExecutionPlan:
    """C4 admission: bind the authorized query to contracts and a backend,
    or reject with every violated invariant."""
    reasons: list[str] = []
    if operator_mode is not operator_contract.mode:
        reasons.append(
            f"operator_mode {operator_mode.value} does not match contract mode "
            f"{operator_contract.mode.value}"
        )
    if fold_contract.family not in operator_contract.accepted_fold_families:
        reasons.append(
            f"fold family {fold_contract.family} not accepted by operator "
            f"{operator_contract.operator}"
        )
    if operator_contract.operator not in fold_contract.supported_operators:
        reasons.append(
            f"fold family {fold_contract.family} does not support operator "
            f"{operator_contract.operator}"
        )
    if operator_contract.operator not in backend.supported_operators:
        reasons.append(
            f"backend {backend.backend_name} cannot run operator " f"{operator_contract.operator}"
        )
    exactness_mode = query.query.exactness_mode
    if exactness_mode not in backend.exactness_modes:
        reasons.append(f"backend {backend.backend_name} cannot satisfy exactness {exactness_mode}")
    if backend.backend_name not in query.allowed_backends:
        reasons.append(f"backend {backend.backend_name} not in allowed_backends")
    if fallback_policy.permitted and not fallback_policy.marked:
        reasons.append("permitted fallback must be marked")
    if operator_mode is FoldMode.REHYDRATE and not (
        fallback_policy.permitted and fallback_policy.marked
    ):
        reasons.append("rehydration plan requires a permitted, marked fallback")
    if residual_budget < 0 or movement_budget < 0:
        reasons.append("budgets must be non-negative")
    if reasons:
        raise PlanningRejected(tuple(reasons))
    plan = ExecutionPlan(
        plan_id=plan_id,
        query=query,
        object_ids=object_ids,
        fold_family=fold_contract.family,
        operator=operator_contract.operator,
        operator_mode=operator_mode,
        backend_target=backend.backend_name,
        exactness_mode=exactness_mode,
        residual_budget=residual_budget,
        movement_budget=movement_budget,
        proof_requirement=proof_requirement,
        policy_context=query.policy_context,
        fallback_policy=fallback_policy,
    )
    plan.validate()
    return plan


__all__ = [name for name in globals() if not name.startswith("_")]
