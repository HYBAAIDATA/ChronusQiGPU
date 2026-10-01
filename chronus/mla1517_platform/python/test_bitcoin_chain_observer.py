"""Bitcoin chain-observer safety: network distinction and URL rules.

The observer must report which chain the configured node is actually on,
fail closed when the operator declares a different network, and refuse
unsafe URL/credential forms.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from chronus.mla1517.mining.chain_observer import BitcoinChainObserver


class FakeObserver(BitcoinChainObserver):
    def __init__(self, chain: str) -> None:
        self._chain = chain
        self.calls: list[str] = []

    def _call(self, method: str, params: list) -> object:
        self.calls.append(method)
        if method == "getblockchaininfo":
            return {"chain": self._chain, "blocks": 1}
        raise AssertionError(f"unexpected RPC call {method}")


class ChainNamingTests(unittest.TestCase):
    def test_chain_reports_the_nodes_network(self) -> None:
        obs = FakeObserver("signet")
        self.assertEqual(obs.chain(), "signet")
        self.assertEqual(obs.calls, ["getblockchaininfo"])

    def test_assert_chain_passes_on_match(self) -> None:
        FakeObserver("main").assert_chain("main")

    def test_assert_chain_fails_closed_on_mismatch(self) -> None:
        obs = FakeObserver("regtest")
        with self.assertRaises(RuntimeError) as ctx:
            obs.assert_chain("main")
        self.assertIn("regtest", str(ctx.exception))
        self.assertIn("PYTHIA_BITCOIN_NETWORK", str(ctx.exception))


class UrlRuleTests(unittest.TestCase):
    def test_remote_http_refused(self) -> None:
        with self.assertRaises(ValueError):
            BitcoinChainObserver("http://192.0.2.1:8332")

    def test_credentials_in_url_refused(self) -> None:
        with self.assertRaises(ValueError):
            BitcoinChainObserver("https://user:pass@node.example:8332")

    def test_from_environment_uses_cookie_file(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".cookie", delete=False) as f:
            f.write("alice:secret")
            cookie = f.name
        try:
            env = {
                "PYTHIA_BITCOIN_RPC_URL": "http://127.0.0.1:8332",
                "PYTHIA_BITCOIN_RPC_COOKIE": cookie,
            }
            with patch.dict(os.environ, env):
                obs = BitcoinChainObserver.from_environment()
            self.assertIsNotNone(obs)
            self.assertEqual(obs.credentials, "alice:secret")  # type: ignore[union-attr]
        finally:
            os.unlink(cookie)

    def test_from_environment_absent(self) -> None:
        env = {"PYTHIA_BITCOIN_RPC_URL": "", "PYTHIA_BITCOIN_RPC_AUTH": ""}
        with patch.dict(os.environ, env):
            self.assertIsNone(BitcoinChainObserver.from_environment())


class StartupValidationTests(unittest.TestCase):
    def test_network_declared_without_rpc_url_fails_startup(self) -> None:
        import mining_runtime

        with patch.dict(os.environ, {"PYTHIA_BITCOIN_NETWORK": "main"}):
            with self.assertRaises(SystemExit) as ctx:
                mining_runtime.assert_declared_chain(None)
        self.assertIn("PYTHIA_BITCOIN_RPC_URL", str(ctx.exception))

    def test_network_mismatch_fails_startup(self) -> None:
        import mining_runtime

        env = {"PYTHIA_BITCOIN_NETWORK": "main"}
        with patch.dict(os.environ, env):
            with self.assertRaises(SystemExit) as ctx:
                mining_runtime.assert_declared_chain(FakeObserver("test"))
        self.assertIn("test", str(ctx.exception))

    def test_matching_network_is_silent(self) -> None:
        import mining_runtime

        with patch.dict(os.environ, {"PYTHIA_BITCOIN_NETWORK": "signet"}):
            mining_runtime.assert_declared_chain(FakeObserver("signet"))

    def test_unset_network_makes_no_rpc_call(self) -> None:
        import mining_runtime

        env = {"PYTHIA_BITCOIN_NETWORK": ""}
        with patch.dict(os.environ, env):
            mining_runtime.assert_declared_chain(FakeObserver("main"))


if __name__ == "__main__":
    unittest.main()
