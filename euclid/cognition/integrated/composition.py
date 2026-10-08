"""Planning, representation restructuring, composition and decision.

* :class:`CausalHierarchicalPlanner` decomposes the goal into causally
  ordered subgoals over the learned model and records, for each stage, the
  program that would reach it (scored counterfactually by the core).
* :class:`RepresentationSelector` keeps the legacy problem-representation
  controller and adds *measured* search-representation restructuring: each
  representation is trial-planned under the current model and adopted only
  for measured net utility (success minus normalised search cost); ties go to
  the simplest representation, so complexity never wins by itself.
* :class:`ModelBasedComposer` turns plans, repairs, transferred programmes and
  bound skills into executable candidates; without a world model it runs the
  v16-style model-free program search driven only by execution feedback.
* :class:`AdaptiveDecisionObjective` ranks by calibrated success probability
  plus auxiliary signals whose weight is *earned* by measured predictive
  validity (φ, novelty and transfer start at zero weight); every weight and
  its evidence are recorded on each candidate.
* :class:`DynamicObjectiveController` derives intermediate objectives from
  the goal and measured signals, and flags proxies that detach from the goal.
"""
from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any, Mapping, Sequence

from ..adaptive import IntermediateObjective, ObjectiveController, RepresentationController
from ..state import CandidateAction, CognitiveState, MemoryKind, PlanNode
from ..worlds.world import ASSIGN
from .context import PlanCandidate
from .control import ASSIGN_STRATEGIES, RESPONSE_STRATEGIES_NEUTRAL, RESPONSE_STRATEGIES_PHI
from .planning import REPRESENTATIONS, dependency_order, plan
from .reasoning import outcome_entropy

PHI = (1.0 + 5.0 ** 0.5) / 2.0


class CausalHierarchicalPlanner:
    def __init__(self, context: Any) -> None:
        self.context = context

    def plan(self, goal: str, state: CognitiveState) -> list[PlanNode]:
        ctx = self.context
        spec = ctx.spec
        if spec.objective != ASSIGN:
            return [
                PlanNode("p0", f"goal: {goal}", children=("p1", "p2")),
                PlanNode("p1", f"locate optimum of {spec.parametric[0]} by search",
                         skill_ref=state.selected_strategy),
                PlanNode("p2", "submit located optimum"),
            ]
        posterior = ctx.posterior
        if posterior is None:
            return [PlanNode("p0", f"goal: {goal}", status="active",
                             skill_ref="model-free-search")]
        table = posterior.map_table()
        ordered = dependency_order(table, spec.goal)
        nodes: list[PlanNode] = []
        uncertain = ctx.relevant_uncertain_ops(ctx.candidate_programs())
        for op in uncertain:
            nodes.append(PlanNode(f"id:{op}", f"identify:{op}", skill_ref="causal-discrimination"))
        state_now = ctx.start
        prefix: list[str] = []
        children = []
        for index, clause in enumerate(ordered):
            result = plan(table, spec.operators, state_now, [clause], spec.domains,
                          representation="causal-relevance",
                          max_length=spec.max_program_length - len(prefix),
                          node_budget=max(50, ctx.node_budget() // max(1, len(ordered))))
            ctx.planning_expansions += result.expanded
            node_id = f"sg{index}:{spec.variables[clause[0]]}={clause[1]}"
            if result.program is None:
                nodes.append(PlanNode(node_id, f"subgoal {node_id} (no plan under model)",
                                      status="failed"))
                children.append(node_id)
                continue
            prefix.extend(result.program)
            for op in result.program:
                state_now = table[op].apply(state_now, spec.domains)
            scored = posterior.success_probability(tuple(prefix), ctx.start, spec.goal,
                                                   seed=ctx.seed)
            candidate = PlanCandidate(tuple(prefix), float(scored["probability"]),
                                      str(scored["method"]), "subgoal-prefix",
                                      "causal-relevance", result.expanded)
            nodes.append(PlanNode(node_id, ctx.register(candidate), skill_ref="toe-free:gbfs"))
            children.append(node_id)
        nodes.insert(0, PlanNode("goal", f"goal: {goal}", status="active",
                                 children=tuple(children)))
        return nodes

    def replan(self, goal: str, state: CognitiveState, failure: Mapping[str, Any]) -> list[PlanNode]:
        previous = {node.node_id: node for node in state.plan}
        fresh = self.plan(goal, state)
        for index, node in enumerate(fresh):
            old = previous.get(node.node_id)
            if old is not None and old.description != node.description:
                fresh[index] = replace(node, status="substituted")
        return fresh


class RepresentationSelector(RepresentationController):
    def __init__(self, context: Any) -> None:
        self.context = context

    def restructure(self, state: CognitiveState, *, exclude: Sequence[str] = ()) -> dict[str, Any]:
        ctx = self.context
        posterior = ctx.posterior
        if posterior is None or ctx.spec.objective != ASSIGN:
            ctx.representation = "literal"
            return {"selected": "literal", "trials": [],
                    "basis": "no mechanism model: nothing to restructure"}
        spec = ctx.spec
        table = posterior.map_table()
        trial_budget = max(50, ctx.node_budget() // 4)
        macros = ctx.macros(table)
        trials = []
        for index, representation in enumerate(REPRESENTATIONS):
            if representation in exclude:
                continue
            result = plan(table, spec.operators, ctx.start, spec.goal, spec.domains,
                          representation=representation, max_length=spec.max_program_length,
                          node_budget=trial_budget, macros=macros)
            ctx.planning_expansions += result.expanded
            utility = (1.0 if result.found else 0.0) - result.expanded / trial_budget
            trials.append({"representation": representation, "found": result.found,
                           "expanded": result.expanded, "net_utility": round(utility, 6),
                           "complexity_rank": index})
        if not trials:
            return {"selected": ctx.representation, "trials": [],
                    "basis": "every representation excluded"}
        best = max(trials, key=lambda t: (t["net_utility"], -t["complexity_rank"]))
        ctx.representation = best["representation"]
        return {"selected": best["representation"], "trials": trials,
                "trial_budget": trial_budget,
                "basis": "measured planning success minus normalised search cost; "
                         "ties to the simplest representation"}


def _program_descriptor(program: Sequence[Any], max_length: int, n_ops: int) -> list[float]:
    flat = [step if isinstance(step, str) else step[0] for step in program]
    distinct = len(set(flat))
    repeats = sum(1 for a, b in zip(flat, flat[1:]) if a == b)
    return [len(flat) / max(1, max_length), distinct / max(1, n_ops),
            repeats / max(1, len(flat))]


class ModelBasedComposer:
    def __init__(self, context: Any, memory: Any | None = None) -> None:
        self.context = context
        self.memory = memory
        self.mathematical_enabled = True

    def available_strategies(self) -> tuple[str, ...]:
        ctx = self.context
        if ctx.spec.objective != ASSIGN:
            return (RESPONSE_STRATEGIES_PHI if ctx.ablations.mathematical_structure
                    else RESPONSE_STRATEGIES_NEUTRAL)
        if ctx.posterior is None:
            return ("evolve-synthesise-transfer",)
        strategies = ASSIGN_STRATEGIES
        if not ctx.ablations.analogy:
            strategies = tuple(s for s in strategies if s != "analogy-causal-plan")
        if not ctx.ablations.causal_reasoning:
            strategies = tuple(s for s in strategies if s not in (
                "abduce-intervene-deduce", "voi-plan", "analogy-causal-plan"))
        return strategies

    # -- shared feature construction ---------------------------------------------------------
    def _features(self, candidate: PlanCandidate, state: CognitiveState) -> dict[str, float]:
        ctx = self.context
        spec = ctx.spec
        descriptor = _program_descriptor(candidate.program, spec.max_program_length,
                                         len(spec.operators))
        archive = ctx.knowledge.novelty.descriptors
        novelty = (min(1.0, min(math.dist(descriptor, d) for d in archive))
                   if archive else 1.0)
        phi_signal = 0.0
        if "resonance" in spec.observables and ctx.posterior is not None:
            final = ctx.posterior.map_table()
            current = ctx.start
            for op in candidate.program:
                current = final[op].apply(current, spec.domains)
            phi_signal = (sum((k + 1) * v for k, v in enumerate(current)) * PHI) % 1.0
        stats = ctx.knowledge.strategies.class_stats.get(ctx.problem_class, {})
        row = stats.get(state.selected_strategy or "", [0.0, 0.0])
        strategy_value = row[0] / row[1] if row[1] else 0.5
        transfer = 1.0 if (candidate.origin.startswith("transfer") or candidate.macros_used) else 0.0
        return {
            "correctness_estimate": float(candidate.probability),
            "cost": len(candidate.program) / max(1, spec.max_program_length),
            "uncertainty": outcome_entropy(min(1.0, max(0.0, candidate.probability))),
            "novelty": float(novelty),
            "transfer_value": transfer,
            "phi_signal": float(phi_signal),
            "strategy_value": float(strategy_value),
        }

    def _action(self, candidate: PlanCandidate, state: CognitiveState) -> CandidateAction:
        ctx = self.context
        action_id = ctx.register(candidate)
        features = self._features(candidate, state)
        ctx.features[action_id] = features
        return CandidateAction(
            action_id,
            f"{candidate.origin}: {list(candidate.program)} "
            f"(P(goal)={candidate.probability:.3f}, {candidate.method or 'estimated'})",
            origin=f"integrated:{candidate.origin}",
            features=features,
            payload={"program": list(candidate.program), "skills": list(candidate.macros_used),
                     "origin": candidate.origin, "representation": candidate.representation},
        )

    def _submitted(self) -> set[tuple]:
        return {tuple(tuple(s) if isinstance(s, list) else s for s in row["program"])
                for row in self.context.submissions}

    # -- composition --------------------------------------------------------------------------
    def compose(self, goal: str, state: CognitiveState) -> list[CandidateAction]:
        ctx = self.context
        ctx.strategy = state.selected_strategy or ""
        ctx.budget_scale = float(state.representation.get("planning_budget_scale", 1.0))
        chosen = state.representation.get("planning_representation")
        if chosen:
            ctx.representation = str(chosen)
        if ctx.spec.objective != ASSIGN:
            return self._compose_response(state)
        if ctx.posterior is None or ctx.strategy == "evolve-synthesise-transfer":
            return self._compose_model_free(state)
        submitted = self._submitted()
        candidates = [c for c in ctx.candidate_programs() if c.program not in submitted]
        if not candidates:
            # No plan reaches the goal under any sampled model: fall back to
            # exploratory programmes (recorded as such) rather than to plan
            # nodes the governed executor cannot run.
            fallback = self._compose_model_free(state)
            return [replace(a, origin="integrated:fallback-model-free") for a in fallback]
        return [self._action(candidate, state) for candidate in candidates[:5]]

    def _compose_response(self, state: CognitiveState) -> list[CandidateAction]:
        ctx = self.context
        op = ctx.response.operator
        submitted = self._submitted()
        answers = [a for a in ctx.response_answers(ctx.strategy)
                   if ((op, a),) not in submitted]
        if len(answers) < 2:
            from .phi_mechanisms import golden_weyl_points, grid_points

            size = ctx.response.size
            spread = (golden_weyl_points(size, size) if ctx.ablations.mathematical_structure
                      else grid_points(size, size))
            answers += [x for x in spread if ((op, x),) not in submitted and x not in answers][
                : 2 - len(answers)]
        # The search's answer is correct exactly when its shape assumption
        # holds: estimate it by the learned unimodality frequency (zero once a
        # violation has been observed for a unimodal-only search).  Later
        # answers only matter if the first is wrong, so they rank strictly lower.
        unimodal = 0.0 if ctx.response.violation else ctx.knowledge.unimodal_prior()
        robust = ctx.strategy == "explore-refine"
        estimate = unimodal if not robust else max(unimodal, 1.0 - unimodal)
        actions = []
        for rank, setting in enumerate(answers[:2]):
            probability = estimate if rank == 0 else min(estimate, 1.0 - estimate) * 0.5
            candidate = PlanCandidate(((op, int(setting)),), probability,
                                      "strategy-class-frequency", f"search:{ctx.strategy}",
                                      "literal")
            action = self._action(candidate, state)
            actions.append(replace(action, payload={**action.payload,
                                                    "program": [[op, int(setting)]]}))
        return actions

    def _compose_model_free(self, state: CognitiveState) -> list[CandidateAction]:
        """v16-style search: candidates scored only by executed feedback."""
        ctx = self.context
        spec = ctx.spec
        ops = list(spec.operators)
        executed = {}
        for item in state.evidence_items:
            if not item.evidence_id.startswith("exec-"):
                continue
            result = item.content.get("result", {})
            program = tuple(result.get("program", ()))
            if not program:
                continue
            if "scores" in result and item.evidence_id not in ctx.audited_executions:
                ctx.audited_executions.add(item.evidence_id)
                ctx.audit.observe(result.get("trajectory", ()), result["scores"],
                                  spec.goal, ctx.start)
            proxy_ok = not (ctx.proxy_guard and ctx.audit.detached_proxy)
            score = max(result.get("scores", [0]) or [0]) if proxy_ok else 0
            fitness = 100.0 * bool(result.get("goal_met")) + float(score) - 0.01 * len(program)
            executed[program] = fitness
        ctx.model_free_population = sorted(((f, p) for p, f in executed.items()), reverse=True)
        submitted = set(executed)
        rng = random.Random(ctx.seed * 104729 + len(submitted))
        proposals: list[tuple[tuple[str, ...], str]] = []
        if self.memory is not None and ctx.ablations.analogy:
            for item in self.memory.of_kind(MemoryKind.PROCEDURAL):
                surface = item.payload.get("surface_program")
                if surface and all(op in ops for op in surface):
                    proposals.append((tuple(surface), "transfer:surface-replay"))
        if ctx.model_free_population:
            best = ctx.model_free_population[0][1]
            for _ in range(12):
                mutant = list(best)
                move = rng.randrange(3)
                if move == 0 or not mutant:
                    mutant.insert(rng.randrange(len(mutant) + 1), rng.choice(ops))
                elif move == 1:
                    mutant[rng.randrange(len(mutant))] = rng.choice(ops)
                elif len(mutant) > 1:
                    del mutant[rng.randrange(len(mutant))]
                proposals.append((tuple(mutant[: spec.max_program_length]), "mutation"))
        enumeration = [(op,) for op in ops] + [(a, b) for a in ops for b in ops]
        if self.mathematical_enabled:
            from ..phi_schedule import phi_order

            enumeration = [enumeration[i] for i in phi_order(len(enumeration))]
        proposals.extend((program, "enumeration") for program in enumeration)
        for _ in range(8):
            length = rng.randint(3, min(8, spec.max_program_length))
            proposals.append((tuple(rng.choice(ops) for _ in range(length)), "random"))
        seen: set[tuple] = set()
        actions = []
        for program, origin in proposals:
            if program in submitted or program in seen or not program:
                continue
            seen.add(program)
            candidate = PlanCandidate(program, 0.0, "model-free", origin, "literal")
            actions.append(self._action(candidate, state))
            if len(actions) >= 6:
                break
        return actions


class AdaptiveDecisionObjective:
    """Validity-weighted, auditable multi-objective ranking."""

    BASE = {
        "correctness_estimate": 1.0,
        "cost": -0.15,
        "uncertainty": -0.10,
        "novelty": 0.05,
        "transfer_value": 0.05,
        "phi_signal": 0.05,
        "strategy_value": 0.05,
    }
    DECLARED = ("correctness_estimate", "cost")
    PRIOR_STRENGTH = 10.0
    CAP = 0.5

    def __init__(self, knowledge: Any) -> None:
        self.knowledge = knowledge
        self.last_rationale: dict[str, Any] = {}

    def weights(self) -> tuple[dict[str, float], dict[str, Any]]:
        weights: dict[str, float] = {}
        rationale: dict[str, Any] = {}
        for name, base in self.BASE.items():
            if name in self.DECLARED:
                weights[name] = base
                rationale[name] = "declared"
                continue
            rho, n = self.knowledge.feature_validity(name)
            reliability = max(0.0, rho * math.copysign(1.0, base)) * n / (n + self.PRIOR_STRENGTH)
            weight = base * reliability
            weight = max(-self.CAP, min(self.CAP, weight))
            weights[name] = weight
            rationale[name] = {"validity": round(rho, 4), "n": n,
                               "reliability": round(reliability, 4)}
        return weights, rationale

    def evaluate(self, candidates: Sequence[CandidateAction],
                 context: Mapping[str, Any]) -> list[CandidateAction]:
        weights, rationale = self.weights()
        self.last_rationale = rationale
        scored = []
        for candidate in candidates:
            components = {name: w * float(candidate.features.get(name, 0.0))
                          for name, w in weights.items()}
            scored.append(replace(candidate, scores=components,
                                  total=sum(components.values()), weights_used=dict(weights)))
        return sorted(scored, key=lambda c: (-(c.total or 0.0), c.action_id))


class DynamicObjectiveController(ObjectiveController):
    """Intermediate objectives from the goal, the model and the proxy audit."""

    def __init__(self, context: Any) -> None:
        super().__init__()
        self.context = context
        self.history: list[dict[str, Any]] = []

    def derive(self, goal: str, *, uncertainty: float, contradictions: int,
               missing_evidence: int, prediction_error: float) -> list[IntermediateObjective]:
        base = super().derive(goal, uncertainty=uncertainty, contradictions=contradictions,
                              missing_evidence=missing_evidence,
                              prediction_error=prediction_error)
        ctx = self.context
        derived: list[IntermediateObjective] = []
        spec = ctx.spec
        if spec.objective == ASSIGN and ctx.posterior is not None:
            ordered = dependency_order(ctx.posterior.map_table(), spec.goal)
            for rank, (index, value) in enumerate(ordered):
                derived.append(IntermediateObjective(
                    f"subgoal-{rank}", f"establish {spec.variables[index]} = {value}", goal,
                    "causal dependency order under the current model",
                    f"clause:{index}", float(value), 0.0,
                ))
        if "score" in spec.observables:
            status = "detached-proxy" if ctx.audit.detached_proxy else "active"
            derived.append(IntermediateObjective(
                "proxy-score", "keep the score observable aligned with goal progress", goal,
                f"proxy audit {ctx.audit.to_json()}", "score", 0.0, 0.0, status,
            ))
        objectives = list(base) + derived
        self.history.append({
            "objectives": [o.objective_id for o in objectives],
            "detached": [o.objective_id for o in objectives if o.status == "detached-proxy"],
        })
        return objectives


__all__ = [
    "AdaptiveDecisionObjective",
    "CausalHierarchicalPlanner",
    "DynamicObjectiveController",
    "ModelBasedComposer",
    "RepresentationSelector",
]
