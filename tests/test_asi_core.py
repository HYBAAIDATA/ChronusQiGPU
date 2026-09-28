"""ASI orchestration contract: the composition root must report honestly.

Every assertion here corresponds to behaviour implemented in
``asi/asi_core.py``. The point of this file is to *prove* the claims rather
than assert them in a docstring:

- ``ASICore`` composes the five real substrates.
- ``capability_report`` never reports a capability as available unless its
  probe method exists AND ran without raising.
- The two unbounded background loops are scheduled, awaited to their first
  suspension, and fully torn down — no leaked tasks.
"""

import asyncio

from asi.asi_core import ASI_CAPABILITIES, ASICore


def _make_core(**overrides):
    """Build an ASICore, optionally injecting stub substrates."""
    return ASICore(**overrides)


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------


def test_capability_surface_is_the_five_declared_capabilities():
    core = _make_core()
    assert core.capabilities == list(ASI_CAPABILITIES)
    assert set(ASI_CAPABILITIES) == {
        "self_healing",
        "novel_problem_solving",
        "quantum_algorithm_creation",
        "continuous_learning",
        "system_optimization",
    }


def test_every_capability_resolves_to_a_real_substrate():
    core = _make_core()
    for name in ASI_CAPABILITIES:
        assert core.component(name) is not None, name


def test_unknown_capability_returns_none():
    core = _make_core()
    assert core.component("no_such_capability") is None


def test_singletons_are_shared_and_per_instance_substr_are_not():
    a = _make_core()
    b = _make_core()
    # The three that expose get_* factories are process-wide singletons.
    assert a.problem_solver is b.problem_solver
    assert a.quantum_creator is b.quantum_creator
    assert a.web_learner is b.web_learner
    # These two carry per-instance state and are built fresh.
    assert a.self_healing is not b.self_healing
    assert a.system_optimizer is not b.system_optimizer


def test_injected_substrates_are_used_verbatim():
    sentinel = object()
    core = _make_core(system_optimizer=sentinel)
    assert core.component("system_optimization") is sentinel


# --------------------------------------------------------------------------
# capability_report: the honesty contract
# --------------------------------------------------------------------------


def test_report_marks_every_declared_capability_present():
    report = _make_core().capability_report()
    for name in ASI_CAPABILITIES:
        assert report[name]["available"] is True, (name, report[name])


def test_report_actually_executes_the_probes():
    """``statistics`` must be present — proving the probe really ran."""
    report = _make_core().capability_report()
    for name in ASI_CAPABILITIES:
        assert "statistics" in report[name], name


# --------------------------------------------------------------------------
# Background loop lifecycle
# --------------------------------------------------------------------------


class _CountingLoop:
    """A background loop that records how many times it was entered."""

    def __init__(self):
        self.entered = 0
        self.stopped = False
        self.active = False

    async def _run(self):
        self.entered += 1
        self.active = True
        try:
            while not self.stopped:
                await asyncio.sleep(0)
        finally:
            self.active = False

    async def start_monitoring(self):
        await self._run()

    def stop_monitoring(self):
        self.stopped = True

    async def start(self):
        await self._run()

    def stop(self):
        self.stopped = True


def test_start_schedules_both_loops_without_deadlocking():
    async def scenario():
        healing = _CountingLoop()
        learner = _CountingLoop()
        core = _make_core(self_healing=healing, web_learner=learner)

        assert await asyncio.wait_for(core.start(), timeout=2.0) is True
        assert core.running is True
        assert set(core.background_tasks) == {"self_healing", "continuous_learning"}
        # Both loops were actually entered, not merely scheduled.
        assert healing.entered == 1
        assert learner.entered == 1
        return await asyncio.wait_for(core.stop(), timeout=2.0)

    assert asyncio.run(scenario()) is True


def test_stop_tears_down_every_task_and_leaves_none_running():
    async def scenario():
        healing = _CountingLoop()
        learner = _CountingLoop()
        core = _make_core(self_healing=healing, web_learner=learner)
        await core.start()
        assert await core.stop() is True

        assert core.background_tasks == {}
        assert core.running is False
        # The loops observed their stop signal and exited.
        assert healing.active is False
        assert learner.active is False
        # No task objects survive the teardown.
        leftover = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        assert leftover == []

    asyncio.run(scenario())


def test_stop_is_idempotent_and_safe_without_start():
    core = _make_core()
    assert asyncio.run(core.stop()) is True


def test_double_start_does_not_duplicate_tasks():
    async def scenario():
        healing = _CountingLoop()
        learner = _CountingLoop()
        core = _make_core(self_healing=healing, web_learner=learner)
        assert await core.start() is True
        assert await core.start() is True  # second call is a no-op
        assert len(core.background_tasks) == 2
        assert healing.entered == 1
        await core.stop()

    asyncio.run(scenario())


def test_missing_loop_entry_point_fails_closed():
    class NoStart:
        def stop_monitoring(self):
            pass

    async def scenario():
        core = _make_core(self_healing=NoStart())
        # start() must not report success when a loop cannot be scheduled.
        assert await core.start() is False
        await core.stop()

    asyncio.run(scenario())


def test_missing_probe_method_is_reported_unavailable_not_skipped():
    class NoProbe:
        """Stands in for a substrate missing its statistics method."""

    core = _make_core(system_optimizer=NoProbe())
    entry = core.capability_report()["system_optimization"]
    assert entry["available"] is False
    assert "no callable analyze_system()" in entry["reason"]
    # Crucially, no statistics key: nothing was invented.
    assert "statistics" not in entry


def test_raising_probe_is_downgraded_to_unavailable():
    class Exploding:
        def analyze_system(self):
            raise RuntimeError("substrate offline")

    core = _make_core(system_optimizer=Exploding())
    entry = core.capability_report()["system_optimization"]
    assert entry["available"] is False
    assert "analyze_system() raised RuntimeError" in entry["reason"]


def test_report_reflects_not_running_before_start():
    assert _make_core().capability_report()["running"] is False
