import time
import unittest
from dataclasses import dataclass
from hyba_contracts import *
from hyba_services.observability import *


class Tests(unittest.TestCase):
    def test_financial_pack_validation_compose_and_gaps(self):
        now = 100
        pack = financial_services_pack("sig", "issuer", 90, 200)
        mods = {m: "0.1.0" for m in pack.requires.modules_min}
        pack.validate(
            "0.1.0",
            {},
            mods,
            {"identity": "CONTRACTED", "schema": "CONTRACTED"},
            lambda p: p.signature == "sig",
            now,
        )
        composed = compose(pack, {"controls": ({"id": "CORE"},)})
        self.assertEqual(len(composed.controls), 6)
        report = emit_gap_report(
            STARTER_ASSURANCE_PACKS[0],
            {"FS.C1"},
            {"T.RESIDENCY"},
            {"E.RESIDENCY"},
            lambda r: "signed",
            now,
        )
        self.assertTrue(report["gaps"])
        self.assertEqual(report["signature"], "signed")

    def test_version_classification_migration_and_abi(self):
        self.assertEqual(classify(Change(alters_byte_layout=True)), ChangeLevel.MAJOR)
        self.assertEqual(classify(Change(adds_public_symbol=True)), ChangeLevel.MINOR)
        self.assertEqual(classify(Change(bug_fix=True)), ChangeLevel.PATCH)
        migrator = SchemaMigrator(
            {
                (1, 2): lambda o: upgrade_v1_to_v2(o, lambda _: 0),
                (2, 3): lambda o: upgrade_v2_to_v3(o, lambda _: "fold@1"),
            }
        )
        v3 = migrator.migrate({"schema_version": 1, "payload_type": "x"}, 3)
        self.assertEqual(v3["fold_contract_ref"], "fold@1")
        raw = HOT_DESCRIPTOR_V1.pack(1, *([0] * 14))
        self.assertTrue(check_abi(1, raw))
        self.assertEqual(len(read_hot(1, raw)), 15)
        with self.assertRaises(DowngradeNotSupported):
            migrator.migrate(v3, 2)

    def test_observability_tenant_isolation_trace_and_export(self):
        t = InMemoryTransport()
        o = Observability(t)
        now = int(time.time())
        m = Metric(
            "mla1517.bytes.moved",
            MetricKind.COUNTER,
            "bytes",
            {},
            12,
            now,
            "tenant-a",
            "i",
            "enterprise",
            Source.MLA1517,
        )
        o.emit(m)
        self.assertEqual(len(o.query_metrics((m.name,), "tenant-a", now - 1, now + 1)), 1)
        self.assertEqual(o.query_metrics((m.name,), "tenant-b", now - 1, now + 1), [])
        span = o.start_span("fold.execute", "tenant-a", "i", "enterprise")
        o.end_span(span, "OK")
        export = o.export_evidence("tenant-a", now - 1, now + 1, b"k" * 32)
        self.assertTrue(export["signature"])
        self.assertEqual(len(export["metrics"]), 1)
        with self.assertRaises(ValueError):
            o.emit(
                Metric(
                    "unknown",
                    MetricKind.COUNTER,
                    "1",
                    {},
                    1,
                    now,
                    "t",
                    "i",
                    "enterprise",
                    Source.SERVICES,
                )
            )

    def test_resource_truth_measured_only(self):
        @dataclass
        class E:
            scale: int = 10
            logical_size: int = 100
            physical_bytes: int = 64
            bytes_moved: int = 128
            proof_bytes: int = 32
            checkpoints: int = 1
            capacity_mode: str = "bounded_measured"

        report = resource_truth(E())
        self.assertEqual(report.performance_claim, "measured_only")
        self.assertEqual(len(dashboard("enterprise", "t")), 10)


if __name__ == "__main__":
    unittest.main()
