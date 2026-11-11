# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Pool logins stay on the machine: stores, redaction, and no leak into logs, ledger or repo."""

import asyncio
import io
import json
import logging
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path

import _support
from _support import PACKAGE_ROOT, REPO_ROOT, SENTINEL_PASSWORD, SENTINEL_USER, TempHome, VerifyingPool

from chronus.execution.elevation import Route

from hyba_mine.bist import run_preflight
from hyba_mine.cli import main as cli_main
from hyba_mine.control import grant_approval
from hyba_mine.credentials import (
    CredentialMissing,
    CredentialStoreError,
    FileStore,
    KeychainStore,
    PoolLogin,
    make_login,
    require_login,
)
from hyba_mine.dispatch import LocalIGPUDispatcher
from hyba_mine.igpu import ROUTE_MODE_A, LaneUnavailable, ModeALane
from hyba_mine.ledger import Ledger
from hyba_mine.logsafe import SECRETS, configure_logging, login_fingerprint
from hyba_mine.plan import PythiaItinerary, UnitSpec
from hyba_mine.runtime import MinerRuntime, RuntimeOptions
from hyba_mine.status import render_text, summarize

FAKE_SECURITY = r'''
import json, os, sys
path = os.environ["FAKE_KEYCHAIN"]
items = json.load(open(path)) if os.path.exists(path) else {}
args = sys.argv[1:]
def opt(flag):
    return args[args.index(flag) + 1]
key = opt("-s") + "/" + opt("-a")
if args[0] == "add-generic-password":
    items[key] = opt("-w")
    json.dump(items, open(path, "w"))
elif args[0] == "find-generic-password":
    if key not in items:
        sys.exit(44)
    print(items[key])
elif args[0] == "delete-generic-password":
    if items.pop(key, None) is None:
        sys.exit(44)
    json.dump(items, open(path, "w"))
'''


class TestStores(unittest.TestCase):
    def test_keychain_store_round_trip_through_the_security_tool(self):
        with TempHome() as home:
            script = home.root / "fake_security.py"
            script.write_text(FAKE_SECURITY)
            os.environ["FAKE_KEYCHAIN"] = str(home.root / "keychain.json")
            try:
                store = KeychainStore(command=(sys.executable, str(script)))
                login = make_login("viabtc", SENTINEL_USER, SENTINEL_PASSWORD)
                self.assertIsNone(store.get("viabtc"))
                store.put("viabtc", login)
                self.assertEqual(store.get("viabtc"), login)
                stored = json.loads((home.root / "keychain.json").read_text())
                self.assertEqual(list(stored), ["HYBA-Mine/pool:viabtc"])
                self.assertTrue(store.delete("viabtc"))
                self.assertFalse(store.delete("viabtc"))
            finally:
                os.environ.pop("FAKE_KEYCHAIN", None)

    def test_missing_security_tool_is_reported(self):
        with self.assertRaises(CredentialStoreError):
            KeychainStore(command=("/nonexistent/security",))

    def test_file_store_is_private_and_refused_inside_a_repository(self):
        with TempHome() as home:
            if not home.file_permissions:
                self.skipTest("this test filesystem ignores chmod; covered on macOS and CI")
            store = FileStore(home.layout.credentials)
            store.put("braiins", PoolLogin(SENTINEL_USER, SENTINEL_PASSWORD))
            self.assertEqual(home.layout.credentials.stat().st_mode & 0o777, 0o600)
            os.chmod(home.layout.credentials, 0o644)
            with self.assertRaises(CredentialStoreError):
                store.get("braiins")
        repo = Path(tempfile.mkdtemp(prefix="hyba-mine-repo-"))
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        (repo / ".git").mkdir()
        with self.assertRaises(ValueError):
            FileStore(repo / "nested" / "credentials.json")

    def test_require_login_fails_closed_and_logins_are_validated(self):
        with TempHome() as home:
            with self.assertRaises(CredentialMissing):
                require_login(home.store(), "nicehash")
        for bad in ("", "no worker", "a.b c", "x" * 200):
            with self.assertRaises(ValueError):
                make_login("viabtc", bad, "x")
        with self.assertRaises(ValueError):
            make_login("viabtc", "hyba.macbook", "line\nbreak")
        with self.assertRaises(ValueError):
            make_login("f2pool", "hyba.macbook", "x")

    def test_login_repr_reveals_neither_field(self):
        login = PoolLogin(SENTINEL_USER, SENTINEL_PASSWORD)
        for text in (repr(login), str(login), json.dumps(login.public())):
            self.assertNotIn(SENTINEL_USER, text)
            self.assertNotIn(SENTINEL_PASSWORD, text)
        self.assertEqual(login.public(), {"login_fingerprint": login_fingerprint(SENTINEL_USER), "worker": "macbook"})


class TestRedaction(unittest.TestCase):
    def test_log_lines_and_ledger_records_are_redacted(self):
        SECRETS.register(SENTINEL_USER, SENTINEL_PASSWORD)
        stream = io.StringIO()
        previous = sys.excepthook
        try:
            configure_logging(logging.INFO, None, stream)
            logging.getLogger("hyba_mine.test").info("pool said: unknown worker %s / %s", SENTINEL_USER, SENTINEL_PASSWORD)
        finally:
            sys.excepthook = previous
        self.assertNotIn(SENTINEL_USER, stream.getvalue())
        self.assertIn("[redacted]", stream.getvalue())
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger)
            ledger.append("pool_message", {"text": f"hello {SENTINEL_USER}"})
            raw = home.layout.ledger.read_text()
            self.assertNotIn(SENTINEL_USER, raw)
            self.assertTrue(json.loads(raw)["data"]["_redacted"])
            self.assertTrue(ledger.verify().ok)

    def test_short_or_hex_like_placeholders_are_not_treated_as_secrets(self):
        SECRETS.register("x", "123", "deadbeef")
        self.assertEqual(SECRETS.redact("nonce deadbeef x 123"), "nonce deadbeef x 123")


class TestNothingLeaks(unittest.TestCase):
    def test_full_session_leaves_no_login_in_logs_ledger_state_or_repository(self):
        stream = io.StringIO()
        previous = sys.excepthook

        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            home.put_login("viabtc")
            ledger = Ledger(home.layout.ledger, home.layout.ledger_lock)
            options = RuntimeOptions(endpoints={"viabtc": (pool.endpoint(),)}, backoff=(0.05,), stats_interval=0.2,
                                     control_interval=0.1, itinerary=PythiaItinerary(override=(UnitSpec(0, 0, 4096),)),
                                     stop_when_itinerary_ends=True)
            dispatcher = LocalIGPUDispatcher(ModeALane(workers=1), Route("auto", ROUTE_MODE_A, "METAL_UNAVAILABLE: test"))
            runtime = MinerRuntime(home.layout, ledger, home.store(), dispatcher, "viabtc", options)
            task = asyncio.create_task(runtime.run())
            for _ in range(200):
                if any(r["kind"] == "job" for r in ledger.records()):
                    break
                await asyncio.sleep(0.02)
            await pool.broadcast({"id": None, "method": "client.show_message",
                                  "params": [f"Welcome {SENTINEL_USER}, password {SENTINEL_PASSWORD}"]})
            code = await task
            dispatcher.close()
            await pool.stop()
            return code, len(pool.accepted)

        try:
            with TempHome() as home:
                configure_logging(logging.DEBUG, home.layout.log_file, stream)
                grant_approval(home.layout)
                code, accepted = _support.run(scenario(home))
                self.assertEqual(code, 0)
                self.assertGreater(accepted, 0)

                def no_metal():
                    raise LaneUnavailable("test host")

                async def preflight():
                    pool = VerifyingPool()
                    await pool.start()
                    report = await asyncio.to_thread(
                        run_preflight, home.layout, Ledger(home.layout.ledger, home.layout.ledger_lock),
                        home.store(), "viabtc", endpoints=(pool.endpoint(),), mode_a_workers=1,
                        open_metal=no_metal, full_window=False, handshake_timeout=10)
                    await pool.stop()
                    return report

                report = _support.run(preflight())
                self.assertTrue(report.passed, [c.name for c in report.failures()])
                report.lane.close()
                summary = summarize(Ledger(home.layout.ledger).records())
                rendered = render_text(summary) + json.dumps(summary)
                for handler in logging.getLogger().handlers:
                    handler.flush()
                exposed = []
                for path in home.root.rglob("*"):
                    if path.is_file() and path.name != "credentials.json":
                        data = path.read_bytes()
                        if SENTINEL_USER.encode() in data or SENTINEL_PASSWORD.encode() in data:
                            exposed.append(str(path))
                for name, text in (("stream", stream.getvalue()), ("status", rendered)):
                    if SENTINEL_USER in text or SENTINEL_PASSWORD in text:
                        exposed.append(name)
                self.assertEqual(exposed, [])
                self.assertIn("[redacted]", home.layout.ledger.read_text())
                self.assertTrue(home.layout.log_file.exists())
        finally:
            sys.excepthook = previous
            logging.basicConfig(level=logging.INFO, force=True)
        repository_hits = []
        for root in (PACKAGE_ROOT, REPO_ROOT / "scripts" / "mine", REPO_ROOT / "docs" / "mine"):
            for path in root.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts and path.name != "_support.py":
                    data = path.read_bytes()
                    if SENTINEL_USER.encode() in data or SENTINEL_PASSWORD.encode() in data:
                        repository_hits.append(str(path))
        self.assertEqual(repository_hits, [])

    def test_cli_login_never_echoes_the_password(self):
        with TempHome() as home:
            if not home.file_permissions:
                self.skipTest("this test filesystem ignores chmod; covered on macOS and CI")
            out = io.StringIO()
            stdin = sys.stdin
            sys.stdin = io.StringIO(SENTINEL_PASSWORD + "\n")
            try:
                with redirect_stdout(out):
                    code = cli_main(["login", "viabtc", "--store", "file", "--username", SENTINEL_USER, "--password-stdin"])
            finally:
                sys.stdin = stdin
            self.assertEqual(code, 0)
            self.assertNotIn(SENTINEL_PASSWORD, out.getvalue())
            self.assertNotIn(SENTINEL_USER, out.getvalue())
            self.assertEqual(home.layout.credentials.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(SENTINEL_PASSWORD, home.layout.ledger.read_text())

    def test_cli_login_output_ledger_and_log_never_carry_the_login(self):
        from unittest import mock

        with TempHome() as home:
            store = _support.MemoryStore()
            out = io.StringIO()
            stdin = sys.stdin
            sys.stdin = io.StringIO(SENTINEL_PASSWORD + "\n")
            try:
                with mock.patch("hyba_mine.cli.open_store", return_value=store), redirect_stdout(out):
                    code = cli_main(["login", "viabtc", "--username", SENTINEL_USER, "--password-stdin"])
                    status_code = cli_main(["status", "--json"])
            finally:
                sys.stdin = stdin
            self.assertEqual((code, status_code), (0, 0))
            self.assertEqual(store.get("viabtc").password, SENTINEL_PASSWORD)
            text = out.getvalue()
            ledger_text = home.layout.ledger.read_text()
            for secret in (SENTINEL_PASSWORD, SENTINEL_USER):
                self.assertNotIn(secret, text)
                self.assertNotIn(secret, ledger_text)
            self.assertIn("login_stored", ledger_text)
            for path in home.root.rglob("*"):
                if path.is_file():
                    data = path.read_bytes()
                    self.assertNotIn(SENTINEL_PASSWORD.encode(), data, str(path))


if __name__ == "__main__":
    unittest.main()
