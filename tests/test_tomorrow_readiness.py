"""Synthetic unit fixtures are never deployment evidence."""

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "tomorrow_readiness",
    Path(__file__).resolve().parents[1] / "tools/tomorrow_readiness.py",
)
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.doc = r.template()
        self.doc.update(
            source_revision="test-fixture-not-a-deployment",
            offering="fixture",
            environment="unit-test",
        )
        self.doc["policy"]["approved_verifiers"] = ["test-fixture"]

    def receipt(self, subject, measurement=None, **updates):
        receipt = {
            "schema": r.RECEIPT_SCHEMA,
            "subject": subject,
            **{k: self.doc[k] for k in ("source_revision", "offering", "environment")},
            "observed_at": NOW.isoformat(),
            "verifier_id": "test-fixture",
            "status": "PASS",
            "checks": {
                k: True
                for k in r.GATE_CHECKS.get(
                    subject.removeprefix("gate."), ("fixture_check",)
                )
            },
        }
        if measurement is not None:
            receipt["measurement"] = measurement
        receipt.update(updates)
        data = json.dumps(receipt).encode()
        filename = f"{subject}.json"
        (self.root / filename).write_bytes(data)
        self.doc["evidence"][subject] = {
            "path": filename,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        return subject

    def answer(self, cid, value=True, threshold=None):
        answer = {"value": value}
        if threshold is not None:
            answer["threshold"] = threshold
        answer["evidence"] = self.receipt(cid, copy.deepcopy(answer))
        self.doc["answers"][cid] = answer

    def full(self):
        for cid, c in r.CRITERIA.items():
            self.answer(
                cid,
                True if c[2] == "BOOL" else 5 if c[2] == "SCALE_1_5" else 100,
                {"unit": "fixture-only", "worst": 0, "target": 100}
                if c[2] == "METRIC"
                else None,
            )
        for name in r.CONTEXTS:
            value = 0 if name == "ai_demand_pressure" else 100
            ref = self.receipt(f"context.{name}", {"value": value})
            self.doc["context"][name] = {"value": value, "evidence": ref}
        for gate in r.GATES:
            self.doc["gates"][gate] = {"evidence": self.receipt(f"gate.{gate}")}

    def assess(self):
        return r.assess(self.doc, self.root, NOW)

    def criterion(self, cid):
        return next(
            c for a in self.assess()["areas"] for c in a["criteria"] if c["id"] == cid
        )

    def test_unknown_is_zero_not_ready(self):
        report = self.assess()
        self.assertEqual(report["criterion_count"], 31)
        self.assertEqual(report["composite_score"], 0)
        self.assertEqual(report["verified_criteria"], 0)
        self.assertFalse(report["qualification_evidence_complete"])
        self.assertFalse(report["assessment_passed"])

    def test_unproven_claim_halved(self):
        self.doc["answers"]["C1.1"]["value"] = True
        c = self.criterion("C1.1")
        self.assertEqual(c["score"], 50)
        self.assertFalse(c["verified"])

    def test_fully_verified_synthetic_fixture(self):
        self.full()
        report = self.assess()
        self.assertEqual(report["composite_score"], 100)
        self.assertEqual(report["verified_criteria"], 31)
        self.assertTrue(report["assessment_passed"])
        self.assertEqual(
            report["production_qualification"], "not_established_by_this_assessment"
        )

    def test_valid_criterion(self):
        self.answer("C1.1")
        self.assertTrue(self.criterion("C1.1")["verified"])

    def test_tampered_hash(self):
        self.answer("C1.1")
        (self.root / "C1.1.json").write_text("{}")
        self.assertEqual(self.criterion("C1.1")["evidence_status"], "digest_mismatch")

    def test_scope_binding(self):
        self.answer("C1.1")
        for field in ("source_revision", "environment", "offering"):
            with self.subTest(field=field):
                ref = self.receipt("C1.1", {"value": True}, **{field: "OTHER"})
                self.doc["answers"]["C1.1"]["evidence"] = ref
                self.assertEqual(
                    self.criterion("C1.1")["evidence_status"], "scope_mismatch"
                )

    def test_stale_future_and_naive_times_rejected(self):
        self.answer("C1.1")
        for when in (
            (NOW - timedelta(days=2)).isoformat(),
            (NOW + timedelta(seconds=1)).isoformat(),
            "2026-10-22T12:00:00",
        ):
            self.receipt("C1.1", {"value": True}, observed_at=when)
            self.assertFalse(self.criterion("C1.1")["verified"])

    def test_unapproved_verifier(self):
        self.answer("C1.1")
        self.doc["policy"]["approved_verifiers"] = []
        self.assertEqual(
            self.criterion("C1.1")["evidence_status"], "verifier_not_approved"
        )

    def test_failed_empty_and_truthy_checks_rejected(self):
        self.answer("C1.1")
        for updates in (
            {"status": "FAIL"},
            {"checks": {}},
            {"checks": {"a": 1}},
            {"checks": {"a": "true"}},
            {"checks": {"a": False}},
        ):
            self.receipt("C1.1", {"value": True}, **updates)
            self.assertFalse(self.criterion("C1.1")["verified"])

    def test_wrong_measurement_rejected(self):
        self.answer("C1.1")
        self.receipt("C1.1", {"value": False})
        self.assertEqual(
            self.criterion("C1.1")["evidence_status"], "measurement_mismatch"
        )

    def test_truthy_measurement_not_boolean(self):
        self.answer("C1.1")
        self.receipt("C1.1", {"value": 1})
        self.assertFalse(self.criterion("C1.1")["verified"])

    def test_metric_threshold_and_unit_are_bound(self):
        self.answer("C1.5", 60, {"unit": "percent", "worst": 0, "target": 100})
        self.assertEqual(self.criterion("C1.5")["score"], 60)
        self.doc["answers"]["C1.5"]["threshold"]["target"] = 60
        self.assertFalse(self.criterion("C1.5")["verified"])

    def test_metric_lower_is_better_and_clamping(self):
        for raw, expected in ((50, 0.5), (-10, 1), (120, 0)):
            self.assertEqual(
                r.normalise(
                    r.CRITERIA["C1.5"],
                    {
                        "value": raw,
                        "threshold": {"unit": "ms", "worst": 100, "target": 0},
                    },
                ),
                expected,
            )

    def test_bad_answers_rejected(self):
        for cid, value in (
            ("C1.1", 1),
            ("C1.6", True),
            ("C1.6", 0),
            ("C1.6", 5.5),
            ("C1.5", float("nan")),
            ("C1.5", 100),
        ):
            with self.subTest(cid=cid, value=value):
                self.doc["answers"][cid] = {"value": value}
                with self.assertRaises(ValueError):
                    self.assess()
                self.doc["answers"][cid] = {"value": None}

    def test_context_measurement_mismatch_conservative(self):
        self.full()
        self.doc["context"]["ai_demand_pressure"]["value"] = 1
        result = self.assess()
        pressure = next(c for c in result["context"] if c["id"] == "ai_demand_pressure")
        self.assertEqual(pressure["effective_value"], 100)
        self.assertFalse(result["assessment_passed"])

    def test_no_dependency_uplift_and_order_independent(self):
        self.full()
        self.doc["answers"]["C2.1"]["value"] = False
        report = self.assess()
        self.assertTrue(all(a["score"] <= a["base_score"] for a in report["areas"]))
        with (
            patch.object(r, "AREAS", tuple(reversed(r.AREAS))),
            patch.object(r, "DEPENDENCIES", tuple(reversed(r.DEPENDENCIES))),
        ):
            other = self.assess()
        self.assertEqual(
            {a["id"]: a["score"] for a in report["areas"]},
            {a["id"]: a["score"] for a in other["areas"]},
        )

    def test_risk_acceptance_is_not_evidence(self):
        before = self.assess()
        self.doc["accepted_risks"] = [
            "regression failures accepted",
            "no accepted share accepted",
        ]
        after = self.assess()
        self.assertEqual(before["composite_score"], after["composite_score"])
        self.assertEqual(before["qualification_gates"], after["qualification_gates"])

    def test_criterion_receipt_cannot_pass_gate(self):
        self.answer("C1.1")
        self.doc["gates"]["regression_suite"] = {"evidence": "C1.1"}
        gate = self.assess()["qualification_gates"][0]
        self.assertEqual(gate["status"], "NOT_ESTABLISHED")

    def test_unknown_ids_are_errors(self):
        self.doc["answers"]["TYPO"] = {}
        with self.assertRaises(ValueError):
            self.assess()

    def test_path_escape_and_absolute_rejected(self):
        self.answer("C1.1")
        for path in ("../outside.json", str(self.root / "C1.1.json")):
            self.doc["evidence"]["C1.1"]["path"] = path
            self.assertFalse(self.criterion("C1.1")["verified"])

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "evidence.json"
            target.write_text("{}")
            escape = self.root / "escape"
            try:
                escape.symlink_to(target)
            except OSError as exc:
                if getattr(exc, "winerror", None) != 1314:
                    raise
                escape.write_text("{}")
                orig_resolve = Path.resolve

                def _resolve(path_obj, *args, **kwargs):
                    if orig_resolve(path_obj) == orig_resolve(escape):
                        return orig_resolve(target)
                    return orig_resolve(path_obj, *args, **kwargs)

                with patch.object(Path, "resolve", autospec=True, side_effect=_resolve):
                    with self.assertRaises(ValueError):
                        r.bounded_file(self.root, "escape")
                return
            with self.assertRaises(ValueError):
                r.bounded_file(self.root, "escape")

    def test_receipt_read_once_per_check(self):
        self.answer("C1.1")
        with patch.object(r, "bounded_file", wraps=r.bounded_file) as read:
            self.assess()
        self.assertEqual(read.call_count, 1)

    def test_json_duplicate_and_nonfinite_rejected(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                r.strict_loads(data)

    def test_maturity_boundaries(self):
        for score, expected in (
            (0, "ABSENT"),
            (19.99, "ABSENT"),
            (20, "EXPERIMENTING"),
            (40, "DEVELOPING"),
            (60, "DEPLOYING"),
            (80, "OPTIMISED"),
            (100, "OPTIMISED"),
        ):
            self.assertEqual(r.maturity(score), expected)

    def test_size_limits(self):
        (self.root / "large").write_bytes(b"x" * 33)
        with patch.object(r, "MAX_FILE_BYTES", 32):
            with self.assertRaises(ValueError):
                r.bounded_file(self.root, "large")

    def test_missing_metric_targets_is_not_silent_success(self):
        self.doc["answers"]["C5.1"]["value"] = 1
        with self.assertRaises(ValueError):
            self.assess()

    def test_nonpositive_age_rejected(self):
        self.doc["policy"]["max_evidence_age_seconds"] = 0
        with self.assertRaises(ValueError):
            self.assess()

    def test_gate_requires_specific_checks(self):
        self.full()
        self.receipt("gate.pool_acceptance", checks={"connected": True})
        gate = next(
            g
            for g in self.assess()["qualification_gates"]
            if g["id"] == "pool_acceptance"
        )
        self.assertEqual(gate["evidence_status"], "required_checks_missing")

    def test_runtime_probe_does_not_qualify_system_or_leak_private_fields(self):
        path = self.root / "probe.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "chronus.mla1517.ready/1",
                    "ready": True,
                    "scope": "control_plane",
                    "components": {
                        "custody": {"state": "not_ready", "path": "private"},
                        "guardian": {"state": "not_configured", "reason": "private"},
                    },
                    "secret": "private",
                }
            )
        )
        observation = r.runtime_observation(path)
        self.assertTrue(observation["reported_ready"])
        self.assertFalse(observation["qualification_credit"])
        self.assertFalse(observation["current_liveness_established"])
        self.assertNotIn("private", json.dumps(observation))
        self.assertFalse(self.assess()["qualification_evidence_complete"])

    def test_unknown_probe_schema_rejected(self):
        path = self.root / "probe.json"
        path.write_text('{"ready": true}')
        with self.assertRaises(ValueError):
            r.runtime_observation(path)

    def test_cli_writes_report_and_returns_one_for_gaps(self):
        source = self.root / "assessment.json"
        output = self.root / "report.json"
        source.write_text(json.dumps(self.doc))
        self.assertEqual(r.main(["--input", str(source), "--output", str(output)]), 1)
        self.assertFalse(json.loads(output.read_text())["assessment_passed"])

    def test_cli_malformed_input_returns_two(self):
        source = self.root / "bad.json"
        source.write_text('{"x": NaN}')
        with self.assertRaises(SystemExit) as error:
            r.main(["--input", str(source)])
        self.assertEqual(error.exception.code, 2)

    def test_verified_false_is_evidence_but_still_a_gap(self):
        self.answer("C1.1", False)
        self.assertTrue(self.criterion("C1.1")["verified"])
        self.assertEqual(self.criterion("C1.1")["score"], 0)
        self.assertTrue(any(g["criterion_id"] == "C1.1" for g in self.assess()["gaps"]))

    def test_does_not_mutate_input(self):
        self.full()
        before = copy.deepcopy(self.doc)
        self.assess()
        self.assertEqual(before, self.doc)


if __name__ == "__main__":
    unittest.main()
