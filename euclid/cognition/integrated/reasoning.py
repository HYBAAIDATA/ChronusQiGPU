"""Abduction, deduction, causal discrimination and the active world model.

These specialists implement the core's interfaces over the shared
:class:`~.context.EpisodeContext`:

* :class:`MechanismAbducer` keeps *competing* explanations — mechanism
  hypotheses per unidentified operator, observation-noise regimes, and for
  response tasks the unimodal/multimodal shape hypotheses.  It never
  collapses to one explanation; only evidence does.
* :class:`MechanismDeducer` derives what each explanation predicts a probe
  would show.
* :class:`InformationGainDiscriminator` chooses the probe with maximal
  expected information gain and performs the likelihood-based update.
* :class:`MechanismWorldModel` is the active substrate: predictions,
  imagined rollouts (always labelled imagined), counterfactual comparison
  against doing nothing, learning from whole execution trajectories,
  breakdown detection and selective repair.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from ..interfaces import Intervention, ModelHealth
from ..state import CognitiveState, Hypothesis, HypothesisStatus, PredictionRecord
from ..worlds.mechanisms import Mechanism
from .world_model import entropy_bits

TOP_HYPOTHESES = 3


def _hypothesis_id(op: str, mechanism: Mechanism) -> str:
    return f"{op}=>" + json.dumps(mechanism.to_json(), separators=(",", ":"))


class MechanismAbducer:
    def __init__(self, context: Any) -> None:
        self.context = context

    def hypothesise(self, observations: Sequence[Any], state: CognitiveState) -> list[Hypothesis]:
        ctx = self.context
        hypotheses: list[Hypothesis] = []
        if ctx.response is not None:
            prior = ctx.knowledge.unimodal_prior()
            violation = ctx.response.violation
            p_uni = 0.0 if violation else prior
            # Shape hypotheses stay in competition (confidence carries the
            # evidence); the search keeps gathering evidence either way.
            hypotheses.append(Hypothesis(
                "response=>unimodal", "the response curve has a single peak",
                "semantic-memory:response-shape-prior", p_uni,
            ))
            hypotheses.append(Hypothesis(
                "response=>multimodal", "the response curve has several peaks",
                "semantic-memory:response-shape-prior", 1.0 - p_uni,
            ))
            return hypotheses
        posterior = ctx.posterior
        if posterior is None:
            return hypotheses
        for model, p in zip(posterior.noise_models, posterior.model_posterior()):
            hypotheses.append(Hypothesis(
                f"noise=>{model.name}",
                f"observations follow the {model.name} reading model (eps={model.epsilon})",
                "world-model:competing-noise-models", min(1.0, max(0.0, p)),
            ))
        for op in posterior.operators:
            rows = posterior.marginal(op)
            if not rows:
                continue
            if rows[0][1] >= 1.0 - 1e-9:
                mechanism, p = rows[0]
                hypotheses.append(Hypothesis(
                    _hypothesis_id(op, mechanism),
                    f"{op} implements {mechanism.describe(ctx.spec.variables)}",
                    self._provenance(op, mechanism), min(1.0, p),
                ))
                continue
            for mechanism, p in rows[:TOP_HYPOTHESES]:
                hypotheses.append(Hypothesis(
                    _hypothesis_id(op, mechanism),
                    f"{op} implements {mechanism.describe(ctx.spec.variables)}",
                    self._provenance(op, mechanism), min(1.0, max(0.0, p)),
                ))
        return hypotheses

    def _provenance(self, op: str, mechanism: Mechanism) -> str:
        boost = self.context.posterior.boosts.get(op)
        if boost and mechanism.to_json() in boost["mechanisms"]:
            return f"analogy:{boost['source']}"
        grammar = self.context.posterior.grammar[op]
        return "mechanism-grammar:" + ("expanded" if "pair" in grammar else "default")


class MechanismDeducer:
    def __init__(self, context: Any) -> None:
        self.context = context

    def consequences(self, hypothesis: Hypothesis, world_model: Any,
                     context: str) -> list[PredictionRecord]:
        ctx = self.context
        if "=>" not in hypothesis.hypothesis_id or ctx.posterior is None:
            return []
        op, encoded = hypothesis.hypothesis_id.split("=>", 1)
        if op in ("noise", "response"):
            return []
        mechanism = Mechanism.from_json(json.loads(encoded))
        outcome = mechanism.apply(ctx.start, ctx.spec.domains)
        return [PredictionRecord(
            f"ded-{hypothesis.hypothesis_id}", context, f"probe:{op}",
            json.dumps(list(outcome), separators=(",", ":")),
            hypothesis.confidence, imagined=False,
        )]


class InformationGainDiscriminator:
    """Choose the maximally informative intervention; update by likelihood."""

    def __init__(self, context: Any) -> None:
        self.context = context

    def discriminate(self, hypotheses: Sequence[Hypothesis],
                     predictions: Mapping[str, Sequence[PredictionRecord]]) -> Intervention | None:
        ctx = self.context
        if ctx.probes_remaining <= 0:
            return None
        if ctx.response is not None:
            query = ctx.next_response_query(getattr(ctx, "strategy", "") or "")
            if query is None:
                return None
            return Intervention(
                f"probe:{ctx.response.operator}@{query}", 1.0,
                f"response search requires the value at setting {query}",
                {"program": [[ctx.response.operator, int(query)]]},
            )
        candidates = ctx.probe_candidates()
        if not candidates:
            return None
        cost = ctx.spec.probe_cost
        program, gain = candidates[0]
        if getattr(ctx, "golden_tiebreak", False):
            ties = [row for row in candidates if abs(row[1] - gain) < 1e-12]
            if len(ties) > 1:
                from .phi_mechanisms import golden_weyl_points

                index = golden_weyl_points(1, len(ties), offset=(ctx.probes_used * 0.618) % 1)[0]
                program, gain = ties[index]
        return Intervention(
            "probe:" + "+".join(program), gain,
            f"expected information gain {gain:.3f} bits for cost {cost:g} "
            f"({len(candidates)} candidate probes)",
            {"program": list(program)},
        )

    def posterior_update(self, state: CognitiveState, intervention: Intervention,
                         observed: Mapping[str, Any]) -> tuple[list[Hypothesis], dict[str, Any]]:
        ctx = self.context
        ctx.account(observed)
        if observed.get("budget_exhausted"):
            return [], {"budget_exhausted": True}
        program = list(intervention.payload.get("program", ()))
        if ctx.response is not None:
            for step, value in zip(observed.get("trajectory", ()), observed.get("responses", ())):
                ctx.response.observe(int(step[0]), float(value))
            hypotheses = MechanismAbducer(ctx).hypothesise((), state)
            return hypotheses, {"response": ctx.response_budget_view()}
        posterior = ctx.posterior
        before = {op: posterior.op_entropy(op) for op in posterior.operators}
        records = posterior.observe_trajectory(program, ctx.start, observed["trajectory"])
        if "scores" in observed:
            ctx.audit.observe(observed["trajectory"], observed["scores"], ctx.spec.goal, ctx.start)
        after = {op: posterior.op_entropy(op) for op in posterior.operators}
        updated: list[Hypothesis] = []
        alive: dict[str, float] = {}
        for op in posterior.operators:
            for mechanism, p in posterior.marginal(op):
                alive[_hypothesis_id(op, mechanism)] = p
        for hypothesis in state.hypotheses:
            if "=>" not in hypothesis.hypothesis_id or hypothesis.hypothesis_id.startswith(
                ("noise=>", "response=>")
            ):
                continue
            if hypothesis.status is not HypothesisStatus.ACTIVE:
                continue
            p = alive.get(hypothesis.hypothesis_id, 0.0)
            if p <= 0.0:
                updated.append(hypothesis.with_update(
                    confidence=0.0, status=HypothesisStatus.REFUTED,
                    refute=f"likelihood-zero:{intervention.action}",
                ))
            elif p >= 1.0 - 1e-9:
                updated.append(hypothesis.with_update(
                    confidence=min(1.0, p), status=HypothesisStatus.CONFIRMED,
                    support=f"posterior:{intervention.action}",
                ))
            else:
                updated.append(hypothesis.with_update(confidence=p))
        noise = dict(zip([m.name for m in posterior.noise_models], posterior.model_posterior()))
        for hypothesis in state.hypotheses:
            if hypothesis.hypothesis_id.startswith("noise=>"):
                name = hypothesis.hypothesis_id.split("=>", 1)[1]
                updated.append(hypothesis.with_update(confidence=min(1.0, noise.get(name, 0.0))))
        details = {
            "program": program,
            "surprise_bits": [r["surprise_bits"] for r in records],
            "entropy_reduction_bits": round(sum(before.values()) - sum(after.values()), 6),
            "noise_model_posterior": {k: round(v, 6) for k, v in noise.items()},
            "exact_collapsed": posterior.exact_collapsed(),
            "proxy_audit": ctx.audit.to_json(),
        }
        return updated, details


class MechanismWorldModel:
    """Core-facing world model over the shared posterior."""

    def __init__(self, context: Any) -> None:
        self.context = context
        self._sequence = 0

    def _candidate(self, action: str):
        return self.context.programs.get(action)

    def _final_state(self, program: Sequence[Any]) -> list[int] | None:
        ctx = self.context
        if ctx.posterior is None:
            return None
        table = ctx.posterior.map_table()
        state = ctx.start
        for op in program:
            state = table[op].apply(state, ctx.spec.domains)
        return list(state)

    def _record(self, context: str, action: str, imagined: bool) -> PredictionRecord:
        self._sequence += 1
        candidate = self._candidate(action)
        if candidate is None:
            return PredictionRecord(f"mwm-{self._sequence}", context, action, "unknown",
                                    0.0, imagined)
        final = self._final_state(candidate.program)
        expected = (json.dumps(final, separators=(",", ":")) if final is not None
                    else json.dumps({"program": list(candidate.program)}))
        return PredictionRecord(f"mwm-{self._sequence}", context, action, expected,
                                min(1.0, max(0.0, candidate.probability)), imagined)

    def predict(self, context: str, action: str) -> PredictionRecord:
        return self._record(context, action, False)

    def rollout(self, context: str, actions: Sequence[str]) -> list[PredictionRecord]:
        return [self._record(context, action, True) for action in actions]

    def update(self, context: str, action: str, observed: str) -> float:
        record = self._record(context, action, False)
        return 0.0 if record.expected == observed else 1.0

    def counterfactual(self, context: str, actions: Sequence[str]) -> list[dict[str, Any]]:
        """Predicted goal progress of each plan stage versus doing nothing."""
        ctx = self.context
        goal = ctx.spec.goal
        rows = []
        for action in actions:
            if action == "no-intervention":
                progress = sum(1 for i, v in goal if ctx.start[i] == v)
            else:
                candidate = self._candidate(action)
                final = self._final_state(candidate.program) if candidate else None
                if final is None:
                    continue
                progress = sum(1 for i, v in goal if final[i] == v)
            rows.append({"action": action,
                         "future": {"outcome": progress / max(1, len(goal))},
                         "epistemic_status": "predicted", "imagined": True})
        return rows

    def observe_result(self, context: str, action: str, result: Mapping[str, Any]) -> float:
        """Learn from an executed program; return |outcome − predicted P(goal)|."""
        ctx = self.context
        candidate = self._candidate(action)
        predicted = candidate.probability if candidate is not None else 0.0
        goal_met = bool(result.get("goal_met"))
        if result.get("budget_exhausted"):
            return 0.0
        ctx.calibration.append((float(predicted), goal_met))
        if ctx.response is not None:
            for step, value in zip(result.get("trajectory", ()), result.get("responses", ())):
                ctx.response.observe(int(step[0]), float(value))
        elif ctx.posterior is not None and result.get("trajectory"):
            ctx.posterior.observe_trajectory(
                list(result["program"]), ctx.start, result["trajectory"]
            )
            if "scores" in result:
                ctx.audit.observe(result["trajectory"], result["scores"], ctx.spec.goal,
                                  ctx.start)
        return abs(float(goal_met) - float(predicted))

    def health(self) -> ModelHealth:
        ctx = self.context
        if ctx.posterior is None:
            return ModelHealth("healthy", 0.0, "no mechanism model in this episode")
        collapsed = ctx.posterior.exact_collapsed()
        errors = [abs(float(y) - p) for p, y in ctx.calibration]
        mean = sum(errors) / len(errors) if errors else 0.0
        if collapsed:
            return ModelHealth("breakdown", mean, f"exact model contradicted for {collapsed}")
        return ModelHealth("degraded" if mean > 0.5 else "healthy", mean)

    def repair(self, state: CognitiveState) -> dict[str, Any]:
        posterior = self.context.posterior
        if posterior is None:
            return {"repaired": []}
        reports = [posterior.rebuild(op) for op in posterior.exact_collapsed()]
        return {"repaired": reports}

    def uncertainty_summary(self) -> dict[str, Any]:
        ctx = self.context
        if ctx.response is not None:
            return {"kind": "response", **ctx.response_budget_view()}
        posterior = ctx.posterior
        if posterior is None:
            return {"kind": "none"}
        entropies = {op: posterior.op_entropy(op) for op in posterior.operators}
        return {
            "kind": "mechanism",
            "total_entropy_bits": round(sum(entropies.values()), 6),
            "unidentified_ops": sorted(op for op, h in entropies.items() if h > 1e-9),
            "noise_model_posterior": [round(p, 6) for p in posterior.model_posterior()],
        }

    def assumptions(self) -> list[dict[str, Any]]:
        ctx = self.context
        rows: list[dict[str, Any]] = []
        if ctx.response is not None:
            rows.append({"assumption": "response curve is unimodal",
                         "status": "contradicted" if ctx.response.violation else "assumed"})
            return rows
        posterior = ctx.posterior
        if posterior is None:
            return rows
        noise = posterior.model_posterior()
        rows.append({"assumption": "readings are exact", "probability": round(noise[0], 6),
                     "status": "inferred" if noise[0] > 0.99 else "uncertain"})
        for op in posterior.operators:
            mechanism, p = posterior.map_mechanism(op)
            if mechanism is None:
                rows.append({"assumption": f"{op} has a grammar mechanism",
                             "status": "contradicted"})
                continue
            rows.append({
                "assumption": f"{op}: {mechanism.describe(ctx.spec.variables)}",
                "probability": round(p, 6),
                "status": "inferred" if p >= 1.0 - 1e-9 else "uncertain",
            })
        return rows


def outcome_entropy(probability: float) -> float:
    return entropy_bits({0: probability, 1: 1.0 - probability})


__all__ = [
    "InformationGainDiscriminator",
    "MechanismAbducer",
    "MechanismDeducer",
    "MechanismWorldModel",
    "outcome_entropy",
]
