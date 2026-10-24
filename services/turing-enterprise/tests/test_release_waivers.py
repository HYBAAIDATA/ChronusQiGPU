"""Real signature/file validation; fixture authority is never a deployment approval."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hyba_turing_service.control import Unavailable, canonical
from hyba_turing_service.release import GATES, verify_bundle


class ReleaseWaiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = Ed25519PrivateKey.generate()
        self.public = base64.b64encode(
            self.key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
        ).decode()
        self.commit = "a" * 40
        self.now = 1000
        (self.root / "decision.json").write_text('{"fixture":true}')
        raw = (self.root / "decision.json").read_bytes()
        self.entry = {
            "state": "PASS",
            "reviewer": "TEST-REVIEWER",
            "executed_at": self.now,
            "artifact": "decision.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        self.manifest = {
            "schema": "turing.promotion.v1",
            "billing_scope": "deferred",
            "commit": self.commit,
            "issued_at": self.now,
            "expires_at": self.now + 100,
            "gates": {g: copy.deepcopy(self.entry) for g in GATES},
        }

    def waive(self, gate="runtime_integration"):
        entry = self.manifest["gates"][gate]
        entry.pop("reviewer", None)
        entry.pop("executed_at", None)
        entry.update(
            state="WAIVED",
            risk_acceptance={
                "approver": "TEST-OPERATOR",
                "reason": "Fixture risk decision, not execution evidence",
                "authorization_reference": "fixture://authorization",
                "accepted_at": self.now,
            },
        )
        return entry

    def write(self):
        signature = self.key.sign(canonical(self.manifest).encode())
        (self.root / "approval.json").write_text(
            json.dumps(
                {"manifest": self.manifest, "signature": base64.b64encode(signature).decode()}
            )
        )

    def verify(self, **options):
        self.write()
        return verify_bundle(self.root, self.public, self.commit, now=self.now, **options)

    def test_strict_pass_unchanged(self):
        self.assertEqual(self.verify()["commit"], self.commit)

    def test_default_rejects_signed_waiver(self):
        self.waive()
        with self.assertRaises(Unavailable):
            self.verify()

    def test_explicit_policy_preserves_waived_state(self):
        self.waive()
        result = self.verify(allow_waivers=True)
        self.assertEqual(result["gates"]["runtime_integration"]["state"], "WAIVED")

    def test_all_qualification_gates_can_be_waived(self):
        for gate in GATES:
            self.waive(gate)
        self.assertTrue(
            all(e["state"] == "WAIVED" for e in self.verify(allow_waivers=True)["gates"].values())
        )

    def test_truthy_non_boolean_does_not_enable_waivers(self):
        self.waive()
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers="yes")

    def test_missing_authorization_fields_rejected(self):
        for field in ("approver", "reason", "authorization_reference", "accepted_at"):
            with self.subTest(field=field):
                entry = self.waive()
                entry["risk_acceptance"].pop(field)
                with self.assertRaises(Unavailable):
                    self.verify(allow_waivers=True)

    def test_blank_authorization_fields_rejected(self):
        for field in ("approver", "reason", "authorization_reference"):
            with self.subTest(field=field):
                self.waive()["risk_acceptance"][field] = "  "
                with self.assertRaises(Unavailable):
                    self.verify(allow_waivers=True)

    def test_future_stale_and_boolean_acceptance_rejected(self):
        for value in (self.now + 1, self.now - 7 * 86400 - 1, True):
            with self.subTest(value=value):
                self.waive()["risk_acceptance"]["accepted_at"] = value
                with self.assertRaises(Unavailable):
                    self.verify(allow_waivers=True)

    def test_waiver_cannot_claim_execution(self):
        self.waive()["executed_at"] = self.now
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_expired_bundle_rejected(self):
        self.waive()
        self.manifest["expires_at"] = self.now
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_changed_commit_rejected(self):
        self.waive()
        self.manifest["commit"] = "b" * 40
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_untrusted_key_rejected(self):
        self.waive()
        self.public = base64.b64encode(b"0" * 32).decode()
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_tampered_decision_rejected(self):
        self.waive()
        (self.root / "decision.json").write_text("tampered")
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_missing_artifact_rejected(self):
        self.waive()
        (self.root / "decision.json").unlink()
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_parent_path_rejected(self):
        self.waive()["artifact"] = "../decision.json"
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_symlink_artifact_rejected(self):
        (self.root / "linked.json").symlink_to(self.root / "decision.json")
        self.waive()["artifact"] = "linked.json"
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_missing_gate_rejected(self):
        self.waive()
        self.manifest["gates"].pop("recovery_load")
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)

    def test_publication_rights_not_waivable(self):
        self.manifest["gates"]["publication_rights"] = copy.deepcopy(self.entry)
        self.waive("publication_rights")
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True, publication=True)

    def test_publication_requires_separate_pass(self):
        self.waive()
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True, publication=True)
        self.manifest["gates"]["publication_rights"] = copy.deepcopy(self.entry)
        self.assertEqual(self.verify(allow_waivers=True, publication=True)["commit"], self.commit)

    def test_unknown_gate_state_rejected(self):
        self.waive()["state"] = "FORCE_PASS"
        with self.assertRaises(Unavailable):
            self.verify(allow_waivers=True)


if __name__ == "__main__":
    unittest.main()
