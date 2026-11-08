"""
Behavioral Test Suite: Live Runner Configuration and Network Engine.
Verifies configuration hierarchy, fallback resolution, and engine instantiation without mock servers.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from chronus_live_miner import load_env_config, ChronusRealMiningEngine
from chronus_live_pool_runner import LivePoolRunner


class TestBehavioralLiveRunner(unittest.TestCase):

    def setUp(self):
        self._orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_load_env_config_default_viabtc(self):
        """When no pool is specified, defaults to VIABTC."""
        for key in list(os.environ.keys()):
            if "MINING_" in key or "VIABTC_" in key or "BRAIINS_" in key:
                del os.environ[key]

        pool, host, port, user, password = load_env_config()
        self.assertEqual(pool, "VIABTC")
        self.assertEqual(host, "btc.viabtc.io")
        self.assertEqual(port, 3333)
        self.assertIn("PYTHIA", user)

    def test_load_env_config_braiins_selection(self):
        """When MINING_ACTIVE_POOL is set to BRAIINS, resolves Braiins endpoints."""
        os.environ["MINING_ACTIVE_POOL"] = "BRAIINS"
        os.environ["MINING_BRAIINS_HOST"] = "stratum.braiins.com"
        os.environ["MINING_BRAIINS_PORT"] = "3333"
        os.environ["MINING_BRAIINS_USER"] = "worker.test"
        os.environ["MINING_BRAIINS_PASSWORD"] = "my_pass"

        pool, host, port, user, password = load_env_config()
        self.assertEqual(pool, "BRAIINS")
        self.assertEqual(host, "stratum.braiins.com")
        self.assertEqual(port, 3333)
        self.assertEqual(user, "worker.test")
        self.assertEqual(password, "my_pass")

    def test_engine_initialization_invariants(self):
        """Verifies that the live engine initializes all 5 modules correctly."""
        engine = ChronusRealMiningEngine(
            host="127.0.0.1",
            port=3333,
            user="test_worker",
            password="123",
        )
        self.assertEqual(engine.host, "127.0.0.1")
        self.assertEqual(engine.port, 3333)
        self.assertIsNotNone(engine.gateway)
        self.assertIsNotNone(engine.gatekeeper)
        self.assertIsNotNone(engine.token_bucket)
        self.assertIsNotNone(engine.priority_queue)
        self.assertIsNotNone(engine.partitioner)
        self.assertEqual(engine.token_bucket.rate_per_sec, 15)

    def test_live_pool_runner_initialization(self):
        """Verifies LivePoolRunner binds gateway, gatekeeper, and rate limiter."""
        runner = LivePoolRunner(
            host="127.0.0.1",
            port=3333,
            user="runner_worker",
            password="x",
            stealth_cap=5.0,
        )
        self.assertEqual(runner.stealth_cap, 5.0)
        self.assertEqual(runner.user, "runner_worker")
        self.assertEqual(runner.gateway.host, "127.0.0.1")

    def test_miner_runs_without_max_seconds(self):
        """Asserts that default max_seconds for ChronusRealMiningEngine.run is None (non-terminating)."""
        import inspect
        engine = ChronusRealMiningEngine(
            host="127.0.0.1",
            port=3333,
            user="test_worker",
            password="123",
        )
        sig = inspect.signature(engine.run)
        self.assertIsNone(sig.parameters["max_seconds"].default)


if __name__ == "__main__":
    unittest.main()
