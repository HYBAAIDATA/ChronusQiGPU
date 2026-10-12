"""Offline configuration checks; no real credentials or service startup."""

import json
import unittest

from scripts.runtime_environment_preflight import KEYS, REQUIRED, evaluate


class RuntimeEnvironmentPreflightTests(unittest.TestCase):
    def env(self):
        env = {name: "fixture-value" for name in REQUIRED}
        for name in KEYS:
            env[name] = "ab" * 32
        env.update(
            {
                "MLA1517_STRATUM_USER": "PYTHIA.001",
                "MLA1517_VIABTC_USER": "PYTHIA.001",
                "MLA1517_BRAIINS_USER": "PYTHAGOROS.PYTHIA.002",
                "PYTHIA_STORAGE_DB": "/persist/mining.db",
                "PYTHIA_STORAGE_ROOT": "/persist/cas",
                "PYTHIA_STORAGE_CUSTODY_ROOT": "/persist/custody",
                "PYTHIA_POOLS": "viabtc,braiins",
                "PYTHIA_POOL_PROFILE": "viabtc",
                "PYTHIA_M3_REQUIRED": "1",
                "PYTHIA_AUTOSTART_WORKERS": "0",
            }
        )
        return env

    def test_configured_is_not_live_evidence(self):
        report = evaluate(self.env())
        self.assertEqual(report["state"], "CONFIGURED")
        self.assertFalse(report["network_attempted"])
        self.assertFalse(report["mining_started"])

    def test_every_required_value_blocks_when_missing(self):
        for name in REQUIRED:
            with self.subTest(name=name):
                env = self.env()
                del env[name]
                self.assertEqual(evaluate(env)["state"], "BLOCKED")

    def test_no_values_in_report(self):
        report = json.dumps(evaluate(self.env()))
        for value in ("fixture-value", "PYTHIA.001", "ab" * 32, "/persist/mining.db"):
            self.assertNotIn(value, report)

    def test_placeholder_and_whitespace_identity_fail(self):
        for value in ("account.worker", "bad worker"):
            env = self.env()
            env["MLA1517_BRAIINS_USER"] = value
            self.assertEqual(evaluate(env)["state"], "BLOCKED")

    def test_primary_identity_and_password_must_match(self):
        for name in ("MLA1517_STRATUM_USER", "MLA1517_STRATUM_PASSWORD"):
            env = self.env()
            env[name] = "different.value"
            self.assertEqual(evaluate(env)["state"], "BLOCKED")

    def test_integrity_keys_are_validated(self):
        for name in KEYS:
            for value in ("zz" * 32, "ab" * 16):
                env = self.env()
                env[name] = value
                self.assertEqual(evaluate(env)["state"], "BLOCKED")

    def test_relative_storage_paths_fail(self):
        env = self.env()
        env["PYTHIA_STORAGE_DB"] = "mining.db"
        self.assertEqual(evaluate(env)["state"], "BLOCKED")

    def test_autostart_and_missing_m3_fail(self):
        for name in ("PYTHIA_AUTOSTART_WORKERS", "PYTHIA_M3_REQUIRED"):
            env = self.env()
            env[name] = "unexpected"
            self.assertEqual(evaluate(env)["state"], "BLOCKED")

    def test_external_phylaxis_settings_are_not_claimed_as_wired(self):
        env = self.env()
        env["PHYLAXIS_DB_HOST"] = "fixture-host"
        self.assertEqual(evaluate(env)["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
