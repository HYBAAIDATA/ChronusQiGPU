"""Regression coverage for candidate sharing and chooser fault recovery."""

import multiprocessing

import pytest

from python_backend.phi_grover_v4 import bus_broadcast, bus_read, bus_solve, make_bus
from python_backend.pythia_mining.intelligence_chooser import MiningIntelligenceChooser


def _publish_candidate(bus, started, finished):
    started.set()
    bus_broadcast(bus, 3, 2**32 - 1, 0.9, 4.5, 3)
    finished.set()


def test_candidate_update_uses_shared_lock():
    ctx = multiprocessing.get_context("spawn")
    with ctx.Manager() as manager:
        bus = make_bus(manager)
        started, finished = ctx.Event(), ctx.Event()
        worker = ctx.Process(target=_publish_candidate, args=(bus, started, finished))
        try:
            with bus["lock"]:
                worker.start()
                assert started.wait(10)
                assert not finished.wait(0.2)
                assert bus["best_r"].value == 0.0
            assert finished.wait(10)
            worker.join(10)
            assert worker.exitcode == 0
            assert bus_read(bus) == (0.9, 2**32 - 1, 3)
            assert bus["best_S"].value == 4.5

            # A later, weaker candidate cannot replace any part of the winner.
            bus_broadcast(bus, 4, 12, 0.8, 2.5, 4)
            assert bus_read(bus) == (0.9, 2**32 - 1, 3)
            assert bus["best_S"].value == 4.5
            assert bus["warrior_r"][4] == 0.8
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(10)


@pytest.mark.parametrize("nonce", [0, 2**31, 2**32 - 1])
def test_solution_preserves_unsigned_nonce_range(nonce):
    with multiprocessing.Manager() as manager:
        bus = make_bus(manager)
        bus_solve(bus, nonce)
        assert bus["found"].value == 1
        assert bus["solution"].value == nonce
        bus_solve(bus, (nonce + 1) % 2**32)
        assert bus["solution"].value == nonce


@pytest.mark.parametrize("nonce", [-1, 2**32, 2**64 - 1, True, 0.5])
def test_solution_rejects_non_bitcoin_nonce(nonce):
    with multiprocessing.Manager() as manager:
        bus = make_bus(manager)
        with pytest.raises(ValueError):
            bus_solve(bus, nonce)
        assert bus["found"].value == 0


@pytest.mark.parametrize(
    "has_job,job_stale", [(True, False), (True, True), (False, False), (False, True)]
)
@pytest.mark.parametrize("search_label", ["quantum_lucas", "custom_search", None])
def test_chooser_fault_preserves_search_contract(monkeypatch, has_job, job_stale, search_label):
    chooser = MiningIntelligenceChooser()
    normal = chooser.choose(
        has_job=has_job, error_count=0, job_stale=job_stale, search_label=search_label
    )

    def fail(**kwargs):
        raise RuntimeError("decision unavailable")

    monkeypatch.setattr(chooser, "_choose_impl", fail)
    fallback = chooser.choose(
        has_job=has_job, error_count=0, job_stale=job_stale, search_label=search_label
    )
    assert fallback["search"] == normal["search"]
    assert fallback["search"] == (search_label if has_job and not job_stale else None)
    assert fallback["proof"] == "sha256d"
    assert fallback["throttle"] is True
    assert fallback["degraded"] is True
