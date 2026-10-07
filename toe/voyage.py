"""TOE power-on self-test: the canonical and cross-domain voyages.

``cross_domain_voyage()`` sends materially different problem classes —
tabular records, an explicit causal system, a graph, a time series, Python
source structure, an integer sequence, a precision-critical linear system,
and the legacy HR surface — through ONE :class:`~toe.machine.TOEMachine`
and records, per domain, which adapter translated it and which backend
callables executed. The adapters are the only per-domain code.

``canonical_voyage()`` exercises the machine as a machine::

    problem → episode (VOI says: acquire evidence first)
            → experiment executed in a simulated world
            → outcome bound → contradiction → revision
            → THESEUS persistence → restart → recovery
            → related problem → changed, now-confident decision
            → replay of the first decision → negative-transfer guard

The worlds here are declared simulators (seeded); they are the test
environment, not evidence about any real domain.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Mapping, Optional

from .adapters import (
    CausalSystemAdapter,
    CodeStructureAdapter,
    GraphAdapter,
    LegacyHRAdapter,
    LinearSystemAdapter,
    RecurrenceAdapter,
    TabularAdapter,
    TimeSeriesAdapter,
)
from .machine import TOEMachine
from .problem import Problem, Structure
from .planning import OperatorSpec
from .policy import Objective

VOYAGE_VERSION = "toe.voyage/v1"
PHI = (1 + 5**0.5) / 2


# ---------------------------------------------------------------------------
# Fixtures — raw domain inputs (what a caller in that domain would hold)
# ---------------------------------------------------------------------------


def _confounded_rows(n: int = 2000, seed: int = 11) -> List[Dict[str, float]]:
    """season → promo, season → sales, promo → sales with a NEGATIVE effect
    that the raw association hides (it comes out positive)."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        season = rng.gauss(0, 1)
        promo = 2.0 * season + PHI * rng.gauss(0, 0.3)
        sales = -0.5 * promo + 3.0 * season + PHI * rng.gauss(0, 0.3)
        rows.append({"season": PHI * season, "promo": promo, "sales": sales})
    return rows


def fixture_tabular() -> Dict[str, Any]:
    return {
        "domain": "tabular.retail",
        "rows": _confounded_rows(),
        "relations": [["season", "promo"], ["season", "sales"], ["promo", "sales"]],
        "current": {"season": 0.0, "promo": 1.0, "sales": 0.0},
        "levers": {"promo": [0.0, 1.0, 2.0]},
        "goal": {"maximize": "sales"},
        "question": ["promo", "sales"],
    }


def fixture_causal_system() -> Dict[str, Any]:
    """Budget trap: one-shot greedy takes the big step, two small steps win."""
    return {
        "domain": "causal.operations",
        "equations": {"y": {"x": 1.0}},
        "factual": {"x": 0.0, "y": 0.0},
        "deltas": {"x": [2.0, 3.0]},
        "operators": [
            {"name": "small_step", "node": "x", "deltas": [2.0], "cost": 1.0},
            {"name": "big_step", "node": "x", "deltas": [3.0], "cost": 2.0},
        ],
        "target": "y",
        "budget": 2.0,
        "horizon": 2,
        "noise_sd": {"x": 0.1, "y": 0.1},
        "question": ["x", "y"],
    }


def fixture_graph() -> Dict[str, Any]:
    """A walled grid: geometry (straight-line closeness) misleads, topology
    does not."""
    nodes = [(x, y) for x in range(7) for y in range(7) if not (x == 3 and y >= 1)]
    keep = set(nodes)
    edges = []
    for x, y in nodes:
        for dx, dy in ((1, 0), (0, 1)):
            if (x + dx, y + dy) in keep:
                edges.append([f"{x},{y}", f"{x + dx},{y + dy}"])
    return {
        "domain": "graph.facility",
        "edges": edges,
        "positions": {f"{x},{y}": [x, y] for x, y in nodes},
        "from": "0,6",
        "to": "6,6",
    }


def _ts(n: int = 120, seed: int = 5) -> Dict[str, List[float]]:
    rng = random.Random(seed)
    x, u = [1.0], []
    for _ in range(n):
        ut = rng.choice([-1.0, 0.0, 1.0])
        u.append(ut)
        x.append(0.8 * x[-1] + 0.5 * ut + PHI * rng.gauss(0, 0.05))
    u.append(0.0)
    return {"level": x, "input": u}


def fixture_temporal() -> Dict[str, Any]:
    return {
        "domain": "temporal.process",
        "series": _ts(),
        "state": "level",
        "control": "input",
        "levels": [-1.0, 0.0, 1.0],
        "goal": "maximize",
        "cap": 10.0,
    }


CODE_SAMPLE = """
def main(argv):
    config = parse(argv)
    if validate(config):
        return run(config)
    return 1

def parse(argv):
    return dict(a.split("=") for a in argv)

def validate(config):
    return bool(config) and check_keys(config)

def check_keys(config):
    return all(isinstance(k, str) for k in config)

def run(config):
    for k in config:
        emit(k)
    return 0

def emit(k):
    print(k)

def legacy_export(rows):
    for r in rows:
        emit(r)
"""


def fixture_code() -> Dict[str, Any]:
    return {
        "domain": "code.cli_tool",
        "source": CODE_SAMPLE,
        "entry": "main",
        "target": "check_keys",
    }


def fixture_recurrence() -> Dict[str, Any]:
    return {
        "domain": "scientific.sequence",
        "sequence": [2, 1, 3, 4, 7, 11, 18, 29, 47, 76, 123],
        "steps": 1000,
    }


def fixture_recurrence_negative() -> Dict[str, Any]:
    rng = random.Random(3)
    return {
        "domain": "scientific.sequence",
        "sequence": [round(rng.uniform(0, 10), 3) for _ in range(12)],
        "steps": 5,
    }


def fixture_linear_system() -> Dict[str, Any]:
    """y = 1e16·a + 1·b − 1e16·c with b ← a, c ← a. Exactly, do(a=1) gives
    y = 1 and do(a=0) gives 0; float64 adds 1e16 + 1 first and loses the 1,
    seeing a tie. The decision must be made in exact arithmetic."""
    return {
        "domain": "scientific.linear_system",
        "equations": {"b": {"a": 1.0}, "c": {"a": 1.0}, "y": {"a": 1e16, "b": 1.0, "c": -1e16}},
        "factual": {},
        "interventions": {"a": [0.0, 1.0]},
        "target": "y",
        "units": {"a": "V", "b": "V", "c": "V", "y": "W"},
    }


def _hr_rows(n: int = 300, seed: int = 21) -> List[Dict[str, float]]:
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        comp = rng.uniform(0.8, 1.2)
        promo = float(rng.random() < 0.3)
        perf = rng.uniform(0, 1)
        eng = 0.6 * comp + 0.3 * promo + PHI * rng.gauss(0, 0.05)
        churn = -0.5 * eng - 0.2 * perf + PHI * rng.gauss(0, 0.05)
        rows.append(
            {
                "compensation_ratio": comp,
                "promotion": promo,
                "performance_score": perf,
                "engagement": eng,
                "churn_risk": churn,
            }
        )
    return rows


def fixture_legacy_hr() -> Dict[str, Any]:
    return {
        "domain": "legacy_hr",
        "employees": _hr_rows(),
        "current": {
            "compensation_ratio": 1.0,
            "promotion": 0.0,
            "performance_score": 0.5,
            "engagement": 0.6,
            "churn_risk": -0.4,
        },
        "levers": {"compensation_ratio": [1.0, 1.1], "promotion": [0.0, 1.0]},
    }


class _OperatorAwareCausalAdapter(CausalSystemAdapter):
    """Accepts explicit operator lists (several operators on one node)."""

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        problem = super().to_problem(
            {k: v for k, v in raw.items() if k not in ("operators", "deltas")}
        )
        if not raw.get("operators"):
            return problem
        from dataclasses import replace

        ops = tuple(
            OperatorSpec(
                o["name"],
                o["node"],
                tuple(o.get("levels", ())),
                tuple(o.get("deltas", ())),
                float(o.get("cost", 1.0)),
            )
            for o in raw["operators"]
        )
        return replace(problem, operators=ops)


DOMAINS: Dict[str, Any] = {
    "tabular": (TabularAdapter, fixture_tabular),
    "causal_system": (_OperatorAwareCausalAdapter, fixture_causal_system),
    "graph": (GraphAdapter, fixture_graph),
    "temporal": (TimeSeriesAdapter, fixture_temporal),
    "code": (CodeStructureAdapter, fixture_code),
    "scientific.recurrence": (RecurrenceAdapter, fixture_recurrence),
    "scientific.linear_system": (LinearSystemAdapter, fixture_linear_system),
    "legacy_hr": (LegacyHRAdapter, fixture_legacy_hr),
}


def _key_result(name: str, ep: Mapping[str, Any]) -> Dict[str, Any]:
    dec = ep.get("decision") or {}
    out: Dict[str, Any] = {"status": ep.get("status")}
    if dec.get("selected_action"):
        out["selected"] = dec["selected_action"]
        out["futures_rung"] = dec.get("futures_rung")
    if ep.get("recommendation", {}).get("kind") == "plan":
        out["plan"] = ep["recommendation"]["sequence"]
    if ep.get("arbitration"):
        out["arbitration"] = ep["arbitration"]["status"]
    if dec.get("precision"):
        out["precision"] = {
            k: dec["precision"].get(k) for k in ("regime", "exact_ordering", "override")
        }
    lad = (ep.get("understanding") or {}).get("causal_ladder") or {}
    if lad.get("rung1_association", {}).get("available"):
        out["association_slope"] = lad["rung1_association"]["slope_E_y_given_x"]
        out["interventional_effect"] = lad["rung2_interventional"]["effect_per_unit_E_y_do_x"]
    nav = ep.get("navigation") or {}
    if nav:
        out["reachable"] = nav.get("reachable")
        out["representations"] = {r["name"]: r["delivered"] for r in nav.get("representations", [])}
        out["unreachable_from_source"] = nav.get("unreachable_from_source")
    if ep.get("forecast"):
        out["forecast_method"] = ep["forecast"].get("method")
        out["forecast_value"] = ep["forecast"].get("value")
    return out


def cross_domain_voyage(machine: Optional[TOEMachine] = None) -> Dict[str, Any]:
    """Every fixture domain through one machine; adapters are the only
    domain code. Returns per-domain evidence plus the reuse measurement."""
    machine = machine or TOEMachine()
    per: Dict[str, Any] = {}
    backend_sets: Dict[str, set] = {}
    for name, (adapter_cls, fixture) in DOMAINS.items():
        adapter = adapter_cls()
        problem = adapter.to_problem(fixture())
        ep = machine.run(problem)
        backends = set(ep["backends"])
        backend_sets[name] = backends
        per[name] = {
            "adapter": f"{adapter_cls.__module__}.{adapter_cls.__qualname__}",
            "adapter_code_lines": adapter.domain_code_lines(),
            "backend": "toe.machine.TOEMachine",
            "backend_callables": sorted(backends),
            "adapter_code_in_backend_trace": sorted(b for b in backends if ".adapters." in b),
            "result": _key_result(name, ep),
            "interpretation": adapter.interpret(ep),
            "episode_sha256": ep["episode_sha256"],
            "elapsed_s": ep.get("elapsed_s"),
        }
    union = set().union(*backend_sets.values())
    shared = set.intersection(*backend_sets.values())
    return {
        "version": VOYAGE_VERSION,
        "machine_instances": 1,
        "domains": per,
        "reuse": {
            "backend_callables_total": len(union),
            "shared_by_every_domain": sorted(shared),
            "per_domain_fraction_of_union": {
                k: len(v) / len(union) for k, v in backend_sets.items()
            },
            "adapter_code_in_any_backend_trace": sorted(
                {b for v in backend_sets.values() for b in v if ".adapters." in b}
            ),
        },
    }


# ---------------------------------------------------------------------------
# The canonical learning voyage
# ---------------------------------------------------------------------------

TRUE_WEIGHTS = {("x", "y"): 0.5, ("z", "y"): 1.0}


def voyage_problem(*, domain: str = "voyage.allocation", z_state: float = 0.0) -> Problem:
    """Two levers into one outcome. The prior believes x is the stronger
    lever (2.0 vs 1.0); the simulated world disagrees (0.5 vs 1.0). The
    x→y strength is declared uncertain over a range that flips the choice."""
    return Problem(
        domain=domain,
        observation={"x": [0.0, 1.0, 0.5, 0.2], "z": [0.0, 0.3, 0.9, 1.0]},
        state={"x": 0.0, "z": z_state},
        structure=Structure.of([("x", "y", 2.0), ("z", "y", 1.0)]),
        operators=(OperatorSpec("raise_x", "x", (1.0,)), OperatorSpec("raise_z", "z", (1.0,))),
        objective=Objective("y", "maximize"),
        uncertain={"edge:x->y": (0.2, 1.0, 2.0)},
        noise_sd={"x": 1.0, "z": 1.0, "y": 0.05},
        query=("x", "y"),
    )


def simulated_world(
    interventions: Mapping[str, float], *, n: int, seed: int
) -> List[Dict[str, float]]:
    """The declared test world: y = 0.5·x + 1.0·z + φ·u_y."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        x = float(interventions.get("x", PHI * rng.gauss(0, 1.0)))
        z = float(interventions.get("z", PHI * rng.gauss(0, 1.0)))
        y = TRUE_WEIGHTS[("x", "y")] * x + TRUE_WEIGHTS[("z", "y")] * z + PHI * rng.gauss(0, 0.05)
        out.append({"x": x, "z": z, "y": y})
    return out


def canonical_voyage(custody_factory: Optional[Callable[[], Any]] = None) -> Dict[str, Any]:
    """Run the full cycle. ``custody_factory()`` must return a THESEUS custody
    bound to the SAME durable store on every call (the restart opens a new
    one); without it persistence/restart are reported UNAVAILABLE."""
    report: Dict[str, Any] = {"version": VOYAGE_VERSION}
    machine = TOEMachine(custody=custody_factory() if custody_factory else None, stream="voyage")
    p1 = voyage_problem()
    ep1 = machine.run(p1)
    report["episode_1"] = {
        "status": ep1["status"],
        "selected": ep1["decision"]["selected_action"],
        "voi": {k: v["recommend_evidence"] for k, v in ep1["meta"]["value_of_information"].items()},
        "evidence_plan": ep1["meta"].get("evidence_plan"),
        "predicted_y": ep1["decision"]["predicted_future"].get("y"),
    }
    # The evidence the machine asked for: intervene on x, observe y.
    observed = simulated_world(ep1["recommendation"]["interventions"], n=6, seed=101)
    learned = machine.learn(ep1, observed)
    report["learning"] = {
        "assessment": learned["assessment"]["status"],
        "revised": learned["revision"] is not None,
        "weights_after": (learned["revision"] or {}).get("after"),
        "standard_errors": learned["standard_errors"],
        "persisted": learned.get("persisted"),
    }
    ep2 = machine.run(voyage_problem(z_state=0.25))
    report["episode_2_same_process"] = {
        "status": ep2["status"],
        "selected": ep2["decision"]["selected_action"],
        "voi": {k: v["recommend_evidence"] for k, v in ep2["meta"]["value_of_information"].items()},
    }
    report["decision_changed"] = (
        ep1["decision"]["selected_action"] != ep2["decision"]["selected_action"]
    )
    report["replay_episode_1"] = machine.replay(ep1["episode_sha256"])
    # Negative transfer: same shape, different domain → untouched prior.
    other = machine.run(voyage_problem(domain="voyage.unrelated", z_state=0.25))
    report["negative_transfer_guard"] = {
        "other_domain_selected": other["decision"]["selected_action"],
        "other_domain_revision": other["identity"]["model_revision"],
        "guard_held": other["identity"]["model_revision"] == 0,
    }
    if custody_factory is None:
        report["restart"] = {"available": False, "reason": "no THESEUS custody bound (UNAVAILABLE)"}
        return report
    restarted = TOEMachine(custody=custody_factory(), stream="voyage")
    ep3 = restarted.run(voyage_problem(z_state=0.25))
    report["restart"] = {
        "available": True,
        "recovered_from": restarted.recovered_from,
        "selected_after_restart": ep3["decision"]["selected_action"],
        "status_after_restart": ep3["status"],
        "model_revision_after_restart": ep3["identity"]["model_revision"],
        "matches_pre_restart_decision": ep3["decision"]["selected_action"]
        == ep2["decision"]["selected_action"],
        "replay_after_restart": restarted.replay(ep1["episode_sha256"]),
    }
    return report


__all__ = [
    "DOMAINS",
    "TRUE_WEIGHTS",
    "VOYAGE_VERSION",
    "canonical_voyage",
    "cross_domain_voyage",
    "simulated_world",
    "voyage_problem",
]
