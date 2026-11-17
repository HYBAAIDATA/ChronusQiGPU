# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""THESEUS custody of pool switches: fail closed, and no login in any record."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from chronus.storage.durable import DurableTheseusService
from hyba_mine.custody import (
    EVENT_APPLIED,
    EVENT_REQUESTED,
    CustodyError,
    PoolSwitchCustody,
    custody_from_environment,
)
from hyba_mine.runtime import MinerRuntime


class _FailingService:
    def append_journal_event(self, tenant_id, event_type, payload):
        raise OSError("store unavailable")


class _RecordingService:
    def __init__(self):
        self.calls = []

    def append_journal_event(self, tenant_id, event_type, payload):
        self.calls.append((tenant_id, event_type, json.loads(payload)))


class CustodyTests(unittest.TestCase):
    def test_a_record_carries_schema_event_and_no_pool_login(self):
        service = _RecordingService()
        PoolSwitchCustody(service, "tenant-a").record(
            EVENT_REQUESTED, {"request_id": "r1", "from": "viabtc", "to": "braiins", "reason": None})
        tenant, event, body = service.calls[0]
        self.assertEqual((tenant, event), ("tenant-a", EVENT_REQUESTED))
        self.assertEqual(body["schema"], "hyba-mine.pool-switch/1")
        self.assertEqual(body["request_id"], "r1")
        self.assertNotIn("password", json.dumps(body).lower())

    def test_a_failed_write_raises_custody_error(self):
        with self.assertRaises(CustodyError):
            PoolSwitchCustody(_FailingService(), "tenant-a").record(EVENT_REQUESTED, {"request_id": "r1"})

    def test_environment_is_off_when_unset_and_refuses_half_configuration(self):
        self.assertIsNone(custody_from_environment({}))
        with self.assertRaises(CustodyError):
            custody_from_environment({"HYBA_MINE_CUSTODY_PATH": "theseus.sqlite3"})
        with self.assertRaises(CustodyError):
            custody_from_environment({"HYBA_MINE_TENANT_ID": "tenant-a"})

    def test_records_survive_a_reopened_theseus_store(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = str(Path(tmp) / "theseus.sqlite3")
            custody = custody_from_environment({"HYBA_MINE_CUSTODY_PATH": path, "HYBA_MINE_TENANT_ID": "tenant-a"})
            custody.record(EVENT_REQUESTED, {"request_id": "r1", "from": "viabtc", "to": "braiins", "reason": None})
            custody.record(EVENT_APPLIED, {"request_id": "r1", "to": "braiins", "reason": None})
            reopened = DurableTheseusService(path)
            self.assertTrue(reopened.verify_journal_continuity("tenant-a"))

    def test_the_switch_gate_refuses_when_the_request_cannot_be_recorded(self):
        stub = SimpleNamespace(custody=PoolSwitchCustody(_FailingService(), "tenant-a"),
                               profile=SimpleNamespace(pool_id="viabtc"))
        reason = MinerRuntime._custody_gate(stub, "r1", "braiins")
        self.assertIsNotNone(reason)
        self.assertIn("custody record unavailable", reason)

    def test_the_switch_gate_passes_when_custody_is_off(self):
        stub = SimpleNamespace(custody=None, profile=SimpleNamespace(pool_id="viabtc"))
        self.assertIsNone(MinerRuntime._custody_gate(stub, "r1", "braiins"))


if __name__ == "__main__":
    unittest.main()
