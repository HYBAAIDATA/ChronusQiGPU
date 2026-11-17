# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Cross-platform layer: credential store, start-at-login, stop requests, launcher, locks."""

import os
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from _support import TempHome
from hyba_mine import autostart, launch, portable
from hyba_mine.control import clear_stop_request, read_stop_request, request_stop
from hyba_mine.credentials import (
    CredentialStoreError,
    PoolLogin,
    WindowsCredentialStore,
    default_backend,
    open_store,
)


class FakeCredApi:
    """In-memory stand-in for hyba_mine._win32's Credential Manager calls."""

    class Record:
        def __init__(self, blob):
            self.blob = blob

    def __init__(self, fail=None):
        self.items, self.fail, self.writes = {}, fail, []

    def cred_write(self, target, label, comment, blob):
        if self.fail:
            raise OSError(self.fail)
        self.writes.append((target, label, comment))
        self.items[target] = blob

    def cred_read(self, target):
        if self.fail:
            raise OSError(self.fail)
        blob = self.items.get(target)
        return None if blob is None else self.Record(blob)

    def cred_delete(self, target):
        return self.items.pop(target, None) is not None


class WindowsCredentialStoreTests(unittest.TestCase):
    def test_round_trip_and_delete(self):
        api = FakeCredApi()
        store = WindowsCredentialStore(api=api)
        store.put("viabtc", PoolLogin("acct.worker", "123"))
        self.assertEqual(store.get("viabtc").username, "acct.worker")
        self.assertTrue(store.delete("viabtc"))
        self.assertIsNone(store.get("viabtc"))

    def test_target_label_and_comment_carry_no_secret(self):
        api = FakeCredApi()
        WindowsCredentialStore(api=api).put("braiins", PoolLogin("hyba.desk", "s3cret-value"))
        target, label, comment = api.writes[0]
        self.assertEqual(target, "HYBA-Mine:pool:braiins")
        for visible in (target, label, comment):
            self.assertNotIn("s3cret-value", visible)
            self.assertNotIn("hyba.desk", visible)

    def test_api_failure_never_leaks_the_login(self):
        store = WindowsCredentialStore(api=FakeCredApi(fail="access denied"))
        with self.assertRaises(CredentialStoreError) as caught:
            store.put("viabtc", PoolLogin("acct.worker", "s3cret-value"))
        self.assertNotIn("s3cret-value", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_default_backend_matches_the_os(self):
        expected = {"darwin": "keychain", "win32": "wincred"}.get(sys.platform, "file")
        if sys.platform == "darwin" and not os.path.exists("/usr/bin/security"):
            expected = "file"
        self.assertEqual(default_backend(), expected)

    def test_store_for_another_os_is_refused(self):
        with TempHome() as home:
            other = "keychain" if sys.platform != "darwin" else "wincred"
            with self.assertRaises(ValueError):
                open_store(other, home.layout)


class AutostartWindowsTests(unittest.TestCase):
    def test_task_xml_runs_the_launcher_unelevated_for_this_user(self):
        with TempHome() as home:
            xml = autostart.windows_task_xml(home.layout, r"C:\Py\pythonw.exe", "S-1-5-21-1-2-3-1001")
        self.assertTrue(xml.startswith(b"\xff\xfe"))  # UTF-16 BOM, as schtasks /XML expects
        root = ET.fromstring(xml.decode("utf-16").split("?>", 1)[1])
        ns = {"t": autostart.TASK_NS}
        self.assertEqual(root.findtext("t:Principals/t:Principal/t:RunLevel", namespaces=ns), "LeastPrivilege")
        self.assertEqual(root.findtext("t:Principals/t:Principal/t:LogonType", namespaces=ns), "InteractiveToken")
        self.assertEqual(root.findtext("t:Triggers/t:LogonTrigger/t:UserId", namespaces=ns), "S-1-5-21-1-2-3-1001")
        args = root.findtext("t:Actions/t:Exec/t:Arguments", namespaces=ns)
        self.assertIn("hyba_mine.launch", args)
        self.assertIn(str(home.layout.home), args)

    def test_commands_never_store_a_password_or_elevate(self):
        commands = autostart.windows_task_commands(autostart.Path("task.xml"), start=True)
        flat = [part.upper() for cmd in commands for part in cmd]
        for forbidden in ("/RU", "/RP", "HIGHEST"):
            self.assertNotIn(forbidden, flat)
        self.assertEqual(commands[-1][1:], ["/Run", "/TN", autostart.WINDOWS_TASK_NAME])

    def test_enable_writes_a_private_task_file_and_runs_schtasks(self):
        calls = []

        def runner(argv):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        with TempHome() as home:
            path = autostart.enable(autostart.Path("unused"), home.layout, start=False, runner=runner,
                                    platform_id="windows", python="pythonw.exe", sid="S-1-5-21-9")
            self.assertTrue(path.exists())
            if sys.platform == "win32":
                self.assertTrue(portable.describe_access(path).private)
        self.assertEqual([c[1] for c in calls], ["/Create"])

    def test_enable_reports_schtasks_failure(self):
        def runner(argv):
            return subprocess.CompletedProcess(argv, 1, "", "Access is denied.")

        with TempHome() as home:
            with self.assertRaisesRegex(RuntimeError, "schtasks /Create failed .*Access is denied"):
                autostart.enable(autostart.Path("unused"), home.layout, runner=runner,
                                 platform_id="windows", python="pythonw.exe", sid="S-1-5-21-9")

    def test_status_reads_the_installed_task(self):
        with TempHome() as home:
            xml = autostart.windows_task_xml(home.layout, autostart.launcher_python(), "S-1-5-21-9").decode("utf-16")

        def runner(argv):
            return subprocess.CompletedProcess(argv, 0, xml, "")

        state = autostart.status(runner=runner, platform_id="windows")
        self.assertTrue(state["installed"] and state["enabled"] and state["matches_expected"])

    def test_status_when_not_installed(self):
        state = autostart.status(runner=lambda a: subprocess.CompletedProcess(a, 1, "", ""), platform_id="windows")
        self.assertFalse(state["installed"])


class AutostartLinuxTests(unittest.TestCase):
    def test_unit_and_commands(self):
        calls = []
        with TempHome() as home:
            path = autostart.enable(autostart.Path("unused"), home.layout, start=True, platform_id="linux",
                                    python="/usr/bin/python3", unit_dir=home.root,
                                    runner=lambda a: calls.append(a) or subprocess.CompletedProcess(a, 0, "", ""))
            text = path.read_text()
        self.assertIn("Restart=on-failure", text)
        self.assertIn("hyba_mine.launch", text)
        self.assertEqual(calls[-1][-2:], ["--now", autostart.SYSTEMD_UNIT])


class StopRequestTests(unittest.TestCase):
    def test_round_trip_and_independent_of_pool_switch(self):
        from hyba_mine.control import read_control_request, request_pool_switch

        with TempHome() as home:
            switch = request_pool_switch(home.layout, "braiins")
            stop = request_stop(home.layout, "operator")
            self.assertEqual(read_stop_request(home.layout)["request_id"], stop["request_id"])
            self.assertEqual(read_control_request(home.layout)["request_id"], switch["request_id"])
            clear_stop_request(home.layout)
            self.assertIsNone(read_stop_request(home.layout))
            self.assertIsNotNone(read_control_request(home.layout))


class LauncherTests(unittest.TestCase):
    def test_sets_home_and_logs_then_runs_start(self):
        seen = {}

        def fake_main(argv):
            seen["argv"] = argv
            seen["home"] = os.environ["HYBA_MINE_HOME"]
            seen["logs"] = os.environ["HYBA_MINE_LOG_DIR"]
            return 0

        with TempHome(), patch("hyba_mine.cli.main", fake_main):
            self.assertEqual(launch.main(["--home", "H", "--logs", "L", "--tls", "require"]), 0)
        self.assertEqual(seen, {"argv": ["start", "--tls", "require"], "home": "H", "logs": "L"})


class LockTests(unittest.TestCase):
    def test_second_process_cannot_take_a_held_lock(self):
        with TempHome() as home:
            lock = home.root / "x.lock"
            code = ("import sys; from hyba_mine import portable\n"
                    "try:\n    portable.FileLock(sys.argv[1]).acquire(blocking=False); print('got')\n"
                    "except portable.LockHeld:\n    print('held')")
            env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
            with portable.exclusive_lock(lock):
                held = subprocess.run([sys.executable, "-c", code, str(lock)], capture_output=True, text=True, env=env)
            free = subprocess.run([sys.executable, "-c", code, str(lock)], capture_output=True, text=True, env=env)
        self.assertEqual(held.stdout.strip(), "held")
        self.assertEqual(free.stdout.strip(), "got")


if __name__ == "__main__":
    unittest.main()
