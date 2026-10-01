import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from al_haras.claim_register import Claim
from al_haras.claim_register import ClaimRegister
from al_haras.claim_register import ClaimRejected
from al_haras.claim_register import ClaimStatus
from al_haras.conformance import Backend
from al_haras.conformance import BackendDivergence
from al_haras.conformance import run_all_backends
from al_haras.envelope import FoldMode
from al_haras.envelope import build_envelope
from al_haras.envelope import replace
from al_haras.envelope import verify_envelope
from al_haras.no_float_guard import FloatForbidden
from al_haras.no_float_guard import scan_paths
from al_haras.promotion_gates import DEFINITIONS
from al_haras.promotion_gates import PromotionState
from al_haras.promotion_gates import evaluate_gate
from al_haras.refuted_claims import ClaimRefuted
from al_haras.refuted_claims import assert_claims

KEY = b"e" * 32


def envelope(**changes):
    values = dict(
        payload={"ok": True},
        object_id="o",
        tenant="t",
        instance="i",
        fold_family="rational",
        fold_mode=FoldMode.PRESERVE,
        rehydration_count=0,
        residual=None,
        cassini_ok=True,
        zeckendorf_ok=True,
        chain_head="head",
        witness_receipt_id="receipt",
        backend_certificate="cert",
        backend_name="python",
        bytes_moved=1,
        proof_bytes=2,
        latency_ms=None,
        energy_joules=None,
        verdict={"signature": "valid"},
    )
    values.update(changes)
    return build_envelope(signing_key=KEY, **values)


def verify(env):
    return verify_envelope(
        env,
        signing_key=KEY,
        verdict_verifier=lambda v: v.get("signature") == "valid",
        witness_verifier=lambda r, h: (r, h) == ("receipt", "head"),
        backend_verifier=lambda c, b: (c, b) == ("cert", "python"),
    )


class PromotionEvidenceTests(unittest.TestCase):
    def test_every_subsystem_contract_can_be_evaluated(self):
        for name, definition in DEFINITIONS.items():
            evidence = {r: True for r in definition.requirements[PromotionState.CONTRACTED]}
            result = evaluate_gate(name, PromotionState.CONTRACTED, evidence)
            self.assertTrue(result.passed, name)
            self.assertEqual(result.achieved, PromotionState.CONTRACTED)

    def test_missing_evidence_blocks_and_pilot_requires_rollback(self):
        self.assertFalse(evaluate_gate("guardian", PromotionState.VERIFIED, {}).passed)
        definition = DEFINITIONS["guardian"]
        evidence = {
            r: True
            for s, rs in definition.requirements.items()
            if s <= PromotionState.PILOT
            for r in rs
        }
        self.assertFalse(evaluate_gate("guardian", PromotionState.PILOT, evidence).passed)
        self.assertTrue(
            evaluate_gate(
                "guardian", PromotionState.PILOT, evidence, rollback_evidence=("rollback-envelope",)
            ).passed
        )

    def test_envelope_verification_and_tamper(self):
        env = envelope()
        self.assertTrue(verify(env))
        self.assertFalse(verify(replace(env, bytes_moved=9)))
        with self.assertRaises(ValueError):
            envelope(fold_mode=FoldMode.REHYDRATE, rehydration_count=0)

    def test_claim_register_requires_evidence_and_review(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            self.addCleanup(os.unlink, f.name)
            reg = ClaimRegister(f.name, lambda eid: eid == "env-ok")
            with self.assertRaises(ClaimRejected):
                reg.register(Claim("c", "claim", ClaimStatus.VERIFIED, (), "owner"))
            reg.register(Claim("c", "claim", ClaimStatus.VERIFIED, ("env-ok",), "owner"))
            self.assertEqual(reg.section_status(("c",)), ClaimStatus.VERIFIED)
            with self.assertRaises(ClaimRejected):
                reg.register(Claim("p", "prod", ClaimStatus.PRODUCTION, ("env-ok",), "owner"))
            reg.close()

    def test_refuted_claims_enforced(self):
        with self.assertRaises(ClaimRefuted):
            assert_claims("We assert PULVINI is compression")
        assert_claims("PULVINI is a reversible exact pair transform")

    def test_no_float_guard(self):
        with tempfile.TemporaryDirectory() as d:
            exact = Path(d) / "exact.py"
            exact.write_text("from fractions import Fraction\nx=Fraction(1,3)\n")
            self.assertEqual(len(scan_paths([exact])), 1)
            exact.write_text("x=1.25\n")
            with self.assertRaises(FloatForbidden):
                scan_paths([exact])
            exact.write_text(
                "def exact(x):\n if isinstance(x,float): raise TypeError('exact input required')\n return x\n"
            )
            self.assertEqual(len(scan_paths([exact])), 1)

    def test_conformance_requires_alignment(self):
        a = Backend("a", lambda k, v: (k, v))
        b = Backend("b", lambda k, v: (k, v))
        self.assertEqual(run_all_backends((a, b), (("fibonacci", 15),)), 1)
        with self.assertRaises(BackendDivergence):
            run_all_backends((a, Backend("bad", lambda k, v: None)), (("fibonacci", 15),))


if __name__ == "__main__":
    unittest.main()
