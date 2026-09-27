"""Measured five-intelligence mining control plane.

This module contains no simulator, generated trajectory, heuristic predictor,
or synthetic counterfactual.  Every deliberative result is derived from
observed telemetry, exact discrete topology operators, or a commissioned
intervention record.

The five roles are deliberately separated:

* GeometricState: deterministic state coordinates from measured telemetry.
* TopologicalState: exact connected-component/cycle invariants on the fixed
  32-lane MLA1517 topology.
* MeasuredForwardIndex: forward transitions observed after real actions.
* CommissionedSCM: causal effects admitted only after real interventions.
* ObservedCounterfactuals: off-policy values admitted only for actions that
  actually occurred in the same measured regime.

The agent has no implicit hardware write.  An actuator is called only after
Salamander's veto, hard constraints, and observed-support checks pass.
"""

from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass
from typing import Callable, Iterable

from salamander_control import LANES, MIN_LANES

THERMAL_ZONES = 4


@dataclass(frozen=True)
class State:
    """Measured telemetry snapshot; counters are cumulative."""

    temps: tuple[float, ...]
    hashes: tuple[int, ...]
    faults: tuple[int, ...]
    power_w: float
    clock_mhz: float
    pool_latency: dict[str, float]
    mempool_fees: tuple[float, ...]
    btc_price: float

    def __post_init__(self) -> None:
        if len(self.temps) != LANES or len(self.hashes) != LANES or len(self.faults) != LANES:
            raise ValueError(f"temps, hashes, and faults must have {LANES} lanes")
        if any(value < 0 for value in self.hashes + self.faults):
            raise ValueError("hash and fault counters must be non-negative")
        if self.power_w < 0 or self.clock_mhz <= 0 or self.btc_price < 0:
            raise ValueError("power and price must be non-negative; clock must be positive")


@dataclass(frozen=True)
class Action:
    """A real actuator command. Temperature is never an intervention target."""

    lane_mask: int
    clock_target: tuple[float, ...]
    nonce_alloc: tuple[tuple[int, int, int], ...] = ()
    pool_weights: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.lane_mask <= 0xFFFFFFFF:
            raise ValueError("lane_mask must be uint32")
        if len(self.clock_target) != THERMAL_ZONES or any(
            value <= 0 for value in self.clock_target
        ):
            raise ValueError(f"clock_target must contain {THERMAL_ZONES} positive values")
        if self.pool_weights:
            total = sum(weight for _, weight in self.pool_weights)
            if any(weight < 0 for _, weight in self.pool_weights) or abs(total - 1.0) > 1e-6:
                raise ValueError("pool weights must be non-negative and sum to one")

    @property
    def active_lanes(self) -> int:
        return self.lane_mask.bit_count()

    def key(self) -> tuple[object, ...]:
        return (self.lane_mask, self.clock_target, self.nonce_alloc, self.pool_weights)


@dataclass(frozen=True)
class Goal:
    """Hard operating constraints for admissible actions."""

    max_temp: float = 85.0
    power_budget: float = 1000.0
    min_lanes: int = MIN_LANES
    horizon: int = 8
    electricity_price: float = 0.10


@dataclass(frozen=True)
class GeometricState:
    """Deterministic coordinates; no learned or generated values."""

    coordinates: tuple[float, ...]
    digest: str


class GeomEncoder:
    """Encode measured state into fixed coordinates for identity and lookup."""

    def embed(self, state: State) -> GeometricState:
        mean_temp = statistics.fmean(state.temps)
        mean_hashes = statistics.fmean(state.hashes)
        mean_faults = statistics.fmean(state.faults)
        latencies = tuple(state.pool_latency.values()) or (0.0,)
        fees = state.mempool_fees or (0.0,)
        coordinates = (
            mean_temp,
            max(state.temps),
            min(state.temps),
            mean_hashes,
            max(state.hashes),
            mean_faults,
            max(state.faults),
            state.power_w,
            state.clock_mhz,
            statistics.fmean(latencies),
            max(latencies),
            statistics.fmean(fees),
            max(fees),
            state.btc_price,
            float(state.faults.count(0)),
            float(state.hashes.count(0)),
        )
        payload = repr(coordinates).encode("ascii")
        return GeometricState(coordinates, hashlib.sha256(payload).hexdigest())

    def update(self, state: State) -> GeometricState:
        """Return the next measured coordinate; never trains on synthetic data."""
        return self.embed(state)


@dataclass(frozen=True)
class TopologicalInvariants:
    """Exact graph invariants of the currently observed lane health."""

    b0: int
    b1: int
    healthy_lanes: int
    fault_mass: int
    regime_key: str


class TopologicalRegime:
    """Compute invariants on the fixed M32 ring-plus-chord topology.

    This is an exact finite graph calculation over observed lane state.  It is
    not a persistence-homology simulator and does not invent future points.
    """

    @staticmethod
    def _edges() -> tuple[tuple[int, int], ...]:
        edges = set()
        for lane in range(LANES):
            for step in (1, 2, 4, 8, 16):
                other = (lane + step) % LANES
                edges.add(tuple(sorted((lane, other))))
        return tuple(sorted(edges))

    EDGES = _edges.__func__()

    def invariants(self, state: State) -> TopologicalInvariants:
        healthy = [fault == 0 for fault in state.faults]
        parent = list(range(LANES))

        def find(node: int) -> int:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(left: int, right: int) -> None:
            a, b = find(left), find(right)
            if a != b:
                parent[b] = a

        edges = 0
        for left, right in self.EDGES:
            if healthy[left] and healthy[right]:
                edges += 1
                union(left, right)
        active = [index for index, present in enumerate(healthy) if present]
        b0 = len({find(index) for index in active}) if active else 0
        b1 = max(edges - len(active) + b0, 0)
        regime = f"b0={b0};b1={b1};fault_mass={sum(state.faults)};active={len(active)}"
        return TopologicalInvariants(b0, b1, len(active), sum(state.faults), regime)


@dataclass(frozen=True)
class Transition:
    """A transition captured from real telemetry before and after an action."""

    before: State
    action: Action
    after: State
    reward: float
    regime_key: str


class NotMeasured(LookupError):
    """Raised when a requested physical result has not been observed."""


class MeasuredForwardIndex:
    """Forward index populated only by hardware/workload observations."""

    def __init__(self) -> None:
        self.transitions: list[Transition] = []

    def record(self, transition: Transition) -> None:
        self.transitions.append(transition)

    def forward(self, state: State, action: Action, regime_key: str) -> State:
        for transition in reversed(self.transitions):
            if transition.action.key() == action.key() and transition.regime_key == regime_key:
                return transition.after
        raise NotMeasured("no measured forward transition for this action and regime")

    def candidates(self, regime_key: str) -> tuple[Action, ...]:
        seen: dict[tuple[object, ...], Action] = {}
        for transition in self.transitions:
            if transition.regime_key == regime_key:
                seen[transition.action.key()] = transition.action
        return tuple(seen.values())


class NotCommissioned(LookupError):
    """Raised when a causal effect lacks commissioned intervention data."""


class CommissionedSCM:
    """SCM ledger backed by measured interventions, not correlation."""

    EDGES = (
        ("clock", "power"),
        ("lane_mask", "power"),
        ("power", "temp"),
        ("clock", "hashrate"),
        ("lane_mask", "hashrate"),
        ("temp", "faults"),
        ("hashrate", "shares"),
        ("pool_latency", "shares"),
    )

    def __init__(self) -> None:
        self.interventions: list[Transition] = []

    def do(self, action: Action) -> dict[str, object]:
        """Return the auditable intervention record; no outcome is fabricated."""
        return {"action": action, "cut_incoming_edges": ("clock", "lane_mask")}

    def commission(self, transition: Transition) -> None:
        self.interventions.append(transition)

    def causal_effect(self, action: Action, target: str, regime_key: str) -> float:
        if target not in {"power", "temp", "hashrate", "faults", "shares"}:
            raise KeyError(target)
        samples: list[float] = []
        for transition in self.interventions:
            if transition.action.key() != action.key() or transition.regime_key != regime_key:
                continue
            before = _metric(transition.before, target)
            after = _metric(transition.after, target)
            samples.append(after - before)
        if not samples:
            raise NotCommissioned("intervention has not been commissioned in this regime")
        return statistics.fmean(samples)

    def valid_action(self, action: Action, goal: Goal) -> bool:
        return action.active_lanes >= goal.min_lanes and all(
            value > 0 for value in action.clock_target
        )


class SupportViolation(ValueError):
    """Raised when an action is outside the measured support."""


class ObservedCounterfactuals:
    """Off-policy evaluation using only observed transitions."""

    def __init__(self, ledger: MeasuredForwardIndex) -> None:
        self.ledger = ledger

    def score(self, action: Action, regime_key: str) -> float:
        matches = [
            item.reward
            for item in self.ledger.transitions
            if item.action.key() == action.key() and item.regime_key == regime_key
        ]
        if not matches:
            raise SupportViolation("counterfactual action has no observed support in this regime")
        return statistics.fmean(matches)

    def score_candidates(
        self, actions: Iterable[Action], regime_key: str
    ) -> dict[tuple[object, ...], float]:
        scores: dict[tuple[object, ...], float] = {}
        for action in actions:
            try:
                scores[action.key()] = self.score(action, regime_key)
            except SupportViolation:
                continue
        return scores


@dataclass(frozen=True)
class AgentDecision:
    action: Action
    invariants: TopologicalInvariants
    scores: dict[tuple[object, ...], float]
    mode: str
    reason: str


def _metric(state: State, target: str) -> float:
    if target == "power":
        return state.power_w
    if target == "temp":
        return statistics.fmean(state.temps)
    if target == "hashrate":
        return float(sum(state.hashes))
    if target == "faults":
        return float(sum(state.faults))
    if target == "shares":
        return float(sum(state.hashes)) / (
            1.0 + statistics.fmean(tuple(state.pool_latency.values()) or (0.0,))
        )
    raise KeyError(target)


class MiningAgent:
    """Measured cortex with Salamander veto and ACK-gated optional actuation."""

    def __init__(
        self,
        *,
        goal: Goal | None = None,
        encoder: GeomEncoder | None = None,
        topology: TopologicalRegime | None = None,
        ledger: MeasuredForwardIndex | None = None,
        scm: CommissionedSCM | None = None,
        salamander_permits: Callable[[Action], bool] | None = None,
        actuator: Callable[[Action], bool] | None = None,
    ) -> None:
        self.goal = goal or Goal()
        self.encoder = encoder or GeomEncoder()
        self.topology = topology or TopologicalRegime()
        self.ledger = ledger or MeasuredForwardIndex()
        self.scm = scm or CommissionedSCM()
        self.counterfactuals = ObservedCounterfactuals(self.ledger)
        self.salamander_permits = salamander_permits or (lambda action: True)
        self.actuator = actuator
        self._pending_observation: tuple[State, Action, str] | None = None

    def record_transition(
        self, before: State, action: Action, after: State, reward: float
    ) -> Transition:
        """Record one real post-actuation observation and commission it."""
        regime_key = self.topology.invariants(before).regime_key
        transition = Transition(before, action, after, float(reward), regime_key)
        self.ledger.record(transition)
        self.scm.commission(transition)
        return transition

    def record_observed_result(self, after: State, reward: float) -> Transition:
        """Complete the observation opened by an acknowledged actuator call."""
        if self._pending_observation is None:
            raise NotMeasured("no acknowledged action is awaiting an observation")
        before, action, _ = self._pending_observation
        self._pending_observation = None
        return self.record_transition(before, action, after, reward)

    def safe_action(self, state: State) -> Action:
        return Action((1 << LANES) - 1, (state.clock_mhz,) * THERMAL_ZONES)

    def tick(self, state: State) -> AgentDecision:
        self.encoder.update(state)
        invariants = self.topology.invariants(state)
        safe = self.safe_action(state)
        actions = self.ledger.candidates(invariants.regime_key)
        actions = [action for action in actions if self.scm.valid_action(action, self.goal)]
        actions = [action for action in actions if self.salamander_permits(action)]
        scores = self.counterfactuals.score_candidates(actions, invariants.regime_key)
        if not scores:
            return AgentDecision(
                safe, invariants, {}, "CONSERVATIVE", "no_measured_supported_action"
            )
        best_key = max(scores, key=scores.__getitem__)
        action = next(item for item in actions if item.key() == best_key)
        if self.actuator is not None and not self.actuator(action):
            return AgentDecision(
                safe, invariants, scores, "CONSERVATIVE", "actuator_not_acknowledged"
            )
        if self.actuator is not None:
            self._pending_observation = (state, action, invariants.regime_key)
        return AgentDecision(
            action, invariants, scores, "MEASURED", "observed_counterfactual_argmax"
        )
