"""Honesty-contract regressions: refactored agi compute paths must be
deterministic, return real measured keys, and never emit canned payloads."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agi.simulations import BayesianMCMC, MonteCarloSimulation


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestMonteCarloDeterminism:
    MODEL = {
        "type": "general",
        "variables": {"x": {"mean": 1.0, "std": 0.5}},
        "distributions": {"x": "normal"},
    }

    def test_reproducible(self):
        a = run(MonteCarloSimulation().simulate(self.MODEL, 200))
        b = run(MonteCarloSimulation().simulate(self.MODEL, 200))
        assert a["success"] and b["success"]
        assert a["results"] == b["results"]

    def test_mean_matches_distribution(self):
        r = run(MonteCarloSimulation().simulate(self.MODEL, 4001))
        assert r["success"]
        stats = r["results"].get("statistics") or r["results"]
        assert abs(stats.get("mean", r["results"].get("mean", 0.0)) - 1.0) < 0.1


class TestExactPosterior:
    def test_posterior_mean_sensible(self):
        data = [1.9, 2.0, 2.1, 2.05, 1.95, 2.1, 1.98, 2.03]
        model = {
            "parameters": {"mean": 2.0, "std": 0.2},
            "priors": {"mean": {"mu": 0.0, "sigma": 5.0}},
        }
        r = run(BayesianMCMC().analyze(data, model, 1000))
        assert r["success"]
        results = r["results"]
        # Posterior mean should shrink the MLE (~2.0) toward the prior (0).
        post = results["posterior_means"]["mean"]
        assert 1.0 < post < 2.1

    def test_deterministic(self):
        data = [1.0, 1.1, 0.9]
        model = {
            "parameters": {"mean": 1.0, "std": 0.3},
            "priors": {"mean": {"mu": 0.0, "sigma": 2.0}},
        }
        a = run(BayesianMCMC().analyze(data, model, 500))
        b = run(BayesianMCMC().analyze(data, model, 500))
        assert a["results"] == b["results"]


class TestNoRNGAnywhere:
    """Zero np.random / random. / statistics. call sites in agi modules."""

    BANNED_ATTR_ROOTS = {"random", "statistics"}
    BANNED_NUMPY_ATTR = "random"

    def test_no_rng_call_sites(self):
        import ast

        agi_dir = Path(__file__).resolve().parents[1]
        offenders = []
        for py in agi_dir.rglob("*.py"):
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    if node.value.id in self.BANNED_ATTR_ROOTS:
                        offenders.append(f"{py.name}:{node.lineno} {node.value.id}.{node.attr}")
                    if node.value.id == "np" and node.attr == self.BANNED_NUMPY_ATTR:
                        offenders.append(f"{py.name}:{node.lineno} np.random")
        assert offenders == []
