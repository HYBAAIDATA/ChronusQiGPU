"""CognitiveService: wires the integrated intelligence loop into EuclidRuntime.

This is the composition point the v16 consolidation was missing.  Enabling
intelligence on a runtime:

* registers governed organs for the v16 engine and the cognition core;
* grants creator-scoped dispatch rights (execution stays fail-closed);
* hydrates episodic memory, the program world model and the strategy policy
  from durable state (they survive restart);
* routes every cognition request through the canonical loop and records a
  sealed CognitiveEpisode plus a governed Experience per episode.

No new authority is created: search/probe execution is PROPOSE-class work
performed by the existing sandbox; world mutation stays with Kairos;
learning flows only through the existing LearningService.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Mapping

from ..contracts import Experience, RewardAuthority
from ..evidence import atomic_write, load_json
from ..governance import Authority, Organ
from ..search.deep_mcts import DeepMCTSEngine, SearchBudget
from ..adapter import EuclidEngineAdapter
from .baselines import (
    BanditMetaLearner,
    InMemoryMemorySystem,
    SignalMetaController,
    StructuralAnalogyEngine,
    WeightedObjective,
)
from .core import AblationConfig, GeneralIntelligenceCore
from .episode import CognitiveEpisode, episode_from_state
from .interfaces import MemoryItem
from .program_domain import (
    DivergenceDiscriminator,
    ProgramAbducer,
    ProgramDeducer,
    ProgramWorldModel,
    program_signature,
    signature_class,
)
from .state import CandidateAction, MemoryKind
from .planner import HierarchicalPlanner

STRATEGIES = ("deep-mcts", "evolutionary-search", "greedy-surrogate")

# Wall-clock telemetry belongs in the timestamped evidence chain, never in
# the replay-deterministic cognitive state or the sealed episode core.
NON_DETERMINISTIC_KEYS = frozenset({"wall_time_ms"})


def strip_non_deterministic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            k: strip_non_deterministic(v)
            for k, v in value.items()
            if k not in NON_DETERMINISTIC_KEYS
        }
    if isinstance(value, list):
        return [strip_non_deterministic(v) for v in value]
    return value


OBJECTIVE_WEIGHTS = {
    "correctness_estimate": 0.5,
    "cost": -0.2,
    "uncertainty": -0.15,
    "novelty": 0.05,
    "transfer_value": 0.1,
}


class _StrategyComposer:
    """Candidate actions are the strategy portfolio, scored from learned stats."""

    def __init__(self, metalearner: BanditMetaLearner, problem_class: str) -> None:
        self._learner = metalearner
        self._class = problem_class

    def compose(self, goal: str, state) -> list[CandidateAction]:
        candidates = []
        stats = self._learner._stats  # read-only introspection for scoring
        for strategy in STRATEGIES:
            successes, trials = stats.get((self._class, strategy), [0, 0])
            estimate = successes / trials if trials else 0.5  # ignorant prior
            candidates.append(
                CandidateAction(
                    f"strategy:{strategy}",
                    f"solve via {strategy}",
                    origin=f"strategy-portfolio:{strategy}",
                    features={
                        "correctness_estimate": estimate,
                        "cost": {
                            "deep-mcts": 0.6,
                            "evolutionary-search": 0.4,
                            "greedy-surrogate": 0.2,
                        }[strategy],
                        "uncertainty": 1.0 / (1.0 + trials),
                        "novelty": 0.0,
                        "transfer_value": 0.3 if trials else 0.0,
                    },
                )
            )
        return candidates


class _GovernedEpisodeExecutor:
    """Routes every intervention/plan execution through the runtime's
    governed Delegator; captures the episode's problem context."""

    def __init__(self, service: "CognitiveService", context: dict[str, Any]) -> None:
        self._service = service
        self._context = context

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        runtime = self._service.runtime
        kind = str(payload.get("kind", ""))
        if kind == "intervention":
            request = {
                "op_kind": "probe",
                "operator": action,
                "code": self._context["code"],
                "external_test_code": self._context.get("external_test_code"),
            }
            result = dict(
                runtime.delegator.dispatch(
                    "euclid-engine", "probe", request, confident=True, safe=True
                )
            )
            return strip_non_deterministic(result)
        strategy = action.split(":", 1)[-1]
        request = {
            "op_kind": "search",
            "strategy": strategy,
            "code": self._context["code"],
            "target": self._context["problem_id"],
            "seed": self._context["seed"],
            "budget_evaluations": self._context["budget_evaluations"],
            "external_test_code": self._context.get("external_test_code"),
            "signature": self._context["signature"],
        }
        result = dict(
            runtime.delegator.dispatch(
                "euclid-engine", "search", request, confident=True, safe=True
            )
        )
        return strip_non_deterministic(result)


class CognitiveService:
    """Owns the live wiring between EuclidRuntime and the intelligence stack."""

    def __init__(
        self,
        runtime: Any,
        *,
        seed: int = 42,
        clock: Callable[[], float] = time.time,
        ablations: AblationConfig | None = None,
        software_revision: str = "unknown",
    ) -> None:
        self.runtime = runtime
        self.seed = int(seed)
        self.clock = clock
        self.ablations = ablations or AblationConfig()
        self.software_revision = software_revision
        self.state_root = Path(runtime.state_dir) / "cognition"
        self.episodes_dir = self.state_root / "episodes"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)

        self.adapter = EuclidEngineAdapter(
            persistent_repo_path=str(
                Path(runtime.state_dir)
                / "var"
                / "euclid"
                / "registry"
                / "primitive_repository.json"
            )
        )
        self.world_model = self._load_world_model()
        self.metalearner = self._load_strategy_stats()
        self.memory = InMemoryMemorySystem()
        self._hydrate_memory()
        self._register_organs()

    # -- persistence ---------------------------------------------------------
    @property
    def _world_model_path(self) -> Path:
        return self.state_root / "world_model.json"

    @property
    def _strategy_path(self) -> Path:
        return self.state_root / "strategy_stats.json"

    def _load_world_model(self) -> ProgramWorldModel:
        if self._world_model_path.is_file():
            return ProgramWorldModel.from_dict(load_json(self._world_model_path))
        return ProgramWorldModel()

    def _load_strategy_stats(self) -> BanditMetaLearner:
        if self._strategy_path.is_file():
            return BanditMetaLearner.from_dict(load_json(self._strategy_path))
        return BanditMetaLearner()

    def _persist(self) -> None:
        atomic_write(self._world_model_path, self.world_model.to_dict())
        atomic_write(self._strategy_path, self.metalearner.to_dict())

    def _consolidate(self, episode: CognitiveEpisode) -> None:
        """Knowledge consolidation: a completed episode becomes episodic
        memory immediately (live) — not only after a restart rehydration."""
        memory_id = f"episode:{episode.problem_id}"
        if any(m.memory_id == memory_id for m in self.memory.retrieve(frozenset())):
            return
        self.memory.store(
            MemoryItem(
                memory_id=memory_id,
                kind=MemoryKind.EPISODIC,
                payload={
                    "outcome": episode.outcome,
                    "signature": sorted(episode.representation.get("structure", ())),
                    "surface": [episode.problem_id],
                    "selected_strategy": episode.selected_strategy,
                    "executed_action": (
                        episode.candidates[0]["action_id"] if episode.candidates else None
                    ),
                    "executed_arm": episode.actual_result.get("strategy"),
                    "success": episode.outcome == "solved",
                },
                provenance=f"cognitive-episode:{episode.episode_id}",
                structural_features=frozenset(episode.representation.get("structure", ())),
                transfer_value=0.5 if episode.outcome == "solved" else 0.1,
            )
        )

    def _hydrate_memory(self) -> None:
        for path in sorted(self.episodes_dir.glob("*.json")):
            try:
                episode = CognitiveEpisode.load(path)
            except ValueError:
                continue  # tampered/foreign episode files never enter memory
            self._consolidate(episode)

    # -- governed organ registration ------------------------------------------
    def _register_organs(self) -> None:
        runtime = self.runtime

        def engine_handler(request: Mapping[str, Any]) -> Mapping[str, Any]:
            return self._execute_engine_request(dict(request))

        runtime.register_organ(
            Organ(
                organ_id="euclid-engine",
                capabilities=frozenset({"analyze", "probe", "search"}),
                authority=Authority.PROPOSE,
                handler=engine_handler,
            )
        )
        for capability in ("analyze", "probe", "search"):
            runtime.rights.grant(runtime.creator_id, "euclid-engine", capability, "dispatch")

    def _execute_engine_request(self, request: dict[str, Any]) -> Mapping[str, Any]:
        op_kind = request.get("op_kind")
        if op_kind == "probe":
            return self._probe(request)
        if op_kind == "search":
            return self._search(request)
        if op_kind == "analyze":
            return self.adapter.analyze(
                str(request.get("target", "unknown")), str(request.get("code", ""))
            )
        raise ValueError("unsupported engine op_kind")

    # -- real implementations behind the organ ---------------------------------
    def _probe(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Discriminating intervention: apply one operator, sandbox-evaluate,
        measure the true fitness delta bucket.  Real execution, small cost."""
        from ..core.primitives import ASTPrimitives

        operator = str(request["operator"])
        code = str(request["code"])
        test_code = request.get("external_test_code")
        op_funcs = dict(ASTPrimitives.get_all_operators())
        if operator not in op_funcs:
            return {
                "observation": "unknown",
                "goal_met": False,
                "diagnostic": "operator not in vocabulary",
            }
        calculator = self.adapter.engine.calculator
        base_features = calculator.extract_features(code)
        node_count = int(base_features.get("node_count", 50))
        base_fitness = calculator.compute_multi_objective_fitness(
            code, initial_node_count=node_count, tests_passed=True
        )
        candidate, _ = op_funcs[operator](code, self.seed)
        parse_v, compile_v, test_v, msg = self.adapter.engine.evaluator.evaluate_validity(
            candidate, None, test_code
        )
        if not (parse_v and compile_v and test_v):
            delta = -0.5
        else:
            fitness = calculator.compute_multi_objective_fitness(
                candidate, initial_node_count=node_count, tests_passed=True
            )
            delta = round(fitness - base_fitness, 6)
        bucket = ProgramWorldModel._bucket(delta)
        signature = program_signature(code)
        self.world_model.observe_gain(signature, operator, delta)
        return {"observation": bucket, "delta": delta, "goal_met": False, "diagnostic": msg}

    def _search(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Plan execution: run the selected strategy under a hard budget."""
        strategy = str(request["strategy"])
        code = str(request["code"])
        test_code = request.get("external_test_code")
        budget_evals = int(request.get("budget_evaluations", 12))
        seed = int(request.get("seed", self.seed))
        signature = request.get("signature")
        signature = frozenset(signature) if signature else program_signature(code)

        if strategy == "deep-mcts":
            engine = DeepMCTSEngine(
                repository=self.adapter.repository,
                seed=seed,
                world_model=self.world_model,
            )
            result = engine.search(
                str(request.get("target", "target.py")),
                code,
                budget=SearchBudget(
                    max_evaluations=budget_evals, max_depth=4, max_wall_seconds=20.0
                ),
                signature=signature,
                external_test_code=test_code,
            )
            improvement = result["measured_improvement"]
            telemetry = {
                key: value
                for key, value in result.items()
                if key not in ("best_code", "phi_diagnostics")
            }
        elif strategy == "evolutionary-search":
            self.adapter.engine.seed = seed
            result = self.adapter.engine.run_optimization(
                str(request.get("target", "target.py")),
                code,
                max_generations=max(1, budget_evals // 6),
                external_test_code=test_code,
            )
            improvement = result["total_delta_phi"]
            telemetry = {key: value for key, value in result.items() if key != "final_code"}
        elif strategy == "greedy-surrogate":
            self.adapter.engine.seed = seed
            result = self.adapter.engine.run_optimization(
                str(request.get("target", "target.py")),
                code,
                max_generations=1,
                external_test_code=test_code,
            )
            improvement = result["total_delta_phi"]
            telemetry = {key: value for key, value in result.items() if key != "final_code"}
        else:
            raise ValueError(f"unknown strategy {strategy!r}")

        bucket = ProgramWorldModel._bucket(float(improvement))
        # The world model is updated exactly once per executed action, in the
        # core loop's compare phase; observing here as well double-counted
        # every measured transition (adversarial review finding).
        return {
            "observation": bucket,
            "goal_met": float(improvement) > 0.0,
            "measured_improvement": float(improvement),
            "strategy": strategy,
            "telemetry": telemetry,
        }

    # -- the canonical entrypoint ------------------------------------------------
    def solve(
        self,
        problem: Mapping[str, Any],
        *,
        budget_evaluations: int = 12,
    ) -> CognitiveEpisode:
        code = str(problem.get("code", ""))
        if not code.strip():
            raise ValueError("problem requires code")
        problem_id = str(problem.get("problem_id") or "").strip()
        if not problem_id:
            raise ValueError("problem requires a problem_id")
        goal = str(problem.get("goal") or "improve measured fitness with tests passing")
        seed = int(problem.get("seed", self.seed))
        test_code = problem.get("external_test_code")

        signature = program_signature(code)
        problem_class = signature_class(signature)
        context_key = problem_class

        composer = _StrategyComposer(self.metalearner, problem_class)
        core = GeneralIntelligenceCore(
            world_model=self.world_model,
            memory=self.memory,
            analogy=StructuralAnalogyEngine(min_overlap=0.3),
            abducer=ProgramAbducer(),
            deducer=ProgramDeducer(),
            discriminator=DivergenceDiscriminator(),
            metacontroller=SignalMetaController(),
            metalearner=self.metalearner,
            planner=HierarchicalPlanner(),
            skills=composer,
            objective=WeightedObjective(OBJECTIVE_WEIGHTS),
            executor=_GovernedEpisodeExecutor(
                self,
                {
                    "code": code,
                    "problem_id": problem_id,
                    "seed": seed,
                    "budget_evaluations": budget_evaluations,
                    "external_test_code": test_code,
                    "signature": sorted(signature),
                },
            ),
            evidence=self.runtime.evidence,
            clock=self.clock,
            max_cycles=2,
            ablations=self.ablations,
        )
        state = core.solve(
            {
                "problem_id": problem_id,
                "goal": goal,
                "context_key": context_key,
                "problem_class": problem_class,
                "structure": sorted(signature),
                "surface": [problem_id],
                "observations": [f"target program of {len(code)} bytes"],
            },
            goal=goal,
            problem_class=problem_class,
        )

        actual = self._last_execution_result(state)
        strategy_basis = self.metalearner.select_strategy(problem_class, STRATEGIES).basis
        episode = episode_from_state(
            state,
            goal=goal,
            problem_class=problem_class,
            strategy_basis=strategy_basis,
            actual_result=actual,
            causal_attribution={
                "method": "sandbox-discriminating-intervention + measured search outcome",
                "hypotheses": {h.hypothesis_id: h.status.value for h in state.hypotheses},
            },
            memory_updates=(f"episode:{problem_id}",),
            promoted_or_rejected={
                "promoted_primitives": sorted(self.adapter.repository.repository),
                "note": "promotion requires sandbox trials; phi alone never promotes",
            },
            replay_lineage=(f"episode:{problem_id}",),
            software_revision=self.software_revision,
            created_at=self.clock(),
        )
        episode.save(self.episodes_dir / f"{problem_id}.json")
        self._consolidate(episode)
        self._persist()
        try:
            self._record_experience(problem_id, problem_class, goal, state, actual)
        except ValueError as exc:
            # Replay protection fails closed; record the rejection as evidence
            # rather than crashing a completed episode.
            self.runtime.evidence.append(
                "cognition-experience-rejected",
                {
                    "problem_id": problem_id,
                    "reason": str(exc),
                },
            )
        self.runtime.evidence.append(
            "cognition-episode-sealed",
            {
                "episode_id": episode.episode_id,
                "problem_id": problem_id,
                "outcome": episode.outcome,
            },
        )
        return episode

    @staticmethod
    def _last_execution_result(state) -> dict[str, Any]:
        for item in reversed(state.evidence_items):
            if item.evidence_id.startswith("exec-"):
                return dict(item.content.get("result", {}))
        return {"observation": "none", "goal_met": False}

    @staticmethod
    def _last_executed_action(state) -> str | None:
        for item in reversed(state.evidence_items):
            if item.evidence_id.startswith("exec-"):
                action = item.content.get("action")
                return str(action) if action else None
        return None

    def _record_experience(
        self, problem_id: str, problem_class: str, goal: str, state, actual: Mapping[str, Any]
    ) -> None:
        improvement = float(actual.get("measured_improvement") or 0.0)
        reward = max(-1.0, min(1.0, improvement))
        executed = self._last_executed_action(state)
        action = (
            executed.split(":", 1)[1]
            if isinstance(executed, str) and executed.startswith("strategy:")
            else executed
        )
        self.runtime.learning.record(
            Experience(
                experience_id=f"cognition-{problem_id}",
                mission_id="cognition",
                domain=problem_class,
                source="cognitive-service",
                observation={"problem_id": problem_id, "goal": goal},
                action=action or state.selected_strategy or "none",
                outcome={
                    "outcome": state.outcome.value if state.outcome else "unexecuted",
                    "measured_improvement": improvement,
                },
                reward=reward,
                reward_authority=RewardAuthority.MEASURED_ENVIRONMENT,
                provenance=f"cognitive-episode:{problem_id}",
                uncertainty=0.0,
                replay_id=f"episode-replay:{problem_id}",
            )
        )


def enable_intelligence(
    runtime: Any,
    *,
    seed: int = 42,
    clock: Callable[[], float] = time.time,
    ablations: AblationConfig | None = None,
    software_revision: str = "unknown",
) -> CognitiveService:
    """Wire the intelligence stack into a runtime (idempotent per runtime)."""
    existing = getattr(runtime, "intelligence", None)
    if isinstance(existing, CognitiveService):
        return existing
    service = CognitiveService(
        runtime,
        seed=seed,
        clock=clock,
        ablations=ablations,
        software_revision=software_revision,
    )
    runtime.intelligence = service
    return service


__all__ = ["CognitiveService", "STRATEGIES", "enable_intelligence"]
