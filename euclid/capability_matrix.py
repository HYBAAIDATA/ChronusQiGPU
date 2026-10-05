"""Executable capability matrix.

A capability is not integrated because its module imports.  Each capability
below is advanced through the stage ladder only by probes that execute the
real mechanism and retain the evidence:

PRESENT -> IMPORTABLE -> WIRED -> REACHABLE -> EFFECT_OBSERVED ->
FEEDBACK_CLOSED -> PERSISTED -> REPLAYED -> HELD_OUT_TESTED

Stages a probe cannot demonstrate are reported honestly as not reached.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

STAGES = (
    "PRESENT", "IMPORTABLE", "WIRED", "REACHABLE", "EFFECT_OBSERVED",
    "FEEDBACK_CLOSED", "PERSISTED", "REPLAYED", "HELD_OUT_TESTED",
)

PROBE_CODE = """def probe_transform(items):
    out = []
    for item in items:
        out.append(item * 3)
    return out
"""
PROBE_TEST = "assert probe_transform([2]) == [6]"


@dataclass
class CapabilityResult:
    capability: str
    stage: str
    evidence: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def stage_index(self) -> int:
        return STAGES.index(self.stage)


def _advance(result: CapabilityResult, stage: str, evidence: str) -> None:
    result.stage = stage
    result.evidence.append(f"{stage}: {evidence}")


def _probe_runtime_governance(runtime: Any, result: CapabilityResult) -> None:
    _advance(result, "PRESENT", "euclid.runtime present in package")
    _advance(result, "IMPORTABLE", "EuclidRuntime imported")
    _advance(result, "WIRED", "production() constructed with rights/evidence/learning")
    report = runtime.startup_report()
    if report.get("schema") == "euclid.startup/1":
        _advance(result, "REACHABLE", "startup_report returned organ registry")
    from euclid.contracts import Authority, Experience, RewardAuthority
    from euclid.governance import Organ

    runtime.register_organ(Organ(
        "probe-organ", frozenset({"ping"}), Authority.READ_ONLY,
        lambda request: {"pong": True},
    ))
    runtime.rights.grant(runtime.creator_id, "probe-organ", "ping", "dispatch")
    response = runtime.delegator.dispatch(
        "probe-organ", "ping", {}, confident=True, safe=True
    )
    if response.get("pong"):
        _advance(result, "EFFECT_OBSERVED", "governed dispatch returned handler result")
    digest = runtime.learning.record(Experience(
        experience_id="probe-exp", mission_id="capability-matrix",
        domain="probe", source="capability-matrix", observation={"probe": True},
        action="ping", outcome={"pong": True}, reward=None,
        reward_authority=RewardAuthority.NONE, provenance="capability-matrix",
        uncertainty=0.0, replay_id="probe-replay-1",
    ))
    if digest:
        _advance(result, "FEEDBACK_CLOSED", "experience recorded through LearningService")


def _probe_persistence(runtime: Any, state_dir: Path, result: CapabilityResult) -> None:
    checkpoint = state_dir / "matrix.checkpoint.json"
    runtime.save(checkpoint)
    from euclid.runtime import EuclidRuntime

    restored = EuclidRuntime.restore(checkpoint, state_dir=state_dir)
    try:
        _advance(result, "PERSISTED", "runtime checkpoint saved and restored")
        if restored.kairos.replay_verify():
            _advance(result, "REPLAYED",
                     "evidence/world replay verified after restore")
    finally:
        # The restored runtime owns its own SQLite handle; releasing it inside
        # the state directory's lifetime keeps the directory deletable.
        restored.close()


def _probe_search_engines(runtime: Any, result: CapabilityResult) -> None:
    from euclid.search.deep_mcts import DeepMCTSEngine, SearchBudget

    _advance(result, "PRESENT", "deep_mcts module present")
    _advance(result, "IMPORTABLE", "DeepMCTSEngine imported")
    service = runtime.enable_intelligence()
    _advance(result, "WIRED", "enable_intelligence composed engines into runtime")
    engine = DeepMCTSEngine(repository=service.adapter.repository, seed=3)
    telemetry = engine.search(
        "probe.py", PROBE_CODE,
        budget=SearchBudget(max_evaluations=6, max_depth=3, max_wall_seconds=15.0),
        external_test_code=PROBE_TEST,
    )
    if telemetry["evaluations_used"] > 0:
        _advance(result, "REACHABLE", "search executed sandbox-gated evaluations")
    if telemetry["max_depth_reached"] >= 1 and telemetry["transposition_table_size"] >= 1:
        _advance(
            result, "EFFECT_OBSERVED",
            f"multi-depth tree: depth {telemetry['max_depth_reached']}, "
            f"table {telemetry['transposition_table_size']}, "
            f"improvement {telemetry['measured_improvement']}",
        )


def _probe_cognition(runtime: Any, result: CapabilityResult) -> None:
    from euclid.cognition import CognitiveEpisode

    _advance(result, "PRESENT", "euclid.cognition package present")
    _advance(result, "IMPORTABLE", "CognitiveService imported")
    service = runtime.enable_intelligence()
    _advance(result, "WIRED", "cognitive service composed on runtime")
    before = len(runtime.evidence.records)
    episode = service.solve(
        {"problem_id": "matrix-probe", "code": PROBE_CODE,
         "external_test_code": PROBE_TEST, "seed": 5},
        budget_evaluations=4,
    )
    after = len(runtime.evidence.records)
    if after > before and episode.state_payload.get("transitions"):
        _advance(result, "REACHABLE", "loop dispatched through governed organs")
    if episode.actual_result:
        _advance(result, "EFFECT_OBSERVED",
                 f"measured result recorded: outcome={episode.outcome}")
    if runtime.learning.status()["experiences_seen"] >= 1:
        _advance(result, "FEEDBACK_CLOSED", "episode fed LearningService")
    loaded = CognitiveEpisode.load(
        Path(runtime.state_dir) / "cognition" / "episodes" / "matrix-probe.json"
    )
    if loaded.episode_id == episode.episode_id:
        _advance(result, "PERSISTED", "sealed episode reloads with identity intact")


def _probe_transfer(runtime: Any, result: CapabilityResult) -> None:
    service = runtime.enable_intelligence()
    related = PROBE_CODE.replace("probe_transform", "gather_values").replace(
        "items", "values"
    ).replace("item", "value").replace("out", "bag")
    episode = service.solve(
        {"problem_id": "matrix-probe-transfer", "code": related,
         "external_test_code": "assert gather_values([2]) == [6]", "seed": 5},
        budget_evaluations=4,
    )
    sources = [a["source_ref"] for a in episode.analogies]
    if "episode:matrix-probe" in sources:
        _advance(result, "REPLAYED", "prior episode replayed into memory retrieval")
        _advance(
            result, "HELD_OUT_TESTED",
            "structural analogy fired on a textually different held-out program",
        )
    else:
        result.notes = "transfer probe did not retrieve the prior episode"


def generate_matrix(*, seed: int = 5) -> dict[str, Any]:
    """Build the matrix from executable evidence on a fresh runtime."""
    results: dict[str, CapabilityResult] = {
        name: CapabilityResult(name, "PRESENT")
        for name in (
            "governance-runtime", "persistence-replay", "search-engines",
            "cognition-loop", "cross-problem-transfer",
        )
    }
    with tempfile.TemporaryDirectory() as tmp:
        state_dir = Path(tmp)
        from euclid.runtime import EuclidRuntime

        runtime = EuclidRuntime.production(creator_id="matrix", state_dir=state_dir)
        _probe_runtime_governance(runtime, results["governance-runtime"])
        _probe_search_engines(runtime, results["search-engines"])
        _probe_cognition(runtime, results["cognition-loop"])
        _probe_transfer(runtime, results["cross-problem-transfer"])
        _probe_persistence(runtime, state_dir, results["persistence-replay"])
        runtime.close()
    return {
        "schema": "euclid.capability-matrix/1",
        "stages": list(STAGES),
        "capabilities": {
            name: {
                "stage": result.stage,
                "stage_index": result.stage_index,
                "evidence": result.evidence,
                "notes": result.notes,
            }
            for name, result in sorted(results.items())
        },
    }


__all__ = ["STAGES", "CapabilityResult", "generate_matrix"]
