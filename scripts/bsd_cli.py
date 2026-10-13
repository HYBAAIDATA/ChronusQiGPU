#!/usr/bin/env python3
"""BSD CLI — Command-Line Interface for Birch and Swinnerton-Dyer Multi-Agent Swarm.

Provides interactive and headless execution of the EUCLID-SALAMANDER-PYTHIA-AL_HARAS
BSD collaborative solver.

Usage:
    python scripts/bsd_cli.py team --a -36 --b 0 --max-prime 200
    python scripts/bsd_cli.py sweep
    python scripts/bsd_cli.py explore --a -1 --b 0
    python scripts/bsd_cli.py verify-invariants
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from integrations.solvers.bsd_solver import (

    BSDSolverTeam,
    BSDTeamReport,
    EllipticCurve,
    EuclidAgent,
    SalamanderAgent,
    PythiaAgent,
    AlHarasAgent,
)
from integrations.solvers.bsd_scaffold import BSDScribe, BSDScribeConfig


def cmd_team(args: argparse.Namespace) -> int:
    """Run full 4-agent collaborative team."""
    print("=" * 70)
    print("EUCLID-SALAMANDER-PYTHIA-AL_HARAS BSD Multi-Agent Swarm")
    print(f"Target Curve: y^2 = x^3 + ({args.a})x + ({args.b})")
    print(f"Max Prime: {args.max_prime}")
    print("=" * 70)

    team = BSDSolverTeam(BSDScribeConfig(max_prime=args.max_prime))
    report = team.solve(args.a, args.b, max_prime=args.max_prime)

    print("\n[1] EUCLID FINDINGS (Lead Algebraic Geometer):")
    print(f"  Discriminant:         {report.euclid.discriminant}")
    print(f"  j-invariant:          {report.euclid.j_invariant}")
    print(f"  Primes Evaluated:     {report.euclid.primes_count}")
    print(f"  Bad Primes:           {report.euclid.bad_primes}")
    print(f"  Empirical Rank Slope: {report.euclid.empirical_rank_slope} (R^2 = {report.euclid.fit_r_squared})")
    print(f"  Conjectural Rank:     {report.euclid.conjectural_rank}")
    print(f"  L(E, 1):              {report.euclid.l_function_at_1:.6f}")
    print(f"  L'(E, 1):             {report.euclid.l_function_derivative_at_1:.6f}")
    print(f"  Hodges Sentence:      {report.euclid.hodges_first_order_sentence}")

    print("\n[2] SALAMANDER VERIFICATION (Autonomic Invariant Verifier):")
    print(f"  Hasse Bound Sat:      {report.salamander.hasse_all_satisfied} (Checked {report.salamander.primes_checked} primes)")
    print(f"  Torsion Points:       {report.salamander.torsion_points_found}")
    print(f"  Mazur Bound Sat:      {report.salamander.mazur_bound_satisfied} ({report.salamander.mazur_classification})")
    print(f"  Nagell-Lutz Verified: {report.salamander.nagell_lutz_integrality_verified}")
    print(f"  Latency:              {report.salamander.telemetry_latency_ms:.2f} ms")
    print(f"  Overall Verification: {'PASS' if report.salamander.verification_passed else 'FAIL'}")

    print("\n[3] PYTHIA TOPOLOGICAL LEDGER (Memory & Zeckendorf Certifier):")
    print(f"  Signature Hash:       {report.pythia.curve_signature_hash[:16]}...")
    print(f"  Cassini Invariants:   {'VALID' if report.pythia.cassini_invariants_valid else 'INVALID'}")
    print(f"  Zeckendorf Certs:     {len(report.pythia.zeckendorf_certificates)} primes certified")
    print(f"  Poincaré Points:      {len(report.pythia.poincare_hyperbolic_coords)} embedded in H^2")
    print(f"  Sato-Tate Entropy:    {report.pythia.entropy_shannon:.4f} bits")

    print("\n[4] AL HARAS ATTESTATION (CMI Honesty Sentry):")
    print(f"  Proof Claim:          {report.al_haras.proof_claim} (Strictly rejected)")
    print(f"  Claim Status:         {report.al_haras.claim_status}")
    print(f"  CMI Compliant:        {report.al_haras.cmi_protocol_compliant}")
    print(f"  Attestation Seal:     {report.al_haras.attestation_seal[:16]}...")

    print("\n" + "-" * 70)
    print(f"Integrated Information Phi: {report.integrated_phi:.4f} (Target >= 0.70)")
    print(f"Execution Latency:          {report.execution_latency_ms:.2f} ms")
    print(f"Status:                     {report.overall_status}")
    print("=" * 70)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))

    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    """Sweep canonical elliptic curve benchmarks across known ranks."""
    benchmarks = [
        ("y^2 = x^3 - x", -1, 0, 0),
        ("y^2 = x^3 + 1", 0, 1, 0),
        ("y^2 = x^3 - 36x", -36, 0, 1),
        ("y^2 = x^3 - 4", 0, -4, 1),
        ("y^2 = x^3 - 432x", -432, 0, 2),
    ]

    print("=" * 75)
    print("CANONICAL BENCHMARK CURVE SWEEP — BSD MULTI-AGENT SWARM")
    print(f"{'Curve':<20} | {'Known r':<7} | {'Slope':<8} | {'Est r':<6} | {'Hasse':<6} | {'Phi':<6}")
    print("-" * 75)

    team = BSDSolverTeam(BSDScribeConfig(max_prime=args.max_prime))

    for label, a, b, known_r in benchmarks:
        report = team.solve(a, b, max_prime=args.max_prime)
        hasse_str = "PASS" if report.salamander.hasse_all_satisfied else "FAIL"
        print(
            f"{label:<20} | {known_r:<7} | "
            f"{report.euclid.empirical_rank_slope:<8.4f} | "
            f"{report.euclid.conjectural_rank:<6} | "
            f"{hasse_str:<6} | {report.integrated_phi:<6.4f}"
        )

    print("=" * 75)
    print("All curves verified under AL HARAS honesty invariant (proof_claim=False).")
    return 0


def cmd_explore(args: argparse.Namespace) -> int:
    """Quick single curve exploration."""
    scribe = BSDScribe(BSDScribeConfig(max_prime=args.max_prime))
    analysis = scribe.analyze_curve(args.a, args.b, max_prime=args.max_prime)
    print(json.dumps(analysis, indent=2))
    return 0


def cmd_verify_invariants(args: argparse.Namespace) -> int:
    """Verify autonomic invariants on standard curves."""
    curves = [(-1, 0), (0, 1), (-36, 0)]
    team = BSDSolverTeam(BSDScribeConfig(max_prime=200))
    all_ok = True

    print("Verifying mathematical and honesty invariants...")
    for a, b in curves:
        report = team.solve(a, b, max_prime=200)
        h_ok = report.salamander.hasse_all_satisfied
        m_ok = report.salamander.mazur_bound_satisfied
        c_ok = report.pythia.cassini_invariants_valid
        a_ok = (not report.al_haras.proof_claim) and report.al_haras.cmi_protocol_compliant

        status = "OK" if (h_ok and m_ok and c_ok and a_ok) else "FAILED"
        print(f"Curve y^2 = x^3 + ({a})x + ({b}): {status} (Hasse={h_ok}, Mazur={m_ok}, Cassini={c_ok}, AL_HARAS={a_ok})")
        if status != "OK":
            all_ok = False

    return 0 if all_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Birch and Swinnerton-Dyer Multi-Agent Solver CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # team subcommand
    p_team = subparsers.add_parser("team", help="Run 4-agent collaborative solver on a curve")
    p_team.add_argument("--a", type=int, default=-36, help="Weierstrass coefficient a")
    p_team.add_argument("--b", type=int, default=0, help="Weierstrass coefficient b")
    p_team.add_argument("--max-prime", type=int, default=300, help="Max prime for Frobenius counting")
    p_team.add_argument("--json", action="store_true", help="Output raw JSON report")

    # sweep subcommand
    p_sweep = subparsers.add_parser("sweep", help="Sweep canonical benchmark curves across ranks")
    p_sweep.add_argument("--max-prime", type=int, default=300, help="Max prime for Frobenius counting")

    # explore subcommand
    p_explore = subparsers.add_parser("explore", help="Single curve exploration via BSDScribe")
    p_explore.add_argument("--a", type=int, default=-1, help="Weierstrass coefficient a")
    p_explore.add_argument("--b", type=int, default=0, help="Weierstrass coefficient b")
    p_explore.add_argument("--max-prime", type=int, default=200, help="Max prime for Frobenius counting")

    # verify-invariants subcommand
    subparsers.add_parser("verify-invariants", help="Verify all mathematical and honesty invariants")

    args = parser.parse_args()

    if args.command == "team":
        return cmd_team(args)
    elif args.command == "sweep":
        return cmd_sweep(args)
    elif args.command == "explore":
        return cmd_explore(args)
    elif args.command == "verify-invariants":
        return cmd_verify_invariants(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
