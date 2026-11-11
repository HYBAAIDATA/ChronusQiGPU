# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Append-only ledger, status derived from it, and the local status page."""

import json
import multiprocessing
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import _support  # noqa: F401  (import paths)
from _support import TempHome

from hyba_mine.console import ConsoleServer
from hyba_mine.control import read_control_request, update_state
from hyba_mine.ledger import GENESIS_HASH, Ledger
from hyba_mine.status import format_rate, render_text, summarize


def _append_many(path: str, lock: str, count: int) -> None:
    ledger = Ledger(path, lock)
    for i in range(count):
        ledger.append("work", {"i": i})


class TestLedger(unittest.TestCase):
    def test_chain_verifies_and_detects_edits_deletions_and_reordering(self):
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger)
            first = ledger.append("session_start", {"pool": "viabtc"})
            self.assertEqual(first["prev"], GENESIS_HASH)
            for i in range(5):
                ledger.append("work", {"executed": i})
            self.assertTrue(ledger.verify().ok)
            lines = home.layout.ledger.read_text().splitlines()
            tampered = lines[:]
            record = json.loads(tampered[2])
            record["data"]["executed"] = 999
            tampered[2] = json.dumps(record, sort_keys=True, separators=(",", ":"))
            for variant in (tampered, lines[:2] + lines[3:], [lines[0], lines[2], lines[1]] + lines[3:]):
                home.layout.ledger.write_text("\n".join(variant) + "\n")
                self.assertFalse(Ledger(home.layout.ledger).verify().ok)

    def test_torn_tail_is_tolerated_and_the_chain_continues(self):
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger)
            ledger.append("session_start", {})
            with open(home.layout.ledger, "ab") as handle:
                handle.write(b'{"seq": 1, "kind": "wo')
            fresh = Ledger(home.layout.ledger)
            fresh.append("work", {"executed": 1})
            result = fresh.verify()
            self.assertTrue(result.ok, result.error)
            self.assertEqual((result.records, result.torn_lines), (2, 1))

    def test_concurrent_writers_keep_one_valid_chain(self):
        with TempHome() as home:
            path, lock = str(home.layout.ledger), str(home.layout.ledger_lock)
            context = multiprocessing.get_context("spawn")
            workers = [context.Process(target=_append_many, args=(path, lock, 25)) for _ in range(3)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(60)
            result = Ledger(path, lock).verify()
            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.records, 75)


class TestStatus(unittest.TestCase):
    def _records(self, now):
        def at(seconds, kind, data):
            ts = (now - timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
            return {"ts": ts, "kind": kind, "data": data}

        return [
            at(300, "session_start", {"pool": "viabtc", "requested_route": "auto", "executed_route": "chronus_igpu_metal",
                                      "fallback_reason": None, "node": "imac"}),
            at(299, "pool_connected", {"pool": "viabtc", "endpoint": "stratum+ssl://btc-ssl.viabtc.io:551", "tls": True,
                                       "login_fingerprint": "abc123", "worker": "imac"}),
            at(298, "job", {"job_id": "j1", "clean_jobs": True, "difficulty": "8192", "received_at": "t"}),
            at(200, "work", {"node": "imac", "route": "chronus_igpu_metal", "executed": 10 ** 12, "device_ns": 10 ** 9}),
            at(30, "work", {"node": "imac", "route": "chronus_igpu_metal", "executed": 4 * 10 ** 9, "device_ns": 2 * 10 ** 9}),
            at(20, "share_submitted", {"share_id": "s1"}),
            at(19, "pool_response", {"share_id": "s1", "accepted": True, "reply": {"result": True, "error": None}}),
            at(15, "share_submitted", {"share_id": "s2"}),
            at(14, "pool_response", {"share_id": "s2", "accepted": False, "reply": {"result": None, "error": [23, "Low difficulty share", None]}}),
            at(10, "share_submitted", {"share_id": "s3"}),
        ]

    def test_values_come_only_from_ledger_records(self):
        now = datetime.now(timezone.utc)
        summary = summarize(self._records(now), now=now)
        self.assertEqual(summary["state"], "MINING")
        self.assertEqual(summary["shares"]["submitted"], 3)
        self.assertEqual(summary["shares"]["accepted"], 1)
        self.assertEqual(summary["shares"]["rejected"], 1)
        self.assertEqual(summary["shares"]["awaiting_or_unacknowledged"], 1)
        self.assertEqual(summary["hashrate"]["hashrate_hs"], 2e9)
        self.assertEqual(summary["hashrate"]["display"], "2 GH/s")
        self.assertEqual(summary["pool"]["endpoint"], "stratum+ssl://btc-ssl.viabtc.io:551")
        self.assertEqual(summary["route"]["executed"], "chronus_igpu_metal")
        self.assertAlmostEqual(summary["session"]["uptime_seconds"], 300, delta=2)
        text = render_text(summary)
        self.assertIn("accepted 1 | rejected 1", text)
        self.assertIn("Low difficulty share", text)

    def test_no_work_records_means_not_measured(self):
        now = datetime.now(timezone.utc)
        summary = summarize(self._records(now)[:3], now=now)
        self.assertIsNone(summary["hashrate"]["hashrate_hs"])
        self.assertEqual(summary["hashrate"]["display"], "not measured")
        self.assertEqual(format_rate(1500.0), "1.5 kH/s")
        self.assertEqual(summarize([], now=now)["state"], "NO SESSION")

    def test_a_silent_ledger_is_not_reported_as_mining(self):
        now = datetime.now(timezone.utc)
        summary = summarize(self._records(now - timedelta(hours=1)), now=now)
        self.assertEqual(summary["state"], "NO RECENT ACTIVITY")
        self.assertIsNone(summary["hashrate"]["hashrate_hs"])


class TestConsolePage(unittest.TestCase):
    def test_page_reads_the_ledger_and_pool_switch_needs_token_and_loopback_host(self):
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger)
            ledger.append("session_start", {"pool": "viabtc", "requested_route": "auto",
                                            "executed_route": "chronus_igpu_mode_a", "fallback_reason": "METAL_UNAVAILABLE: x"})
            update_state(home.layout, active_pool="viabtc")
            console = ConsoleServer(home.layout, ledger, port=0).start()
            try:
                page = urllib.request.urlopen(console.url, timeout=10).read().decode()
                self.assertIn("Chronus iGPU - Mode A (software-defined GPU)", page)
                self.assertIn("METAL_UNAVAILABLE", page)
                status = json.loads(urllib.request.urlopen(console.url + "status.json", timeout=10).read())
                self.assertEqual(status["source"], "ledger")
                post = urllib.request.Request(console.url + "pool", data=b"token=wrong&pool=braiins", method="POST")
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(post, timeout=10)
                self.assertEqual(caught.exception.code, 403)
                self.assertIsNone(read_control_request(home.layout))
                forged = urllib.request.Request(console.url, headers={"Host": "evil.example:80"})
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(forged, timeout=10)
                body = f"token={console.token}&pool=braiins".encode()
                urllib.request.urlopen(urllib.request.Request(console.url + "pool", data=body, method="POST"), timeout=10)
                request = read_control_request(home.layout)
                self.assertEqual(request["pool_id"], "braiins")
            finally:
                console.stop()


if __name__ == "__main__":
    unittest.main()
