"""Shared evidence structures for one integrated reasoning episode.

Specialists never call each other directly; they read and write this
episode context (and long-term :class:`~.memory.AgentKnowledge`).  The
context owns budget accounting, the posterior, the response-search state,
cached candidate plans keyed by posterior version, the proxy-score audit and
the value-of-information quantities the evidence policy needs.

:class:`AgentConfig` holds every compute parameter.  They are declared once,
fixed before any evaluation run, and identical for every system compared.
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from ...contracts import domain_hash
from ..worlds.mechanisms import Mechanism, State
from ..worlds.world import ASSIGN, MAXIMISE_RESPONSE, TaskSpec
from .phi_mechanisms import unimodal_violation
from .planning import PlanResult, plan, repair
from .world_model import MechanismPosterior


@dataclass(frozen=True)
class AgentConfig:
    """Declared compute budget (never tuned on evaluation data)."""

    node_budget: int = 2500
    plan_samples: int = 3
    max_probes_per_cycle: int = 24
    probe_prefix_depth: int = 2
    probe_candidate_limit: int = 64
    voi_samples: int = 96
    novelty_threshold: float = 0.2
    seed: int = 0

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def structural_class(spec: TaskSpec) -> str:
    """Coarse, vocabulary-free problem class from public structure only."""
    if spec.objective == MAXIMISE_RESPONSE:
        return "response"
    states = math.prod(spec.domains)
    size = "small" if states < 128 else "medium" if states < 2048 else "large"
    ratio = spec.submission_cost / max(1e-9, spec.probe_cost)
    costs = "cheap-submit" if ratio <= 1.0 else "balanced" if ratio <= 3.0 else "costly-submit"
    return f"assign|{size}|{costs}"


def structure_tokens(spec: TaskSpec) -> list[str]:
    """Public structural features used for retrieval (no names, no vocabulary)."""
    tokens = [
        f"objective:{spec.objective}",
        f"vars:{len(spec.domains)}",
        f"ops:{len(spec.operators)}",
        "domains:" + "-".join(str(m) for m in sorted(spec.domains)),
        f"goal-size:{len(spec.goal)}",
        f"class:{structural_class(spec)}",
    ]
    tokens.extend(f"observable:{name}" for name in spec.observables)
    if spec.objective == MAXIMISE_RESPONSE:
        tokens.append("parametric-response")
    return tokens


def success_value(spec: TaskSpec) -> float:
    """Declared value of success: the full interaction budget's cost.

    Spending the whole budget to succeed is break-even; this sets the scale on
    which evidence costs are compared, using only declared task quantities.
    """
    return spec.probe_budget * spec.probe_cost + spec.submission_budget * spec.submission_cost


@dataclass
class PlanCandidate:
    program: tuple[Any, ...]
    probability: float
    method: str
    origin: str
    representation: str
    expanded: int = 0
    macros_used: tuple[str, ...] = ()

    @property
    def action_id(self) -> str:
        return "program:" + domain_hash("euclid.program.v1", list(self.program))[:16]


@dataclass
class ProxyAudit:
    """Tracks whether the ``score`` observable moves with true goal progress."""

    aligned: int = 0
    detached: int = 0
    regressions: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)

    def observe(self, readings: Sequence[Sequence[int]], scores: Sequence[float],
                goal: Sequence[tuple[int, int]], start: State) -> None:
        # Every run restarts from the declared initial state, whose score is
        # its goal progress (no bonus has accrued yet), so the first step is
        # audited too.
        previous_progress = sum(1 for i, v in goal if start[i] == v)
        previous_score: float = float(previous_progress)
        for reading, score in zip(readings, scores):
            progress = sum(1 for i, v in goal if reading[i] == v)
            d_score = float(score) - previous_score
            d_progress = progress - previous_progress
            if d_score > 0 and d_progress <= 0:
                self.detached += 1
            elif d_score > 0 and d_progress > 0:
                self.aligned += 1
            elif d_score < 0 and d_progress < 0:
                self.regressions += 1
            previous_score, previous_progress = float(score), progress

    @property
    def detached_proxy(self) -> bool:
        """Score rose without goal progress more often than it rose with it."""
        return self.detached > 0 and self.detached >= self.aligned

    def to_json(self) -> dict[str, Any]:
        return {"aligned": self.aligned, "detached": self.detached,
                "regressions": self.regressions, "detached_proxy": self.detached_proxy}


@dataclass
class ResponseSearch:
    """Evidence about a parametric response curve."""

    size: int
    operator: str
    values: dict[int, float] = field(default_factory=dict)

    def observe(self, setting: int, value: float) -> None:
        self.values[int(setting)] = float(value)

    @property
    def violation(self) -> bool:
        return unimodal_violation(self.values)

    def ranked(self) -> list[int]:
        return sorted(self.values, key=lambda k: (-self.values[k], k))


class EpisodeContext:
    """Per-episode shared state between specialists (never long-term)."""

    def __init__(
        self,
        spec: TaskSpec,
        knowledge: Any,
        config: AgentConfig,
        ablations: Any,
        *,
        seed: int,
    ) -> None:
        self.spec = spec
        self.knowledge = knowledge
        self.config = config
        self.ablations = ablations
        self.seed = int(seed)
        self.rng = random.Random(seed)
        self.start: State = tuple(spec.initial_state)
        self.problem_class = structural_class(spec)
        self.value = success_value(spec)
        self.posterior: MechanismPosterior | None = None
        self.response: ResponseSearch | None = None
        if spec.objective == ASSIGN and ablations.world_model:
            self.posterior = MechanismPosterior(
                spec.domains,
                spec.operators,
                kind_prior=knowledge.kind_prior(),
                noise_prior=knowledge.noise_prior(),
            )
        if spec.objective == MAXIMISE_RESPONSE:
            op, size = spec.parametric  # type: ignore[misc]
            self.response = ResponseSearch(size, op)
        self.probes_used = 0
        self.submissions_used = 0
        self.planning_expansions = 0
        self.programs: dict[str, PlanCandidate] = {}
        self.transfer_programs: list[tuple[tuple[str, ...], str]] = []
        self.representation = "literal"
        self.budget_scale = 1.0
        self.last_plan: PlanResult | None = None
        self.last_submission: dict[str, Any] | None = None
        self.submissions: list[dict[str, Any]] = []
        self.audit = ProxyAudit()
        self.events: list[dict[str, Any]] = []
        self.calibration: list[tuple[float, bool]] = []
        self.executed_features: list[tuple[dict[str, float], bool]] = []
        self.model_free_population: list[tuple[float, tuple[str, ...]]] = []
        self.strategy_outcomes: list[dict[str, Any]] = []
        self._plan_cache: dict[tuple, list[PlanCandidate]] = {}
        self.analogy_sources: dict[str, dict[str, Any]] = {}
        self.audited_executions: set[str] = set()
        #: decision features of every composed candidate (validity learning)
        self.features: dict[str, dict[str, float]] = {}
        self._outcome_cache: dict[tuple[str, State], Any] = {}
        self._outcome_version = -1
        self._probe_cache: tuple[int, list] | None = None
        #: whether a detached proxy may still steer search (False for v16.4)
        self.proxy_guard = True
        self.golden_tiebreak = bool(ablations.mathematical_structure)
        self.strategy = ""

    # -- budgets -----------------------------------------------------------------------
    @property
    def probes_remaining(self) -> int:
        return self.spec.probe_budget - self.probes_used

    @property
    def submissions_remaining(self) -> int:
        return self.spec.submission_budget - self.submissions_used

    @property
    def cost(self) -> float:
        return (self.probes_used * self.spec.probe_cost
                + self.submissions_used * self.spec.submission_cost)

    def account(self, result: Mapping[str, Any]) -> None:
        if "probes_remaining" in result:
            self.probes_used = self.spec.probe_budget - int(result["probes_remaining"])
        if "submissions_remaining" in result:
            self.submissions_used = (
                self.spec.submission_budget - int(result["submissions_remaining"])
            )

    # -- programs --------------------------------------------------------------------------
    def register(self, candidate: PlanCandidate) -> str:
        self.programs[candidate.action_id] = candidate
        return candidate.action_id

    def node_budget(self) -> int:
        return int(self.config.node_budget * self.budget_scale)

    def macros(self, table: Mapping[str, Mechanism]) -> dict[str, tuple[str, ...]]:
        if not self.ablations.learned_primitives:
            return {}
        return self.knowledge.skills.bind(table, self.spec.operators)

    def candidate_programs(self) -> list[PlanCandidate]:
        """Plans under the MAP model and posterior samples, scored by P(goal)."""
        posterior = self.posterior
        if posterior is None or self.spec.objective != ASSIGN:
            return []
        key = (posterior.version, self.representation, self.budget_scale,
               len(self.transfer_programs), bool(self.last_submission))
        if key in self._plan_cache:
            return self._plan_cache[key]
        spec = self.spec
        rng = random.Random(self.seed * 7919 + posterior.version)
        tables = [("map-plan", posterior.map_table())]
        samples = int(self.knowledge.params.get("plan_samples", self.config.plan_samples))
        tables += [
            (f"sample-plan-{i}", posterior.sample_table(rng))
            for i in range(samples)
        ]
        found: dict[tuple[str, ...], PlanCandidate] = {}
        budget = self.node_budget()
        for origin, table in tables:
            result = plan(
                table, spec.operators, self.start, spec.goal, spec.domains,
                representation=self.representation,
                max_length=spec.max_program_length,
                node_budget=budget,
                macros=self.macros(table),
            )
            self.planning_expansions += result.expanded
            if origin == "map-plan":
                self.last_plan = result
            if result.program is not None and result.program not in found:
                found[result.program] = PlanCandidate(
                    result.program, 0.0, "", origin, self.representation,
                    result.expanded, tuple(result.macros_used),
                )
        last = self.last_submission
        if last and not last.get("goal_met") and last.get("trajectory"):
            table = posterior.map_table()
            failed = tuple(last["program"])
            predicted = []
            state = self.start
            for op in failed:
                state = table[op].apply(state, spec.domains)
                predicted.append(list(state))
            repaired = repair(
                failed, last["trajectory"], predicted, table, spec.operators,
                self.start, spec.goal, spec.domains,
                representation=self.representation, max_length=spec.max_program_length,
                node_budget=budget, macros=self.macros(table),
            )
            self.planning_expansions += repaired.expanded
            if repaired.program is not None and repaired.program not in found:
                found[repaired.program] = PlanCandidate(
                    repaired.program, 0.0, "", "repair", self.representation,
                    repaired.expanded, tuple(repaired.macros_used),
                )
        for program, source in self.transfer_programs:
            if program and len(program) <= spec.max_program_length and program not in found:
                found[program] = PlanCandidate(program, 0.0, "", f"transfer:{source}",
                                               self.representation)
        candidates = []
        for program, candidate in found.items():
            scored = posterior.success_probability(
                program, self.start, spec.goal, seed=self.seed
            )
            candidate.probability = float(scored["probability"])
            candidate.method = str(scored["method"])
            candidates.append(candidate)
        candidates.sort(key=lambda c: (-c.probability, len(c.program), c.action_id))
        self._plan_cache[key] = candidates
        return candidates

    # -- evidence quantities -------------------------------------------------------------------
    def relevant_uncertain_ops(self, candidates: Sequence[PlanCandidate]) -> list[str]:
        """Unidentified operators that can matter for the goal.

        Relevance is probabilistic: an operator counts if it appears in a
        leading plan, or if the posterior gives non-negligible mass to
        mechanisms that write a goal variable (or a variable those writers
        read).  With no plan at all, every unidentified operator is relevant —
        nothing can be ruled out yet.
        """
        posterior = self.posterior
        if posterior is None:
            return []
        uncertain = [op for op in self.spec.operators
                     if posterior.map_mechanism(op)[1] < 1.0 - 1e-9]
        if not candidates:
            return uncertain
        ops: list[str] = []
        for candidate in candidates[:3]:
            for op in candidate.program:
                if op in uncertain and op not in ops:
                    ops.append(op)
        targets = {i for i, _ in self.spec.goal}
        for mechanism in posterior.map_table().values():
            if mechanism.writes() & targets:
                targets |= mechanism.reads()
        for op in uncertain:
            if op in ops:
                continue
            mass = sum(p for mechanism, p in posterior.marginal(op)
                       if mechanism.writes() & targets)
            if mass > 1e-3:
                ops.append(op)
        return ops

    def _step_outcomes(
        self, op: str, state: State, restricted: Mapping[str, list[tuple[int, float]]]
    ) -> dict[State, tuple[float, list[tuple[int, float]]]]:
        """Outcome distribution of ``op`` at ``state`` and the consistent subsets."""
        posterior = self.posterior
        rows = restricted.get(op)
        cache_key = None
        if rows is None:
            if self._outcome_version != posterior.version:
                self._outcome_cache.clear()
                self._outcome_version = posterior.version
            cache_key = (op, state)
            cached = self._outcome_cache.get(cache_key)
            if cached is not None:
                return cached
            rows = posterior.marginal_indices(op)
        outputs = posterior._outputs_for(op, state)
        total = sum(p for _, p in rows) or 1.0
        grouped: dict[State, tuple[float, list[tuple[int, float]]]] = {}
        for index, p in rows:
            nxt = outputs[index]
            mass, members = grouped.get(nxt, (0.0, []))
            members.append((index, p))
            grouped[nxt] = (mass + p / total, members)
        if cache_key is not None:
            self._outcome_cache[cache_key] = grouped
        return grouped

    def sequence_information(self, program: Sequence[str], *, branch_cap: int = 12) -> float:
        """Expected information (bits) a probe programme reveals about mechanisms.

        Every step of a probe is observed, so the gain is
        ``Σ_t E[H(s_t | s_{t-1}, earlier observations)]``.  Branches carry the
        hypotheses each operator is still consistent with on that branch, so an
        operator applied twice is conditioned on its first application (this is
        what separates ``add`` from ``set``).  Branches below the top
        ``branch_cap`` by probability are truncated (declared approximation).
        """
        branches: list[tuple[State, float, dict[str, list[tuple[int, float]]]]] = [
            (self.start, 1.0, {})
        ]
        information = 0.0
        for op in program:
            grown = []
            for state, weight, restricted in branches:
                outcomes = self._step_outcomes(op, state, restricted)
                probs = {nxt: mass for nxt, (mass, _) in outcomes.items()}
                information += weight * sum(
                    -q * math.log2(q) for q in probs.values() if q > 0.0
                )
                for nxt, (mass, members) in outcomes.items():
                    child = dict(restricted)
                    child[op] = members
                    grown.append((nxt, weight * mass, child))
            grown.sort(key=lambda row: -row[1])
            kept = grown[:branch_cap]
            norm = sum(w for _, w, _ in kept) or 1.0
            branches = [(s_, w / norm, r) for s_, w, r in kept]
        return information

    def probe_candidates(self) -> list[tuple[tuple[str, ...], float]]:
        """Probe programmes ranked by expected information gain per probe.

        A probe costs the same whatever its length (up to the declared limit),
        and every intermediate state is observed, so programmes are grown
        greedily step by step to maximise total expected information,
        starting from every operator.
        """
        posterior = self.posterior
        if posterior is None:
            return []
        if self._probe_cache and self._probe_cache[0] == posterior.version:
            return self._probe_cache[1]
        spec = self.spec
        length = max(1, spec.max_probe_length)
        uncertain = [op for op in spec.operators if posterior.op_entropy(op) > 1e-9]
        if not uncertain:
            self._probe_cache = (posterior.version, [])
            return []
        pool = sorted(spec.operators, key=lambda op: (-posterior.op_entropy(op), op))
        scored: dict[tuple[str, ...], float] = {}
        for first in pool:
            program: tuple[str, ...] = (first,)
            gain = self.sequence_information(program)
            while len(program) < length:
                best_next, best_gain = None, gain
                for op in pool:
                    trial = self.sequence_information(program + (op,))
                    if trial > best_gain + 1e-9:
                        best_next, best_gain = op, trial
                if best_next is None:
                    break
                program, gain = program + (best_next,), best_gain
            if gain > 1e-9:
                scored[program] = gain
        ranked = sorted(scored.items(), key=lambda row: (-row[1], len(row[0]), row[0]))
        ranked = ranked[: self.config.probe_candidate_limit]
        self._probe_cache = (posterior.version, ranked)
        return ranked

    def voi_bound(self, candidates: Sequence[PlanCandidate]) -> dict[str, float]:
        """Non-myopic value-of-perfect-information bound versus its cost.

        Perfect knowledge of the uncertain operators the leading plans rely on
        can raise P(goal) to at most 1, worth ``(1 - P_best) · V``; acquiring
        it costs about one probe per such operator.  Both terms use declared
        task quantities only.
        """
        best = candidates[0].probability if candidates else 0.0
        uncertain = self.relevant_uncertain_ops(candidates)
        return {
            "p_best": best,
            "value_of_success": self.value,
            "vpi": (1.0 - best) * self.value,
            "uncertain_relevant_ops": float(len(uncertain)),
            "identification_cost": max(1, len(uncertain)) * self.spec.probe_cost,
        }

    # -- response search (replayable, query-driven) ---------------------------------------
    def _run_response(self, strategy: str) -> tuple[int | None, Any]:
        """Replay the chosen search over known evaluations.

        Returns ``(query, trace)``: the first unknown setting the search needs
        (``None`` when it has finished or the budget is spent) and the trace.
        """
        from . import phi_mechanisms as phi

        response = self.response
        known = dict(response.values)

        class _Need(Exception):
            def __init__(self, setting: int) -> None:
                self.setting = setting

        def evaluate(setting: int) -> float:
            if setting in known:
                return known[setting]
            raise _Need(setting)

        size = response.size
        budget = max(0, self.probes_remaining)
        golden = bool(self.ablations.mathematical_structure)
        try:
            if strategy == "fibonacci-search":
                trace = phi.fibonacci_search(evaluate, size, budget, known=known)
            elif strategy == "ternary-search":
                trace = phi.ternary_search(evaluate, size, budget, known=known)
            else:
                exploration = max(2, int(round(
                    self.knowledge.params["explore_fraction"] * self.spec.probe_budget)))
                trace = phi.explore_then_refine(
                    evaluate, size, budget, exploration=exploration, golden=golden, known=known
                )
        except _Need as need:
            return need.setting, None
        return None, trace

    def next_response_query(self, strategy: str) -> int | None:
        if self.response is None or self.probes_remaining <= 0:
            return None
        query, _ = self._run_response(strategy)
        return query

    def response_answers(self, strategy: str) -> list[int]:
        """Best settings to submit: the search's answer, then best observed."""
        response = self.response
        if response is None:
            return []
        query, trace = self._run_response(strategy)
        ranked = response.ranked()
        answers: list[int] = []
        if trace is not None:
            answers.append(int(trace.best))
        for setting in ranked:
            if setting not in answers:
                answers.append(setting)
        if not answers:
            answers.append(response.size // 2)
        return answers

    def response_budget_view(self) -> dict[str, Any]:
        response = self.response
        if response is None:
            return {}
        return {
            "evaluated": len(response.values),
            "unimodal_violation": response.violation,
            "best": response.ranked()[0] if response.values else None,
        }


__all__ = [
    "AgentConfig",
    "EpisodeContext",
    "PlanCandidate",
    "ProxyAudit",
    "ResponseSearch",
    "structural_class",
    "structure_tokens",
    "success_value",
]
