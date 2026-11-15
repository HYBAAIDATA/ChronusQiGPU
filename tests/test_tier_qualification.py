"""QualificationHarness, seal gate, and internal identity regressions."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronus.core.seal import assert_sealed, find_banned_tokens  # noqa: E402
from chronus.core.workload_alias import (  # noqa: E402
    externalize_scaling_result,
    externalize_workload_type,
    normalize_workload_type,
)
from chronus.math.binet_lucas import fibonacci_fast, lucas_recurrence  # noqa: E402
from chronus.qualification import QualificationHarness  # noqa: E402
from chronus.qualification.harness import (  # noqa: E402
    _residual,
    _sha256_hex,
    verify_transcript_integrity,
)
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

    def test_default_workload_type_normalizes_to_backend_value(self) -> None:
        req = WorkloadRequest(payload_bytes=b'{"index":1}', tenant_id="tenant-test")
        self.assertEqual(req.workload_type, WorkloadType.EXACT_Q5_ALGEBRAIC.value)
        self.assertEqual(req.internal_workload_type(), "EXACT_Q5_ALGEBRAIC")
        # Enum instance must not stringify as "WorkloadType.EXACT_Q5_ALGEBRAIC".
        self.assertEqual(
            normalize_workload_type(WorkloadType.EXACT_Q5_ALGEBRAIC),
            "EXACT_Q5_ALGEBRAIC",
        )

    def test_pointer_operation_alias_survives_uppercasing(self) -> None:
        from chronus.core.workload_alias import normalize_pointer_operation

        self.assertEqual(normalize_pointer_operation("scaling.v1"), "LUCAS_PV_SCALING")
        self.assertEqual(normalize_pointer_operation("SCALING.V1"), "LUCAS_PV_SCALING")
        self.assertEqual(normalize_pointer_operation("pv_lattice_fold"), "PV_LATTICE_FOLD")


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
        self.assertEqual(first.public_view["qualification_scope"], "reference_model_class")

    def test_localcontext_isolates_decimal_precision(self) -> None:
        from concurrent.futures import ThreadPoolExecutor
        from decimal import ROUND_DOWN, Inexact, getcontext, localcontext

        harness = QualificationHarness()
        baseline = harness.qualify("LUCAS_PV_SCALING", seed=7).evidence_hash

        def worker() -> str:
            getcontext().prec = 28  # hostile caller/thread context
            return QualificationHarness().qualify("LUCAS_PV_SCALING", seed=7).evidence_hash

        with ThreadPoolExecutor(max_workers=1) as pool:
            other = pool.submit(worker).result()
        self.assertEqual(baseline, other)

        with localcontext() as ctx:
            ctx.rounding = ROUND_DOWN
            ctx.traps[Inexact] = True
            ctx.prec = 28
            hostile = harness.qualify("LUCAS_PV_SCALING", seed=7).evidence_hash
        self.assertEqual(baseline, hostile)

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
                    (size, format(Decimal(bound) * Decimal(10), "f"))
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
            (size, format(max(Decimal(bound) * Decimal("1e-9"), Decimal(0)), "f"))
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
        self.assertTrue(suspended.contract.suspended)
        self.assertEqual(suspended.tier, Tier.SUSPENDED)
        self.assertEqual(
            suspended.evidence_hash, suspended.audit_transcript["evidence_hash"]
        )
        self.assertEqual(suspended.audit_transcript["decision"], Tier.SUSPENDED.value)
        self.assertEqual(suspended.audit_transcript["reason"], "envelope_violation")
        self.assertIn("breached", suspended.audit_transcript)
        self.assertTrue(verify_transcript_integrity(suspended.audit_transcript))
        # Sticky: re-verifying a suspended result must not clear it.
        still = harness.reverify_contract(suspended)
        self.assertTrue(still.contract.suspended)
        self.assertEqual(still.evidence_hash, suspended.evidence_hash)


class ForgeryAndPrecisionTests(unittest.TestCase):
    def test_recomputed_hash_forgery_rejected(self) -> None:
        result = QualificationHarness().qualify("LUCAS_PV_SCALING", seed=11)
        forged = dict(result.audit_transcript)
        forged["residuals"] = list(forged["residuals"])
        forged["residuals"][0] = "999.0"
        body = {k: v for k, v in forged.items() if k not in ("evidence_hash", "signature")}
        forged["evidence_hash"] = _sha256_hex(body)
        self.assertFalse(verify_transcript_integrity(forged))

    def test_signature_only_alteration_rejected(self) -> None:
        result = QualificationHarness().qualify("LUCAS_PV_SCALING", seed=11)
        altered = dict(result.audit_transcript)
        altered["signature"] = "00" * 64
        self.assertFalse(verify_transcript_integrity(altered))
        missing = {k: v for k, v in result.audit_transcript.items() if k != "signature"}
        self.assertFalse(verify_transcript_integrity(missing))

    def test_custom_signer_verifies_with_matching_verifier(self) -> None:
        from chronus.security.signers import Ed25519Signer

        custom = Ed25519Signer()
        result = QualificationHarness().qualify(
            "LUCAS_PV_SCALING", seed=17, signer=custom.sign
        )
        self.assertFalse(verify_transcript_integrity(result.audit_transcript))
        self.assertTrue(
            verify_transcript_integrity(
                result.audit_transcript, verifier=custom.verify
            )
        )

    def test_tampered_recalled_transcript_suspends_attach(self) -> None:
        from chronus.qualification.transcript_store import clear, remember
        from chronus.service.models import WorkloadStatus
        from chronus.service.routers.workloads import _attach_tier_fields

        clear()
        clean = QualificationHarness().qualify("LUCAS_PV_SCALING", seed=19)
        tampered_audit = dict(clean.audit_transcript)
        tampered_audit["signature"] = "00" * 64
        tampered = type(clean)(
            tier=clean.tier,
            contract=clean.contract,
            evidence_hash=clean.evidence_hash,
            audit_transcript=tampered_audit,
            public_view=clean.public_view,
            economics=clean.economics,
        )
        remember(tampered)
        fields = _attach_tier_fields("scaling.v1", status=WorkloadStatus.COMPLETED)
        self.assertTrue(fields["tier_suspended"])
        self.assertEqual(fields["tier"], Tier.SUSPENDED.value)
        clear()

    def test_attach_includes_submission_index_in_probes(self) -> None:
        from chronus.qualification.transcript_store import clear
        from chronus.service.models import WorkloadStatus
        from chronus.service.routers.workloads import _attach_tier_fields

        clear()
        sealed = {
            "backend": "python-math-reference",
            "result": {"family": "scaling.v1", "index": 10, "sequence_value": "123"},
        }
        fields = _attach_tier_fields(
            "scaling.v1", status=WorkloadStatus.COMPLETED, result=sealed
        )
        self.assertTrue(fields["metadata_submission_index_probed"])
        sizes = [point["size"] for point in fields["envelope"]["residual_bound"]]
        self.assertIn(10, sizes)
        clear()

    def test_suspended_class_stays_suspended_across_jobs(self) -> None:
        from chronus.qualification.transcript_store import clear, remember
        from chronus.service.models import WorkloadStatus
        from chronus.service.routers.workloads import _attach_tier_fields

        clear()
        harness = QualificationHarness()
        tight = harness.qualify("LUCAS_PV_SCALING", seed=5)
        from chronus.qualification.tiers import TIER_CONTRACT_VERSION, TierContract

        tightened = type(tight)(
            tier=tight.tier,
            contract=TierContract(
                tier=tight.tier,
                tier_contract_version=TIER_CONTRACT_VERSION,
                residual_bound_by_size=tuple(
                    (size, format(Decimal(bound) * Decimal("1e-9"), "f"))
                    for size, bound in tight.contract.residual_bound_by_size
                ),
                qualification_evidence_hash=tight.evidence_hash,
                suspended=False,
            ),
            evidence_hash=tight.evidence_hash,
            audit_transcript=tight.audit_transcript,
            public_view=tight.public_view,
            economics=tight.economics,
        )
        remember(tightened)
        first = _attach_tier_fields("scaling.v1", status=WorkloadStatus.COMPLETED)
        self.assertTrue(first["tier_suspended"])
        second = _attach_tier_fields(
            "scaling.v1",
            status=WorkloadStatus.COMPLETED,
            result={
                "result": {"family": "scaling.v1", "index": 10, "sequence_value": "123"}
            },
        )
        self.assertTrue(second["tier_suspended"])
        self.assertEqual(second["tier"], Tier.SUSPENDED.value)
        clear()

    def test_large_probe_residual_is_accurate(self) -> None:
        n = 500
        with localcontext() as ctx:
            ctx.prec = 1200
            beta = (Decimal(1) - Decimal(5).sqrt()) / Decimal(2)
            reference = abs(beta) ** n
        measured = _residual(n)
        self.assertGreater(measured, 0)
        self.assertLess(abs(measured - reference), reference * Decimal("1e-60"))
        result = QualificationHarness().qualify(
            "LUCAS_PV_SCALING", seed=13, sizes=(300, 400, 500)
        )
        self.assertEqual(result.contract.residual_bound_by_size[-1][0], 500)


class ScalingResultSealTests(unittest.TestCase):
    def test_scaling_result_is_sealed(self) -> None:
        from chronus.execution.reference import NativeMathReferenceBackend

        raw = NativeMathReferenceBackend().execute(b'{"index":10}', "scaling.v1")
        sealed = externalize_scaling_result({"backend": "x", "result": raw})
        payload = json.dumps(sealed)
        self.assertEqual(find_banned_tokens(payload), [])
        self.assertEqual(sealed["result"]["family"], "scaling.v1")
        self.assertEqual(sealed["result"]["sequence_value"], str(lucas_recurrence(10)))

    def test_already_sealed_adapter_result_keeps_index(self) -> None:
        sealed_in = {
            "backend": "adapter",
            "result": {
                "family": "scaling.v1",
                "index": 10,
                "sequence_value": "123",
                "companion_value": "55",
                "identity_verified": True,
            },
        }
        sealed = externalize_scaling_result(sealed_in)
        self.assertEqual(sealed["result"]["index"], 10)
        self.assertEqual(sealed["result"]["sequence_value"], "123")
        self.assertEqual(find_banned_tokens(json.dumps(sealed)), [])

    def test_envelope_declares_discrete_scope(self) -> None:
        result = QualificationHarness().qualify("LUCAS_PV_SCALING", seed=3)
        self.assertEqual(result.public_view["envelope"]["scope"], "discrete_probe_sizes")

    def test_inventory_workloads_are_externalized(self) -> None:
        from chronus.execution import execution_router
        from chronus.execution.qigpu import QiGPUOrchestrator

        inventory = QiGPUOrchestrator(execution_router).inventory()
        payload = json.dumps(inventory)
        self.assertEqual(find_banned_tokens(payload), [])
        workloads = {
            name
            for surface in inventory["surfaces"]
            for name in surface["workloads"]
        }
        self.assertIn("scaling.v1", workloads)
        self.assertNotIn("LUCAS_PV_SCALING", workloads)

    def test_al_haras_self_tests_are_sealed(self) -> None:
        from chronus.security.al_haras.topological_os import public_self_tests

        sealed = public_self_tests()
        payload = json.dumps(sealed)
        self.assertEqual(find_banned_tokens(payload), [])
        self.assertIn("sequence_identity_exact", sealed)
        self.assertNotIn("binet_lucas_identity_exact", sealed)


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
