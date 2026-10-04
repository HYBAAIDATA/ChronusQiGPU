"""Adaptive cognition mechanisms with explicit, falsifiable evidence.

These mechanisms operate on the shared cognitive envelope.  They never promote
complexity, novelty, mathematical structure, skills, or strategies without a
measured comparison against a declared baseline.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..contracts import domain_hash
from ..evidence import atomic_write
from .interfaces import StrategyChoice

_SEAL_DOMAIN = "euclid.strategy-learning.seal.v1"


@dataclass(frozen=True)
class RepresentationTrial:
    representation_id: str
    kind: str
    payload: Mapping[str, Any]
    baseline_utility: float
    candidate_utility: float
    cost: float
    accepted: bool
    rationale: str


class RepresentationController:
    """Change representation only when measured net utility improves."""

    def candidates(self, problem: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        structure = [str(x) for x in problem.get("structure", ())]
        observations = [str(x) for x in problem.get("observations", ())]
        candidates: list[tuple[str, dict[str, Any]]] = [
            ("relational", {"relations": sorted(set(structure))}),
        ]
        if any("->" in item or "depends" in item for item in observations):
            edges = []
            for item in observations:
                if "->" in item:
                    left, right = item.split("->", 1)
                    edges.append((left.strip(), right.strip()))
            candidates.append(("graph", {"edges": sorted(edges), "relations": structure}))
        source = problem.get("initial_code")
        if isinstance(source, str) and source.strip():
            import ast
            try:
                tree = ast.parse(source)
            except (SyntaxError, TypeError, ValueError):
                # Malformed source is a valid repair input.  It cannot support
                # a source-dependency representation, so retain other measured
                # candidates and let the literal source reach diagnosis.
                tree = None
            if tree is not None:
                dependencies = sorted({
                    node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
                })
                candidates.append(("source-dependency", {"symbols": dependencies}))
        numeric = [
            float(value) for value in problem.get("state_vector", ())
            if isinstance(value, (int, float)) and math.isfinite(float(value))
        ]
        if numeric:
            norm = math.sqrt(sum(value * value for value in numeric)) or 1.0
            candidates.append((
                "manifold-direction",
                {"unit_direction": [value / norm for value in numeric],
                 "evidence_class": "exploratory-parametric"},
            ))
        return candidates

    def select(
        self, problem: Mapping[str, Any],
        evaluator: Callable[[str, Mapping[str, Any]], tuple[float, float]],
    ) -> RepresentationTrial:
        baseline_kind = str(problem.get("representation_kind", "literal"))
        baseline_payload = {"problem": dict(problem)}
        baseline_utility, baseline_cost = evaluator(baseline_kind, baseline_payload)
        best = RepresentationTrial(
            baseline_kind, baseline_kind, baseline_payload,
            baseline_utility, baseline_utility, baseline_cost, False,
            "baseline retained",
        )
        for kind, payload in self.candidates(problem):
            utility, cost = evaluator(kind, payload)
            net = utility - cost
            baseline_net = baseline_utility - baseline_cost
            if net > baseline_net and net > best.candidate_utility - best.cost:
                best = RepresentationTrial(
                    "repr-" + domain_hash("euclid.representation.v1", {
                        "kind": kind, "payload": payload,
                    })[:16],
                    kind, payload, baseline_utility, utility, cost, True,
                    f"net utility {net:.6g} exceeds baseline {baseline_net:.6g}",
                )
        return best


@dataclass(frozen=True)
class IntermediateObjective:
    objective_id: str
    description: str
    parent_goal: str
    evidence_basis: str
    metric: str
    target: float
    weight: float
    status: str = "active"


class ObjectiveController:
    """Construct intermediate objectives and detect proxy detachment."""

    def derive(
        self, goal: str, *, uncertainty: float, contradictions: int,
        missing_evidence: int, prediction_error: float,
    ) -> list[IntermediateObjective]:
        specs: list[tuple[str, str, float, float]] = []
        if uncertainty > 0:
            specs.append(("reduce uncertainty", "uncertainty", 0.0, 0.30))
        if contradictions:
            specs.append(("resolve contradictions", "contradictions", 0.0, 0.30))
        if missing_evidence:
            specs.append(("acquire missing evidence", "evidence_gap", 0.0, 0.20))
        if prediction_error > 0:
            specs.append(("repair predictive model", "prediction_error", 0.0, 0.20))
        if not specs:
            specs.append(("verify terminal goal", "goal_verified", 1.0, 1.0))
        total = sum(weight for _, _, _, weight in specs)
        return [
            IntermediateObjective(
                f"objective-{index}", description, goal,
                "measured cognitive-state signals", metric, target, weight / total,
            )
            for index, (description, metric, target, weight) in enumerate(specs)
        ]

    @staticmethod
    def audit_alignment(
        objective: IntermediateObjective, *,
        metric_improved: bool, goal_progressed: bool,
    ) -> IntermediateObjective:
        if metric_improved and not goal_progressed:
            return IntermediateObjective(
                **{**asdict(objective), "status": "detached-proxy"}
            )
        return objective


class PersistentStrategyLearner:
    """Per-class strategy evidence with durable negative-transfer records."""

    SCHEMA = "euclid.strategy-learning/1"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.stats: dict[str, dict[str, dict[str, float]]] = {}
        self.negative_transfer: list[dict[str, Any]] = []
        if self.path.is_file():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("schema") != self.SCHEMA:
                raise ValueError("unsupported strategy-learning schema")
            body = {key: payload.get(key) for key in ("schema", "stats", "negative_transfer")}
            if payload.get("seal") != domain_hash(_SEAL_DOMAIN, body):
                raise ValueError("strategy-learning ledger seal mismatch")
            self.stats = dict(payload.get("stats", {}))
            self.negative_transfer = list(payload.get("negative_transfer", ()))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "schema": self.SCHEMA,
            "stats": self.stats,
            "negative_transfer": self.negative_transfer,
        }
        atomic_write(self.path, {**body, "seal": domain_hash(_SEAL_DOMAIN, body)})

    def select_strategy(
        self, problem_class: str, available: Sequence[str]
    ) -> StrategyChoice:
        if not available:
            raise ValueError("at least one strategy is required")
        class_stats = self.stats.get(problem_class, {})
        scored = []
        for strategy in available:
            record = class_stats.get(strategy)
            if record and record["trials"] > 0:
                mean = record["utility"] / record["trials"]
                uncertainty = 1.0 / math.sqrt(record["trials"])
                scored.append((mean + 0.1 * uncertainty, strategy, record))
        if not scored:
            return StrategyChoice(
                available[0], tuple(available[1:]),
                f"no evidence for class {problem_class!r}; cross-class preference blocked",
            )
        scored.sort(key=lambda row: (-row[0], row[1]))
        selected = scored[0][1]
        return StrategyChoice(
            selected, tuple(item for item in available if item != selected),
            f"per-class measured utility over {int(scored[0][2]['trials'])} trial(s)",
        )

    def update(
        self, problem_class: str, strategy_id: str, success: bool,
        detail: str = "",
    ) -> None:
        utility = 1.0 if success else 0.0
        record = self.stats.setdefault(problem_class, {}).setdefault(
            strategy_id, {"successes": 0.0, "trials": 0.0, "utility": 0.0}
        )
        record["successes"] += utility
        record["trials"] += 1.0
        record["utility"] += utility
        self._save()

    def record_transfer(
        self, source_class: str, target_class: str, strategy_id: str,
        baseline_utility: float, transfer_utility: float,
    ) -> None:
        delta = float(transfer_utility) - float(baseline_utility)
        if delta < 0:
            self.negative_transfer.append({
                "source_class": source_class,
                "target_class": target_class,
                "strategy_id": strategy_id,
                "delta": delta,
                "timestamp": time.time(),
            })
        self._save()


@dataclass
class CapabilityRecord:
    capability_id: str
    kind: str
    dependencies: tuple[str, ...]
    provenance: str
    status: str = "sandbox"
    trials: int = 0
    successes: int = 0
    failures: int = 0
    domains: set[str] = field(default_factory=set)
    semantic_digest: str | None = None


class CapabilityLifecycle:
    """Evidence-gated primitive/skill hierarchy with deprecation history."""

    def __init__(self) -> None:
        self.records: dict[str, CapabilityRecord] = {}
        self.events: list[dict[str, Any]] = []

    def discover(
        self, capability_id: str, *, kind: str, dependencies: Sequence[str],
        provenance: str,
    ) -> CapabilityRecord:
        if kind not in {"primitive", "composed-primitive", "skill", "composed-skill", "strategy"}:
            raise ValueError("unsupported capability kind")
        if capability_id in self.records:
            return self.records[capability_id]
        record = CapabilityRecord(
            capability_id, kind, tuple(dependencies), provenance
        )
        self.records[capability_id] = record
        self.events.append({"event": "discovered", "capability_id": capability_id})
        return record

    def validate(
        self, capability_id: str, *,
        implementation: Callable[[Any], Any],
        reference: Callable[[Any], Any],
        corpus: Sequence[Any],
        domain: str,
    ) -> bool:
        record = self.records[capability_id]
        outputs = []
        valid = True
        for item in corpus:
            expected = reference(item)
            actual = implementation(item)
            outputs.append({"input": item, "expected": expected, "actual": actual})
            record.trials += 1
            if actual == expected:
                record.successes += 1
            else:
                record.failures += 1
                valid = False
        record.domains.add(domain)
        record.semantic_digest = domain_hash(
            "euclid.capability.semantic-equivalence.v1", outputs
        )
        record.status = "validated" if valid else "rejected"
        self.events.append({
            "event": record.status, "capability_id": capability_id,
            "domain": domain, "semantic_digest": record.semantic_digest,
        })
        return valid

    def promote(self, capability_id: str, *, min_domains: int = 2) -> None:
        record = self.records[capability_id]
        if record.status != "validated" or record.failures:
            raise ValueError("only semantically validated capabilities may be promoted")
        if len(record.domains) < min_domains:
            raise ValueError("generalisation evidence is insufficient")
        record.status = "promoted"
        self.events.append({"event": "promoted", "capability_id": capability_id})

    def deprecate(self, capability_id: str, rationale: str) -> None:
        if not rationale:
            raise ValueError("deprecation rationale is required")
        self.records[capability_id].status = "deprecated"
        self.events.append({
            "event": "deprecated", "capability_id": capability_id,
            "rationale": rationale,
        })


class NoveltyArchive:
    """Behavioural novelty subordinate to correctness and invariants."""

    def __init__(self, threshold: float = 0.25) -> None:
        self.threshold = float(threshold)
        self.descriptors: list[tuple[float, ...]] = []

    @staticmethod
    def _distance(left: Sequence[float], right: Sequence[float]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))

    def consider(
        self, descriptor: Sequence[float], *, correct: bool,
        invariants_hold: bool,
    ) -> dict[str, Any]:
        point = tuple(map(float, descriptor))
        if not correct or not invariants_hold:
            return {"accepted": False, "reason": "correctness/invariant gate failed"}
        novelty = (
            min(self._distance(point, prior) for prior in self.descriptors)
            if self.descriptors else math.inf
        )
        accepted = novelty >= self.threshold
        if accepted:
            self.descriptors.append(point)
        return {"accepted": accepted, "novelty": novelty, "descriptor": point}


__all__ = [
    "CapabilityLifecycle",
    "CapabilityRecord",
    "IntermediateObjective",
    "NoveltyArchive",
    "ObjectiveController",
    "PersistentStrategyLearner",
    "RepresentationController",
    "RepresentationTrial",
]
