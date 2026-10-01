"""World model + revision + consequence loop + online adaptation — §§23-26.

§23: ``WorldModel`` is not a dict of variables — it carries declared
entities, relations, causal structure, linear dynamics, constraints,
available operators and observed outcomes, and it *predicts
transitions*: ``predict_transition(state, action)`` uses fitted
edge weights + declared action effects.

§24: ``assess`` compares predictions against fresh evidence and returns
MODEL_SUPPORTED / MODEL_DRIFT / MODEL_CONTRADICTED /
INSUFFICIENT_EVIDENCE. ``revise`` refits weights only past an evidence
threshold and appends to a revision log — history is never rewritten.

§25: ``bind_outcome`` closes prediction → action → outcome → error →
attribution, binding the exact decision's receipt SHA to its observed
outcome — no outcome is ever attributed to a different decision.

§26: ``OnlineAdapter`` runs the loop: online least-squares on observed
transitions, a CUSUM-style detector on prediction error, and honest
metrics — pre/post performance, detection latency, catastrophic
forgetting via re-test on the old regime.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .receipts import ReceiptLedger

WORLD_MODEL_VERSION = "toe.world_model/v1"

MODEL_SUPPORTED = "MODEL_SUPPORTED"
MODEL_DRIFT = "MODEL_DRIFT"
MODEL_CONTRADICTED = "MODEL_CONTRADICTED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def _mse(pairs: Sequence[tuple]) -> float:
    if not pairs:
        return 0.0
    return sum((a - b) ** 2 for a, b in pairs) / len(pairs)


class WorldModel:
    """Linear-dynamics world model with declared structure.

    ``nodes``: entity/state variables. ``edges``: (parent, child)
    relations forming the causal skeleton. ``dynamics``: per-child
    coefficient on each parent plus a bias — fitted online.
    ``constraints``: (name, predicate). ``actions``: declared operator
    names with the node they set — action effect = the node becomes the
    intervened value. ``outcomes``: observed transitions (with receipts).
    """

    def __init__(
        self,
        *,
        nodes: Sequence[str],
        edges: Sequence[tuple],
        actions: Optional[Mapping[str, str]] = None,
        constraints: Optional[Mapping[str, Callable[[Mapping[str, float]], bool]]] = None,
        ledger: Optional[ReceiptLedger] = None,
    ) -> None:
        self.nodes = list(nodes)
        self.edges = list(edges)
        self.parents: Dict[str, List[str]] = {n: [] for n in self.nodes}
        for p, c in self.edges:
            self.parents[c].append(p)
        self.actions = dict(actions or {})
        self.constraints = dict(constraints or {})
        self.dynamics: Dict[str, Dict[str, float]] = {
            c: {p: 1.0 for p in ps} | {"bias": 0.0}
            for c, ps in self.parents.items()
        }
        self.outcomes: List[Dict[str, Any]] = []
        self.revisions: List[Dict[str, Any]] = []
        self.ledger = ledger or ReceiptLedger(run_id="world_model")

    # -- §23 prediction ----------------------------------------------

    def predict_transition(
        self,
        state: Mapping[str, float],
        action: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, float]:
        """Next-state prediction: actions pin their nodes; every other
        node follows the fitted linear dynamics from the (post-action)
        parent values."""
        post = dict(state)
        for node, value in (action or {}).items():
            post[node] = float(value)
        pred: Dict[str, float] = {}
        for node in self.nodes:
            if action and node in action:
                pred[node] = post[node]
                continue
            if not self.parents[node]:
                # exogenous input: persistence, not a fitted claim
                pred[node] = float(post.get(node, 0.0))
                continue
            w = self.dynamics.get(node, {})
            pred[node] = w.get("bias", 0.0) + sum(
                w.get(p, 0.0) * float(post.get(p, 0.0)) for p in self.parents[node]
            )
        return pred

    def observe(
        self,
        prev_state: Mapping[str, float],
        action: Optional[Mapping[str, float]],
        next_state: Mapping[str, float],
    ) -> Dict[str, Any]:
        """Record one observed transition; returns the prediction-error
        decomposition used by §§24-26."""
        pred = self.predict_transition(prev_state, action)
        # score only endogenous nodes (those with parents): error on an
        # exogenous input measures the driving process, not the model
        errors = {
            n: float(next_state.get(n, 0.0)) - pred.get(n, 0.0)
            for n in self.nodes
            if self.parents[n]
        }
        rec = {
            "prev": dict(prev_state),
            "action": dict(action or {}),
            "next": dict(next_state),
            "predicted": pred,
            "errors": errors,
            "mse": _mse([(0.0, v) for v in errors.values()]),
        }
        receipt = self.ledger.issue(
            "world_model.observe",
            inputs={"prev": dict(prev_state), "action": dict(action or {})},
            config={},
            output=dict(next_state),
        )
        rec["receipt_sha256"] = receipt.receipt_sha256
        self.outcomes.append(rec)
        return rec

    # -- §24 revision -------------------------------------------------

    def assess(
        self, evidence: Optional[Sequence[Mapping[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Prediction vs fresh evidence → one of the four states.

        Thresholds are declared, not tuned per case: mean |error| under
        ``0.05`` = supported; under ``0.5`` = drift; beyond = contradicted.
        Fewer than 3 observations = insufficient evidence.
        """
        rows = list(evidence) if evidence is not None else self.outcomes[-20:]
        if len(rows) < 3:
            return {"status": INSUFFICIENT_EVIDENCE, "observations": len(rows)}
        mean_abs = sum(
            abs(e) for r in rows for e in r["errors"].values()
        ) / max(1, sum(len(r["errors"]) for r in rows))
        if mean_abs < 0.05:
            status = MODEL_SUPPORTED
        elif mean_abs < 0.5:
            status = MODEL_DRIFT
        else:
            status = MODEL_CONTRADICTED
        return {
            "status": status,
            "mean_abs_error": mean_abs,
            "observations": len(rows),
            "thresholds": {"supported": 0.05, "drift": 0.5},
        }

    def revise(self, min_evidence: int = 5, lr: float = 0.2) -> Dict[str, Any]:
        """Refit dynamics on accumulated outcomes — only with sufficient
        evidence. Every revision is appended to ``revisions`` (history
        kept, never rewritten)."""
        if len(self.outcomes) < min_evidence:
            return {
                "revised": False,
                "reason": f"insufficient evidence ({len(self.outcomes)} < {min_evidence})",
            }
        before = {c: dict(w) for c, w in self.dynamics.items()}
        for child in self.nodes:
            if not self.parents[child]:
                continue
            for obs in self.outcomes:
                target = float(obs["next"].get(child, 0.0))
                post = dict(obs["prev"])
                post.update(obs["action"])
                for p in self.parents[child]:
                    grad = float(post.get(p, 0.0))
                    pred = self.predict_transition(obs["prev"], obs["action"])[child]
                    self.dynamics[child][p] += lr * (target - pred) * grad
                pred = self.predict_transition(obs["prev"], obs["action"])[child]
                self.dynamics[child]["bias"] = self.dynamics[child].get("bias", 0.0) + lr * (
                    target - pred
                )
        self.revisions.append(
            {
                "n_observations": len(self.outcomes),
                "before": before,
                "after": {c: dict(w) for c, w in self.dynamics.items()},
            }
        )
        self.ledger.issue(
            "world_model.revise",
            inputs={"n": len(self.outcomes)},
            config={"lr": lr},
            output={"revisions": len(self.revisions)},
        )
        return {"revised": True, "revision_index": len(self.revisions) - 1}


# -- §25 consequence loop --------------------------------------------


def bind_outcome(
    decision_sha256: str,
    decision_selected_action: Any,
    predicted_future: Mapping[str, float],
    observed_outcome: Mapping[str, float],
    ledger: ReceiptLedger,
) -> Dict[str, Any]:
    """Bind the observed outcome to the EXACT decision that generated it.

    Returns the prediction error and the per-dimension attribution — the
    closed loop prediction → action → outcome → error → attribution.
    """
    errors = {
        k: float(observed_outcome.get(k, 0.0)) - float(predicted_future.get(k, 0.0))
        for k in set(predicted_future) | set(observed_outcome)
    }
    abs_err = {k: abs(v) for k, v in errors.items()}
    attribution = max(abs_err, key=abs_err.get) if abs_err else None
    receipt = ledger.issue(
        "consequence.bind",
        inputs={
            "decision_sha256": decision_sha256,
            "action": decision_selected_action,
        },
        config={},
        output=dict(observed_outcome),
    )
    return {
        "decision_sha256": decision_sha256,
        "receipt_sha256": receipt.receipt_sha256,
        "prediction_error": errors,
        "largest_error_dimension": attribution,
        "bound": True,
    }


# -- §26 online adaptation -------------------------------------------


class OnlineAdapter:
    """Controlled online-learning loop with honest metrics.

    ``step(state, action, next_state)`` observes a transition, updates
    the model, and feeds a CUSUM detector on per-step absolute error.
    ``metrics()`` reports pre/post-change performance, detection latency
    against the declared change point, and catastrophic forgetting via a
    held-out old-regime probe — no hidden truth leak: the detector sees
    only prediction errors, never the regime label.
    """

    def __init__(
        self,
        model: WorldModel,
        *,
        cusum_threshold: float = 1.0,
        lr: float = 0.15,
    ) -> None:
        self.model = model
        self.lr = lr
        self.cusum_threshold = cusum_threshold
        self.cusum = 0.0
        self.baseline_err = 0.0
        self.steps = 0
        self.detected_at: Optional[int] = None
        self.errors: List[float] = []

    def step(
        self,
        prev_state: Mapping[str, float],
        action: Optional[Mapping[str, float]],
        next_state: Mapping[str, float],
    ) -> Dict[str, Any]:
        obs = self.model.observe(prev_state, action, next_state)
        err = max(abs(e) for e in obs["errors"].values()) if obs["errors"] else 0.0
        self.errors.append(err)
        self.steps += 1
        if self.steps > 20 and self.baseline_err == 0.0:
            self.baseline_err = sum(self.errors[:20]) / 20 + 1e-6
        self.cusum = max(0.0, self.cusum + (err - self.baseline_err))
        if self.detected_at is None and self.cusum > self.cusum_threshold:
            self.detected_at = self.steps
        # online gradient step on this transition
        self.model.revise(min_evidence=1, lr=self.lr)
        return {"step": self.steps, "error": err, "cusum": self.cusum,
                "detected": self.detected_at is not None}

    def metrics(
        self, change_point: int, forgetting_probe: Optional[Callable[[], float]] = None
    ) -> Dict[str, Any]:
        pre = self.errors[:change_point]
        post = self.errors[change_point:]
        tail = post[max(0, len(post) - 20):]
        out = {
            "performance_before_change": sum(pre) / len(pre) if pre else None,
            "performance_after_adaptation": sum(tail) / len(tail) if tail else None,
            "detection_latency": (
                self.detected_at - change_point
                if self.detected_at is not None and self.detected_at >= change_point
                else None
            ),
            "detected": self.detected_at is not None,
            "steps": self.steps,
        }
        if forgetting_probe is not None:
            out["catastrophic_forgetting_error"] = forgetting_probe()
        return out


__all__ = [
    "WORLD_MODEL_VERSION",
    "MODEL_SUPPORTED",
    "MODEL_DRIFT",
    "MODEL_CONTRADICTED",
    "INSUFFICIENT_EVIDENCE",
    "WorldModel",
    "bind_outcome",
    "OnlineAdapter",
]
