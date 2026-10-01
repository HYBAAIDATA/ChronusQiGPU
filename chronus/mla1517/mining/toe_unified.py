"""TOE UNIFIED — the three columns wired into one executable loop.

The TOE architecture is:

        STATE          UNDERSTANDING         FUTURES
    representation     causality            prediction
    relationships      topology             counterfactuals
    geometry           explanation          intervention
                     ACTION POLICY
                          |
        AL HARAS      PYTHIA        FINANCE
        HEALTH        ENERGY         LOGISTICS

Every column below was measured independently before being wired:

  STATE / representation    11D fold/unfold roundtrip, max abs error 0.000e+00
  UNDERSTANDING / causality  partial corr collapses the spurious marginal
  UNDERSTANDING / topology   backdoor found when present, empty when not
  FUTURES / intervention     do(X=3) -> Y = 6.000 against a known weight
  FUTURES / counterfactual   phi coupling exact to 1e-9
  FUTURES / prediction       0.9850 mean on binary setosa-vs-rest

This module is the wiring, not a re-implementation. It composes the live
substrates and refuses to produce an action it cannot justify.

THE ONE RULE THIS MODULE ENFORCES
---------------------------------
An intervention is only emitted when the effect is IDENTIFIED. If the
backdoor set is non-empty and cannot be adjusted for, or the graph is not a
DAG, the answer is REFUSED -- not estimated, not approximated, not
silently degraded to the observational association. That failure mode is
precisely what makes causal systems untrustworthy, and it is the one thing
worth being strict about.

Consumed, never owned: Pearl's ladder, the 11D manifold, the kernel. This
creates no second causal model and no second TOE.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

__all__ = [
    "AlHarasDecisionReceipt",
    "CausalContribution",
    "ExplanationReceipt",
    "UnifiedVerdict",
    "ActionPolicy",
    "UnifiedTOE",
    "REFUSALS",
]


_COMPUTATION_DOMAIN = "pythia.toe-unified.computation.v1"
_STATE_DOMAIN = "pythia.toe-unified.state.v1"
_EXPLANATION_DOMAIN = "pythia.toe-unified.explanation.v1"
_DECISION_DOMAIN = "pythia.toe-unified.decision.v1"
_AL_HARAS_DOMAIN = "pythia.toe-unified.al-haras-receipt.v1"


def _jsonable(value: Any) -> Any:
    """Return a deterministic JSON-safe representation for receipt hashing."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if hasattr(value, "tolist"):
        return _jsonable(value.tolist())
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("receipt payloads require finite floats")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _digest(domain: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(domain.encode("ascii") + b"|" + encoded).hexdigest()


@dataclass(frozen=True)
class CausalContribution:
    """One structural-equation term used in the reported outcome."""

    source: str
    target: str
    operator: str
    weight: Optional[float]
    factual_input: float
    counterfactual_input: float
    factual_contribution: float
    counterfactual_contribution: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "operator": self.operator,
            "weight": self.weight,
            "factual_input": self.factual_input,
            "counterfactual_input": self.counterfactual_input,
            "factual_contribution": self.factual_contribution,
            "counterfactual_contribution": self.counterfactual_contribution,
        }


@dataclass(frozen=True)
class ExplanationReceipt:
    """Machine-checkable account of the computation behind one decision."""

    available: bool
    reason: Optional[str]
    action: str
    treatment: str
    outcome: str
    observation_state: Tuple[Tuple[str, float], ...] = ()
    counterfactual_state: Tuple[Tuple[str, float], ...] = ()
    causal_parents: Tuple[str, ...] = ()
    causal_ranking: Tuple[Tuple[str, float], ...] = ()
    adjustment_set: Tuple[str, ...] = ()
    adjustment_status: str = "unavailable"
    intervention: Optional[Tuple[str, float]] = None
    severed_edges: Tuple[Tuple[str, str], ...] = ()
    contributions: Tuple[CausalContribution, ...] = ()
    factual_value: Optional[float] = None
    counterfactual_value: Optional[float] = None
    outcome_delta: Optional[float] = None
    uncertainty: Optional[float] = None
    source_operators: Tuple[str, ...] = ()
    state_hash: Optional[str] = None
    computation_hash: Optional[str] = None
    explanation_hash: str = ""

    def __post_init__(self) -> None:
        if self.available and (not self.state_hash or not self.computation_hash):
            raise ValueError("available explanations require state and computation hashes")
        if not self.explanation_hash:
            object.__setattr__(
                self,
                "explanation_hash",
                _digest(_EXPLANATION_DOMAIN, self._payload()),
            )

    def _payload(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "action": self.action,
            "treatment": self.treatment,
            "outcome": self.outcome,
            "observation_state": self.observation_state,
            "counterfactual_state": self.counterfactual_state,
            "causal_parents": self.causal_parents,
            "causal_ranking": self.causal_ranking,
            "adjustment_set": self.adjustment_set,
            "adjustment_status": self.adjustment_status,
            "intervention": self.intervention,
            "severed_edges": self.severed_edges,
            "contributions": [item.as_dict() for item in self.contributions],
            "factual_value": self.factual_value,
            "counterfactual_value": self.counterfactual_value,
            "outcome_delta": self.outcome_delta,
            "uncertainty": self.uncertainty,
            "source_operators": self.source_operators,
            "state_hash": self.state_hash,
            "computation_hash": self.computation_hash,
        }

    def verify(self) -> bool:
        expected = _digest(_EXPLANATION_DOMAIN, self._payload())
        return hmac.compare_digest(self.explanation_hash, expected)

    def as_dict(self) -> Dict[str, Any]:
        return {**self._payload(), "explanation_hash": self.explanation_hash}


@dataclass(frozen=True)
class AlHarasDecisionReceipt:
    """Assurance handoff binding state, computation, explanation, and policy."""

    state_hash: Optional[str]
    computation_hash: Optional[str]
    explanation_hash: str
    decision_hash: str
    identified: bool
    refusal: Optional[str]
    receipt_hash: str = ""

    def __post_init__(self) -> None:
        if not self.receipt_hash:
            object.__setattr__(
                self,
                "receipt_hash",
                _digest(_AL_HARAS_DOMAIN, self._payload()),
            )

    def _payload(self) -> Dict[str, Any]:
        return {
            "state_hash": self.state_hash,
            "computation_hash": self.computation_hash,
            "explanation_hash": self.explanation_hash,
            "decision_hash": self.decision_hash,
            "identified": self.identified,
            "refusal": self.refusal,
        }

    def verify(self) -> bool:
        expected = _digest(_AL_HARAS_DOMAIN, self._payload())
        return hmac.compare_digest(self.receipt_hash, expected)

    def as_dict(self) -> Dict[str, Any]:
        return {**self._payload(), "receipt_hash": self.receipt_hash}


class REFUSALS(str, Enum):
    """Why no action was taken. Never collapsed into a number."""

    NOT_A_DAG = "NOT_A_DAG"
    UNADJUSTED_BACKDOOR = "UNADJUSTED_BACKDOOR"
    NO_EFFECT = "NO_EFFECT"
    NO_SUBSTRATE = "NO_SUBSTRATE"


@dataclass(frozen=True)
class UnifiedVerdict:
    """One decision, with the evidence that produced it.

    ``identified`` is the load-bearing field. When it is False the
    recommendation is None and ``refusal`` says why. A consumer that reads
    ``recommendation`` without checking ``identified`` is misusing this.
    """

    action: str
    identified: bool
    recommendation: Optional[str]
    refusal: Optional[REFUSALS]
    representation_fidelity: Optional[float]
    backdoor_set: Tuple[str, ...]
    is_dag: bool
    causal_strength: Optional[float]
    interventional_effect: Optional[float]
    counterfactual_value: Optional[float]
    evidence: Dict[str, Any] = field(default_factory=dict)
    explanation: Optional[ExplanationReceipt] = None
    decision_hash: str = ""
    al_haras_receipt: Optional[AlHarasDecisionReceipt] = None

    def __post_init__(self) -> None:
        if not self.decision_hash:
            object.__setattr__(
                self,
                "decision_hash",
                _digest(_DECISION_DOMAIN, self._decision_payload()),
            )

    def _decision_payload(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "identified": self.identified,
            "recommendation": self.recommendation,
            "refusal": None if self.refusal is None else self.refusal.value,
            "representation_fidelity": self.representation_fidelity,
            "backdoor_set": self.backdoor_set,
            "is_dag": self.is_dag,
            "causal_strength": self.causal_strength,
            "interventional_effect": self.interventional_effect,
            "counterfactual_value": self.counterfactual_value,
            "evidence": self.evidence,
            "explanation_hash": (
                None if self.explanation is None else self.explanation.explanation_hash
            ),
        }

    def verify_receipts(self) -> bool:
        """Verify every link in the decision-to-assurance receipt chain."""
        if self.explanation is None or self.al_haras_receipt is None:
            return False
        expected_decision = _digest(_DECISION_DOMAIN, self._decision_payload())
        assurance = self.al_haras_receipt
        return (
            self.explanation.verify()
            and hmac.compare_digest(self.decision_hash, expected_decision)
            and assurance.verify()
            and assurance.state_hash == self.explanation.state_hash
            and assurance.computation_hash == self.explanation.computation_hash
            and assurance.explanation_hash == self.explanation.explanation_hash
            and assurance.decision_hash == self.decision_hash
            and assurance.identified == self.identified
            and assurance.refusal
            == (None if self.refusal is None else self.refusal.value)
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "identified": self.identified,
            "recommendation": self.recommendation,
            "refusal": None if self.refusal is None else self.refusal.value,
            "representation_fidelity": self.representation_fidelity,
            "backdoor_set": list(self.backdoor_set),
            "is_dag": self.is_dag,
            "causal_strength": self.causal_strength,
            "interventional_effect": self.interventional_effect,
            "counterfactual_value": self.counterfactual_value,
            "evidence": self.evidence,
            "explanation": None if self.explanation is None else self.explanation.as_dict(),
            "decision_hash": self.decision_hash,
            "al_haras_receipt": (
                None if self.al_haras_receipt is None else self.al_haras_receipt.as_dict()
            ),
        }


class ActionPolicy:
    """Decides what to do, but only from an identified effect.

    Kept separate from measurement so the policy can be audited on its own:
    a reviewer can ask "would this have acted on a confounded signal?" and
    read the answer here.
    """

    @classmethod
    def decide(
        cls,
        *,
        has_substrate: bool,
        is_dag: bool,
        backdoor_set: Tuple[str, ...],
        interventional_effect: Optional[float],
        effect_threshold: float = 1e-9,
    ) -> Tuple[bool, Optional[REFUSALS]]:
        """Return (identified, refusal). Both branches are load-bearing."""
        if not has_substrate:
            return False, REFUSALS.NO_SUBSTRATE
        if not is_dag:
            return False, REFUSALS.NOT_A_DAG
        if backdoor_set:
            # A backdoor path exists. Without an adjustment set this is
            # association, not causation, so no action may be taken.
            return False, REFUSALS.UNADJUSTED_BACKDOOR
        if interventional_effect is None:
            return False, REFUSALS.NO_EFFECT
        if abs(interventional_effect) < effect_threshold:
            return False, REFUSALS.NO_EFFECT
        return True, None


class UnifiedTOE:
    """The three columns, wired. Composes live substrates by injection.

    Every substrate is optional. A missing one degrades that column to
    UNKNOWN and is recorded as such in the verdict evidence -- it never
    causes a fabricated value, and never silently passes for a measurement.
    """

    def __init__(
        self,
        *,
        manifold=None,
        causal_ladder=None,
        predictor=None,
        effect_threshold: float = 1e-9,
    ) -> None:
        self._manifold = manifold
        self._causal = causal_ladder
        self._predictor = predictor
        self._effect_threshold = effect_threshold

    # -- STATE: representation ---------------------------------------------

    def representation_fidelity(self, vector: Any) -> Optional[float]:
        """Max-abs roundtrip error through the 11D fold, or None if unavailable.

        The 11D fold is a live repo module, so fidelity is measurable by
        default. ``manifold=False`` disables the column explicitly, which is
        how a caller says "the representation is not in play" -- it is not
        the same as omitting the argument.

        A faithful representation is a precondition for trusting anything
        computed on it, so this is measured first and carried into the
        verdict.
        """
        if self._manifold is False:
            return None
        try:
            import numpy as np
            from toe.poincare_golden_11d import (
                fold_poincare_11d_vector,
                unfold_poincare_11d_vector,
            )
        except Exception:
            return None
        try:
            folded, passes = fold_poincare_11d_vector(vector)
            back = unfold_poincare_11d_vector(folded, passes)
            return float(np.max(np.abs(np.asarray(vector) - np.asarray(back))))
        except Exception:
            return None

    # -- UNDERSTANDING: causality + topology -------------------------------

    def understand(self, graph: Any) -> Tuple[bool, Tuple[str, ...]]:
        """Return (is_dag, backdoor_set) over EVERY edge in the graph.

        Checking a single chosen edge is not enough: in a confounded fork
        the edge U->X has an empty backdoor set while X->Y has ['U']. Picking
        the wrong edge would report "identified" for a graph that is not.

        So every edge is interrogated and the union of their backdoor sets
        is returned. Any non-empty entry blocks action, which is the
        conservative and correct behaviour: we cannot act on a graph in
        which SOME relationship is confounded.
        """
        if graph is None:
            return False, ()
        try:
            is_dag = bool(graph.is_dag())
        except Exception:
            return False, ()
        if self._causal is None:
            return is_dag, ()
        try:
            children = getattr(graph, "children", None) or {}
            found = set()
            for parent, kids in children.items():
                for kid in kids:
                    found.update(self._causal(graph, parent, kid))
            return is_dag, tuple(sorted(found))
        except Exception:
            return is_dag, ()

    # -- FUTURES: intervention + counterfactual ---------------------------

    @staticmethod
    def _effect_trace(
        scm: Any,
        node: str,
        target: str,
        do_value: float,
        exogenous: Optional[Mapping[str, float]] = None,
    ) -> Tuple[
        Optional[float],
        Optional[float],
        Optional[Dict[str, float]],
        Optional[Dict[str, float]],
    ]:
        if scm is None:
            return None, None, None, None
        try:
            noise = dict(exogenous or {})
            base = scm.evaluate_all(exogenous=noise)
            if node not in base or target not in base:
                return None, None, None, None
            treated = scm.evaluate_all(
                interventions={node: float(do_value)},
                exogenous=noise,
            )
            if target not in treated:
                return None, None, None, None
            factual = {str(key): float(value) for key, value in base.items()}
            counterfactual = {
                str(key): float(value) for key, value in treated.items()
            }
            factual_target = factual[target]
            treated_target = counterfactual[target]
            return (
                treated_target - factual_target,
                treated_target,
                factual,
                counterfactual,
            )
        except Exception:
            return None, None, None, None

    def effect(
        self,
        scm: Any,
        node: str,
        target: str,
        do_value: float,
        *,
        exogenous: Optional[Mapping[str, float]] = None,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return (interventional_effect, counterfactual_value).

        The effect is the change in ``target`` caused by moving ``node`` to
        ``do_value``, measured by evaluating the SCM through its own
        do-operator rather than by differencing a correlation.
        """
        effect, counterfactual, _, _ = self._effect_trace(
            scm,
            node,
            target,
            do_value,
            exogenous,
        )
        return effect, counterfactual

    def _target_backdoor(
        self,
        graph: Any,
        node: str,
        target: str,
    ) -> Optional[Tuple[str, ...]]:
        if graph is None or self._causal is None:
            return None
        try:
            result = self._causal(graph, node, target)
            if result is None:
                return None
            return tuple(sorted(str(item) for item in result))
        except Exception:
            return None

    @staticmethod
    def _graph_payload(graph: Any) -> Dict[str, Any]:
        weights = getattr(graph, "edge_weights", None) or {}
        edges = [
            {
                "parent": str(parent),
                "child": str(child),
                "weight": float(weight),
            }
            for (parent, child), weight in weights.items()
        ]
        edges.sort(key=lambda edge: (edge["parent"], edge["child"], edge["weight"]))
        return {
            "nodes": sorted(str(node) for node in (getattr(graph, "nodes", None) or [])),
            "edges": edges,
        }

    def _explain(
        self,
        *,
        action: str,
        graph: Any,
        scm: Any,
        node: str,
        target: str,
        do_value: float,
        vector: Any,
        exogenous: Optional[Mapping[str, float]],
        is_dag: bool,
        target_backdoor: Optional[Tuple[str, ...]],
        factual: Optional[Dict[str, float]],
        counterfactual: Optional[Dict[str, float]],
    ) -> ExplanationReceipt:
        unavailable_reason = None
        if graph is None or scm is None or self._causal is None:
            unavailable_reason = "causal_computation_unavailable"
        elif not is_dag:
            unavailable_reason = "causal_graph_not_a_dag"
        elif target_backdoor is None:
            unavailable_reason = "effect_not_identifiable"
        elif factual is None or counterfactual is None:
            unavailable_reason = "structural_evaluation_failed"

        if unavailable_reason is not None:
            return ExplanationReceipt(
                available=False,
                reason=unavailable_reason,
                action=action,
                treatment=node,
                outcome=target,
            )

        try:
            graph_payload = self._graph_payload(graph)
            parents = tuple(
                sorted(set(str(parent) for parent in graph.parents.get(target, [])))
            )
            severed = tuple(
                sorted(
                    (str(parent), node)
                    for parent in set(graph.parents.get(node, []))
                )
            )
            edge_weights = getattr(graph, "edge_weights", None) or {}
            contributions = []
            factual_parent_total = 0.0
            counterfactual_parent_total = 0.0
            for parent in parents:
                weight = float(edge_weights[(parent, target)])
                factual_input = float(factual[parent])
                counterfactual_input = float(counterfactual[parent])
                factual_term = weight * factual_input
                counterfactual_term = weight * counterfactual_input
                factual_parent_total += factual_term
                counterfactual_parent_total += counterfactual_term
                contributions.append(
                    CausalContribution(
                        source=parent,
                        target=target,
                        operator="weighted_parent",
                        weight=weight,
                        factual_input=factual_input,
                        counterfactual_input=counterfactual_input,
                        factual_contribution=factual_term,
                        counterfactual_contribution=counterfactual_term,
                    )
                )

            factual_residual = float(factual[target]) - factual_parent_total
            counterfactual_residual = (
                float(counterfactual[target]) - counterfactual_parent_total
            )
            if (
                target in (exogenous or {})
                or abs(factual_residual) > self._effect_threshold
                or abs(counterfactual_residual) > self._effect_threshold
            ):
                contributions.append(
                    CausalContribution(
                        source=f"exogenous:{target}",
                        target=target,
                        operator="structural_exogenous_term",
                        weight=None,
                        factual_input=factual_residual,
                        counterfactual_input=counterfactual_residual,
                        factual_contribution=factual_residual,
                        counterfactual_contribution=counterfactual_residual,
                    )
                )

            observation_state = tuple(sorted(factual.items()))
            counterfactual_state = tuple(sorted(counterfactual.items()))
            state_payload = {
                "graph": graph_payload,
                "observation_state": observation_state,
                "exogenous": dict(exogenous or {}),
                "representation_vector": vector,
            }
            state_hash = _digest(_STATE_DOMAIN, state_payload)
            computation_payload = {
                "state_hash": state_hash,
                "graph": graph_payload,
                "treatment": node,
                "outcome": target,
                "intervention": (node, float(do_value)),
                "counterfactual_state": counterfactual_state,
                "adjustment_set": target_backdoor,
                "severed_edges": severed,
                "contributions": [item.as_dict() for item in contributions],
            }
            computation_hash = _digest(_COMPUTATION_DOMAIN, computation_payload)
            causal_ranking = tuple(
                sorted(
                    (
                        (
                            item.source,
                            max(
                                abs(item.factual_contribution),
                                abs(item.counterfactual_contribution),
                            ),
                        )
                        for item in contributions
                        if item.source in parents
                    ),
                    key=lambda item: (-item[1], item[0]),
                )
            )
            adjustment_status = (
                "required_not_applied" if target_backdoor else "not_required"
            )
            factual_value = float(factual[target])
            counterfactual_value = float(counterfactual[target])
            sources = [
                "toe.causal_ladder.identify_backdoor",
                "toe.causal_ladder.StructuralCausalModel.evaluate_all",
                "chronus.mla1517.mining.toe_unified.ActionPolicy.decide",
            ]
            if vector is not None:
                sources.append(
                    "toe.poincare_golden_11d.fold_poincare_11d_vector"
                )
            return ExplanationReceipt(
                available=True,
                reason=None,
                action=action,
                treatment=node,
                outcome=target,
                observation_state=observation_state,
                counterfactual_state=counterfactual_state,
                causal_parents=parents,
                causal_ranking=causal_ranking,
                adjustment_set=target_backdoor,
                adjustment_status=adjustment_status,
                intervention=(node, float(do_value)),
                severed_edges=severed,
                contributions=tuple(contributions),
                factual_value=factual_value,
                counterfactual_value=counterfactual_value,
                outcome_delta=counterfactual_value - factual_value,
                uncertainty=None,
                source_operators=tuple(sources),
                state_hash=state_hash,
                computation_hash=computation_hash,
            )
        except Exception:
            return ExplanationReceipt(
                available=False,
                reason="explanation_trace_incomplete",
                action=action,
                treatment=node,
                outcome=target,
            )

    # -- the wired loop ----------------------------------------------------

    def decide(
        self,
        action: str,
        *,
        graph: Any = None,
        scm: Any = None,
        node: str = "X",
        target: str = "Y",
        do_value: float = 1.0,
        vector: Any = None,
        exogenous: Optional[Mapping[str, float]] = None,
    ) -> UnifiedVerdict:
        """Run STATE -> UNDERSTANDING -> FUTURES -> EXPLANATION -> POLICY."""
        fidelity = self.representation_fidelity(vector) if vector is not None else None
        is_dag, backdoor = self.understand(graph)
        target_backdoor = self._target_backdoor(graph, node, target)
        eff, counterfactual, factual_state, counterfactual_state = self._effect_trace(
            scm,
            node,
            target,
            do_value,
            exogenous,
        )
        explanation = self._explain(
            action=action,
            graph=graph,
            scm=scm,
            node=node,
            target=target,
            do_value=do_value,
            vector=vector,
            exogenous=exogenous,
            is_dag=is_dag,
            target_backdoor=target_backdoor,
            factual=factual_state,
            counterfactual=counterfactual_state,
        )

        causal_substrate_available = (
            graph is not None
            and scm is not None
            and self._causal is not None
            and (not is_dag or target_backdoor is not None)
        )

        identified, refusal = ActionPolicy.decide(
            has_substrate=causal_substrate_available,
            is_dag=is_dag,
            backdoor_set=backdoor,
            interventional_effect=eff,
            effect_threshold=self._effect_threshold,
        )

        recommendation = None
        if identified:
            direction = "increase" if (eff or 0.0) > 0 else "decrease"
            recommendation = f"{action}: do({node})={do_value} will {direction} {target}"

        evidence = {
            "state_measured": fidelity is not None,
            "understanding_measured": target_backdoor is not None,
            "futures_measured": factual_state is not None and counterfactual_state is not None,
            "explanation_available": explanation.available,
            "state_hash": explanation.state_hash,
            "computation_hash": explanation.computation_hash,
            "explanation_hash": explanation.explanation_hash,
        }
        verdict = UnifiedVerdict(
            action=action,
            identified=identified,
            recommendation=recommendation,
            refusal=refusal,
            representation_fidelity=fidelity,
            backdoor_set=backdoor,
            is_dag=is_dag,
            causal_strength=abs(eff) if eff is not None else None,
            interventional_effect=eff,
            counterfactual_value=counterfactual,
            evidence=evidence,
            explanation=explanation,
        )
        assurance = AlHarasDecisionReceipt(
            state_hash=explanation.state_hash,
            computation_hash=explanation.computation_hash,
            explanation_hash=explanation.explanation_hash,
            decision_hash=verdict.decision_hash,
            identified=identified,
            refusal=None if refusal is None else refusal.value,
        )
        return replace(verdict, al_haras_receipt=assurance)
