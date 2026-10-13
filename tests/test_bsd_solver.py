"""Tests for Birch and Swinnerton-Dyer (BSD) Multi-Agent Solver Team.

Validates the complete 4-agent collaborative system:
- EUCLID: Conjectural reasoning, Frobenius traces, Euler product slope, Hodges sentences.
- SALAMANDER: Autonomic invariant verification (Hasse bounds, Mazur torsion bounds, Nagell-Lutz).
- PYTHIA: Zeckendorf certificates, Cassini invariants, Poincaré disk embeddings.
- AL HARAS: Claim honesty sentry (proof_claim == False, CMI protocol enforcement).
"""

import math
from fractions import Fraction
import pytest

from integrations.solvers.bsd_scaffold import (
    EllipticCurve,
    EllipticCurvePoint,
    BSDScribe,
    BSDScribeConfig,
)
from integrations.solvers.bsd_solver import (
    BSDSolverTeam,
    BSDTeamReport,
    EuclidAgent,
    SalamanderAgent,
    PythiaAgent,
    AlHarasAgent,
    HonestyBoundaryViolation,
)
from integrations.agi_external import ExternalAGI
from kellogg.scales import cassini, zeckendorf, zeckendorf_is_legal


class TestEllipticCurveArithmetic:
    """Validate exact Weierstrass curve arithmetic and group law."""

    def test_point_addition_and_doubling(self):
        # Curve y^2 = x^3 - 36x (rank 1 curve)
        # Point P = (-3, 9): (-3)^3 - 36*(-3) = -27 + 108 = 81 = 9^2
        curve = EllipticCurve(-36, 0)
        p1 = EllipticCurvePoint(Fraction(-3), Fraction(9))
        assert curve.contains(p1)

        # Doubling P
        p2 = curve.double(p1)
        assert curve.contains(p2)
        assert not p2.is_infinity
        # 2P = (25/4, -35/8)
        assert p2.x == Fraction(25, 4)
        assert p2.y == Fraction(-35, 8)

        # Identity
        inf = EllipticCurvePoint.infinity()
        assert curve.add(p1, inf) == p1
        assert curve.add(inf, p1) == p1

    def test_discriminant_and_j_invariant(self):
        # y^2 = x^3 - x: a = -1, b = 0
        # Delta = -16 * (4*(-1)^3 + 27*0) = -16 * (-4) = 64
        curve = EllipticCurve(-1, 0)
        assert curve.discriminant == 64
        assert curve.j_invariant == 1728.0

        # Singular curve raises ValueError
        with pytest.raises(ValueError, match="Singular curve"):
            EllipticCurve(0, 0)


class TestSalamanderInvariantVerifier:
    """Validate SALAMANDER autonomic invariant verification."""

    def test_hasse_bounds_across_primes(self):
        # Hasse theorem: |a_p| <= 2 sqrt(p) for all good primes p
        team = BSDSolverTeam(BSDScribeConfig(max_prime=150))
        report = team.solve(-36, 0, max_prime=150)
        assert report.salamander.hasse_all_satisfied is True
        assert report.salamander.primes_checked > 25

    def test_mazur_torsion_bounds(self):
        # y^2 = x^3 - x has 4 torsion points: (0,0), (1,0), (-1,0), O
        team = BSDSolverTeam()
        report = team.solve(-1, 0, max_prime=100)
        assert report.salamander.torsion_points_found == 4
        assert report.salamander.mazur_bound_satisfied is True
        assert "Z/4Z or Z/2Z x Z/2Z" in report.salamander.mazur_classification
        assert report.salamander.nagell_lutz_integrality_verified is True


class TestEuclidConjecturalReasoner:
    """Validate EUCLID conjectural reasoning and rank slopes."""

    def test_empirical_rank_slope_rank_1(self):
        # y^2 = x^3 - 36x has rank 1
        team = BSDSolverTeam(BSDScribeConfig(max_prime=200))
        report = team.solve(-36, 0, max_prime=200)
        # Empirical rank slope should be close to 1.0
        assert report.euclid.empirical_rank_slope > 0.6
        assert report.euclid.conjectural_rank == 1

    def test_empirical_rank_slope_rank_0(self):
        # y^2 = x^3 - x has rank 0
        team = BSDSolverTeam(BSDScribeConfig(max_prime=200))
        report = team.solve(-1, 0, max_prime=200)
        # Empirical rank slope should be small (< 0.5)
        assert report.euclid.empirical_rank_slope < 0.5
        assert report.euclid.conjectural_rank == 0

    def test_hodges_first_order_sentence(self):
        team = BSDSolverTeam()
        report = team.solve(-36, 0, max_prime=100)
        stmt = report.euclid.hodges_first_order_sentence
        assert "forall x, y in Q" in stmt
        assert "rank(E(Q)) == ord_{s=1}(L(E, s))" in stmt


class TestPythiaTopologicalLedger:
    """Validate PYTHIA Zeckendorf certificates, Cassini invariants, and embeddings."""

    def test_zeckendorf_certificates_are_legal(self):
        team = BSDSolverTeam(BSDScribeConfig(max_prime=150))
        report = team.solve(-36, 0, max_prime=150)
        certs = report.pythia.zeckendorf_certificates
        assert len(certs) > 0
        for cert in certs:
            assert cert["is_legal_decomposition"] is True
            assert zeckendorf_is_legal(cert["indices"]) is True

    def test_cassini_unimodular_invariant(self):
        team = BSDSolverTeam()
        report = team.solve(-36, 0, max_prime=100)
        assert report.pythia.cassini_invariants_valid is True

    def test_poincare_disk_containment(self):
        team = BSDSolverTeam(BSDScribeConfig(max_prime=150))
        report = team.solve(-36, 0, max_prime=150)
        coords = report.pythia.poincare_hyperbolic_coords
        assert len(coords) > 0
        for pt in coords:
            assert pt["norm"] < 1.0  # Must be strictly inside unit disk


class TestAlHarasClaimHonestySentry:
    """Validate AL HARAS honesty sentry and boundary compliance."""

    def test_proof_claim_strictly_false(self):
        team = BSDSolverTeam()
        report = team.solve(-36, 0, max_prime=100)
        assert report.al_haras.proof_claim is False
        assert report.al_haras.claim_status == "CONJECTURE_EXPLORATION"
        assert report.al_haras.cmi_protocol_compliant is True
        assert len(report.al_haras.attestation_seal) == 64

    def test_forbidden_claim_raises_violation(self):
        # Direct audit with illegal phrase
        sentry = AlHarasAgent()
        team = BSDSolverTeam()
        report = team.solve(-1, 0, max_prime=50)

        # Inject forbidden term into findings
        corrupted = report.euclid
        corrupted.status = "PROVEN THE BSD CONJECTURE"

        with pytest.raises(HonestyBoundaryViolation, match="Forbidden proof assertion"):
            sentry.audit(corrupted, report.salamander, report.pythia)


class TestFullSwarmAndExternalAGI:
    """Validate full swarm coordination and external surface."""

    def test_integrated_information_phi(self):
        team = BSDSolverTeam(BSDScribeConfig(max_prime=150))
        report = team.solve(-36, 0, max_prime=150)
        assert report.integrated_phi >= 0.70
        assert report.overall_status == "VERIFIED_CONJECTURE_SCHEDULE"

    def test_external_agi_explore_bsd_team(self):
        agi = ExternalAGI()
        result = agi.explore_bsd_team(a=-36, b=0, max_prime=150)
        assert result["al_haras"]["proof_claim"] is False
        assert result["salamander"]["verification_passed"] is True
        assert result["integrated_phi"] >= 0.70
        assert result["overall_status"] == "VERIFIED_CONJECTURE_SCHEDULE"
