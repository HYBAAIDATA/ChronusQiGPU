"""Metacognition and meta-learning over cognitive strategies.

:class:`EvidenceMetaController` reasons about the episode's own reasoning:
before acting it decides whether more evidence is worth its declared cost;
after acting it decides whether to continue, replan, repair the model,
abandon transferred knowledge, change representation or strategy, or halt.
Every decision cites the measured signals that caused it.

:class:`ContextualStrategyLearner` learns which cognitive strategy works for
which *structural* problem class, with a weak global prior, explicit
bookkeeping of when that prior misleads (negative strategy transfer), and a
frozen mode for held-out evaluation.

Reporting thresholds that label evidence strength use the conventional
Jeffreys scale (Bayes factor 10 = strong); they are documented, not tuned.
"""
from __future__ import annotations

import math
import random
from typing import Any, Mapping, Sequence

from ..interfaces import ControlAssessment, StrategyChoice
from ..state import CognitiveState

STRONG_EVIDENCE_BF = 10.0  # Jeffreys (1961): "strong"

ASSIGN_STRATEGIES = (
    "abduce-intervene-deduce",
    "analogy-causal-plan",
    "evolve-synthesise-transfer",
    "rollout-search-execute",
    "voi-plan",
)
RESPONSE_STRATEGIES_PHI = ("explore-refine", "fibonacci-search")
RESPONSE_STRATEGIES_NEUTRAL = ("explore-refine", "ternary-search")


class EvidenceMetaController:
    """Evidence-driven pre-action and post-action control."""

    def __init__(self, context: Any) -> None:
        self.context = context
        self.log: list[dict[str, Any]] = []

    # -- before acting ---------------------------------------------------------------
    def pre_action(self, state: CognitiveState) -> ControlAssessment:
        ctx = self.context
        strategy = state.selected_strategy or ""
        ctx.strategy = strategy
        if ctx.probes_remaining <= 0:
            return ControlAssessment("act", "probe budget exhausted",
                                     {"probes_remaining": 0.0})
        if ctx.spec.objective != "assign":
            query = ctx.next_response_query(strategy)
            signals = {"evaluated": float(len(ctx.response.values)),
                       "probes_remaining": float(ctx.probes_remaining),
                       "unimodal_violation": float(ctx.response.violation)}
            if query is not None:
                return ControlAssessment(
                    "seek_evidence", f"search {strategy} needs the response at {query}", signals,
                )
            return ControlAssessment("act", f"search {strategy} has located its optimum",
                                     signals)
        if ctx.posterior is None:
            return ControlAssessment("act", "no world model: evidence cannot be used",
                                     {"world_model": 0.0})
        probes = ctx.probe_candidates()
        best_gain = probes[0][1] if probes else 0.0
        candidates = ctx.candidate_programs()
        bound = ctx.voi_bound(candidates)
        signals = {
            "best_expected_information_bits": best_gain,
            "p_best": bound["p_best"],
            "vpi": bound["vpi"],
            "identification_cost": bound["identification_cost"],
            "uncertain_relevant_ops": bound["uncertain_relevant_ops"],
            "probes_remaining": float(ctx.probes_remaining),
            "plans": float(len(candidates)),
        }
        if best_gain <= 1e-9:
            return ControlAssessment("act", "no probe can change the posterior", signals)
        if strategy == "evolve-synthesise-transfer":
            return ControlAssessment("act", "model-free strategy: evidence policy off", signals)
        if strategy == "rollout-search-execute":
            # Act first: submit as soon as one submission pays for itself in
            # expectation (P·V >= c_submit) and let execution feedback teach.
            break_even = ctx.spec.submission_cost / ctx.value
            signals["submission_break_even"] = break_even
            if candidates and bound["p_best"] >= break_even:
                return ControlAssessment(
                    "act",
                    f"act-first: P(goal) {bound['p_best']:.3f} covers submission break-even "
                    f"{break_even:.3f}",
                    signals,
                )
            return ControlAssessment(
                "seek_evidence",
                f"act-first: P(goal) {bound['p_best']:.3f} below break-even {break_even:.3f}",
                signals,
            )
        if strategy == "abduce-intervene-deduce":
            uncertain = ctx.relevant_uncertain_ops(candidates)
            if uncertain:
                return ControlAssessment(
                    "seek_evidence",
                    f"identification strategy: {len(uncertain)} relevant operator(s) uncertain",
                    signals,
                )
            return ControlAssessment("act", "every relevant operator identified", signals)
        # voi-plan and analogy-causal-plan: value of information versus its cost
        if bound["vpi"] > bound["identification_cost"]:
            return ControlAssessment(
                "seek_evidence",
                f"VPI {bound['vpi']:.3f} exceeds identification cost "
                f"{bound['identification_cost']:.3f}",
                signals,
            )
        return ControlAssessment(
            "act",
            f"VPI {bound['vpi']:.3f} does not cover identification cost "
            f"{bound['identification_cost']:.3f}",
            signals,
        )

    # -- after acting ---------------------------------------------------------------------
    def assess(self, state: CognitiveState) -> ControlAssessment:
        ctx = self.context
        last = ctx.last_submission or {}
        signals: dict[str, float] = {
            "submissions_remaining": float(ctx.submissions_remaining),
            "probes_remaining": float(ctx.probes_remaining),
            "last_goal_met": float(bool(last.get("goal_met"))),
            "latest_prediction_error": float(state.prediction_errors[-1])
            if state.prediction_errors else 0.0,
        }
        if last.get("goal_met"):
            return ControlAssessment("continue", "goal verified", signals)
        if ctx.submissions_remaining <= 0:
            return ControlAssessment("halt_stalled", "submission budget exhausted", signals)
        posterior = ctx.posterior
        if posterior is not None:
            collapsed = posterior.exact_collapsed()
            unresolved = [
                op for op in collapsed
                if not any(r["op"] == op and r["resolution"] != "unresolved"
                           for r in posterior.rebuilds)
            ]
            signals["exact_collapsed_ops"] = float(len(collapsed))
            observed_ops = sum(1 for op in posterior.operators if posterior.observations[op])
            # Localised collapse (one operator inconsistent while others stay
            # exactly explained) is a model failure, not observation noise.
            if len(unresolved) == 1 and observed_ops >= 3:
                return ControlAssessment(
                    "repair_model",
                    f"operator {unresolved[0]!r} contradicts every grammar hypothesis "
                    f"while {observed_ops - 1} others remain exactly explained",
                    signals,
                )
            contradicted = []
            for op in list(posterior.boosts):
                evidence = posterior.boost_evidence(op)
                if evidence and evidence["bayes_factor"] < 1.0 / STRONG_EVIDENCE_BF:
                    contradicted.append(op)
            signals["contradicted_transfers"] = float(len(contradicted))
            if contradicted:
                return ControlAssessment(
                    "abandon_transfer",
                    f"transferred hypotheses for {sorted(contradicted)} have Bayes factor "
                    f"< 1/{STRONG_EVIDENCE_BF:g}",
                    signals,
                )
            plan = ctx.last_plan
            if plan is not None and plan.program is None and plan.budget_exhausted:
                signals["planner_exhausted"] = 1.0
                if ctx.representation != "hierarchical":
                    return ControlAssessment(
                        "change_representation",
                        f"planner exhausted its budget under {ctx.representation!r}",
                        signals,
                    )
                return ControlAssessment("adjust_plan_depth",
                                         "planner exhausted under every representation", signals)
        if state.selected_strategy == "evolve-synthesise-transfer" and posterior is not None:
            return ControlAssessment(
                "change_strategy",
                "model-free search failed while a world model is available",
                signals,
            )
        if ctx.response is not None and ctx.response.violation and state.selected_strategy in (
            "fibonacci-search", "ternary-search"
        ):
            return ControlAssessment(
                "change_strategy",
                "observed responses contradict the unimodality assumption",
                signals,
            )
        return ControlAssessment("replan", "execution failed; repair the plan from evidence",
                                 signals)


class ContextualStrategyLearner:
    """Per-class strategy utilities with a weak global prior and transfer ledger.

    Utility of an episode is in [0, 1]: success scaled by the fraction of the
    declared budget left unspent.  Selection is Thompson sampling over Beta
    posteriors while learning, and the posterior mean once frozen.
    """

    PRIOR_WEIGHT = 2.0  # pseudo-observations imported from the global prior

    def __init__(self, *, seed: int = 0) -> None:
        self.prior_weight = self.PRIOR_WEIGHT
        self.class_stats: dict[str, dict[str, list[float]]] = {}
        self.global_stats: dict[str, list[float]] = {}
        self.negative_transfer: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.frozen = False
        self._rng = random.Random(seed)

    def _negative_transfer_entry(
        self, problem_class: str, strategy: str
    ) -> dict[str, Any] | None:
        return next(
            (
                entry
                for entry in reversed(self.negative_transfer)
                if entry.get("class") == problem_class
                and entry.get("imported") == strategy
            ),
            None,
        )

    def _posterior(self, problem_class: str, strategy: str) -> tuple[float, float, int, bool]:
        klass = self.class_stats.get(problem_class, {}).get(strategy, [0.0, 0.0])
        glob = self.global_stats.get(strategy, [0.0, 0.0])
        alpha, beta = 1.0 + klass[0], 1.0 + klass[1] - klass[0]
        used_prior = False
        blocked_prior = self._negative_transfer_entry(problem_class, strategy) is not None
        if klass[1] < 2 and glob[1] > 0 and not blocked_prior:
            mean = glob[0] / glob[1]
            alpha += self.prior_weight * mean
            beta += self.prior_weight * (1.0 - mean)
            used_prior = True
        return alpha, beta, int(klass[1]), used_prior

    def select_strategy(self, problem_class: str, available: Sequence[str]) -> StrategyChoice:
        if not available:
            raise ValueError("at least one strategy is required")
        original = tuple(available)
        suppressed = tuple(
            strategy for strategy in original
            if self._negative_transfer_entry(problem_class, strategy) is not None
        )
        eligible = tuple(strategy for strategy in original if strategy not in suppressed)
        if eligible:
            available = eligible
        rows = []
        for strategy in available:
            alpha, beta, n, used_prior = self._posterior(problem_class, strategy)
            mean = alpha / (alpha + beta)
            draw = mean if self.frozen else self._rng.betavariate(alpha, beta)
            rows.append((draw, mean, n, used_prior, strategy))
        rows.sort(key=lambda r: (-r[0], r[4]))
        draw, mean, n, used_prior, chosen = rows[0]
        mode = "posterior mean (frozen)" if self.frozen else "Thompson sample"
        basis = (
            f"{mode} {draw:.3f} (mean {mean:.3f}) from {n} class episode(s)"
            + (" + global prior" if used_prior else "")
        )
        if suppressed and eligible:
            basis += " | negative-transfer guard suppressed " + ",".join(sorted(suppressed))
            self.events.append({
                "class": problem_class,
                "event": "abandon_negative_transfer",
                "suppressed": list(sorted(suppressed)),
                "selected": chosen,
            })
        return StrategyChoice(chosen, tuple(s for s in original if s != chosen), basis)

    def update(self, problem_class: str, strategy_id: str, success: bool,
               detail: str = "") -> None:
        """Cycle-level signal from the core: recorded, not used for selection."""
        self.events.append({"class": problem_class, "strategy": strategy_id,
                            "cycle_success": bool(success)})
        if len(self.events) > 500:
            del self.events[:250]

    def update_credit(self, problem_class: str, strategy_id: str, credit: float,
                      detail: str = "") -> None:
        return None

    def record_episode(self, problem_class: str, strategy: str, utility: float) -> dict[str, Any]:
        """Bank an episode utility; detect negative transfer of the global prior."""
        utility = max(0.0, min(1.0, float(utility)))
        report: dict[str, Any] = {"class": problem_class, "strategy": strategy,
                                  "utility": utility}
        if self.frozen:
            report["frozen"] = True
            return report
        klass = self.class_stats.setdefault(problem_class, {}).setdefault(strategy, [0.0, 0.0])
        klass[0] += utility
        klass[1] += 1.0
        glob = self.global_stats.setdefault(strategy, [0.0, 0.0])
        glob[0] += utility
        glob[1] += 1.0
        detected = self._detect_negative_transfer(problem_class)
        if detected:
            report["negative_transfer"] = detected
        return report

    def _detect_negative_transfer(self, problem_class: str) -> dict[str, Any] | None:
        """Detect when an imported global preference is harmful in this class."""
        if not self.global_stats:
            return None
        global_best = max(
            self.global_stats,
            key=lambda s: (self.global_stats[s][0] / max(1.0, self.global_stats[s][1]), s),
        )
        stats = self.class_stats.get(problem_class, {})
        imported = stats.get(global_best)
        if imported is None or imported[1] < 3:
            return None
        if self._negative_transfer_entry(problem_class, global_best) is not None:
            return None

        def beta(row: Sequence[float]) -> tuple[float, float]:
            a, b = 1.0 + row[0], 1.0 + row[1] - row[0]
            mean = a / (a + b)
            var = a * b / ((a + b) ** 2 * (a + b + 1.0))
            return mean, var

        imported_mean, imported_var = beta(imported)
        rivals = [(s, row) for s, row in stats.items() if s != global_best and row[1] >= 3]
        best_rival = None
        rival_probability = 0.0
        rival_mean = None
        if rivals:
            best_rival, rival_row = max(
                rivals, key=lambda kv: (kv[1][0] / kv[1][1], kv[0])
            )
            rival_mean, rival_var = beta(rival_row)
            z = (rival_mean - imported_mean) / math.sqrt(rival_var + imported_var)
            rival_probability = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

        global_row = self.global_stats[global_best]
        source_row = [
            max(0.0, global_row[0] - imported[0]),
            max(0.0, global_row[1] - imported[1]),
        ]
        source_probability = 0.0
        source_mean = None
        if source_row[1] >= 3:
            source_mean, source_var = beta(source_row)
            z = (source_mean - imported_mean) / math.sqrt(source_var + imported_var)
            source_probability = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

        probability = max(rival_probability, source_probability)
        if probability < 0.95:
            return None
        entry = {
            "class": problem_class,
            "imported": global_best,
            "better": best_rival,
            "remediation": "suppress_imported_strategy_and_global_prior",
            "probability_harmful": round(probability, 4),
            "probability_rival_better": round(rival_probability, 4),
            "probability_source_better": round(source_probability, 4),
            "class_mean_imported": round(imported_mean, 4),
            "class_mean_better": round(rival_mean, 4) if rival_mean is not None else None,
            "source_mean_imported": round(source_mean, 4) if source_mean is not None else None,
        }
        self.negative_transfer.append(entry)
        self.events.append({"event": "negative_transfer_detected", **entry})
        return entry

    def summary(self) -> dict[str, Any]:
        return {
            "classes": {
                klass: {s: {"mean": round(row[0] / row[1], 4) if row[1] else None,
                            "n": int(row[1])} for s, row in sorted(stats.items())}
                for klass, stats in sorted(self.class_stats.items())
            },
            "negative_transfer": list(self.negative_transfer),
        }

    def to_payload(self) -> dict[str, Any]:
        return {"schema": "euclid.contextual-strategy/1",
                "class_stats": self.class_stats, "global_stats": self.global_stats,
                "negative_transfer": self.negative_transfer}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ContextualStrategyLearner":
        if payload.get("schema") != "euclid.contextual-strategy/1":
            raise ValueError("unsupported strategy payload")
        learner = cls()
        learner.class_stats = {k: {s: list(r) for s, r in v.items()}
                               for k, v in payload["class_stats"].items()}
        learner.global_stats = {k: list(v) for k, v in payload["global_stats"].items()}
        learner.negative_transfer = list(payload["negative_transfer"])
        return learner


__all__ = [
    "ASSIGN_STRATEGIES",
    "ContextualStrategyLearner",
    "EvidenceMetaController",
    "RESPONSE_STRATEGIES_NEUTRAL",
    "RESPONSE_STRATEGIES_PHI",
    "STRONG_EVIDENCE_BF",
]
