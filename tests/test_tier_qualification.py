"""QualificationHarness, seal gate, and internal identity regressions."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronus.core.seal import assert_sealed, find_banned_tokens  # noqa: E402
from chronus.core.workload_alias import (  # noqa: E402
    externalize_workload_type,
    normalize_workload_type,
)
from chronus.math.binet_lucas import fibonacci_fast, lucas_recurrence  # noqa: E402
from chronus.qualification import QualificationHarness  # noqa: E402
from chronus.qualification.harness import verify_transcript_integrity  # noqa: E402
from chronus.qualification.tiers import Tier  # noqa: E402
from chronus.service.models import WorkloadRequest, WorkloadType  # noqa: E402


class SealTests(unittest.TestCase):
    def test_banned_tokens_detected(self) -> None:
        self.assertIn("lucas", find_banned_tokens("Lucas PV scaling"))
        self.assertIn("phi", find_banned_tokens("field unit phi"))
        self.assertEqual(find_banned_tokens("graphic spiral"), [])

    def test_public_blurb_is_sealed(self) -> None:
        from chronus.core.seal import external_behavior_blurb

        assert_sealed(external_behavior_blurb())

    def test_mechanism_seal_gate_script(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/ci/check_mechanism_seal.py")],
            cwd=ROOT,
            env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)


class AliasTests(unittest.TestCase):
    def test_scaling_v1_round_trip(self) -> None:
        self.assertEqual(normalize_workload_type("scaling.v1"), "LUCAS_PV_SCALING")
        self.assertEqual(externalize_workload_type("LUCAS_PV_SCALING"), "scaling.v1")
        self.assertEqual(normalize_workload_type("LUCAS_PV_SCALING"), "LUCAS_PV_SCALING")

    def test_request_accepts_legacy_and_emits_sealed(self) -> None:
        req = WorkloadRequest(
            payload_bytes=b'{"index":3}',
            workload_type="LUCAS_PV_SCALING",
            tenant_id="tenant-test",
        )
        self.assertEqual(req.workload_type, WorkloadType.SCALING_V1.value)
        self.assertEqual(req.internal_workload_type(), "LUCAS_PV_SCALING")


class HarnessTests(unittest.TestCase):
    def test_same_seed_byte_identical_evidence(self) -> None:
        harness = QualificationHarness()
        first = harness.qualify("LUCAS_PV_SCALING", seed=7)
        second = harness.qualify("LUCAS_PV_SCALING", seed=7)
        self.assertEqual(first.evidence_hash, second.evidence_hash)
        self.assertEqual(first.audit_transcript, second.audit_transcript)
        self.assertEqual(
            json.dumps(first.public_view, sort_keys=True),
            json.dumps(second.public_view, sort_keys=True),
        )
        self.assertEqual(first.tier, Tier.GEOMETRIC)

    def test_degraded_class_drops_tier(self) -> None:
        harness = QualificationHarness()
        clean = harness.qualify("LUCAS_PV_SCALING", seed=7, degrade=False)
        degraded = harness.qualify("LUCAS_PV_SCALING", seed=7, degrade=True)
        self.assertEqual(clean.tier, Tier.GEOMETRIC)
        self.assertEqual(degraded.tier, Tier.STATISTICAL)
        self.assertNotEqual(clean.evidence_hash, degraded.evidence_hash)
        # Envelope bounds are larger under degradation.
        clean_terminal = float(clean.contract.residual_bound_by_size[-1][1])
        degraded_terminal = float(degraded.contract.residual_bound_by_size[-1][1])
        self.assertGreater(degraded_terminal, clean_terminal)

    def test_transcript_tamper_detected(self) -> None:
        harness = QualificationHarness()
        result = harness.qualify("LUCAS_PV_SCALING", seed=11)
        self.assertTrue(verify_transcript_integrity(result.audit_transcript))
        tampered = dict(result.audit_transcript)
        tampered["residuals"] = list(tampered["residuals"])
        tampered["residuals"][0] = "999.0"
        self.assertFalse(verify_transcript_integrity(tampered))

    def test_public_view_has_no_mechanism_tokens(self) -> None:
        harness = QualificationHarness()
        result = harness.qualify("LUCAS_PV_SCALING", seed=3)
        payload = json.dumps(result.public_decision_fields())
        self.assertEqual(find_banned_tokens(payload), [])
        # Audit keeps provenance.
        self.assertIn("L_n", result.audit_transcript["internal_identities"]["sequence"])

    def test_envelope_violation_suspends_tier(self) -> None:
        harness = QualificationHarness()
        clean = harness.qualify("LUCAS_PV_SCALING", seed=5)

        class InflatingHarness(QualificationHarness):
            def qualify(self, *args, **kwargs):
                result = super().qualify(*args, **kwargs)
                # Inflate residual bounds beyond the contracted envelope.
                inflated = tuple(
                    (size, format(float(bound) * 10.0, "f"))
                    for size, bound in result.contract.residual_bound_by_size
                )
                from chronus.qualification.tiers import TIER_CONTRACT_VERSION, TierContract

                return type(result)(
                    tier=result.tier,
                    contract=TierContract(
                        tier=result.tier,
                        tier_contract_version=TIER_CONTRACT_VERSION,
                        residual_bound_by_size=inflated,
                        qualification_evidence_hash=result.evidence_hash + "x",
                        suspended=False,
                    ),
                    evidence_hash=result.evidence_hash + "x",
                    audit_transcript=result.audit_transcript,
                    public_view=result.public_view,
                    economics=result.economics,
                )

        # Re-verify against a fresh run of the original harness after mutating
        # the stored bounds downward so the fresh run exceeds them.
        tight = harness.qualify("LUCAS_PV_SCALING", seed=5)
        from chronus.qualification.tiers import TIER_CONTRACT_VERSION, TierContract

        tightened_bounds = tuple(
            (size, format(max(float(bound) * 1e-9, 0.0), "f"))
            for size, bound in tight.contract.residual_bound_by_size
        )
        tight_contract_result = type(tight)(
            tier=tight.tier,
            contract=TierContract(
                tier=tight.tier,
                tier_contract_version=TIER_CONTRACT_VERSION,
                residual_bound_by_size=tightened_bounds,
                qualification_evidence_hash=tight.evidence_hash,
                suspended=False,
            ),
            evidence_hash=tight.evidence_hash,
            audit_transcript=tight.audit_transcript,
            public_view=tight.public_view,
            economics=tight.economics,
        )
        suspended = harness.reverify_contract(tight_contract_result)
        self.assertTrue(suspended.suspended)
        self.assertEqual(suspended.tier, Tier.SUSPENDED)


class InternalIdentityTests(unittest.TestCase):
    def test_lucas_fibonacci_cross_check(self) -> None:
        for n in range(2, 60):
            self.assertEqual(
                lucas_recurrence(n),
                fibonacci_fast(n - 1) + fibonacci_fast(n + 1),
            )

    def test_float64_boundary_near_73(self) -> None:
        phi = (1.0 + math.sqrt(5.0)) / 2.0
        psi = (1.0 - math.sqrt(5.0)) / 2.0
        # Well below the float64 useful boundary, residual stays tiny.
        n_ok = 40
        exact_ok = lucas_recurrence(n_ok)
        approx_ok = phi**n_ok + psi**n_ok
        self.assertLess(abs(exact_ok - approx_ok), 1e-4)
        # Near n~73 float proxy loses exact agreement (documented boundary).
        n_edge = 73
        exact_edge = lucas_recurrence(n_edge)
        approx_edge = phi**n_edge + psi**n_edge
        self.assertGreater(abs(exact_edge - approx_edge), abs(exact_ok - approx_ok))
        self.assertGreater(abs(exact_edge - approx_edge), 1.0)


if __name__ == "__main__":
    unittest.main()
