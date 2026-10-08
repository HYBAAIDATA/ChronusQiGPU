"""Composition root for EUCLID's integrated adaptive intelligence.

:class:`IntegratedAgent` owns long-term :class:`~.memory.AgentKnowledge` and,
for each problem, composes one :class:`~..core.GeneralIntelligenceCore` from
the integrated specialists around a fresh :class:`~.context.EpisodeContext`.
The core stays an orchestrator; every specialist sits behind a declared
interface; the only path to a world is the governed executor.

System configurations used by the research programme are declared here so
that the v16.4 reference and every ablation are reproducible by name:

* ``v16.4-reference`` — the v16.4 decision architecture as previously defined
  in :class:`~..experiments.BenchmarkProgramme` (no world model, analogy,
  causal reasoning, meta-learning, representation restructuring or
  replanning), with the v16.4 fixed objective weights and objective controller;
* ``integrated`` — everything on;
* ``sysid-plan-pipeline`` — a conventional identify-then-plan pipeline: world
  model and causal interventions only, no integration mechanisms;
* ``minus-*`` — one mechanism removed at its source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...evidence import EvidenceChain
from ..adaptive import ObjectiveController
from ..baselines import WeightedObjective
from ..core import AblationConfig, GeneralIntelligenceCore
from ..state import CognitiveState, Outcome
from ..worlds.world import TaskSpec, normalise_program
from .analogy import GraphAnalogyEngine, _surface_tokens
from .composition import (
    AdaptiveDecisionObjective,
    CausalHierarchicalPlanner,
    DynamicObjectiveController,
    ModelBasedComposer,
    RepresentationSelector,
)
from .consolidation import EpisodeConsolidator
from .context import AgentConfig, EpisodeContext, structural_class, structure_tokens
from .control import EvidenceMetaController
from .memory import AgentKnowledge
from .reasoning import (
    InformationGainDiscriminator,
    MechanismAbducer,
    MechanismDeducer,
    MechanismWorldModel,
)

#: v16.4's fixed objective weights (euclid/runtime.py production composition)
V16_WEIGHTS = {
    "correctness_estimate": 0.55,
    "cost": -0.10,
    "uncertainty": -0.20,
    "novelty": 0.10,
    "transfer_value": 0.15,
}

SYSTEMS: dict[str, AblationConfig] = {
    "v16.4-reference": AblationConfig(
        world_model=False, analogy=False, causal_reasoning=False, meta_learning=False,
        representation_restructuring=False, replanning=False,
    ),
    "integrated": AblationConfig(),
    "sysid-plan-pipeline": AblationConfig(
        analogy=False, meta_learning=False, learned_primitives=False,
        representation_restructuring=False, replanning=False, mathematical_structure=False,
    ),
    "minus-world-model": AblationConfig(world_model=False),
    "minus-causal": AblationConfig(causal_reasoning=False),
    "minus-analogy": AblationConfig(analogy=False),
    "minus-meta-learning": AblationConfig(meta_learning=False),
    "minus-learned-primitives": AblationConfig(learned_primitives=False),
    "minus-representation": AblationConfig(representation_restructuring=False),
    "minus-phi-lucas-manifold": AblationConfig(mathematical_structure=False),
    "minus-replanning": AblationConfig(replanning=False),
}


def build_problem(spec: TaskSpec) -> dict[str, Any]:
    """Public problem envelope: no hidden truth can be reached from here."""
    surface = sorted(_surface_tokens(
        list(spec.variables) + list(spec.operators) + [spec.surface_domain]))
    return {
        "problem_id": spec.task_id,
        "goal": spec.goal_text(),
        "problem_class": structural_class(spec),
        "structure": structure_tokens(spec),
        "surface": surface,
        "observations": [f"initial state {list(spec.initial_state)}"],
        "task_spec": spec.to_json(),
        "context_key": spec.task_id,
    }


class AccountingExecutor:
    """Governed-boundary wrapper: budget accounting and submission records.

    Wraps the real executor (a :class:`~..worlds.world.WorldExecutor`, a
    :class:`~..baselines.DelegatorExecutor`, …) so every system — including
    those without a world model — is charged identically.
    """

    def __init__(self, inner: Any, context: EpisodeContext) -> None:
        self.inner = inner
        self.context = context

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        result = dict(self.inner.execute(action, payload))
        ctx = self.context
        ctx.account(result)
        if payload.get("kind") == "plan" and not result.get("budget_exhausted"):
            candidate = ctx.programs.get(action)
            ctx.last_submission = {
                "program": normalise_program(result.get("program", payload.get("program", ()))),
                "trajectory": [list(row) for row in result.get("trajectory", ())],
                "goal_met": bool(result.get("goal_met")),
                "predicted": candidate.probability if candidate is not None else None,
                "skills": list(payload.get("skills", ())),
            }
            ctx.submissions.append(ctx.last_submission)
        return result


@dataclass
class EpisodeResult:
    state: CognitiveState
    context: EpisodeContext
    solved: bool
    cost: float
    probes: int
    submissions: int
    planning_expansions: int

    def summary(self) -> dict[str, Any]:
        return {
            "task_id": self.context.spec.task_id,
            "solved": self.solved,
            "cost": self.cost,
            "probes": self.probes,
            "submissions": self.submissions,
            "planning_expansions": self.planning_expansions,
            "strategy": self.state.selected_strategy,
            "outcome": self.state.outcome.value if self.state.outcome else None,
            "transitions": len(self.state.transitions),
        }


class IntegratedAgent:
    def __init__(
        self,
        *,
        knowledge: AgentKnowledge | None = None,
        config: AgentConfig | None = None,
        ablations: AblationConfig | None = None,
        reference_v16: bool = False,
        evidence: EvidenceChain | None = None,
        learning_adapter: Any | None = None,
    ) -> None:
        self.knowledge = knowledge or AgentKnowledge()
        self.config = config or AgentConfig()
        self.ablations = ablations or AblationConfig()
        self.reference_v16 = bool(reference_v16)
        self.evidence = evidence
        self.learning_adapter = learning_adapter

    @classmethod
    def for_system(cls, name: str, **kwargs: Any) -> "IntegratedAgent":
        if name not in SYSTEMS:
            raise KeyError(f"unknown system {name!r}")
        return cls(ablations=SYSTEMS[name], reference_v16=name == "v16.4-reference", **kwargs)

    def build_core(self, spec: TaskSpec, executor: Any, *, seed: int) -> tuple[
            GeneralIntelligenceCore, EpisodeContext]:
        self.knowledge.strategies.prior_weight = float(
            self.knowledge.params.get("strategy_prior_weight", 2.0))
        ctx = EpisodeContext(spec, self.knowledge, self.config, self.ablations, seed=seed)
        ctx.proxy_guard = not self.reference_v16
        analogy = GraphAnalogyEngine(ctx, self.knowledge)
        objective = (WeightedObjective(V16_WEIGHTS) if self.reference_v16
                     else AdaptiveDecisionObjective(self.knowledge))
        objective_controller = (ObjectiveController() if self.reference_v16
                                else DynamicObjectiveController(ctx))
        core = GeneralIntelligenceCore(
            world_model=MechanismWorldModel(ctx),
            memory=self.knowledge.memory,
            analogy=analogy,
            abducer=MechanismAbducer(ctx),
            deducer=MechanismDeducer(ctx),
            discriminator=InformationGainDiscriminator(ctx),
            metacontroller=EvidenceMetaController(ctx),
            metalearner=self.knowledge.strategies,
            planner=CausalHierarchicalPlanner(ctx),
            skills=ModelBasedComposer(ctx, self.knowledge.memory),
            objective=objective,
            executor=AccountingExecutor(executor, ctx),
            episode_learner=EpisodeConsolidator(ctx, self.knowledge, analogy,
                                                self.learning_adapter),
            representation_controller=RepresentationSelector(ctx),
            objective_controller=objective_controller,
            evidence=self.evidence if self.evidence is not None else EvidenceChain(),
            max_cycles=spec.submission_budget + 1,
            ablations=self.ablations,
            strategy_first=True,
            max_probes_per_cycle=max(1, min(self.config.max_probes_per_cycle,
                                            spec.probe_budget)),
        )
        return core, ctx

    def solve(self, spec: TaskSpec, executor: Any, *, seed: int = 0) -> EpisodeResult:
        core, ctx = self.build_core(spec, executor, seed=seed)
        problem = build_problem(spec)
        state = core.solve(problem)
        return EpisodeResult(
            state, ctx, state.outcome is Outcome.SOLVED, ctx.cost, ctx.probes_used,
            ctx.submissions_used, ctx.planning_expansions,
        )


__all__ = [
    "AccountingExecutor",
    "EpisodeResult",
    "IntegratedAgent",
    "SYSTEMS",
    "V16_WEIGHTS",
    "build_problem",
]
