"""Finite metacognitive strategy selection; utilities are host estimates, not IQ."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from ._contracts import ContractError, integer, ratio, text
from .assurance import AssuranceLevel


class ReasoningStrategy(Enum):
    DO_NOTHING_OR_WAIT = "wait"
    STOP = "stop"
    CHAIN_OF_VERIFICATION = "chain_of_verification"
    TOOL_RETRIEVAL = "tool_retrieval"
    TOOL_SEARCH = "tool_search"
    RUN_SANDBOXED_EXPERIMENT = "sandboxed_experiment"
    SIMULATE_WORLD_MODEL = "simulate_world_model"
    RETRIEVE_MEMORY = "retrieve_memory"
    DELEGATE_SUBAGENT = "delegate_subagent"
    ASK_HUMAN = "ask_human"
    DIRECT_REASONING = "direct_reasoning"
    CHAIN_OF_THOUGHT = "private_reasoning"
    PROGRAMMATIC_SEARCH = "programmatic_search"
    MATHEMATICAL_DERIVATION = "mathematical_derivation"
    SYMBOLIC_REASONING = "symbolic_reasoning"
    CAUSAL_INFERENCE = "causal_inference"
    RETRIEVAL = "retrieval"
    EXPERIMENT = "experiment"
    SIMULATION = "simulation"
    MODEL_BASED_PLANNING = "model_based_planning"
    DECOMPOSITION = "decomposition"
    DELEGATION = "delegation"
    ADVERSARIAL_DEBATE = "adversarial_debate"
    ENSEMBLE_REASONING = "ensemble_reasoning"
    TOOL_USE = "tool_use"
    HUMAN_CONSULTATION = "human_consultation"
    CAPABILITY_CREATION = "capability_creation"


@dataclass(frozen=True)
class StrategyDecision:
    strategy: ReasoningStrategy
    rationale: str
    expected_value: int
    expected_cost: int
    information_gain: Fraction
    failure_risk: Fraction
    fallback: ReasoningStrategy
    stop_condition: str

    def __post_init__(self):
        if (
            type(self.strategy) is not ReasoningStrategy
            or type(self.fallback) is not ReasoningStrategy
        ):
            raise ContractError("typed strategies required")
        text(self.rationale)
        text(self.stop_condition)
        if type(self.expected_value) is not int:
            raise ContractError("exact utility required")
        integer(self.expected_cost)
        ratio(self.information_gain)
        ratio(self.failure_risk)


def score_strategy_estimates(
    candidates, *, remaining, catastrophic_threshold, information_weight, risk_weight
):
    integer(remaining)
    ratio(catastrophic_threshold)
    integer(information_weight)
    integer(risk_weight)
    if type(candidates) is not tuple or not 1 <= len(candidates) <= 64:
        raise ContractError("finite candidate strategies required")
    admitted = [
        s
        for s in candidates
        if s.expected_cost <= remaining and s.failure_risk < catastrophic_threshold
    ]
    if not admitted:
        raise ContractError("no admissible strategy")
    return max(
        admitted,
        key=lambda s: s.expected_value
        - s.expected_cost
        + information_weight * s.information_gain
        - risk_weight * s.failure_risk,
    )


@dataclass(frozen=True)
class Strategy:
    id: ReasoningStrategy
    cost: int
    applicability: Fraction
    failure_modes: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    minimum_authority: int
    acting: bool
    required_assurance: AssuranceLevel = AssuranceLevel.NONE

    def __post_init__(self):
        if type(self.id) is not ReasoningStrategy or type(self.acting) is not bool:
            raise ContractError("typed strategy registration required")
        integer(self.cost)
        ratio(self.applicability)
        integer(self.minimum_authority, maximum=4)
        if type(self.required_assurance) is not AssuranceLevel:
            raise ContractError("assurance is a separate typed axis")
        if self.id is ReasoningStrategy.STOP:
            raise ContractError("STOP is a control outcome, not a registered strategy")
        if type(self.failure_modes) is not tuple or type(self.evidence_requirements) is not tuple:
            raise ContractError("explicit strategy requirements/failures required")
        if self.id in (ReasoningStrategy.STOP, ReasoningStrategy.DO_NOTHING_OR_WAIT) and (
            self.cost or self.acting or self.minimum_authority
        ):
            raise ContractError("stop/wait cannot spend or acquire authority")


@dataclass(frozen=True)
class TaskCharacterisation:
    task_key: str
    novelty: Fraction
    ambiguity: Fraction
    reversibility: str
    verifiability: str
    remaining_budget: int
    available_evidence: tuple[str, ...]
    risk_profile: tuple[str, ...]
    estimates_confidence: Fraction

    def __post_init__(self):
        for x in (self.novelty, self.ambiguity, self.estimates_confidence):
            ratio(x)
        integer(self.remaining_budget)
        if self.reversibility not in (
            "REVERSIBLE",
            "COSTLY",
            "IRREVERSIBLE",
        ) or self.verifiability not in ("LOCAL", "TOOL", "EXTERNAL_ONLY"):
            raise ContractError("typed reversibility/verifiability required")


@dataclass(frozen=True)
class SelectorPolicy:
    applicability_floor: Fraction
    ambiguity_ceiling: Fraction
    novelty_threshold: Fraction
    pessimistic_prior: Fraction
    success_value: int
    risk_penalty: int
    failure_penalty: int
    estimate_confidence_floor: Fraction

    def __post_init__(self):
        for x in (
            self.applicability_floor,
            self.ambiguity_ceiling,
            self.novelty_threshold,
            self.pessimistic_prior,
            self.estimate_confidence_floor,
        ):
            ratio(x)
        if self.pessimistic_prior > Fraction(1, 2):
            raise ContractError("untested prior cannot be optimistic")
        for x in (self.success_value, self.risk_penalty, self.failure_penalty):
            integer(x)


@dataclass(frozen=True)
class StrategyTrackRecord:
    strategy: ReasoningStrategy
    task_key: str
    success_lower_bound: Fraction
    calibration_ece: Fraction
    quarantined: bool
    qualified_at: int
    expires_at: int
    evidence_digest: str
    signature: str
    context_fingerprint: str = ""

    def body(self):
        from ._contracts import canonical

        return canonical({k: v for k, v in self.__dict__.items() if k != "signature"})


@dataclass(frozen=True)
class StrategyPlan:
    mode: str
    primary: ReasoningStrategy | None
    portfolio: tuple[ReasoningStrategy, ...]
    fallback: ReasoningStrategy | None
    no_fallback_reason: str | None
    checkpoint_before_acting: bool
    reason: str
    ranked: tuple[ReasoningStrategy, ...]


def select_reasoning_strategy(
    registry,
    task,
    *,
    authority,
    policy,
    statistics,
    verify_statistics,
    now,
    ledger,
    achieved_assurance=AssuranceLevel.NONE,
):
    """Gate before ranking. Calibration records are signed by external qualification.

    applicability/characterisation are host estimates and can be wrong. Scores
    select a method; they do not independently confer action permissions.
    """
    from .trust import TrustLevel

    if (
        type(authority) is not TrustLevel
        or type(registry) is not tuple
        or not 1 <= len(registry) <= 64
    ):
        raise ContractError("typed authority and finite strategy registry required")
    if len({s.id for s in registry}) != len(registry):
        raise ContractError("duplicate strategies")
    if type(achieved_assurance) is not AssuranceLevel:
        raise ContractError("typed achieved assurance required")
    from ._contracts import digest

    context_fingerprint = digest(
        (
            ledger.identity.id,
            ledger.identity.model_fingerprint,
            ledger.identity.tool_fingerprint,
            ledger.identity.policy_version,
        )
    )
    records = {}
    for record in statistics:
        ratio(record.success_lower_bound)
        ratio(record.calibration_ece)
        if (
            record.task_key == task.task_key
            and record.context_fingerprint == context_fingerprint
            and record.qualified_at <= now < record.expires_at
            and verify_statistics(record.body(), record.signature)
        ):
            if record.strategy in records:
                raise ContractError("conflicting strategy qualification records")
            records[record.strategy] = record
    candidates = []
    for s in registry:
        if (
            s.applicability <= policy.applicability_floor
            or s.minimum_authority > int(authority)
            or s.required_assurance > achieved_assurance
            or not set(s.evidence_requirements) <= set(task.available_evidence)
        ):
            continue
        record = records.get(s.id)
        if record and record.quarantined:
            continue
        if s.cost > task.remaining_budget:
            continue
        success = (
            max(Fraction(0), record.success_lower_bound - record.calibration_ece)
            if record
            else policy.pessimistic_prior
        )
        risk = len(set(s.failure_modes) & set(task.risk_profile))
        ev = (
            success * policy.success_value
            - s.cost
            - (1 - success) * policy.risk_penalty
            - risk * policy.failure_penalty
        )
        candidates.append((s, ev))
    # Always retain nonacting exits without fabricating execution competence.
    for id in (ReasoningStrategy.DO_NOTHING_OR_WAIT,):
        if not any(s.id is id for s, ev in candidates):
            candidates.append((Strategy(id, 0, Fraction(1), (), (), 0, False), Fraction(0)))
    candidates.sort(key=lambda pair: pair[1], reverse=True)
    ranked = tuple(s.id for s, ev in candidates)
    viable = [
        s
        for s, ev in candidates
        if s.id not in (ReasoningStrategy.STOP, ReasoningStrategy.DO_NOTHING_OR_WAIT)
    ]
    if task.estimates_confidence < policy.estimate_confidence_floor or (
        task.ambiguity > policy.ambiguity_ceiling and task.reversibility != "REVERSIBLE"
    ):
        result = StrategyPlan(
            "PROPOSE",
            ReasoningStrategy.DO_NOTHING_OR_WAIT,
            ranked[:3],
            None,
            "no independently viable fallback pending clarification",
            True,
            "uncertain characterisation or intent",
            ranked,
        )
    elif not viable or candidates[0][0].id is ReasoningStrategy.DO_NOTHING_OR_WAIT:
        result = StrategyPlan(
            "STOP",
            None,
            (),
            ReasoningStrategy.DO_NOTHING_OR_WAIT,
            None,
            False,
            "no authorized viable strategy within budget",
            ranked,
        )
    else:
        primary = candidates[0][0]
        checkpoint = task.reversibility == "IRREVERSIBLE" and task.verifiability == "EXTERNAL_ONLY"
        mode = (
            "SEQUENTIAL_WITH_CHECKPOINT" if task.novelty > policy.novelty_threshold else "PRIMARY"
        )
        diverse = [
            s
            for s in viable
            if s.id != primary.id and set(s.failure_modes) != set(primary.failure_modes)
        ]
        secondary = max(
            diverse,
            key=lambda s: len(set(s.failure_modes) ^ set(primary.failure_modes)),
            default=None,
        )
        portfolio = (
            ((primary.id, secondary.id) if secondary else (primary.id,))
            if mode == "SEQUENTIAL_WITH_CHECKPOINT"
            else (primary.id,)
        )
        result = StrategyPlan(
            mode,
            primary.id,
            portfolio,
            ranked[1] if len(ranked) > 1 else None,
            None if len(ranked) > 1 else "no alternative admissible strategy",
            checkpoint or mode == "SEQUENTIAL_WITH_CHECKPOINT",
            "authority-first calibrated/pessimistic ranking",
            ranked,
        )
    ledger.append("strategy_selected", {"task": task, "plan": result, "policy": policy}, now=now)
    return result


def update_strategy_statistics(episode, ledger, *, now):
    """Raw learning evidence only. Quarantine/promotion requires host qualification."""
    required = {
        "strategy",
        "task_key",
        "outcome",
        "actual_cost",
        "estimated_cost",
        "failure_mode",
        "fallback_used",
        "human_intervention",
        "evidence",
    }
    if type(episode) is not dict or set(episode) != required:
        raise ContractError("complete per-strategy episode required")
    from ._contracts import sha

    sha(episode["evidence"])
    integer(episode["actual_cost"])
    integer(episode["estimated_cost"])
    from .anti_goodhart import disclose_optimization

    disclose_optimization(
        ledger,
        objective="task outcome and cost calibration; not proxy score maximization",
        kind="strategy_learning",
        evidence=episode["evidence"],
        now=now,
    )
    return ledger.append(
        "effect_confirmed", {"phase": "strategy_learning_evidence", "episode": episode}, now=now
    )
