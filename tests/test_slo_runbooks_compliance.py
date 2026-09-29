import hashlib
import hmac
import tempfile
import unittest

from hyba_contracts import STARTER_ASSURANCE_PACKS
from hyba_services.compliance import ControlJob
from hyba_services.compliance import EvidenceRoom
from hyba_services.compliance import RegulatorEvidencePack
from hyba_services.compliance import assemble
from hyba_services.compliance import crosswalk
from hyba_services.compliance import run_scheduled
from hyba_services.compliance import verify_offline
from hyba_services.runbooks import Runbook
from hyba_services.runbooks import RunbookFailed
from hyba_services.runbooks import RunbookRunner
from hyba_services.slo import alert_rules
from hyba_services.slo import otel_config
from hyba_services.slo import prometheus_config
from hyba_services.slo import render_dashboard
from hyba_services.slo import slos_for


class Tests(unittest.TestCase):
    def test_profile_slos_dashboards_and_alerts(self):
        self.assertEqual(len(slos_for("sovereign")), 6)
        self.assertEqual(len(slos_for("developer")), 1)
        self.assertEqual(len(render_dashboard("enterprise")["dashboard"]["panels"]), 10)
        self.assertTrue(alert_rules("enterprise")["groups"][0]["rules"])
        self.assertEqual(
            otel_config("0.1.0", "enterprise", "t")["resource_attributes"]["tenant.id"], "t"
        )
        self.assertEqual(len(prometheus_config()["scrape_configs"]), 3)

    def test_runbook_success_and_rollback(self):
        rb = Runbook(
            "r",
            "R",
            "trigger",
            ("ready",),
            ("step",),
            ("verify",),
            ("undo",),
            ("owner",),
            ("receipt",),
        )
        actions = {
            "ready": lambda: True,
            "step": lambda: None,
            "verify": lambda: True,
            "undo": lambda: None,
        }
        e = RunbookRunner(b"r" * 32).execute(rb, "op", "t", actions)
        self.assertTrue(e.signature)
        self.assertFalse(e.rollback_used)
        called = []
        bad = {**actions, "verify": lambda: False, "undo": lambda: called.append("undo")}
        with self.assertRaises(RunbookFailed):
            RunbookRunner(b"r" * 32).execute(rb, "op", "t", bad)
        self.assertEqual(called, ["undo"])

    def test_offline_compliance_pack(self):
        key = b"c" * 32

        def signer(raw):
            return hmac.new(key, raw, hashlib.sha256).hexdigest()

        receipt = {
            "receipt_id": "r",
            "verified": True,
            "envelope": {"ok": True},
            "witness_receipt_id": "w",
        }
        pack = assemble(
            "t",
            (1, 2),
            ({"id": "C1"},),
            ({"id": "O1"},),
            lambda *x: receipt,
            {"compliance": signer},
        )
        # Verify against the exact canonical payload reconstructed by verify_offline.
        import json
        from dataclasses import asdict

        body = {
            "pack_id": pack.pack_id,
            "tenant": pack.tenant,
            "window": pack.window,
            "controls": pack.controls,
            "obligations": pack.obligations,
            "receipt_ids": tuple(r["receipt_id"] for r in pack.receipts),
            "gaps": tuple(asdict(g) for g in pack.gaps),
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
        expected = signer(raw)
        self.assertTrue(
            verify_offline(
                pack,
                lambda n, s, d: s == expected,
                lambda e: e["ok"],
                lambda r: r["witness_receipt_id"] == "w",
            )
        )

    def test_crosswalk_continuous_and_room(self):
        cw = crosswalk(STARTER_ASSURANCE_PACKS)
        self.assertIn("UK_GDPR.Art5", cw)
        gaps = []
        alerts = []
        run_scheduled(
            (ControlJob("C", 60, lambda: {"verified": False, "reason": "missing"}),),
            lambda *x: alerts.append(x),
            gaps.append,
        )
        self.assertEqual(len(gaps), 1)
        pack = RegulatorEvidencePack(
            "p",
            "t",
            (1, 2),
            (),
            (),
            (),
            (),
            ({"signer": "s", "signature": "x", "payload_sha256": "y"},),
            ("verify",),
        )
        with tempfile.TemporaryDirectory() as d:
            room = EvidenceRoom(d)
            path = room.publish(pack, "regulator")
            self.assertEqual(room.fetch(path)["audience"], "regulator")


if __name__ == "__main__":
    unittest.main()
