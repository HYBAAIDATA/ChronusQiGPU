"""Regression tests for the remaining PYTHAGORAS v12 roadmap gaps."""

from __future__ import annotations

from pythagoras.geometry_evolution import GeometryEvolution
from pythagoras.meta_evolution import MetaEvolutionController
from pythagoras.orchestrator import Pythagoras, run_isolated_execution


def test_isolated_execution_enforces_real_subprocess_timeout():
    ok, reason = run_isolated_execution("while True: pass\n", timeout_seconds=0.1)
    assert ok is False
    assert "timeout" in reason


def test_annealing_is_deterministic_when_seeded():
    left = MetaEvolutionController(random_seed=7, initial_temperature=1.0)
    right = MetaEvolutionController(random_seed=7, initial_temperature=1.0)
    left.in_annealing_mode = True
    right.in_annealing_mode = True
    assert [left.should_accept(-0.2) for _ in range(10)] == [
        right.should_accept(-0.2) for _ in range(10)
    ]


def test_provenance_is_hash_chained():
    meta = MetaEvolutionController()
    meta.update(1, [0.5, 0.6], {"ADD:AnnAssign": 0.1}, file_id="a.py")
    meta.update(2, [0.6, 0.7], {"REFACTOR:Split": 0.1}, file_id="b.py")
    assert meta.provenance_log[0]["previous_hash"] == "GENESIS"
    assert (
        meta.provenance_log[1]["previous_hash"]
        == meta.provenance_log[0]["event_hash"]
    )


def test_session_restores_full_meta_and_geometry_state(tmp_path):
    state = tmp_path / "session.json"
    original = Pythagoras(condition="B")
    original.meta.mutation_rate = 0.33
    original.meta.stall_count = 4
    original.geometry.load_state({"n_cols": 20, "levels_back": 7, "pop_size": 80})
    original.save_session(state)

    restored = Pythagoras(condition="B")
    restored.load_session(state)
    assert restored.meta.mutation_rate == 0.33
    assert restored.meta.stall_count == 4
    assert restored.geometry.get_state() == {
        "n_cols": 20,
        "levels_back": 7,
        "pop_size": 80,
    }
    assert restored.cgp.n_cols == 20
    assert restored.cgp.levels_back == 7
    assert restored.cgp.pop_size == 80


def test_collective_geometry_consensus_is_applied():
    engine = Pythagoras(condition="B")
    consensus = GeometryEvolution.compute_consensus(
        [
            {"n_cols": 10, "levels_back": 3, "pop_size": 40},
            {"n_cols": 18, "levels_back": 7, "pop_size": 80},
            {"n_cols": 14, "levels_back": 5, "pop_size": 60},
        ]
    )
    engine.geometry.load_state(consensus)
    assert engine.geometry.get_state() == {
        "n_cols": 14,
        "levels_back": 5,
        "pop_size": 60,
    }