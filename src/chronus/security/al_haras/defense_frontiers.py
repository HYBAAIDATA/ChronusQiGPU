"""AL HARAS capability demonstrations (HYBA Security).

Four entry points; each returns only what its code computes from its inputs:

1. ``TacticalSwarmMeshEngine.evaluate_swarm_mesh``: swarm state agreement on a
   ring under an explicit bounded-noise model, with an exact tolerance,
   outlier isolation and repair on ``sheaf.GraphSheaf``.
2. ``PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt``: a receipt
   over a stream packet's SHA-256, signed with Ed25519 and with ML-DSA-87
   (FIPS 204) by ``receipts.signed_receipt``; both signatures are verified at
   once, plus a tamper check. No STARK/FRI proof or IVC folding is produced;
   the class and method names are kept for existing callers.
3. ``HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation``:
   exact one-dimensional normal-shock relations for a calorically perfect gas
   and an exact Lucas number. This is not a CFD simulation, and no memory
   compression is claimed.
4. ``CNISelfHealingEngine.audit_and_heal_cni_asset``: Reed-Solomon RS(48, 32)
   protection of an asset's telemetry trace with an optional fault-injection
   drill (``reed_solomon.py``); a repair counts only if SHA-256 verifies.

Frontier labels are neutral capability names. Earlier versions named defence
and intelligence organisations, alliances and certifications and reported an
"operational" status; none of that is claimed here.
"""

import hashlib
import time
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Dict, List, Optional

from chronus.security.al_haras import golden, reed_solomon
from chronus.security.al_haras.exact import (
    decimal_string,
    display_number,
    fraction_str,
    sqrt_decimal_string,
    to_fraction,
)
from chronus.security.al_haras.receipts import ReceiptSigner, signed_receipt
from chronus.security.al_haras.sheaf import MAX_NODES, GraphSheaf


def _elapsed_ms(start_ns: int) -> Any:
    """Measured wall-clock milliseconds since ``start_ns`` (``time.perf_counter_ns``)."""
    return display_number(Fraction(time.perf_counter_ns() - start_ns, 1_000_000))


def _require_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _exact_and_decimal(value: Fraction) -> Dict[str, str]:
    return {"exact": fraction_str(value), "decimal": decimal_string(value, 6)}


# ==============================================================================
# FRONTIER 1: SWARM STATE AGREEMENT UNDER BOUNDED NOISE
# ==============================================================================


class TacticalSwarmMeshEngine:
    """Swarm state agreement under bounded noise (frontier 1).

    Model: every honest node reports the reference state plus noise of at most
    ``bound`` per coordinate, with ``bound = min(dB / 1000, 1/20)`` (a drill
    assumption, not a radio-propagation model) and noise values derived from
    SHA-256. Two honest nodes then differ by at most ``2 * bound`` per
    coordinate, so ``|s_u - s_v|^2 <= 4 * bound^2 * dim`` on every edge: that
    exact bound is the tolerance. An injected node reports
    ``31/2 * reference - 77``. Edges over the tolerance are located on the
    ring with exact arithmetic; a node touching every such edge is replaced by
    the exact mean of the other nodes and the tolerance is re-checked.
    """

    STATE_DIM = 8
    MAX_NOISE_BOUND = Fraction(1, 20)

    @staticmethod
    def _noise(node: int, coord: int, bound: Fraction) -> Fraction:
        h = hashlib.sha256(f"swarm-noise:{node}:{coord}".encode("utf-8")).digest()[0]
        return bound * Fraction(2 * h - 255, 255)

    @classmethod
    def evaluate_swarm_mesh(
        cls,
        node_count: int = 16,
        jamming_intensity_db: Any = 45,
        injected_adversarial_vector: bool = False,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        _require_int(node_count, "node_count", 2, MAX_NODES)
        db = to_fraction(jamming_intensity_db)
        if db < 0:
            raise ValueError("jamming intensity must be non-negative")
        bound = min(db / 1000, cls.MAX_NOISE_BOUND)
        reference = [Fraction(golden.fibonacci(k)) for k in range(2, 2 + cls.STATE_DIM)]
        names = [f"node_{i:02d}" for i in range(node_count)]
        injected = node_count // 2 if injected_adversarial_vector else None
        states: Dict[str, List[Fraction]] = {}
        for i, name in enumerate(names):
            if i == injected:
                states[name] = [x * Fraction(31, 2) - 77 for x in reference]
            else:
                states[name] = [x + cls._noise(i, d, bound) for d, x in enumerate(reference)]

        sheaf = GraphSheaf.ring(names, cls.STATE_DIM)
        tolerance_sq = 4 * bound * bound * cls.STATE_DIM
        dis = sheaf.disagreement(states)
        over = [e for e, sq in enumerate(dis["edge_norm_sq"]) if sq > tolerance_sq]
        consistent = not over
        outliers = [] if consistent else [n for n in names if all(n in sheaf.edges[e] for e in over)]

        repair: Dict[str, Any] = {"performed": False}
        if len(outliers) == 1:
            bad = outliers[0]
            others = [n for n in names if n != bad]
            mean = [sum((states[n][d] for n in others), Fraction(0)) / len(others) for d in range(cls.STATE_DIM)]
            repaired = dict(states)
            repaired[bad] = mean
            within = all(sq <= tolerance_sq for sq in sheaf.disagreement(repaired)["edge_norm_sq"])
            repair = {
                "performed": True,
                "method": "replace the outlier by the exact mean of the other nodes",
                "node": bad,
                "replacement_state": [fraction_str(x) for x in mean],
                "verified_within_tolerance": within,
            }

        if consistent:
            status = "CONSENSUS_WITHIN_NOISE_BOUND"
        elif repair.get("verified_within_tolerance"):
            status = "OUTLIER_ISOLATED_AND_REPLACED"
        else:
            status = "DISAGREEMENT_NOT_LOCALISED"
        worst = max(dis["edge_norm_sq"])
        return {
            "frontier": "FRONTIER_1_SWARM_STATE_CONSENSUS",
            "capability": "Swarm state agreement under bounded noise",
            "node_count": node_count,
            "graph": "ring",
            "state_dim": cls.STATE_DIM,
            "jamming_level_db": display_number(db),
            "reference_state": [fraction_str(x) for x in reference],
            "noise_model": {
                "per_coordinate_bound": fraction_str(bound),
                "rule": "bound = min(dB / 1000, 1/20); a drill assumption, not a radio-propagation model",
                "values": "deterministic, from SHA-256(node, coordinate)",
            },
            "tolerance": {
                "edge_residual_norm_sq_max": fraction_str(tolerance_sq),
                "derivation": "honest nodes differ by at most 2*bound per coordinate, so |s_u - s_v|^2 <= 4*bound^2*dim",
            },
            "sheaf_consensus_achieved": consistent,
            "sheaf_check": {
                "method": "exact coboundary on a ring (sheaf.GraphSheaf), compared with the tolerance",
                "consistent_within_tolerance": consistent,
                "exactly_equal_states": dis["total_norm_sq"] == 0,
                "max_edge_residual_norm_sq": fraction_str(worst),
                "max_edge_residual_norm": sqrt_decimal_string(worst, 8),
                "edges_over_tolerance": [list(sheaf.edges[e]) for e in over],
            },
            "injected_node": names[injected] if injected is not None else None,
            "outlier_nodes": outliers,
            "repair": repair,
            "status": status,
            "latency_ms": _elapsed_ms(t0),
        }


# ==============================================================================
# FRONTIER 2: SIGNED STREAM RECEIPTS (ED25519 + ML-DSA-87)
# ==============================================================================


class PostQuantumSubstrateEngine:
    """Signed receipts for stream packets (frontier 2).

    The class name is kept for existing callers. The receipt body binds the
    tenant, the packet's SHA-256 and its length and is signed with Ed25519 and
    with ML-DSA-87 (FIPS 204) through ``receipts.py``; both signatures must
    verify. The result reports an immediate verification of each signature and
    the rejection of a body with an altered hash. Neither STARK/FRI proofs nor
    incrementally verifiable computation are implemented.
    """

    @classmethod
    def generate_line_rate_ivc_receipt(
        cls,
        c4isr_stream_packet: bytes,
        tenant_id: str = "default-tenant",
    ) -> Dict[str, Any]:
        packet = bytes(c4isr_stream_packet)
        digest = hashlib.sha256(packet).hexdigest()
        body = {
            "capability": "signed stream receipt",
            "tenant_id": tenant_id,
            "packet_sha256": digest,
            "packet_bytes": len(packet),
        }
        t_sign = time.perf_counter_ns()
        receipt = signed_receipt(body)
        sign_ns = time.perf_counter_ns() - t_sign
        t_verify = time.perf_counter_ns()
        verified = ReceiptSigner.verify(receipt["body"], receipt["signature"])
        verify_ns = time.perf_counter_ns() - t_verify
        pq = receipt["signature"]["post_quantum"]
        altered = dict(receipt["body"])
        altered["packet_sha256"] = hashlib.sha256(packet + b"\x00").hexdigest()
        tamper_rejected = not ReceiptSigner.verify(altered, receipt["signature"])
        return {
            "frontier": "FRONTIER_2_SIGNED_STREAM_RECEIPTS",
            "capability": "Signed receipts for stream packets",
            "signature_scheme": "Ed25519 (RFC 8032) and ML-DSA-87 (FIPS 204) over canonical JSON; both must verify",
            "post_quantum": ReceiptSigner.verify_ml_dsa(receipt["body"], receipt["signature"]),
            "post_quantum_algorithm": pq["algorithm"],
            "post_quantum_signature_bytes": pq["signature_bytes"],
            "post_quantum_public_key_bytes": pq["public_key_bytes"],
            "tenant_id": tenant_id,
            "packet_sha256": digest,
            "packet_bytes": len(packet),
            "receipt": receipt,
            "signature_verified": verified,
            "tampered_body_rejected": tamper_rejected,
            "key_custody": receipt["signature"]["key_custody"],
            "sign_time_us_measured": decimal_string(Fraction(sign_ns, 1000), 3),
            "verify_time_us_measured": decimal_string(Fraction(verify_ns, 1000), 3),
            "not_implemented": [
                "STARK/FRI proofs and incrementally verifiable computation (IVC)",
                "a FIPS 140-3 validated cryptographic module (the signatures come from pyca/cryptography over OpenSSL)",
            ],
        }


# ==============================================================================
# FRONTIER 3: EXACT NORMAL-SHOCK RELATIONS (NOT CFD)
# ==============================================================================


class HyperscaleDefenseSimulationEngine:
    """Exact normal-shock relations and an exact Lucas number (frontier 3).

    For a calorically perfect gas with ratio of specific heats ``gamma`` and
    upstream Mach number ``M > 1`` (Rankine-Hugoniot relations):

        p2/p1     = 1 + 2 gamma (M^2 - 1) / (gamma + 1)
        rho2/rho1 = (gamma + 1) M^2 / ((gamma - 1) M^2 + 2)
        T2/T1     = (p2/p1) / (rho2/rho1)
        M2^2      = ((gamma - 1) M^2 + 2) / (2 gamma M^2 - (gamma - 1))
        T0/T1     = 1 + (gamma - 1) M^2 / 2

    All are rational in ``M^2`` and computed exactly. Nothing here is a flow
    field, mesh or CFD solver, and at hypersonic Mach numbers real-gas effects
    (vibrational excitation, dissociation, ionisation) that these ideal-gas
    ratios ignore become large. The class and method names are kept for
    existing callers.
    """

    MAX_MACH = 100
    MAX_LUCAS_INDEX = 10_000

    @staticmethod
    def normal_shock_ratios(mach: Fraction, gamma: Fraction) -> Dict[str, Fraction]:
        m2 = mach * mach
        pressure = 1 + 2 * gamma * (m2 - 1) / (gamma + 1)
        density = (gamma + 1) * m2 / ((gamma - 1) * m2 + 2)
        return {
            "pressure_ratio_p2_p1": pressure,
            "density_ratio_rho2_rho1": density,
            "temperature_ratio_t2_t1": pressure / density,
            "downstream_mach_squared": ((gamma - 1) * m2 + 2) / (2 * gamma * m2 - (gamma - 1)),
            "stagnation_to_static_temperature_t0_t1": 1 + (gamma - 1) * m2 / 2,
            "density_ratio_limit_large_mach": (gamma + 1) / (gamma - 1),
        }

    @classmethod
    def execute_hypersonic_cfd_simulation(
        cls,
        mach_number: Any = Fraction(25, 2),
        state_dimensions: int = 479,
        gamma: Any = Fraction(7, 5),
    ) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        mach = to_fraction(mach_number)
        g = to_fraction(gamma)
        if not 0 < mach <= cls.MAX_MACH:
            raise ValueError(f"mach_number must be in (0, {cls.MAX_MACH}]")
        if not 1 < g <= Fraction(5, 3):
            raise ValueError("gamma must be in (1, 5/3]")
        n = _require_int(state_dimensions, "state_dimensions", 0, cls.MAX_LUCAS_INDEX)

        shock: Optional[Dict[str, Any]] = None
        if mach > 1:
            ratios = cls.normal_shock_ratios(mach, g)
            shock = {key: _exact_and_decimal(value) for key, value in ratios.items()}
            shock["downstream_mach"] = {"decimal": sqrt_decimal_string(ratios["downstream_mach_squared"], 6)}
        lucas_n = golden.lucas(n)
        return {
            "frontier": "FRONTIER_3_EXACT_FLOW_RELATIONS",
            "capability": "Exact normal-shock relations (not a CFD simulation)",
            "workload_type": "NORMAL_SHOCK_RELATIONS_CALORICALLY_PERFECT_GAS",
            "mach_number": display_number(mach),
            "mach_number_exact": fraction_str(mach),
            "gamma": fraction_str(g),
            "normal_shock": shock,
            "model_limits": "one-dimensional, inviscid, calorically perfect gas; no flow field, mesh or solver; "
            "real-gas effects at hypersonic Mach numbers are not modelled",
            "lucas_number": {
                "n": n,
                "value": str(lucas_n),
                "decimal_digits": len(str(lucas_n)),
                "binet_identity_verified": golden.binet_lucas_identity(n),
                "note": "exact integer by fast doubling; storing L_n takes about 0.694 n bits",
            },
            "status": "NORMAL_SHOCK_RELATIONS_COMPUTED" if shock else "NO_NORMAL_SHOCK_AT_MACH_1_OR_BELOW",
            "execution_latency_ms": _elapsed_ms(t0),
            "not_implemented": [
                "CFD (no flow field, mesh or solver)",
                "constant-size storage of large Lucas states (the 64-byte claim in older notes)",
                "DEC Lie-Poisson routing, bus saturation and stall figures",
            ],
        }


# ==============================================================================
# FRONTIER 4: TELEMETRY TRACE REPAIR (REED-SOLOMON)
# ==============================================================================


class CNISelfHealingEngine:
    """Telemetry trace repair for an infrastructure asset (frontier 4).

    The asset's synthetic telemetry trace is protected with Reed-Solomon
    RS(48, 32) over GF(257). With ``simulated_cyber_physical_strike`` the
    drill corrupts ``fault_count`` bytes at SHA-256-derived positions; the
    decoder locates and corrects them, and the repair counts only if the
    SHA-256 of the result matches. Corruption beyond 8 symbols per block is
    reported as uncorrectable.
    """

    @classmethod
    def audit_and_heal_cni_asset(
        cls,
        asset_name: str = "NATIONAL_POWER_GRID_SUBSTATION_04",
        simulated_cyber_physical_strike: bool = False,
        fault_count: int = 1,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        trace = f"CNI_TELEMETRY_{asset_name}_STATUS_CONTINUOUS".encode("utf-8")
        _require_int(fault_count, "fault_count", 0, len(trace))
        envelope = reed_solomon.protect(trace)
        positions = reed_solomon.deterministic_fault_positions(trace, fault_count) if simulated_cyber_physical_strike else []
        received = reed_solomon.inject_faults(trace, positions)
        t_decode = time.perf_counter_ns()
        outcome = reed_solomon.heal(received, envelope)
        decode_ns = time.perf_counter_ns() - t_decode
        corrected = outcome["corrected_data_positions"]
        detected = bool(corrected) or bool(outcome["uncorrectable_blocks"])
        if outcome["uncorrectable_blocks"] or not outcome["integrity_verified"]:
            status = "UNCORRECTABLE_CORRUPTION"
        elif corrected:
            status = "TRACE_REPAIRED_AND_VERIFIED"
        else:
            status = "NO_CORRUPTION_DETECTED"
        return {
            "frontier": "FRONTIER_4_TRACE_REPAIR",
            "capability": "Telemetry trace repair (Reed-Solomon)",
            "cni_asset": asset_name,
            "fault_injection_drill": bool(simulated_cyber_physical_strike),
            "cyber_physical_strike_detected": detected,
            "trace_repair": {
                "mechanism": "Reed-Solomon RS(n, k) over GF(257), batched syndrome decoding (Berlekamp-Massey, Chien, Forney)",
                "code_parameters": {
                    "n": envelope["n"],
                    "k": envelope["k"],
                    "correctable_symbols_per_block": envelope["correctable_symbols_per_block"],
                },
                "trace_bytes": len(trace),
                "injected_fault_positions": positions,
                "symbol_errors_corrected": len(corrected),
                "corrected_positions": corrected,
                "uncorrectable_blocks": outcome["uncorrectable_blocks"],
                "integrity_verified": outcome["integrity_verified"],
                "trace_sha256": envelope["sha256"],
                "repaired_trace_sha256": outcome["sha256_after_repair"],
                "decode_time_us_measured": decimal_string(Fraction(decode_ns, 1000), 3),
            },
            "trace_integrity_status": status,
            "audit_latency_ms": _elapsed_ms(t0),
        }


# ==============================================================================
# CATALOGUE AND RUNNER
# ==============================================================================


class StrategicDefenseCoordinator:
    """Catalogue and runner for the four capability demonstrations (class name kept for callers)."""

    FRONTIERS = (
        {
            "frontier_id": "FRONTIER_1",
            "capability": "Swarm state agreement under bounded noise",
            "entry_point": "TacticalSwarmMeshEngine.evaluate_swarm_mesh",
            "mechanism": "exact coboundary on a ring with an exact noise tolerance; outlier isolation and repair",
            "limitations": "the noise bound is a drill assumption; one outlier is localised, several may not be",
        },
        {
            "frontier_id": "FRONTIER_2",
            "capability": "Signed receipts for stream packets",
            "entry_point": "PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt",
            "mechanism": "Ed25519 and ML-DSA-87 (FIPS 204) signatures over the packet SHA-256, both verified, with a tamper check",
            "limitations": "signing keys held in process memory or environment seeds, not an HSM; no STARK/FRI proof or IVC",
        },
        {
            "frontier_id": "FRONTIER_3",
            "capability": "Exact normal-shock relations",
            "entry_point": "HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation",
            "mechanism": "Rankine-Hugoniot ratios for a calorically perfect gas in exact rationals; exact Lucas numbers",
            "limitations": "not CFD; ideal-gas relations only",
        },
        {
            "frontier_id": "FRONTIER_4",
            "capability": "Telemetry trace repair",
            "entry_point": "CNISelfHealingEngine.audit_and_heal_cni_asset",
            "mechanism": "Reed-Solomon RS(48, 32) over GF(257) with SHA-256 verification",
            "limitations": "corrects up to 8 corrupted symbols per 32-byte block; heavier corruption is only detected",
        },
    )

    @classmethod
    def self_checks(cls) -> Dict[str, bool]:
        """Known-answer checks of each demonstration, computed on every call."""
        swarm = TacticalSwarmMeshEngine.evaluate_swarm_mesh(
            node_count=5, jamming_intensity_db=20, injected_adversarial_vector=True
        )
        receipt = PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt(b"self-check packet")
        shock = HyperscaleDefenseSimulationEngine.normal_shock_ratios(Fraction(2), Fraction(7, 5))
        trace = CNISelfHealingEngine.audit_and_heal_cni_asset(asset_name="SELF_CHECK", simulated_cyber_physical_strike=True)
        return {
            "frontier_1_injected_outlier_located": swarm["outlier_nodes"] == [swarm["injected_node"]]
            and bool(swarm["repair"].get("verified_within_tolerance")),
            "frontier_2_receipt_verifies_and_tamper_rejected": receipt["signature_verified"]
            and receipt["tampered_body_rejected"],
            "frontier_3_mach_2_known_answer": (
                shock["pressure_ratio_p2_p1"],
                shock["density_ratio_rho2_rho1"],
                shock["temperature_ratio_t2_t1"],
                shock["downstream_mach_squared"],
            )
            == (Fraction(9, 2), Fraction(8, 3), Fraction(27, 16), Fraction(1, 3)),
            "frontier_4_injected_fault_repaired": trace["trace_repair"]["symbol_errors_corrected"] == 1
            and trace["trace_repair"]["integrity_verified"],
        }

    @classmethod
    def get_strategic_posture_overview(cls) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        checks = cls.self_checks()
        return {
            "catalogue": "AL HARAS capability demonstrations (HYBA Security)",
            "frontiers": [dict(item) for item in cls.FRONTIERS],
            "self_checks": checks,
            "self_checks_all_true": all(checks.values()),
            "self_check_time_ms_measured": _elapsed_ms(t0),
            "claims_not_made": [
                "certification, accreditation or compliance status",
                "deployment, customer or partner use",
                "post-quantum security",
                "CFD capability or hardware performance",
            ],
            "evidence_documents": ["docs/claim-audit.md", "docs/security/AL_HARAS_NOTES_RECONCILIATION.md"],
        }

    @classmethod
    def run_all_frontier_simulations(cls) -> Dict[str, Any]:
        """Run each demonstration once with reference inputs."""
        f1 = TacticalSwarmMeshEngine.evaluate_swarm_mesh(node_count=16, jamming_intensity_db=50)
        f2 = PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt(b"REFERENCE_STREAM_PACKET")
        f3 = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(mach_number=14)
        f4 = CNISelfHealingEngine.audit_and_heal_cni_asset(simulated_cyber_physical_strike=True)
        checks = {
            "frontier_1_consensus_within_tolerance": f1["sheaf_consensus_achieved"],
            "frontier_2_signature_verified": f2["signature_verified"],
            "frontier_3_normal_shock_computed": f3["normal_shock"] is not None,
            "frontier_4_trace_integrity_verified": f4["trace_repair"]["integrity_verified"],
        }
        return {
            "summary": {"runs": 4, "checks": checks, "all_checks_true": all(checks.values())},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frontier_1_swarm_consensus": f1,
            "frontier_2_signed_receipts": f2,
            "frontier_3_flow_relations": f3,
            "frontier_4_trace_repair": f4,
        }
