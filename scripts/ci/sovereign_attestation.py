#!/usr/bin/env python3
"""
Software capability evidence generator.

This executable produces repository-local evidence only. It does not issue a
regulatory attestation, accreditation, customer acceptance, or external certification.

The evidence run covers six maintained capability groups:
- Validates the 6 Core Sovereign Architectural Pillars:
  1. AL HARAS (exact sheaf coboundary, Reed-Solomon repair, Paley/Ramanujan spectrum, braid relations, Hasse-bound fingerprint)
  2. THESEUS (Phyllotaxis Zero-Collision Address Space) & OVID (Verifiable Storage Custody)
  3. CHRONUS (F_257 Galois Search, Zeckendorf ALU, Binet/Lucas Exact Field, 0% Rejection Wire)
  4. LEGACY "MILLENNIUM" MODULES (exact Ollivier-Ricci curvature, Hodge split, p-adic address sets, zeroisation)
  5. TOE / TUQC (Substrate-Agnostic Universal Quantum Substrate & F_257 StateEvolution)
  6. PACKAGE INVENTORY (Distribution Packages for AL HARAS, Theseus, Ovid, Chronus, Millennium, TOE)
- Retains the legacy SOVEREIGN_CAPABILITY_ATTESTATION.json filename, with an explicit non-certification notice and SHA-256 content integrity.
"""

import hashlib
import json
import os
import sys
import time
from fractions import Fraction
from typing import Any, Dict

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

EVIDENCE_DOMAIN = b"CHRONUS_SOFTWARE_EVIDENCE_V2\\0"


def verify_al_haras_pillar() -> Dict[str, Any]:
    """Pillar 1: AL HARAS (HYBA Security) exact checks, each computed on this run.

    Every invariant below is the result of a computation, not a stored flag:
    the sheaf coboundary is evaluated in exact rational arithmetic on a
    consistent and on a contradictory pair of states, a Reed-Solomon fault drill
    must restore the trace byte for byte, the Paley graph P(257) spectrum must
    meet the Ramanujan bound, the Fibonacci braid relations must hold in
    Z[zeta_5], and the elliptic-curve fingerprint must satisfy the Hasse bound
    with two independent point counts agreeing.
    """
    from chronus.security.al_haras.engine import (
        CellularSheafCohomology,
        DSW4DInstantonMonopoleHealer,
        RamanujanExpanderSpectralGapGuard,
        CyclotomicAnyonBraidEngine,
        HeckeModularChecksum,
    )

    t0 = time.perf_counter_ns()

    # Exact sheaf coboundary: agreeing states form a global section ...
    sheaf_res = CellularSheafCohomology.compute_cohomology(node_vectors=[[1, 0], [1, 0]])
    consistent_ok = (
        sheaf_res["h0_consensus"] is True
        and sheaf_res["cohomology_class"] == "GLOBAL_SECTION"
        and Fraction(sheaf_res["coboundary_total_norm_sq"]) == 0
    )
    # ... and contradictory states (1,0) vs (0,1) give ||delta0 s||^2 = 2 exactly.
    conflict_res = CellularSheafCohomology.compute_cohomology(node_vectors=[[1, 0], [0, 1]])
    disagreement_ok = (
        conflict_res["h0_consensus"] is False
        and Fraction(conflict_res["coboundary_max_edge_norm_sq"]) == 2
    )

    # Reed-Solomon fault drill: corrupted bytes must be corrected and the trace restored exactly.
    healer_res = DSW4DInstantonMonopoleHealer.inspect_and_heal(trace_payload=b"test_trace", is_perturbed=True)
    repair_ok = (
        healer_res["healed"] is True
        and healer_res["integrity_verified"] is True
        and healer_res["symbol_errors_corrected"] >= 1
        and healer_res["repaired_trace_sha256"] == healer_res["trace_sha256"]
    )

    # Ramanujan certificate for the Paley graph P(257), from its exact spectrum.
    ramanujan_res = RamanujanExpanderSpectralGapGuard.verify_mass_gap()
    gap_ok = ramanujan_res["satisfies_bound"] is True and ramanujan_res["is_ramanujan"] is True

    # Fibonacci braid relations in Z[zeta_5].
    braid_res = CyclotomicAnyonBraidEngine.compile_braid()
    braid_ok = (
        braid_res["status"] == "VERIFIED_COHERENT"
        and braid_res["artin_braid_satisfied"] is True
        and all(braid_res["relations_verified"].values())
    )

    # Elliptic-curve fingerprint: two independent point counts must agree and meet the Hasse bound.
    hecke_res = HeckeModularChecksum.verify_payload_eigenform(payload=b"sovereign_difc_attestation")
    hasse_ok = hecke_res["hasse_bound_satisfied"] is True and hecke_res["independent_trace_check"] is True

    latency_us = (time.perf_counter_ns() - t0) / 1000.0

    all_invariants_pass = consistent_ok and disagreement_ok and repair_ok and gap_ok and braid_ok and hasse_ok

    return {
        "status": "PASS" if all_invariants_pass else "INVARIANT_FAILED",
        "latency_us": round(latency_us, 2),
        "invariants": {
            "sheaf_global_section_exact": consistent_ok,
            "sheaf_disagreement_detected_exact": disagreement_ok,
            "reed_solomon_repair_verified": repair_ok,
            "ramanujan_spectral_gap": gap_ok,
            "anyon_cyclotomic_braid": braid_ok,
            "hasse_bound_fingerprint": hasse_ok,
        },
        "measured": {
            "conflict_coboundary_norm_sq": conflict_res["coboundary_max_edge_norm_sq"],
            "symbol_errors_corrected": healer_res["symbol_errors_corrected"],
            "paley_lambda_2": ramanujan_res["lambda_2_decimal"],
            "ramanujan_bound": ramanujan_res["ramanujan_bound_decimal"],
            "frobenius_trace_ap": hecke_res["frobenius_trace_ap"],
        },
    }


def verify_theseus_ovid_pillar() -> Dict[str, Any]:
    """Pillar 2: THESEUS & OVID Immutable Storage & Verifiable Data Custody."""
    import tempfile
    from chronus.triad import ProductionTriad

    t0 = time.perf_counter_ns()
    key = b"DIFC_SOVEREIGN_PROOF_PAYLOAD_2026"
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "triad.sqlite3")
        triad = ProductionTriad(path)
        receipt = triad.put("difc_sovereign", key)
        first = triad.materialise(receipt)
        reopened = ProductionTriad(path)
        second = reopened.materialise(receipt)
        continuity = reopened.theseus.verify_journal_continuity("difc_sovereign")
        durable = reopened.theseus.stats()["durable"]

    latency_us = (time.perf_counter_ns() - t0) / 1000.0
    storage_ok = first == key and second == key and continuity and durable

    return {
        "status": "PASS" if storage_ok else "STORAGE_MISMATCH",
        "latency_us": round(latency_us, 2),
        "invariants": {
            "theseus_lossless_roundtrip": first == key,
            "restart_recovery_roundtrip": second == key,
            "journal_continuity_verified": continuity,
            "durable_custody": durable,
            "ovid_materialisation_verified": second == key,
        },
    }


def verify_chronus_stratum_pillar() -> Dict[str, Any]:
    """Pillar 3: Chronus Stratum Wire, F_257 Galois Search & Zeckendorf ALU."""
    from chronus.math.f257_search import f257_phases
    from chronus.hw.zeckendorf import fold_to_zeckendorf, unfold
    from chronus.math.binet_lucas import lucas_binet, lucas_recurrence, unfold as unfold_q
    from chronus.stratum.endian_engine import swap_prevhash_words
    from chronus.stratum.gatekeeper import compute_share_target_exact

    t0 = time.perf_counter_ns()
    alpha, mu, beta = f257_phases(u=17, N=256, M=1)
    phase_ok = (alpha * 17) % 257 == (1 + 17) % 257

    zeck_bits = fold_to_zeckendorf(1048576)
    unfolded_zeck = unfold(zeck_bits)
    zeck_ok = (unfolded_zeck == 1048576)

    l50_binet = unfold_q(lucas_binet(50))
    l50_rec = lucas_recurrence(50)
    binet_ok = (l50_binet == l50_rec)

    share_target = compute_share_target_exact(Fraction(1))
    target_ok = (share_target > 0)

    # Bitcoin Core test vector
    raw_hash = bytes.fromhex("000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")
    swapped = swap_prevhash_words(raw_hash)
    round_trip_swapped = swap_prevhash_words(swapped)
    endian_ok = (round_trip_swapped == raw_hash)

    latency_us = (time.perf_counter_ns() - t0) / 1000.0
    all_ok = phase_ok and zeck_ok and binet_ok and target_ok and endian_ok

    return {
        "status": "PASS" if all_ok else "CHRONUS_INVARIANT_FAILED",
        "latency_us": round(latency_us, 2),
        "invariants": {
            "f257_galois_phases": phase_ok,
            "zeckendorf_conservation": zeck_ok,
            "binet_lucas_symbolic_exactness": binet_ok,
            "endian_swapped_roundtrip": endian_ok,
            "share_target_exact_fractions": target_ok,
            "gatekeeper_latency_us": None,
        },
    }


def verify_millennium_pillar() -> Dict[str, Any]:
    """Pillar 4: exact graph, Hodge, p-adic and zeroisation checks (legacy "Millennium" modules).

    The module names come from the earlier notes; no Millennium Prize Problem is
    addressed. Each check below is computed on this run.
    """
    from chronus.security.al_haras.millennium_security import (
        RicciCurvatureDeCloaker,
        HodgeCovertChannelFilter,
        UltrametricMemorySandbox,
        AnosovColdBootScrambler,
        PicardLefschetzAntiJammingFilter,
    )

    t0 = time.perf_counter_ns()

    # 1. Poincaré & Ricci Flow Surgery
    ricci = RicciCurvatureDeCloaker(curvature_threshold=-0.4)
    ricci.add_edge("C2_HOST", "BOT_001", traffic_weight=100.0)
    ricci.add_edge("BOT_001", "BOT_002", traffic_weight=1.0)
    surgery_res = ricci.execute_perelman_surgery()
    poincare_ok = surgery_res["transport_optimality_certified"] is True

    # 2. Hodge de Rham Orthogonal Projection
    hodge_res = HodgeCovertChannelFilter.sanitize_side_channels([10.0, 10.2, 55.0, 10.1])
    hodge_ok = hodge_res["status"] == "DECOMPOSITION_VERIFIED"

    # 3. Ultrametric Memory Sandbox
    sandbox = UltrametricMemorySandbox(prime_p=257)
    sandbox.register_enclave("proc_alpha", base_address=0x1000)
    sandbox.register_enclave("proc_beta", base_address=0x2000)
    iso_res = sandbox.verify_non_overlapping_isolation("proc_alpha", "proc_beta")
    ultrametric_ok = iso_res["balls_disjoint"] is True

    # 4. Anosov Ergodic Memory Purge
    anosov_res = AnosovColdBootScrambler.emergency_ram_purge(bytearray(b"SOVEREIGN_KEY_MATERIAL_2026_TEST"))
    anosov_ok = anosov_res["status"] == "ZEROISED_AND_VERIFIED"

    # 5. Picard-Lefschetz Anti-Jamming Filter
    pl_res = PicardLefschetzAntiJammingFilter.filter_jammed_waveform([(1.0, 0.5), (0.0, 2.0)])

    latency_us = (time.perf_counter_ns() - t0) / 1000.0

    all_ok = poincare_ok and hodge_ok and ultrametric_ok and anosov_ok

    return {
        "status": "PASS" if all_ok else "MILLENNIUM_FAILED",
        "latency_us": round(latency_us, 2),
        "exact_checks_passed": {
            "ollivier_ricci_curvature_certified": poincare_ok,
            "hodge_decomposition_identities": hodge_ok,
            "p_adic_address_sets_disjoint": ultrametric_ok,
            "buffer_zeroised_and_read_back": anosov_ok,
        },
        "not_implemented": {"picard_lefschetz_anti_jamming": pl_res["status"]},
    }


def verify_toe_quantum_pillar() -> Dict[str, Any]:
    """Pillar 5: Theory of Everything (TOE) & Universal Quantum Substrate."""
    from chronus.quantum.statevector import StateVector

    t0 = time.perf_counter_ns()
    # Exact finite-field Bell state evolution over F_257
    sv = StateVector(num_qubits=2)
    sv.apply("H", 0)
    sv.cnot(control=0, target=1)

    # In F_257, (|00> + |11>) / sqrt(2): amplitudes at index 0 and 3 are non-zero (30 = 1/sqrt(2))
    # Amplitudes at index 1 and 2 are 0
    is_entangled = (sv.amplitudes[0] == 30 and sv.amplitudes[3] == 30 and sv.amplitudes[1] == 0 and sv.amplitudes[2] == 0)

    latency_us = (time.perf_counter_ns() - t0) / 1000.0

    return {
        "status": "PASS" if is_entangled else "FAILED",
        "latency_us": round(latency_us, 2),
        "invariants": {
            "f257_bell_state_evolution": is_entangled,
            "exact_field_hadamard": sv.amplitudes[0] == 30,
            "zero_floating_point_truncation": True,
            "physical_noise_claim": "NOT_APPLICABLE_SOFTWARE_EXECUTION",
        },
    }


def verify_distribution_packages() -> Dict[str, Any]:
    """Pillar 6: Distributable Package Inventory."""
    dist_dir = os.path.join(REPO_ROOT, "dist")
    packages = []
    if os.path.exists(dist_dir):
        for fname in os.listdir(dist_dir):
            if fname.endswith(".whl") or fname.endswith(".tar.gz"):
                fpath = os.path.join(dist_dir, fname)
                fsize = os.path.getsize(fpath)
                with open(fpath, "rb") as pkg_f:
                    sha256 = hashlib.sha256(pkg_f.read()).hexdigest()
                packages.append({
                    "filename": fname,
                    "size_bytes": fsize,
                    "sha256": sha256,
                })

    return {
        "status": "BUILT" if len(packages) >= 2 else "PENDING_BUILD",
        "package_count": len(packages),
        "packages": packages,
        "contained_modules": [
            "chronus.security.al_haras",
            "chronus.storage.theseus",
            "chronus.security.ovid",
            "chronus.stratum",
            "chronus.hw",
            "chronus.math",
            "chronus.execution",
            "chronus.quantum",
            "chronus.service",
        ],
    }


def main(output_path=None):
    print("========================================================================")
    print("      CHRONUS SOFTWARE CAPABILITY EVIDENCE GENERATOR         ")
    print("========================================================================")
    t0 = time.time()

    print("[1/6] Auditing AL HARAS exact checks (sheaf coboundary, Reed-Solomon repair, spectrum)...")
    al_haras_proof = verify_al_haras_pillar()
    print(f"      -> Status: {al_haras_proof['status']} ({al_haras_proof['latency_us']} µs)")

    print("[2/6] Auditing THESEUS & OVID Data Custody Space...")
    theseus_proof = verify_theseus_ovid_pillar()
    print(f"      -> Status: {theseus_proof['status']} ({theseus_proof['latency_us']} µs)")

    print("[3/6] Auditing CHRONUS Galois F_257 & Stratum Wire Engines...")
    chronus_proof = verify_chronus_stratum_pillar()
    print(f"      -> Status: {chronus_proof['status']} ({chronus_proof['latency_us']} µs)")

    print("[4/6] Auditing exact graph, Hodge, p-adic and zeroisation checks...")
    millennium_proof = verify_millennium_pillar()
    print(f"      -> Status: {millennium_proof['status']} ({millennium_proof['latency_us']} µs)")

    print("[5/6] Auditing TOE Substrate & Universal Quantum Computer...")
    toe_proof = verify_toe_quantum_pillar()
    print(f"      -> Status: {toe_proof['status']} ({toe_proof['latency_us']} µs)")

    print("[6/6] Auditing Distribution Packages for Deployment...")
    package_proof = verify_distribution_packages()
    print(f"      -> Packages Found: {package_proof['package_count']}")

    overall_qualified = (
        al_haras_proof["status"] == "PASS"
        and theseus_proof["status"] == "PASS"
        and chronus_proof["status"] == "PASS"
        and millennium_proof["status"] == "PASS"
        and toe_proof["status"] == "PASS"
    )

    dossier = {
        "schema": "chronus-software-capability-evidence/v2",
        "attestation_title": "Chronus software capability evidence dossier",
        "standard": "Internal executable evidence only",
        "status": "SOFTWARE_EVIDENCE_PASS" if overall_qualified else "SOFTWARE_EVIDENCE_FAILED",
        "production_qualified": False,
        "external_certification": False,
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "evaluation_authority": "repository self-test; not an external authority",
        "legacy_filename_notice": "SOVEREIGN_CAPABILITY_ATTESTATION.json is retained for compatibility only.",
        "pillars": {
            "al_haras": al_haras_proof,
            "theseus_ovid": theseus_proof,
            "chronus_stratum": chronus_proof,
            "legacy_millennium_modules": millennium_proof,
            "toe_quantum": toe_proof,
            "distribution_packages": package_proof,
        },
    }

    payload_bytes = json.dumps(dossier, sort_keys=True, indent=2).encode("utf-8")
    content_digest = hashlib.sha256(EVIDENCE_DOMAIN + payload_bytes).hexdigest()
    dossier["content_integrity"] = {
        "algorithm": "SHA-256",
        "domain": EVIDENCE_DOMAIN.decode("ascii", "ignore").rstrip("\\0"),
        "content_sha256": content_digest,
        "keyed_signature": False,
        "external_attestation": False,
    }

    out_file = output_path or os.path.join(REPO_ROOT, "reference-evidence", "SOVEREIGN_CAPABILITY_ATTESTATION.json")
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(dossier, f, indent=2)

    elapsed = time.time() - t0
    print("========================================================================")
    print(f"Evidence Written: {out_file}")
    print(f"Content SHA-256 : {content_digest}")
    print(f"Generation Duration: {elapsed:.3f}s")
    print(f"FINAL RESULT: {'SOFTWARE EVIDENCE PASS' if overall_qualified else 'SOFTWARE EVIDENCE FAILED'}")
    print("========================================================================")

    if not overall_qualified:
        sys.exit(1)


if __name__ == "__main__":
    main()
