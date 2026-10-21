"""Synthetic per-domain technical gates, never domain-expert sign-off."""
import copy
import json
from pathlib import Path
import random
import pytest
from toe.adapters import TabularAdapter
from toe.machine import TOEMachine
from toe.problem import Problem, Structure

PACKS = Path(__file__).resolve().parents[1] / "toe/adapters/qualification"


@pytest.mark.parametrize("path", sorted(PACKS.glob("*.json")), ids=lambda p: p.stem)
def test_each_domain_on_same_backend(path):
    pack = json.loads(path.read_text())
    rng = random.Random(pack["seed"])
    slope = pack["planted_effect"]
    rows = []
    for _ in range(600):
        context = rng.gauss(0, 1)
        driver = 2 * context + rng.gauss(0, 0.4)
        outcome = slope * driver + 3 * context + rng.gauss(0, 0.1)
        rows.append(dict(context=context, driver=driver, outcome=outcome))
    fixture = dict(domain=pack["domain"], rows=rows,
                   relations=[["context", "driver"], ["context", "outcome"], ["driver", "outcome"]],
                   current=dict(context=0.0, driver=1.0, outcome=0.0),
                   levers={"driver": [0.0, 1.0, 2.0]}, goal={"maximize": "outcome"},
                   question=["driver", "outcome"])
    adapter = TabularAdapter()
    machine = TOEMachine()
    episode = machine.run(adapter.to_problem(fixture))
    estimate = episode["identity"]["estimated_from_samples"]["driver->outcome"]
    assert abs(estimate["estimate"] - slope) < max(0.03, 4 * estimate["standard_error"])
    # Negative control: hidden confounding must refuse causal release.
    negative = Problem(domain=pack["domain"],
                       structure=Structure.of([("u", "x", 1.), ("u", "y", 1.), ("x", "y", 1.)], latent=["u"]),
                       samples={"x": [float(i % 7) for i in range(40)], "y": [float(i % 5) for i in range(40)]},
                       query=("x", "y"))
    refused = machine.run(negative)
    assert refused["understanding"]["relationships"]["effect_released"] is False
    # Drift: a separate evaluation instance fits a reversed planted relation.
    # This verifies sensitivity, not a deployed online alerting or regulated workflow.
    drift = copy.deepcopy(fixture)
    for row in drift["rows"]:
        row["outcome"] -= 2 * slope * row["driver"]
    shifted = TOEMachine().run(adapter.to_problem(drift))
    new = shifted["identity"]["estimated_from_samples"]["driver->outcome"]["estimate"]
    assert new * estimate["estimate"] < 0
    assert pack["human_signoff"]["status"] == "PENDING"
    assert pack["production_ready"] is False
