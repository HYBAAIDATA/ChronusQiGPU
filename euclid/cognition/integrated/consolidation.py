"""Episode consolidation: abstraction, skill learning and transfer bookkeeping.

After every episode the consolidator turns what happened into durable,
provenance-carrying knowledge — unless the knowledge is frozen for held-out
evaluation, in which case it reports what it *would* have learned and changes
nothing:

* semantic memory — mechanism-kind and observation-noise frequencies (the
  abduction priors), response-shape frequencies;
* causal memory — the identified mechanism structure (the analogy substrate);
* procedural memory — the abstract and the concrete solution programme;
* episodic memory — the episode summary (deliberately *not* keyed by action
  identity, so the legacy memory-bias channel cannot replay programmes by name);
* strategy memory — episode utility per structural class, with negative
  transfer detection;
* skills — verified solutions feed primitive discovery; periodic lifecycle;
* analogy reliability, decision-feature validity, calibration and novelty;
* the transfer ledger — every transfer attempt with a positive/negative label.
"""
from __future__ import annotations

from typing import Any, Mapping

from ...contracts import domain_hash
from ..state import CognitiveState, MemoryKind, Outcome
from ..worlds.mechanisms import Mechanism
from .analogy import causal_memory_payload
from .composition import _program_descriptor
from .context import structure_tokens
from .memory import memory_item
from .skills import TaskModel, abstract_window

LIFECYCLE_EVERY = 4  # solved-task corpus growth between skill lifecycle passes


class EpisodeConsolidator:
    def __init__(self, context: Any, knowledge: Any, analogy: Any | None = None,
                 learning_adapter: Any | None = None) -> None:
        self.context = context
        self.knowledge = knowledge
        self.analogy = analogy
        self.learning_adapter = learning_adapter
        self.cycle_records: list[str] = []

    def record_episode(self, state: CognitiveState, *, success: bool, cycle: int,
                       result: Mapping[str, Any], channel: str = "consolidation") -> str:
        """Per-cycle closure; delegates to the canonical LearningService if wired."""
        if self.learning_adapter is not None:
            digest = self.learning_adapter.record_episode(
                state, success=success, cycle=cycle, result=result, channel=channel)
        else:
            digest = domain_hash("euclid.integrated.cycle.v1", {
                "problem": state.problem_id, "cycle": cycle, "success": bool(success)})
        self.cycle_records.append(digest)
        return digest

    def consolidate(self, state: CognitiveState) -> dict[str, Any]:
        ctx = self.context
        knowledge = self.knowledge
        spec = ctx.spec
        solved = state.outcome is Outcome.SOLVED
        utility = (max(0.0, 1.0 - ctx.cost / ctx.value) if solved else 0.0)
        posterior = ctx.posterior
        identified: dict[str, Mechanism] = {}
        if posterior is not None:
            identified = {op: m for op, (m, _) in posterior.identified(0.99).items()}
        program = []
        if solved and ctx.submissions:
            program = [step if isinstance(step, str) else list(step)
                       for step in ctx.submissions[-1]["program"]]
        report: dict[str, Any] = {
            "solved": solved,
            "utility": round(utility, 6),
            "cost": ctx.cost,
            "probes": ctx.probes_used,
            "submissions": ctx.submissions_used,
            "planning_expansions": ctx.planning_expansions,
            "strategy": state.selected_strategy,
            "representation": ctx.representation,
            "identified_operators": len(identified),
            "proxy_audit": ctx.audit.to_json(),
        }
        if self.analogy is not None:
            report["analogies"] = self.analogy.outcomes()
        if knowledge.frozen:
            report["learning"] = "frozen (held-out evaluation): nothing written"
            return report
        knowledge.episodes += 1
        ablations = ctx.ablations
        learned: dict[str, Any] = {}

        # semantic memory --------------------------------------------------------------
        if posterior is not None:
            for mechanism in identified.values():
                knowledge.kind_counts[mechanism.kind] = (
                    knowledge.kind_counts.get(mechanism.kind, 0.0) + 1.0)
            noise = posterior.model_posterior()
            dominant = max(range(len(noise)), key=noise.__getitem__)
            if any(posterior.observations[op] for op in posterior.operators):
                name = posterior.noise_models[dominant].name
                knowledge.noise_counts[name] = knowledge.noise_counts.get(name, 0.0) + 1.0
            learned["semantic"] = {"kinds": sorted(m.kind for m in identified.values())}
        if ctx.response is not None:
            if ctx.response.violation:
                knowledge.response_counts["multimodal"] += 1.0
            elif solved:
                knowledge.response_counts["unimodal"] += 1.0

        # strategy memory ----------------------------------------------------------------
        if ablations.meta_learning and state.selected_strategy:
            outcome = knowledge.strategies.record_episode(
                ctx.problem_class, state.selected_strategy, utility)
            if "negative_transfer" in outcome:
                knowledge.transfer_ledger.append(
                    {"kind": "strategy", "outcome": "negative", **outcome["negative_transfer"]})
            learned["strategy"] = outcome

        # calibration and decision validity ---------------------------------------------------
        knowledge.calibration.extend((float(p), int(y)) for p, y in ctx.calibration)
        for row in state.actual_outcomes:
            features = ctx.features.get(str(row["action"]))
            if features:
                knowledge.record_validity(features, bool(row["goal_met"]))

        # structured memories -------------------------------------------------------------------
        tokens = structure_tokens(spec)
        provenance = f"episode:{spec.task_id}"
        knowledge.memory.store(memory_item(
            f"episodic:{spec.task_id}", MemoryKind.EPISODIC,
            {"problem_id": spec.task_id, "strategy": state.selected_strategy,
             "outcome": state.outcome.value if state.outcome else None,
             "utility": utility, "probes": ctx.probes_used,
             "submissions": ctx.submissions_used},
            provenance, tokens, utility,
        ))
        # Causal memory keeps the most probable mechanisms (p > 0.5) and their
        # probabilities: an analogy built on them must still reproduce the
        # target's observations before it is adopted, and is withdrawn on
        # contradicting evidence.
        probable_causal = {}
        if posterior is not None:
            for op in spec.operators:
                mechanism, p = posterior.map_mechanism(op)
                if mechanism is not None and p > 0.5:
                    probable_causal[op] = mechanism
        if probable_causal and ablations.analogy:
            knowledge.memory.store(memory_item(
                f"causal:{spec.task_id}", MemoryKind.CAUSAL,
                causal_memory_payload(spec, probable_causal, program if solved else []),
                provenance, tokens, 1.0 if solved else 0.5,
            ))
        if solved and program and posterior is not None and all(
            isinstance(step, str) and step in identified for step in program
        ):
            abstract = abstract_window([identified[op] for op in program])
            knowledge.memory.store(memory_item(
                f"procedural:{spec.task_id}", MemoryKind.PROCEDURAL,
                {"abstract_program": repr(abstract), "surface_program": program,
                 "strategy": state.selected_strategy},
                provenance, tokens, 1.0,
            ))
        if ablations.meta_learning and state.selected_strategy:
            knowledge.memory.store(memory_item(
                f"strategy:{spec.task_id}", MemoryKind.STRATEGY,
                {"class": ctx.problem_class, "strategy": state.selected_strategy,
                 "utility": utility}, provenance, tokens, utility,
            ))

        # skills: discovery, lifecycle and monitoring ----------------------------------------------
        if ablations.learned_primitives:
            for row in ctx.submissions:
                for label in row.get("skills", ()):
                    knowledge.skills.record_use(label, bool(row["goal_met"]),
                                                surface=spec.surface_domain)
            # The skill corpus uses the most probable mechanisms consistent with
            # the *verified* successful trajectory; every macro mined from it is
            # re-validated by measured planning utility before promotion, and
            # bound plans are re-scored under the live posterior before use.
            probable = {}
            if posterior is not None:
                for op in spec.operators:
                    mechanism, p = posterior.map_mechanism(op)
                    if mechanism is not None and p > 0.5:
                        probable[op] = mechanism
            if solved and program and all(
                isinstance(step, str) and step in probable for step in program
            ):
                model = TaskModel(spec.task_id, spec.surface_domain, tuple(spec.domains),
                                  tuple(spec.operators),
                                  {op: probable.get(op, Mechanism("noop"))
                                   for op in spec.operators},
                                  tuple(spec.initial_state), tuple(spec.goal),
                                  spec.max_program_length)
                knowledge.skills.observe_solution(model, program)
                if len(knowledge.skills.corpus) % LIFECYCLE_EVERY == 0:
                    learned["skills"] = knowledge.skills.lifecycle()

        # analogy reliability and transfer ledger ------------------------------------------------
        if self.analogy is not None:
            for row in self.analogy.outcomes():
                bucket = "exact" if not row["contradicted"] else "partial"
                stats = knowledge.analogy_stats.setdefault(bucket, [0.0, 0.0])
                stats[0] += row["confirmed"]
                stats[1] += row["contradicted"]
                knowledge.memory.record_transfer(row["memory_id"], row["contradicted"] == 0)
                knowledge.transfer_ledger.append({
                    "kind": "analogy", "source": row["memory_id"], "target": spec.task_id,
                    "outcome": "negative" if row["contradicted"] else "positive",
                    "abandoned": row["abandoned"], "solved": solved,
                })

        # novelty (behavioural descriptors of correct solutions only) ---------------------------------
        if solved and program:
            descriptor = _program_descriptor(program, spec.max_program_length,
                                             len(spec.operators))
            learned["novelty"] = knowledge.novelty.consider(
                descriptor, correct=True, invariants_hold=True)
            learned["novelty"] = {k: (v if not isinstance(v, tuple) else list(v))
                                  for k, v in learned["novelty"].items()
                                  if k != "novelty" or v != float("inf")}
        report["learned"] = learned
        return report


__all__ = ["EpisodeConsolidator", "LIFECYCLE_EVERY"]
