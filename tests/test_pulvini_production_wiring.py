"""Production boundary tests for opt-in PULVINI solve-first ordering."""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.search_plan import WorkIdentity
from Intelligence.pulvini_runtime import PulviniRuntime


def _identity() -> WorkIdentity:
    return WorkIdentity(
        pool_session_id="pool-session",
        generation=1,
        job_id="job-1",
        job_fingerprint="f" * 64,
        target_generation=1,
        clean_jobs=True,
        received_at=1.0,
    )


def test_active_pulvini_runs_solve_first_and_persists_checkpoint(tmp_path):
    checkpoint = tmp_path / "pulvini.json"
    runtime = PulviniRuntime(checkpoint_path=str(checkpoint))

    result = runtime.solve(
        job_id="job-1",
        worker_state=bytes(range(32)),
        window=32,
        base_nonce=0,
        top_k=32,
    )

    assert result.path_used in {"solve", "F1", "F2", "F3"}
    assert result.candidates
    expected_stages = {
        "S1_fold",
        "S2_checkpoint",
        "S3_gate",
        "S4_regions",
        "S5_fold_levels",
        "S6_ranked",
    }
    assert expected_stages <= set(result.stage_outputs)
    restored, metadata = runtime.memory.restore_checkpoint("job-1")
    assert restored == bytes(range(32))
    assert metadata == {"window": 32, "base": 0}
    assert checkpoint.is_file()


def test_coordinator_projects_structured_candidates_to_complete_m32_lane_order():
    coordinator = IntelligentPoolCoordinator.__new__(IntelligentPoolCoordinator)
    coordinator._solve_first_enabled = True
    coordinator._solve_first_runtime = SimpleNamespace(
        solve=lambda **_kwargs: SimpleNamespace(
            candidates=[37, 1, 37, 66],
            regime="solve",
            path_used="solve",
            stage_outputs={"S6_ranked": 4},
        )
    )
    coordinator._solve_first_outcomes = deque(maxlen=256)
    coordinator._solve_first_error = None
    coordinator._last_solve_first = None
    coordinator._execution_route = lambda: "cpu_reference"

    order, source, evidence = coordinator._solve_first_lane_order(_identity(), 0)

    assert order[:3] == (5, 1, 2)
    assert sorted(order) == list(range(32))
    assert source == "pulvini_solve"
    assert evidence["complete_lane_coverage"] is True
    assert evidence["candidate_lanes"] == 3


def test_unsupported_route_falls_back_without_touching_consensus():
    coordinator = IntelligentPoolCoordinator.__new__(IntelligentPoolCoordinator)
    coordinator._solve_first_enabled = True
    coordinator._last_solve_first = None
    coordinator._execution_route = lambda: "opencl_range"

    assert coordinator._solve_first_lane_order(_identity(), 0) is None
    assert coordinator._last_solve_first["path_used"] == "canonical_fallback"
