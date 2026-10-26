"""Bridge units with a triad double; no installed-engine or restart claims."""

import hashlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch, sentinel


SOURCE = Path(__file__).resolve().parents[1] / "aethel" / "enterprise_bridge.py"


class EnterpriseBridgeUnits(unittest.TestCase):
    def setUp(self):
        # Load the complete bridge without the unrelated Aethel initializer.
        name = "_enterprise_bridge_units.enterprise_bridge"
        spec = importlib.util.spec_from_file_location(name, SOURCE)
        self.bridge = importlib.util.module_from_spec(spec)
        triad = ModuleType("_enterprise_bridge_units.triad")
        triad.THESEUS_CUSTODY_PROFILE = sentinel.custody_profile
        self.open_triad = triad.open_triad = Mock()
        modules = patch.dict(sys.modules, {name: self.bridge, triad.__name__: triad})
        modules.start()
        self.addCleanup(modules.stop)
        spec.loader.exec_module(self.bridge)
        self.directory = Path("synthetic-custody")
        self.payload = b"\x00bridge\xff"
        self.record = SimpleNamespace(
            uuid="record-id", anchor=7, lane=2, prime_key=11, folded_units=3,
            digest=hashlib.sha256(self.payload).hexdigest(),
        )
        self.custody = {
            "authority": "theseus", "disk_bound": True, "integrity_verified": True,
        }
        self.original = Mock()
        self.original.put.return_value = self.record
        self.original.get.return_value = self.payload
        self.reopened = Mock(storage_profile="theseus-custody/v1")
        self.reopened.get.return_value = self.payload
        self.reopened.verify.return_value = True
        self.reopened.health.return_value = {"custody": self.custody}
        self.open_triad.side_effect = [self.original, self.reopened]

    def test_invalid_durability_is_rejected_before_opening_owner(self):
        cases = [
            ({}, ValueError),
            ({"durable_dir": ""}, ValueError),
            ({"durable_dir": " \t\n"}, ValueError),
            ({"durable": False, "durable_dir": self.directory}, ValueError),
            ({"durable": False, "durable_dir": ""}, ValueError),
        ]
        cases.extend(
            ({"durable": value, "durable_dir": self.directory}, TypeError)
            for value in (None, 0, 1, "true", [], object())
        )
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    self.bridge.open_enterprise_store(**kwargs)
        self.open_triad.assert_not_called()

    def test_directory_and_canonical_profile_are_forwarded(self):
        for directory in (self.directory, str(self.directory)):
            with self.subTest(directory=directory):
                self.open_triad.side_effect = None
                self.open_triad.return_value = sentinel.store
                store = self.bridge.open_enterprise_store(
                    durable_dir=directory, bind_chronus=True,
                )
                self.assertIs(store, sentinel.store)
                self.open_triad.assert_called_with(
                    durable=True, durable_dir=directory,
                    storage_profile=sentinel.custody_profile, bind_chronus=True,
                )

    def test_explicit_memory_mode_uses_canonical_profile(self):
        self.bridge.open_enterprise_store(durable=False)
        self.open_triad.assert_called_once_with(
            durable=False, durable_dir=None,
            storage_profile=sentinel.custody_profile, bind_chronus=False,
        )

    def test_smoke_requires_directory_before_opening_owner(self):
        with self.assertRaisesRegex(ValueError, "durable_dir"):
            self.bridge.smoke_measured_put()
        self.open_triad.assert_not_called()

    def test_smoke_commits_and_reads_each_owner_then_seals_evidence(self):
        envelope = self.bridge.smoke_measured_put(self.payload, durable_dir=self.directory)
        expected = call(
            durable=True, durable_dir=self.directory,
            storage_profile=sentinel.custody_profile, bind_chronus=False,
        )
        self.assertEqual(self.open_triad.call_args_list, [expected, expected])
        self.original.put.assert_called_once_with(self.payload, durable=True)
        self.original.get.assert_called_once_with(self.record.uuid)
        self.reopened.get.assert_called_once_with(self.record.uuid)
        self.reopened.put.assert_not_called()
        self.reopened.verify.assert_called_once_with()
        self.assertEqual(envelope["truth_class"], "measured")
        self.assertEqual(envelope["capability_id"], "E.STORE.SELF_HEAL")
        self.assertEqual(envelope["payload"], {
            "ok": True, **vars(self.record), "custody": self.custody,
            "storage_profile": "theseus-custody/v1",
            "restart_evidence": "reattach_same_process",
        })
        self.assertEqual(
            envelope["provenance_hash"],
            self.bridge.compute_envelope_provenance_hash(envelope),
        )

    def test_empty_payload_can_be_verified(self):
        self.original.get.return_value = self.reopened.get.return_value = b""
        self.record.digest = hashlib.sha256(b"").hexdigest()
        envelope = self.bridge.smoke_measured_put(b"", durable_dir=self.directory)
        self.assertIs(envelope["payload"]["ok"], True)
        self.original.put.assert_called_once_with(b"", durable=True)

    def assert_smoke_refused(self):
        with patch.object(self.bridge, "emit_envelope") as emit:
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                self.bridge.smoke_measured_put(self.payload, durable_dir=self.directory)
            emit.assert_not_called()

    def test_corrupt_original_read_cannot_be_hidden_by_valid_reattach(self):
        self.original.get.return_value = b"corrupt"
        self.assert_smoke_refused()

    def test_corrupt_reattached_read_cannot_be_hidden_by_original(self):
        self.reopened.get.return_value = b"corrupt"
        self.assert_smoke_refused()

    def test_digest_mismatch_refuses_measured_evidence(self):
        self.record.digest = hashlib.sha256(b"different").hexdigest()
        self.assert_smoke_refused()

    def test_verification_requires_literal_true(self):
        for value in (False, None, 1, "verified", {"ok": True}):
            with self.subTest(value=value):
                self.open_triad.side_effect = [self.original, self.reopened]
                self.reopened.verify.return_value = value
                self.assert_smoke_refused()

    def test_custody_facts_fail_closed_independently(self):
        for field, values in {
            "authority": (None, "ovid", "THESEUS"),
            "disk_bound": (None, False, 1, "true"),
            "integrity_verified": (None, False, 1, "true"),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    custody = dict(self.custody)
                    if value is None:
                        custody.pop(field)
                    else:
                        custody[field] = value
                    self.open_triad.side_effect = [self.original, self.reopened]
                    self.reopened.health.return_value = {"custody": custody}
                    self.assert_smoke_refused()

    def test_reattach_failure_does_not_emit_a_success_envelope(self):
        self.open_triad.side_effect = [self.original, OSError("attach failed")]
        with patch.object(self.bridge, "emit_envelope") as emit:
            with self.assertRaisesRegex(OSError, "attach failed"):
                self.bridge.smoke_measured_put(self.payload, durable_dir=self.directory)
            emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
