"""TOEMachine — the TOE reasoning core (one backend, every problem form).

``toe.runtime.TOEIntelligenceRuntime`` is the production composition root
(tenancy, receipts, evidence chain, feedback/ASI loops, mining boundary); it
composes this machine through ``solve`` / ``learn``, one machine per tenant.
The machine itself is the reasoning cycle beneath every domain adapter.

One problem, any domain, one reasoning cycle::

    Problem ─► represent ─► understand ─► futures ─► meta (VOI, precision)
            ─► decide / plan ─► arbitrate ─► explain ─► govern ─► receipt
    outcome ─► bind ─► prediction error ─► assess ─► revise ─► memory ─► persist

Every stage calls the existing TOE module that owns the capability
(``representation``/``intelligence_state``, ``relationships`` +
``causal_stack`` + ``uncertainty``, ``causal_stack.evaluate_futures`` /
``futures_env``, ``meta_reasoning``, ``precision``, ``policy``,
``planning``, ``arbitration``, ``decision_explanation``,
``self_governance``, ``world_model``, ``memory``, ``topology`` +
``geometry``, ``receipts``, ``custody``). The machine adds composition,
provenance and persistence; it is not another intelligence hierarchy.

Invariants enforced here:

* the reasoning path never reads ``problem.domain`` — the label only names
  the learning namespace and the provenance (``trace`` records every
  backend callable executed, so cross-domain reuse is measured);
* futures are predictions: every future carries ``epistemic_status:
  "predicted"`` and the model revision it came from;
* a causal effect is released only when identified; a decision built on a
  supplied structure is labelled model-dependent;
* learning in one namespace never revises another (negative-transfer
  guard); transfer between namespaces is explicit and shape-checked;
* persistence goes through THESEUS custody or is reported UNAVAILABLE.
"""

from __future__ import annotations

import math
import time
from fractions import Fraction
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import __version__ as TOE_VERSION
from .arbitration import arbitrate
from .causal_ladder import (
    ARITHMETIC_EXACT,
    CausalCapabilityUnavailable,
    counterfactual_state,
    intervene,
)
from .causal_stack import evaluate_futures, futures_env, identifiability
from .custody import CustodyUnavailable, SnapshotStore
from .decision_explanation import explain_contrastive, explain_decision, falsify_decision
from .memory import MemoryStore
from .meta_reasoning import choose_path, meta_decide, value_of_information
from .planning import compare_plan_vs_greedy, generate_actions
from .policy import PolicyDecision, counterfactual_futures, decide
from .precision import select_precision
from .problem import Problem, Structure
from .receipts import ReceiptLedger, digest
from .relationships import association, relationship_ladder
from .self_governance import self_check
from .uncertainty import uncertainty_report
from .world_model import (
    INSUFFICIENT_EVIDENCE,
    MODEL_CONTRADICTED,
    MODEL_DRIFT,
    MODEL_SUPPORTED,
    assess_structural,
    bind_outcome,
    fit_structural_weights,
)

MACHINE_VERSION = "toe.machine/v1"
EPISODE_SCHEMA = "toe.episode/v1"

ACT = "ACT"
ACQUIRE_EVIDENCE = "ACQUIRE_EVIDENCE"
NAVIGATE = "NAVIGATE"
UNREACHABLE = "UNREACHABLE"
DESCRIBE = "DESCRIBE"
NO_DECISION = "NO_DECISION"
REFUSED = "REFUSED"

PREDICTED = "predicted (model-dependent; not an observed fact)"


def _ek(p: str, c: str) -> str:
    return f"{p}->{c}"


def _split(key: str) -> Tuple[str, str]:
    p, c = key.split("->", 1)
    return p, c


class _Trace:
    """Which backend callables a run executed — the reuse measurement."""

    def __init__(self) -> None:
        self.steps: List[Dict[str, str]] = []

    def __call__(self, stage: str, fn: Any) -> None:
        name = getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
        module = getattr(fn, "__module__", "?")
        self.steps.append({"stage": stage, "backend": f"{module}.{name}"})

    def backends(self) -> List[str]:
        return sorted({s["backend"] for s in self.steps})


def _primary_series(observation: Any) -> Optional[List[Any]]:
    """Longest numeric series in the observation (for forecasting)."""
    cols: List[List[Any]] = []

    def numeric(seq: Sequence[Any]) -> List[Any]:
        return [x for x in seq if isinstance(x, (int, float)) and not isinstance(x, bool)]

    if isinstance(observation, Mapping):
        for v in observation.values():
            if isinstance(v, (list, tuple)):
                cols.append(numeric(v))
    elif isinstance(observation, (list, tuple)):
        cols.append(numeric(observation))
    cols = [c for c in cols if len(c) >= 2]
    return max(cols, key=len) if cols else None


class TOEMachine:
    """The TOE backend: one machine for every problem form.

    ``custody``: a THESEUS custody (``EnterpriseCustody``-shaped) for
    durable learning state; ``None`` keeps state in-process and every
    persistence answer says UNAVAILABLE. ``stream`` names the snapshot
    chain inside custody. With custody bound, construction recovers the
    newest verified snapshot — a restart is not a newborn model.
    """

    def __init__(
        self,
        *,
        custody: Any = None,
        stream: str = "default",
        bridge: Any = None,
        min_evidence: int = 3,
        lens_policy: str = "signature",
    ) -> None:
        if lens_policy not in ("signature", "measured"):
            raise ValueError("lens_policy must be 'signature' or 'measured'")
        self.min_evidence = int(min_evidence)
        self.lens_policy = lens_policy
        self._bridge = bridge
        self.ledger = ReceiptLedger(run_id="toe.machine")
        self.models: Dict[str, Dict[str, Any]] = {}
        self.memory = MemoryStore()
        self.lens_utility: Dict[str, Dict[str, int]] = {}
        self.episodes: List[Dict[str, Any]] = []
        self.bindings: List[Dict[str, Any]] = []
        self.contradictions: List[Dict[str, Any]] = []
        self.negative_results: List[Dict[str, Any]] = []
        self.transfers: List[Dict[str, Any]] = []
        self.recovered_from: Optional[Dict[str, Any]] = None
        self._store: Optional[SnapshotStore] = (
            SnapshotStore(custody, stream=stream) if custody is not None else None
        )
        if self._store is not None:
            self._recover()

    # ------------------------------------------------------------------
    # shared resources
    # ------------------------------------------------------------------

    @property
    def bridge(self) -> Any:
        if self._bridge is None:
            from .bridge import TOEBridge

            self._bridge = TOEBridge()
        return self._bridge

    # ------------------------------------------------------------------
    # namespace models
    # ------------------------------------------------------------------

    def _model(self, problem: Problem) -> Optional[Dict[str, Any]]:
        if problem.structure is None:
            return None
        ns = problem.namespace()
        if ns not in self.models:
            prior = {_ek(p, c): float(w) for p, c, w in problem.structure.edges}
            self.models[ns] = {
                "namespace": ns,
                "shape_digest": problem.structure.shape_digest(),
                "edges": [[p, c] for p, c, _ in problem.structure.edges],
                "prior_weights": dict(prior),
                "weights": dict(prior),
                "standard_errors": {},
                "observations": [],
                "residuals": [],
                "assessment_from": 0,
                "revisions": [],
                "status": INSUFFICIENT_EVIDENCE,
                "noise_inflation": 1.0,
                "contradictions": 0,
                "evidence_requested": False,
            }
        return self.models[ns]

    def _weights_tuple(self, model: Mapping[str, Any]) -> Dict[Tuple[str, str], float]:
        return {_split(k): float(v) for k, v in model["weights"].items()}

    def _noise(self, problem: Problem, model: Optional[Mapping[str, Any]]) -> Dict[str, float]:
        inflation = float(model["noise_inflation"]) if model else 1.0
        nodes = problem.structure.all_nodes() if problem.structure else []
        return {n: float(problem.noise_sd.get(n, 1.0)) * inflation for n in nodes}

    def transfer(self, source_namespace: str, target: Problem, *, reason: str) -> Dict[str, Any]:
        """Explicit transfer of learned weights to another namespace.

        Allowed only when the structure *shapes* match; recorded with its
        reason. Learning never transfers implicitly.
        """
        src = self.models.get(source_namespace)
        if src is None:
            return {"transferred": False, "reason": f"unknown namespace {source_namespace!r}"}
        if target.structure is None or target.structure.shape_digest() != src["shape_digest"]:
            return {"transferred": False, "reason": "structure shapes differ; transfer refused"}
        model = self._model(target)
        assert model is not None
        before = dict(model["weights"])
        model["weights"] = dict(src["weights"])
        model["standard_errors"] = dict(src["standard_errors"])
        rec = {
            "from": source_namespace,
            "to": model["namespace"],
            "reason": reason,
            "before": before,
            "after": dict(model["weights"]),
        }
        self.transfers.append(rec)
        self.ledger.issue("machine.transfer", inputs={"from": source_namespace}, config={"reason": reason}, output=rec)
        return {"transferred": True, **rec}

    # ------------------------------------------------------------------
    # stages
    # ------------------------------------------------------------------

    def represent(self, problem: Problem, *, trace: Optional[_Trace] = None) -> Dict[str, Any]:
        """Bind the observation to its lenses (one identity, many views)."""
        from .intelligence_state import IntelligenceState
        from .representation import choose

        trace = trace or _Trace()
        obs = problem.observation if problem.observation is not None else dict(problem.state)
        graph = problem.structure.graph() if problem.structure else None
        trace("represent", choose)
        sel = choose(obs, graph=graph)
        selected = [name for name, _why in sel["selection"]["selected"]]
        skipped: List[Tuple[str, str]] = []
        if self.lens_policy == "measured":
            keep = []
            for lens in selected:
                u = self.lens_utility.get(lens, {})
                if u.get("selected", 0) >= 3 and u.get("decision_relevant", 0) == 0 and lens != "statistical":
                    skipped.append((lens, f"measured: selected {u['selected']}x, never decision-relevant"))
                else:
                    keep.append(lens)
            selected = keep
        trace("represent", IntelligenceState.observe)
        state = IntelligenceState.observe(obs, graph=graph, lenses=selected or ["statistical"], bridge=self.bridge)
        views = {name: v.as_dict() for name, v in state.views.items()}
        return {
            "observation_sha256": state.observation_sha256,
            "signature": sel["signature"],
            "selected": sel["selection"]["selected"],
            "rejected": sel["selection"]["rejected"],
            "skipped_by_measured_utility": skipped,
            "available_views": state.available_views(),
            "views": views,
            "provenance": state.verify_views(),
            "_state": state,
        }

    def identify(self, problem: Problem) -> Dict[str, Any]:
        """Identifiability of the problem's causal query (refusal is an answer)."""
        if problem.query is None:
            return {"verdict": None, "reason": "no causal query declared"}
        graph = problem.structure.graph() if problem.structure else None
        observed = problem.observed
        if observed is None and problem.structure is not None:
            observed = [n for n in problem.structure.all_nodes() if n not in problem.structure.latent]
        return identifiability(graph, problem.query[0], problem.query[1], observed=observed)

    def _understand(self, problem: Problem, scm: Any, noise: Mapping[str, float], trace: _Trace) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        treatment, outcome = problem.query if problem.query else (None, None)
        observed = problem.observed
        if observed is None and problem.structure is not None:
            observed = [n for n in problem.structure.all_nodes() if n not in problem.structure.latent]
        if problem.samples or problem.structure is not None:
            trace("understand", relationship_ladder)
            out["relationships"] = relationship_ladder(
                problem.samples,
                treatment=treatment,
                outcome=outcome,
                graph=scm.graph if scm is not None else None,
                observed=observed,
            )
        if problem.query is not None:
            trace("understand", identifiability)
            out["identifiability"] = self.identify(problem)
        if scm is not None and problem.query is not None:
            # The ladder as executed computation: rung 1 association vs
            # rung 2 do() on the model vs rung 3 counterfactual for this unit.
            ladder: Dict[str, Any] = {}
            if problem.samples:
                trace("understand", association)
                ladder["rung1_association"] = association(problem.samples, treatment, outcome)
            trace("understand", intervene)
            hi = intervene(scm, {treatment: 1.0}, arithmetic=ARITHMETIC_EXACT)
            lo = intervene(scm, {treatment: 0.0}, arithmetic=ARITHMETIC_EXACT)
            ladder["rung2_interventional"] = {
                "effect_per_unit_E_y_do_x": hi["values"][outcome] - lo["values"][outcome],
                "arithmetic": hi["arithmetic"],
                "model": "supplied structure (assumption) + current revision",
            }
            if all(n in problem.state for n in scm.graph.nodes):
                trace("understand", counterfactual_state)
                try:
                    cf = counterfactual_state(scm, {treatment: float(problem.state[treatment]) + 1.0}, problem.state, [outcome])
                    ladder["rung3_counterfactual"] = {
                        "unit_outcome_if_treatment_plus_1": cf["outcome_values"][outcome],
                        "factual_outcome": float(problem.state[outcome]),
                        "abduced_exogenous": cf["abduced_exogenous"],
                    }
                except CausalCapabilityUnavailable as exc:
                    ladder["rung3_counterfactual"] = {"available": False, "reason": exc.reason}
            else:
                ladder["rung3_counterfactual"] = {
                    "available": False,
                    "reason": "no complete factual state: a counterfactual needs an abducted unit, not another forward prediction",
                }
            out["causal_ladder"] = ladder
            trace("understand", uncertainty_report)
            out["uncertainty"] = uncertainty_report(
                scm,
                treatment,
                outcome,
                observed=observed,
                samples=problem.samples,
                noise_sd=noise,
            )
        return out

    def _forecast(self, problem: Problem, trace: _Trace) -> Dict[str, Any]:
        """Exact recurrence extrapolation when verified, else labelled trend."""
        series = _primary_series(problem.observation)
        steps = int(problem.forecast or 0)
        if series is None:
            return {"available": False, "reason": "no numeric series to forecast"}
        from kellogg.substrate import FAMILY_COEFFS, family_companion, int_mat_pow

        integral = all(float(x).is_integer() for x in series)
        if integral:
            ints = [int(x) for x in series]
            trace("forecast", family_companion)
            for family, coeffs in FAMILY_COEFFS.items():
                d = len(coeffs) - 1
                if len(ints) < d + 2:
                    continue
                companion = family_companion(family)
                last_row = companion[-1]
                holds = all(
                    ints[i + d] == sum(last_row[j] * ints[i + j] for j in range(d))
                    for i in range(len(ints) - d)
                )
                if not holds:
                    continue
                trace("forecast", int_mat_pow)
                power = int_mat_pow(companion, steps)
                window = ints[-d:]
                value = sum(power[-1][j] * window[j] for j in range(d))
                mults = 0
                n = steps
                while n:
                    mults += 2 if n & 1 else 1
                    n >>= 1
                return {
                    "available": True,
                    "method": "exact integer recurrence (KELLOGG companion-matrix power)",
                    "family": family,
                    "verified_terms": len(ints),
                    "steps": steps,
                    "value": str(value),
                    "operation_count": {"matrix_multiplications": mults, "naive_recurrence_steps": steps},
                    "evidence_class": "EXACT given the recurrence holds beyond the observed window (model assumption)",
                }
        n = len(series)
        xs = list(range(n))
        mx, my = sum(xs) / n, sum(float(v) for v in series) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (float(y) - my) for x, y in zip(xs, series)) / sxx if sxx else 0.0
        return {
            "available": True,
            "method": "least-squares linear trend (no exact recurrence verified)",
            "steps": steps,
            "value": my + slope * (n - 1 + steps - mx),
            "evidence_class": "MODEL-DEPENDENT extrapolation",
        }

    def _navigate(self, problem: Problem, trace: _Trace) -> Dict[str, Any]:
        """Navigation over a transition graph under three representations."""
        from .geometry import GeometryError, bfs_tree, disk_distance, embed_tree, greedy_route
        from .topology import StateTopology

        transitions = [tuple(e) for e in problem.transitions or ()]
        states = sorted({s for e in transitions for s in e}, key=str)
        topo = StateTopology(states, transitions)
        src, dst = problem.navigation if problem.navigation else (None, None)
        trace("navigate", StateTopology.shortest_path)
        path = topo.shortest_path(src, dst) if src is not None else None
        out: Dict[str, Any] = {
            "states": len(states),
            "transitions": len(transitions),
            "components": len(topo.components()),
            "articulation_points": [str(a) for a in topo.articulation_points()][:20],
            "query": [str(src), str(dst)] if src is not None else None,
            "reachable": path is not None,
            "route": [str(s) for s in path] if path else None,
        }
        if src is None or path is None:
            return out
        reps: List[Dict[str, Any]] = [
            {
                "name": "topological_bfs",
                "cost": len(topo.reachable(src)),
                "correctness": "exact-answer",
                "delivered": True,
                "evidence": "global breadth-first search over the declared transition relation",
            }
        ]
        symmetric = all((b, a) in set(transitions) for a, b in transitions)
        if symmetric:
            trace("navigate", embed_tree)
            try:
                emb = embed_tree(bfs_tree(transitions, states[0]))
                coords = emb["coords"]
                trace("navigate", greedy_route)
                res = greedy_route(transitions, src, dst, lambda a, b: disk_distance(coords[a], coords[b]))
                reps.append(
                    {
                        "name": "hyperbolic_greedy",
                        "cost": len(res["path"]) + len(states),
                        "correctness": "exact-answer" if res["delivered"] else "heuristic",
                        "delivered": res["delivered"],
                        "hops": len(res["path"]) - 1,
                        "evidence": "greedy routing on a Sarkar hyperbolic embedding of a spanning tree (delivery guaranteed by construction, measured here)",
                    }
                )
            except GeometryError as exc:
                reps.append({"name": "hyperbolic_greedy", "cost": math.inf, "correctness": "heuristic", "delivered": False, "evidence": str(exc)})
        else:
            out["hyperbolic_rejected"] = "directed transitions: greedy geometric routing assumes symmetric moves"
        if problem.coordinates is not None:
            coords2 = problem.coordinates
            res = greedy_route(
                transitions,
                src,
                dst,
                lambda a, b: math.hypot(coords2[a][0] - coords2[b][0], coords2[a][1] - coords2[b][1]),
            )
            reps.append(
                {
                    "name": "euclidean_greedy",
                    "cost": len(res["path"]),
                    "correctness": "heuristic",
                    "delivered": res["delivered"],
                    "hops": len(res["path"]) - 1,
                    "stuck_at": str(res["stuck_at"]) if res["stuck_at"] is not None else None,
                    "evidence": "greedy descent on declared coordinates (no delivery guarantee)",
                }
            )
        trace("navigate", choose_path)
        out["representations"] = reps
        out["representation_choice"] = choose_path(
            [r for r in reps if r["delivered"]], correctness_required="exact-answer"
        )
        return out

    def _candidates(self, problem: Problem) -> Dict[str, Dict[str, float]]:
        acts = generate_actions(list(problem.operators), dict(problem.state))
        return {a["name"]: dict(a["interventions"]) for a in acts}

    def _futures_fn(self, problem: Problem, scm: Any, noise: Mapping[str, float]) -> Tuple[Callable, int, str]:
        quantile_constraints = any("@" in c.variable for c in problem.constraints)
        if not quantile_constraints and all(n in problem.state for n in scm.graph.nodes):
            return counterfactual_futures(scm), 3, "counterfactual (abduction-action-prediction on this unit)"
        env = futures_env(scm, noise)
        return (lambda state, action: env(action)), 2, "interventional distribution (exact Gaussian moments)"

    def _decide(self, problem: Problem, scm: Any, model: Mapping[str, Any], noise: Mapping[str, float], trace: _Trace) -> Dict[str, Any]:
        candidates = self._candidates(problem)
        futures, rung, rung_label = self._futures_fn(problem, scm, noise)
        model_id = f"{model['namespace']}@rev{len(model['revisions'])}"
        trace("decide", decide)
        decision = decide(
            dict(problem.state),
            candidates,
            futures=futures,
            objective=problem.objective,
            constraints=list(problem.constraints),
            model_id=model_id,
        )
        out: Dict[str, Any] = {
            "candidates": len(candidates),
            "futures_rung": rung,
            "futures_kind": rung_label,
            "model_id": model_id,
            "policy": decision.as_dict(),
            "_decision": decision,
            "_futures": futures,
        }
        # Futures as distributions: what each candidate's world looks like.
        targets = sorted({problem.objective.target} | {c.variable.split("@")[0] for c in problem.constraints})
        trace("futures", evaluate_futures)
        dist = evaluate_futures(
            scm,
            [{"name": n, "interventions": iv} for n, iv in sorted(candidates.items())],
            targets,
            noise_sd=noise,
        )
        for f in dist["actions"]:
            f["epistemic_status"] = PREDICTED
            f["model_id"] = model_id
        out["futures"] = dist
        if not decision.available:
            return out

        admissible = sorted(
            (r for r in decision.futures if r["admissible"]),
            key=lambda r: (-r["objective_value"] if problem.objective.sense == "maximize" else r["objective_value"], r["action"]),
        )
        selected = decision.selected_action
        # Adaptive precision: is the top-two ordering inside float error?
        if len(admissible) > 1:
            a, b = admissible[0], admissible[1]
            if rung == 2:
                trace("precision", select_precision)
                prec = select_precision(scm, candidate_a=a["intervention"], candidate_b=b["intervention"], target=problem.objective.target)
                exact_order = prec.get("exact_ordering") or prec.get("float_ordering")
            else:
                trace("precision", counterfactual_state)
                ea = counterfactual_state(scm, a["intervention"], problem.state, [problem.objective.target], arithmetic=ARITHMETIC_EXACT)
                eb = counterfactual_state(scm, b["intervention"], problem.state, [problem.objective.target], arithmetic=ARITHMETIC_EXACT)
                from kellogg.substrate import QPhi

                qa = ea["exact_values"][problem.objective.target]
                qb = eb["exact_values"][problem.objective.target]
                diff = QPhi(Fraction(qa["a"]), Fraction(qa["b"])) - QPhi(Fraction(qb["a"]), Fraction(qb["b"]))
                sgn = diff.sign()
                exact_order = "a>b" if sgn > 0 else "a<b" if sgn < 0 else "tie"
                prec = {
                    "regime": "exact-verified",
                    "margin": a["objective_value"] - b["objective_value"],
                    "exact_ordering": exact_order,
                    "justification": "counterfactual path: top-two ordering re-decided in exact Q(phi)",
                }
            maximize = problem.objective.sense == "maximize"
            if (exact_order == "a<b" and maximize) or (exact_order == "a>b" and not maximize):
                selected = b["action"]
                prec["override"] = f"exact arithmetic reverses the float ordering: {b['action']} over {a['action']}"
            elif exact_order == "tie":
                prec["exact_tie"] = True
            out["precision"] = prec
        out["selected_action"] = selected
        out["selected_interventions"] = candidates.get(selected, {})
        chosen = next(r for r in decision.futures if r["action"] == selected)
        out["predicted_future"] = dict(chosen["future"] or {})
        out["predicted_future_status"] = PREDICTED
        return out

    def _voi(self, problem: Problem, model: Mapping[str, Any], noise: Mapping[str, float], baseline: Optional[str], trace: _Trace) -> Dict[str, Any]:
        """Would resolving a declared uncertain parameter change the decision?"""
        out: Dict[str, Any] = {}
        for name, declared in sorted(problem.uncertain.items()):
            key = name[len("edge:"):]
            fitted_se = model["standard_errors"].get(key)
            if fitted_se is not None:
                w = float(model["weights"][key])
                lo, hi = min(declared), max(declared)
                rng = sorted({max(lo, w - 3 * fitted_se), w, min(hi, w + 3 * fitted_se)})
                source = "narrowed by observed evidence (estimate ± 3 SE within the declared range)"
            else:
                rng = sorted(float(x) for x in declared)
                source = "declared plausible range"

            def decision_at(value: float, key: str = key) -> str:
                weights = self._weights_tuple(model)
                weights[_split(key)] = float(value)
                scm_v = problem.structure.scm(weights)
                futures, _rung, _ = self._futures_fn(problem, scm_v, noise)
                d = decide(
                    dict(problem.state),
                    self._candidates(problem),
                    futures=futures,
                    objective=problem.objective,
                    constraints=list(problem.constraints),
                    model_id="voi-probe",
                )
                return str(d.selected_action)

            trace("meta", value_of_information)
            voi = value_of_information(parameter=name, plausible_range=rng, decision_fn=decision_at)
            voi["range_source"] = source
            voi["evaluated_range"] = rng
            voi["baseline_selection"] = baseline
            out[name] = voi
        return out

    # ------------------------------------------------------------------
    # the cycle
    # ------------------------------------------------------------------

    def run(self, problem: Problem) -> Dict[str, Any]:
        """One full reasoning cycle. Returns an evidence-bearing episode."""
        t0 = time.perf_counter()
        trace = _Trace()
        ledger = ReceiptLedger(run_id=f"episode:{problem.digest()[:16]}")
        identity = {
            "problem_digest": problem.digest(),
            "content_digest": problem.content_digest(),
            "domain_label": problem.domain,
            "namespace": problem.namespace(),
            "toe_version": TOE_VERSION,
            "machine_version": MACHINE_VERSION,
        }
        episode: Dict[str, Any] = {"schema": EPISODE_SCHEMA, "identity": identity}
        issues = problem.validate()
        if issues:
            episode.update(
                {
                    "status": REFUSED,
                    "refusal": {"reasons": issues},
                    "trace": trace.steps,
                    "backends": trace.backends(),
                }
            )
            rec = ledger.issue("machine.refuse", inputs=identity, config={}, output={"reasons": issues})
            episode["episode_sha256"] = rec.receipt_sha256
            episode["receipts"] = ledger.export()
            return episode

        model = self._model(problem)
        scm = problem.structure.scm(self._weights_tuple(model)) if model else None
        noise = self._noise(problem, model)
        if model:
            identity["model_revision"] = len(model["revisions"])
            identity["model_weights"] = dict(model["weights"])

        rep = self.represent(problem, trace=trace)
        state_obj = rep.pop("_state")
        episode["representation"] = rep
        ledger.issue("machine.represent", inputs=identity, config={"lens_policy": self.lens_policy}, output={"selected": rep["selected"], "observation_sha256": rep["observation_sha256"]})

        episode["understanding"] = self._understand(problem, scm, noise, trace)
        ledger.issue("machine.understand", inputs=identity, config={}, output={"keys": sorted(episode["understanding"])})

        status = DESCRIBE
        decision: Optional[PolicyDecision] = None
        if problem.forecast:
            episode["forecast"] = self._forecast(problem, trace)
        if problem.transitions is not None:
            nav = self._navigate(problem, trace)
            episode["navigation"] = nav
            if problem.navigation is not None:
                status = NAVIGATE if nav["reachable"] else UNREACHABLE

        if scm is not None and problem.operators and problem.objective is not None:
            dec = self._decide(problem, scm, model, noise, trace)
            decision = dec.pop("_decision")
            futures_fn = dec.pop("_futures")
            episode["futures"] = dec.pop("futures")
            episode["decision"] = dec
            if decision.available:
                status = ACT
                # Planning consumes the futures model (quantile-aware env).
                if problem.horizon > 1 or problem.budget is not None:
                    trace("plan", compare_plan_vs_greedy)
                    cmp = compare_plan_vs_greedy(
                        futures_env(scm, noise),
                        list(problem.operators),
                        objective=problem.objective,
                        constraints=list(problem.constraints),
                        depth=max(1, problem.horizon),
                        budget=problem.budget,
                    )
                    episode["plan"] = {
                        "plan_strictly_better": cmp["plan_strictly_better"],
                        "objective_gap": cmp["objective_gap"],
                        "plan": {k: cmp["plan"].get(k) for k in ("available", "sequence", "objective_value", "total_cost", "merged_interventions")},
                        "greedy": {k: cmp["greedy"].get(k) for k in ("available", "sequence", "objective_value", "total_cost")},
                        "env": "futures_env (exact Gaussian moments; constraints may bind quantiles)",
                    }
                # Arbitration between surfaces — never averaged.
                claims = [{"surface": "causal_interventional", "answer": dec["selected_action"]}]
                if problem.samples:
                    assoc_pick = self._associational_pick(problem)
                    if assoc_pick is not None:
                        claims.append({"surface": "associational_predictor", "answer": assoc_pick})
                plan_info = episode.get("plan")
                ptype = "interventional"
                if plan_info and plan_info["plan"]["available"] and plan_info["plan_strictly_better"]:
                    claims.append({"surface": "planning", "answer": plan_info["plan"]["sequence"][0]["name"]})
                    ptype = "planning"
                trace("arbitrate", arbitrate)
                episode["arbitration"] = arbitrate(claims, problem_type=ptype)
                # Value of information + meta-control: act or acquire evidence.
                voi = self._voi(problem, model, noise, dec["selected_action"], trace) if problem.uncertain else {}
                ident = episode["understanding"].get("identifiability", {}) or {}
                trace("meta", meta_decide)
                meta = meta_decide(
                    identifiability=ident.get("verdict"),
                    decision_margin=dec["policy"].get("margin"),
                    margin_tolerance=0.0,
                    evidence_count=len(model["observations"]),
                    min_evidence=self.min_evidence,
                    available_operators=[op.name for op in problem.operators],
                )
                flips = [k for k, v in voi.items() if v["recommend_evidence"]]
                episode["meta"] = {
                    "value_of_information": voi,
                    "meta_decide": meta,
                    "near_tie_rule": "disabled (margin_tolerance=0): expected-value decisions are not flipped by aleatoric noise; epistemic flips are VOI's question",
                    "verdict": ACQUIRE_EVIDENCE if flips else ACT,
                    "reason": (
                        f"evidence on {flips} could change the decision" if flips else "I know enough: the decision is invariant to every declared uncertainty"
                    ),
                }
                if flips:
                    status = ACQUIRE_EVIDENCE
                # Explanation — computational, contrastive, falsifiable.
                trace("explain", explain_decision)
                expl: Dict[str, Any] = {"decision": explain_decision(decision, scm=scm, uncertainty=episode["understanding"].get("uncertainty"), state=problem.state)}
                runners = [r["action"] for r in decision.futures if r["admissible"] and r["action"] != decision.selected_action]
                if runners:
                    trace("explain", explain_contrastive)
                    expl["contrastive"] = explain_contrastive(decision, runners[0], scm=scm)
                    trace("explain", falsify_decision)
                    expl["falsification"] = falsify_decision(decision, futures_fn=futures_fn, state=problem.state)
                episode["explanation"] = expl
            else:
                status = NO_DECISION
            episode["recommendation"] = self._recommendation(episode, status)

        # Self-governance: release only what passes its invariants.
        gov: Dict[str, Any] = {}
        if decision is not None and decision.available:
            chosen = next((r for r in decision.futures if r["action"] == episode["decision"]["selected_action"]), None)
            trace("govern", self_check)
            gov["action"] = self_check("action", {"violated_constraints": (chosen or {}).get("violated", [])})
        rel = episode["understanding"].get("relationships") or {}
        if rel:
            ident = episode["understanding"].get("identifiability") or {}
            gov["causal"] = self_check(
                "causal",
                {"identifiability_verdict": ident.get("verdict"), "estimate_released": rel.get("effect_released", False)},
            )
        gov["representation"] = {"divergent_views": rep["provenance"]["divergent_views"], "ok": rep["provenance"]["ok"]}
        episode["governance"] = gov

        episode["status"] = status
        episode["trace"] = trace.steps
        episode["backends"] = trace.backends()
        episode["elapsed_s"] = time.perf_counter() - t0
        final = ledger.issue(
            "machine.episode",
            inputs=identity,
            config={"min_evidence": self.min_evidence},
            output={
                "status": status,
                "selected": (episode.get("decision") or {}).get("selected_action"),
                "decision_sha256": (episode.get("decision") or {}).get("policy", {}).get("decision_sha256"),
                "backends": episode["backends"],
            },
        )
        episode["episode_sha256"] = final.receipt_sha256
        gov["receipt"] = self_check("receipt", {"verify_ok": ledger.verify()["ok"]})
        episode["receipts"] = ledger.export()
        self._record_lens_utility(rep, episode)
        self._remember_episode(problem, episode)
        return episode

    def _associational_pick(self, problem: Problem) -> Optional[str]:
        """What a purely associational predictor would choose: E[Y|X=level]
        from the sample regression, per single-node candidate."""
        target = problem.objective.target
        best: Optional[Tuple[float, str]] = None
        for name, iv in sorted(self._candidates(problem).items()):
            if len(iv) != 1:
                continue
            (node, level), = iv.items()
            a = association(problem.samples, node, target)
            if not a.get("available"):
                continue
            xs = problem.samples[node]
            ys = problem.samples[target]
            pred = sum(ys) / len(ys) + a["slope_E_y_given_x"] * (level - sum(xs) / len(xs))
            score = pred if problem.objective.sense == "maximize" else -pred
            if best is None or score > best[0]:
                best = (score, name)
        return best[1] if best else None

    def _recommendation(self, episode: Mapping[str, Any], status: str) -> Dict[str, Any]:
        dec = episode.get("decision") or {}
        plan = episode.get("plan") or {}
        if status not in (ACT, ACQUIRE_EVIDENCE):
            return {"kind": "none", "status": status}
        if plan and plan["plan"].get("available") and plan["plan_strictly_better"]:
            return {
                "kind": "plan",
                "sequence": [s["name"] for s in plan["plan"]["sequence"]],
                "interventions": plan["plan"]["merged_interventions"],
                "why_not_greedy": f"plan objective exceeds greedy by {plan['objective_gap']}",
                "status": status,
            }
        return {
            "kind": "action",
            "action": dec.get("selected_action"),
            "interventions": dec.get("selected_interventions"),
            "status": status,
        }

    def _record_lens_utility(self, rep: Mapping[str, Any], episode: Mapping[str, Any]) -> None:
        relevant = set()
        if episode.get("decision"):
            relevant.add("causal_graph")
        if episode.get("forecast", {}).get("family"):
            relevant.add("algebraic")
        for lens in rep["available_views"]:
            u = self.lens_utility.setdefault(lens, {"selected": 0, "decision_relevant": 0})
            u["selected"] += 1
            if lens in relevant:
                u["decision_relevant"] += 1

    def _remember_episode(self, problem: Problem, episode: Dict[str, Any]) -> None:
        dec = episode.get("decision") or {}
        summary = {
            "episode_sha256": episode["episode_sha256"],
            "namespace": episode["identity"]["namespace"],
            "status": episode["status"],
            "selected": dec.get("selected_action"),
            "selected_interventions": dec.get("selected_interventions"),
            "decision_sha256": dec.get("policy", {}).get("decision_sha256"),
            "recommendation": episode.get("recommendation"),
            "model_revision": episode["identity"].get("model_revision"),
            "model_weights": episode["identity"].get("model_weights"),
            "problem_content": problem.content(),
            "domain": problem.domain,
        }
        self.episodes.append(summary)
        self.memory.remember(
            "episodic",
            {k: summary[k] for k in ("episode_sha256", "status", "selected", "model_revision")},
            causal_tags=[summary["namespace"]],
            regime=f"{summary['namespace']}@rev{summary['model_revision']}",
        )

    # ------------------------------------------------------------------
    # learning
    # ------------------------------------------------------------------

    def learn(
        self,
        episode: Mapping[str, Any],
        observed: Any,
        *,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Close the loop: outcome → error → assessment → revision → memory.

        ``observed``: the post-action world (node -> value), or a list of
        them (repeated observations of the executed recommendation). The
        outcome is bound to this episode's exact decision SHA.
        """
        ns = episode["identity"]["namespace"]
        model = self.models.get(ns)
        dec = episode.get("decision") or {}
        rec = episode.get("recommendation") or {}
        if model is None or not dec.get("selected_action"):
            return {"learned": False, "reason": "episode carries no model-based decision to learn from"}
        rows = [observed] if isinstance(observed, Mapping) else list(observed)
        interventions = dict(rec.get("interventions") or dec.get("selected_interventions") or {})
        intervened = sorted(interventions)
        # The prediction error belongs to the model the decision was made
        # with, not to whatever the namespace holds by the time it lands.
        base_weights = {
            _split(k): float(v)
            for k, v in (episode["identity"].get("model_weights") or model["weights"]).items()
        }
        problem = self._problem_from_episode(episode)
        scm = problem.structure.scm(base_weights)
        predicted = intervene(scm, interventions)["values"] if interventions else scm.evaluate_all()
        ledger = ReceiptLedger(run_id=f"learn:{episode['episode_sha256'][:16]}")
        errors_out = []
        for row in rows:
            values = {k: float(v) for k, v in row.items()}
            errors = {
                n: values[n] - float(predicted[n])
                for n in predicted
                if n in values and n not in intervened and n not in problem.structure.latent
                and any(c == n for _p, c in model["edges"])
            }
            model["observations"].append({"values": values, "intervened": intervened, "episode": episode["episode_sha256"]})
            model["residuals"].append(errors)
            binding = bind_outcome(
                dec["policy"]["decision_sha256"],
                dec["selected_action"],
                {n: float(predicted[n]) for n in predicted},
                values,
                ledger,
            )
            self.bindings.append({**binding, "namespace": ns, "episode_sha256": episode["episode_sha256"]})
            errors_out.append(errors)
        noise = {n: float(problem.noise_sd.get(n, 1.0)) for n in problem.structure.all_nodes()} if problem.noise_sd else None
        window = model["residuals"][model["assessment_from"]:]
        assessment = assess_structural(window[-20:], noise_sd=noise, min_observations=self.min_evidence)
        model["status"] = assessment["status"]
        fit = fit_structural_weights(model["edges"], model["observations"], min_evidence=self.min_evidence)
        for (p, c), _w in fit["weights"].items():
            se = fit["fitted"][c]["standard_errors"]
            if se:
                model["standard_errors"][_ek(p, c)] = se[p]
        revision = None
        if assessment["status"] in (MODEL_DRIFT, MODEL_CONTRADICTED) and fit["weights"]:
            before = dict(model["weights"])
            for (p, c), w in fit["weights"].items():
                model["weights"][_ek(p, c)] = w
            old_regime = f"{ns}@rev{len(model['revisions'])}"
            revision = {
                "index": len(model["revisions"]) + 1,
                "trigger": assessment["status"],
                "score": assessment.get("score"),
                "evidence": len(model["observations"]),
                "before": before,
                "after": dict(model["weights"]),
                "estimator": fit["estimator"],
                "skipped": fit["skipped"],
            }
            model["revisions"].append(revision)
            model["assessment_from"] = len(model["residuals"])
            model["noise_inflation"] = 1.0
            model["evidence_requested"] = False
            self.memory.invalidate(old_regime, f"{ns}@rev{len(model['revisions'])}")
            self.memory.remember(
                "world_model",
                {"revision": revision["index"], "after": revision["after"], "trigger": revision["trigger"]},
                causal_tags=[ns],
                regime=f"{ns}@rev{len(model['revisions'])}",
            )
        if assessment["status"] == MODEL_CONTRADICTED and revision is None:
            # Contradiction without enough evidence to refit: widen
            # uncertainty, request evidence, flag replanning.
            score = float(assessment.get("score") or 1.0)
            model["noise_inflation"] = max(model["noise_inflation"], score / 1.5)
            model["evidence_requested"] = True
        if assessment["status"] == MODEL_CONTRADICTED:
            model["contradictions"] += 1
            entry = {
                "namespace": ns,
                "episode_sha256": episode["episode_sha256"],
                "score": assessment.get("score"),
                "revised": revision is not None,
                "consequences": (
                    ["model revision"] if revision else ["uncertainty increase", "new evidence request", "replanning"]
                ),
            }
            self.contradictions.append(entry)
            self.negative_results.append({"kind": "model_contradiction", **entry})
        self.memory.remember(
            "observation",
            {"episode_sha256": episode["episode_sha256"], "errors": errors_out},
            causal_tags=[ns, *intervened],
            regime=f"{ns}@rev{len(model['revisions'])}",
        )
        result = {
            "learned": True,
            "namespace": ns,
            "observations": len(model["observations"]),
            "prediction_errors": errors_out,
            "assessment": assessment,
            "revision": revision,
            "standard_errors": dict(model["standard_errors"]),
            "noise_inflation": model["noise_inflation"],
            "evidence_requested": model["evidence_requested"],
            "receipts_ok": ledger.verify()["ok"],
        }
        if persist and self._store is not None:
            result["persisted"] = self.persist()
        elif persist:
            result["persisted"] = {"available": False, "reason": "no THESEUS custody bound (UNAVAILABLE)"}
        return result

    # ------------------------------------------------------------------
    # persistence + replay
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """The learning state that must survive a restart."""
        return {
            "models": self.models,
            "memory": self.memory.export(),
            "lens_utility": self.lens_utility,
            "episodes": self.episodes,
            "bindings": self.bindings,
            "contradictions": self.contradictions,
            "negative_results": self.negative_results,
            "transfers": self.transfers,
            "min_evidence": self.min_evidence,
        }

    def persist(self) -> Dict[str, Any]:
        if self._store is None:
            return {"available": False, "reason": "no THESEUS custody bound (UNAVAILABLE)"}
        receipt = self._store.commit(_json_safe(self.snapshot()), toe_version=TOE_VERSION)
        return {"available": True, **receipt}

    def _recover(self) -> None:
        assert self._store is not None
        head = self._store.load_head()
        if head is None:
            self.recovered_from = {"recovered": False, "reason": "empty snapshot chain (first start)"}
            return
        snap = head["payload"]
        self.models = snap["models"]
        self.memory = MemoryStore.restore(snap["memory"])
        self.lens_utility = snap["lens_utility"]
        self.episodes = snap["episodes"]
        self.bindings = snap["bindings"]
        self.contradictions = snap["contradictions"]
        self.negative_results = snap["negative_results"]
        self.transfers = snap["transfers"]
        self.recovered_from = {
            "recovered": True,
            "record_id": head["record_id"],
            "revision": head["revision"],
            "snapshot_digest": head["digest"],
            "custody": "theseus",
        }

    def episode_record(self, episode_sha256: str) -> Optional[Dict[str, Any]]:
        """The part of a recorded episode that ``learn`` binds an outcome to.

        Works for episodes solved before a restart: the record is rebuilt
        from the persisted episode summary, not from live objects.
        """
        s = next((e for e in self.episodes if e["episode_sha256"] == episode_sha256), None)
        if s is None:
            return None
        return {
            "episode_sha256": s["episode_sha256"],
            "identity": {
                "namespace": s["namespace"],
                "model_revision": s["model_revision"],
                "model_weights": s.get("model_weights"),
            },
            "status": s["status"],
            "decision": {
                "selected_action": s["selected"],
                "selected_interventions": s.get("selected_interventions"),
                "policy": {"decision_sha256": s["decision_sha256"]},
            },
            "recommendation": s.get("recommendation"),
        }

    def _problem_from_episode(self, episode: Mapping[str, Any]) -> Problem:
        summary = next((e for e in self.episodes if e["episode_sha256"] == episode["episode_sha256"]), None)
        if summary is None:
            raise KeyError("episode is not known to this machine")
        return problem_from_content(summary["domain"], summary["problem_content"])

    def replay(self, episode_sha256: str) -> Dict[str, Any]:
        """Reconstruct a recorded decision from its stored problem + model
        revision and check it reproduces bit-for-bit (decision SHA)."""
        summary = next((e for e in self.episodes if e["episode_sha256"] == episode_sha256), None)
        if summary is None:
            return {"replayed": False, "reason": "unknown episode"}
        problem = problem_from_content(summary["domain"], summary["problem_content"])
        if summary.get("decision_sha256") is None:
            return {"replayed": False, "reason": "episode recorded no decision"}
        model = self.models[summary["namespace"]]
        rev = summary["model_revision"] or 0
        weights = model["prior_weights"] if rev == 0 else model["revisions"][rev - 1]["after"]
        scm = problem.structure.scm({_split(k): float(v) for k, v in weights.items()})
        noise = {n: float(problem.noise_sd.get(n, 1.0)) for n in problem.structure.all_nodes()}
        futures, _rung, _ = self._futures_fn(problem, scm, noise)
        d = decide(
            dict(problem.state),
            self._candidates(problem),
            futures=futures,
            objective=problem.objective,
            constraints=list(problem.constraints),
            model_id=f"{summary['namespace']}@rev{rev}",
        )
        return {
            "replayed": True,
            "episode_sha256": episode_sha256,
            "model_revision": rev,
            "recorded_decision_sha256": summary["decision_sha256"],
            "replayed_decision_sha256": d.decision_sha256,
            "identical": d.decision_sha256 == summary["decision_sha256"],
            "selected": d.selected_action,
        }

    # ------------------------------------------------------------------
    # EUCLID-facing capability calls (EUCLID decides when to invoke)
    # ------------------------------------------------------------------

    def capabilities(self) -> Dict[str, str]:
        return {
            "represent": "bind an observation to multiple lenses under one identity",
            "model": "the current (revised) structural model for a problem's namespace",
            "identify": "identifiability verdict for the causal query (refusal is an answer)",
            "intervene": "E[V | do(action)] on the current model",
            "counterfactual": "unit-level counterfactual by abduction-action-prediction",
            "evaluate_futures": "distributions over futures per candidate action",
            "uncertainty": "five-axis uncertainty decomposition",
            "plan": "multi-step plan vs greedy over the futures model",
            "request_information": "value of information over declared uncertainties",
            "explain": "computational, contrastive and falsifiable explanation",
            "revise": "outcome binding, assessment and model revision",
            "run": "the full cycle",
        }

    def model(self, problem: Problem) -> Dict[str, Any]:
        m = self._model(problem)
        if m is None:
            return {"available": False, "reason": "no structure supplied"}
        return {"available": True, "namespace": m["namespace"], "weights": dict(m["weights"]), "revision": len(m["revisions"]), "status": m["status"]}

    def intervene(self, problem: Problem, action: Mapping[str, float]) -> Dict[str, Any]:
        m = self._model(problem)
        if m is None:
            return {"available": False, "reason": "no structure supplied"}
        return intervene(problem.structure.scm(self._weights_tuple(m)), dict(action), arithmetic=ARITHMETIC_EXACT)

    def counterfactual(self, problem: Problem, action: Mapping[str, float], outcomes: Sequence[str]) -> Dict[str, Any]:
        m = self._model(problem)
        if m is None:
            return {"available": False, "reason": "no structure supplied"}
        try:
            return counterfactual_state(problem.structure.scm(self._weights_tuple(m)), dict(action), dict(problem.state), list(outcomes))
        except CausalCapabilityUnavailable as exc:
            return {"available": False, "reason": exc.reason, "missing": exc.missing}

    def evaluate_futures(self, problem: Problem) -> Dict[str, Any]:
        m = self._model(problem)
        if m is None:
            return {"available": False, "reason": "no structure supplied"}
        scm = problem.structure.scm(self._weights_tuple(m))
        acts = [{"name": n, "interventions": iv} for n, iv in sorted(self._candidates(problem).items())]
        out = evaluate_futures(scm, acts, noise_sd=self._noise(problem, m))
        for f in out["actions"]:
            f["epistemic_status"] = PREDICTED
        return out

    def uncertainty(self, problem: Problem) -> Dict[str, Any]:
        m = self._model(problem)
        if m is None or problem.query is None:
            return {"available": False, "reason": "needs structure and a causal query"}
        return uncertainty_report(
            problem.structure.scm(self._weights_tuple(m)),
            problem.query[0],
            problem.query[1],
            samples=problem.samples,
            noise_sd=self._noise(problem, m),
        )

    def plan(self, problem: Problem) -> Dict[str, Any]:
        m = self._model(problem)
        if m is None or problem.objective is None:
            return {"available": False, "reason": "needs structure and an objective"}
        return compare_plan_vs_greedy(
            futures_env(problem.structure.scm(self._weights_tuple(m)), self._noise(problem, m)),
            list(problem.operators),
            objective=problem.objective,
            constraints=list(problem.constraints),
            depth=max(1, problem.horizon),
            budget=problem.budget,
        )

    def request_information(self, problem: Problem) -> Dict[str, Any]:
        episode = self.run(problem)
        return episode.get("meta", {"verdict": None, "reason": "no decision problem"})

    def explain(self, problem: Problem) -> Dict[str, Any]:
        return self.run(problem).get("explanation", {"available": False})

    def revise(self, episode: Mapping[str, Any], observed: Any) -> Dict[str, Any]:
        return self.learn(episode, observed)


def problem_from_content(domain: str, content: Mapping[str, Any]) -> Problem:
    """Rebuild a :class:`Problem` from :meth:`Problem.content` (replay)."""
    from .planning import OperatorSpec
    from .policy import Constraint, Objective

    st = content.get("structure")
    return Problem(
        domain=domain,
        observation=content.get("observation"),
        state=dict(content.get("state") or {}),
        structure=Structure.of(st["edges"], nodes=st["nodes"], latent=st["latent"]) if st else None,
        samples=content.get("samples"),
        operators=tuple(OperatorSpec(o[0], o[1], tuple(o[2]), tuple(o[3]), float(o[4])) for o in content.get("operators") or ()),
        objective=Objective(**content["objective"]) if content.get("objective") else None,
        constraints=tuple(Constraint.from_dict(c) for c in content.get("constraints") or ()),
        query=tuple(content["query"]) if content.get("query") else None,
        observed=content.get("observed"),
        uncertain={k: tuple(v) for k, v in (content.get("uncertain") or {}).items()},
        noise_sd=dict(content.get("noise_sd") or {}),
        transitions=[tuple(e) for e in content["transitions"]] if content.get("transitions") is not None else None,
        coordinates={k: tuple(v) for k, v in content["coordinates"].items()} if content.get("coordinates") is not None else None,
        navigation=tuple(content["navigation"]) if content.get("navigation") else None,
        forecast=content.get("forecast"),
        horizon=int(content.get("horizon") or 1),
        budget=content.get("budget"),
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


__all__ = [
    "ACQUIRE_EVIDENCE",
    "ACT",
    "DESCRIBE",
    "EPISODE_SCHEMA",
    "MACHINE_VERSION",
    "NAVIGATE",
    "NO_DECISION",
    "PREDICTED",
    "REFUSED",
    "UNREACHABLE",
    "TOEMachine",
    "problem_from_content",
]
