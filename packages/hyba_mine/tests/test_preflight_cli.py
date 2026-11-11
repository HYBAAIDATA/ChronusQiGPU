# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Pre-flight blocks mining on any failure; the CLI fails closed."""

import asyncio
import io
import unittest
from contextlib import redirect_stdout

import _support
from _support import TempHome, VerifyingPool

from hyba_mine.bist import run_preflight
from hyba_mine.cli import main as cli_main
from hyba_mine.control import block_pool, grant_approval, update_state
from hyba_mine.igpu import ROUTE_MODE_A, LaneUnavailable
from hyba_mine.ledger import Ledger
from hyba_mine.runtime import EXIT_CONFIG, EXIT_PREFLIGHT


def _no_metal():
    raise LaneUnavailable("no Metal on this test host")


def _preflight(home, pool, **kwargs):
    async def go():
        server = pool or VerifyingPool()
        await server.start()
        try:
            return await asyncio.to_thread(
                run_preflight, home.layout, Ledger(home.layout.ledger, home.layout.ledger_lock), home.store(),
                kwargs.pop("pool_id", "viabtc"), endpoints=(server.endpoint(),), mode_a_workers=1,
                open_metal=kwargs.pop("open_metal", _no_metal), full_window=False, handshake_timeout=5, **kwargs)
        finally:
            await server.stop()

    report = _support.run(go())
    if report.lane is not None:
        report.lane.close()
    return report


def _failed(report) -> list:
    return [check.name for check in report.failures()]


class TestPreflight(unittest.TestCase):
    def test_everything_present_passes_with_an_honest_route(self):
        with TempHome() as home:
            home.put_login("viabtc")
            grant_approval(home.layout)
            report = _preflight(home, None)
            self.assertTrue(report.passed, _failed(report))
            self.assertEqual(report.route.executed, ROUTE_MODE_A)
            self.assertIsNone(report.route.fallback_reason)
            self.assertEqual(report.route.to_dict()["executed_backend"], "igpu")
            self.assertEqual(report.route.to_dict()["preference"], "ours")
            self.assertEqual(report.handshake["first_job_id"], "genesis")
            record = [r for r in Ledger(home.layout.ledger).records() if r["kind"] == "preflight"][-1]
            self.assertTrue(record["data"]["passed"])

    def test_missing_login_blocks_without_contacting_the_pool(self):
        with TempHome() as home:
            grant_approval(home.layout)
            pool = VerifyingPool()
            report = _preflight(home, pool)
            self.assertFalse(report.passed)
            self.assertIn("pool login is stored on this machine", _failed(report))
            self.assertEqual(pool.authorized, 0)
            self.assertIsNone(report.lane)

    def test_missing_approval_blocks_and_skips_the_pool(self):
        with TempHome() as home:
            home.put_login("viabtc")
            pool = VerifyingPool()
            report = _preflight(home, pool)
            self.assertEqual(
                _failed(report),
                ["operator approval for this machine", "Stratum handshake (subscribe, authorize, first job)"],
            )
            self.assertIn("not run", report.checks[-1].detail)
            self.assertEqual(pool.authorized, 0)

    def test_pool_blocked_after_a_rejected_login_blocks(self):
        with TempHome() as home:
            home.put_login("viabtc")
            grant_approval(home.layout)
            block_pool(home.layout, "viabtc", "the pool rejected the login")
            report = _preflight(home, None)
            self.assertIn("pool is not blocked by an earlier login rejection", _failed(report))

    def test_wrong_login_fails_the_handshake_check(self):
        with TempHome() as home:
            home.put_login("viabtc", password="not-what-the-pool-wants")
            grant_approval(home.layout)
            report = _preflight(home, VerifyingPool())
            self.assertIn("Stratum handshake (subscribe, authorize, first job)", _failed(report))
            again = _preflight(home, VerifyingPool())
            self.assertIn("pool is not blocked by an earlier login rejection", _failed(again))
            self.assertIn("not run", again.checks[-1].detail)

    def test_tampered_ledger_blocks(self):
        with TempHome() as home:
            home.put_login("viabtc")
            grant_approval(home.layout)
            ledger = Ledger(home.layout.ledger)
            ledger.append("session_start", {})
            ledger.append("work", {"executed": 1})
            text = home.layout.ledger.read_text().replace('"executed":1', '"executed":2')
            home.layout.ledger.write_text(text)
            report = _preflight(home, None)
            self.assertIn("ledger hash chain verifies", _failed(report))

    def test_offline_preflight_reports_the_handshake_as_not_run(self):
        with TempHome() as home:
            home.put_login("viabtc")
            grant_approval(home.layout)
            report = _preflight(home, None, network=False)
            self.assertEqual(_failed(report), ["Stratum handshake (subscribe, authorize, first job)"])

    def test_requested_metal_without_metal_blocks(self):
        with TempHome() as home:
            home.put_login("viabtc")
            grant_approval(home.layout)
            report = _preflight(home, None, requested_route="metal")
            self.assertIn("Metal lane present", _failed(report))
            self.assertIsNone(report.route)

    def test_pool_outside_the_catalogue_is_refused(self):
        with TempHome() as home:
            report = _preflight(home, None, pool_id="f2pool")
            self.assertEqual(_failed(report), ["pool is in the HYBA Mine catalogue"])


class TestCommandLine(unittest.TestCase):
    def _cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli_main(list(argv))
        return code, out.getvalue()

    def test_start_without_a_login_never_starts_a_session(self):
        with TempHome() as home:
            grant_approval(home.layout)
            update_state(home.layout, active_pool="braiins", credential_store="file", route="mode_a")
            code, out = self._cli("start", "--workers", "1", "--console-port", "0")
            self.assertEqual(code, EXIT_PREFLIGHT)
            self.assertIn("Pre-flight FAILED", out)
            kinds = [r["kind"] for r in Ledger(home.layout.ledger).records()]
            self.assertNotIn("session_start", kinds)
            self.assertNotIn("work", kinds)

    def test_start_without_a_selected_pool_fails_closed(self):
        with TempHome():
            code, out = self._cli("start", "--console-port", "0")
            self.assertEqual(code, EXIT_CONFIG)
            self.assertIn("No pool selected", out)

    def test_pools_status_ledger_and_pool_commands(self):
        with TempHome() as home:
            code, out = self._cli("pools")
            self.assertEqual(code, 0)
            for name in ("viabtc", "braiins", "nicehash", "ckpool", "btc-ssl.viabtc.io:551", "stratum.braiins.com:3333"):
                self.assertIn(name, out)
            code, out = self._cli("status")
            self.assertEqual(code, 0)
            self.assertIn("NO SESSION", out)
            code, out = self._cli("ledger", "verify")
            self.assertEqual(code, 0)
            code, out = self._cli("pool", "use", "nicehash")
            self.assertEqual(code, EXIT_CONFIG)
            home.put_login("nicehash")
            if home.file_permissions:
                update_state(home.layout, credential_store="file")
                code, out = self._cli("pool", "use", "nicehash")
                self.assertEqual(code, 0)
                self.assertIn("next time", out)
            code, out = self._cli("stop")
            self.assertEqual((code, out.strip()), (0, "HYBA Mine is not running."))
            code, out = self._cli("approve", "--yes")
            self.assertEqual(code, 0)
            code, out = self._cli("revoke")
            self.assertIn("revoked", out)


if __name__ == "__main__":
    unittest.main()
