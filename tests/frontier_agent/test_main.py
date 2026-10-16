import pytest
from dataclasses import replace
from chronus.agent.main import frontier_main
from chronus.agent.control import StoppingCondition as Stop


def test_main_has_no_unbudgeted_retry(wired):
    r, o, c, p, a = wired
    a.fail = True
    out = frontier_main(r, o, c, replace(p, policy=replace(p.policy, max_iterations=1)))
    assert out.iterations == 1 and a.executions == 1
    assert out.stop == Stop.BUDGET_EXHAUSTED


def test_actual_registry_body_binds_one_retained_runtime(wired):
    # Execute the complete actual registry module, not extracted methods or a
    # replacement registry. Full Intelligence package init is a separate gate.
    import importlib.util
    import sys
    from pathlib import Path

    name = "euclid_frontier_registry_contract"
    spec = importlib.util.spec_from_file_location(name, Path("Intelligence/registry.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        reg = module.ModuleRegistry()
        entry = reg.register(
            "euclid_frontier_agent", "chronus.agent", "unit host binding", ["governed_tasks"]
        )
        assert entry.loaded and entry.instantiate() is None
        r, o, c, p, a = wired
        with pytest.raises(RuntimeError):
            reg.run_frontier_task(o, c, p)
        reg.configure_frontier_agent(r)
        assert reg.instantiate_all()["euclid_frontier_agent"] is r
        out = reg.run_frontier_task(o, c, p)
        assert out.stop == Stop.GOAL_ACHIEVED and a.path.read_text() == "after"
    finally:
        sys.modules.pop(name, None)
