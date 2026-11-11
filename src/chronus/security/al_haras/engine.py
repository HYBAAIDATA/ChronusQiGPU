"""
AL HARAS core engine (HYBA Security).

Every result returned here is computed from the inputs by the modules named
below; nothing is a stored constant or a status label chosen in advance.

1. Consistency of node/agent states: exact cellular-sheaf coboundary
   (``sheaf.py``). States agree iff delta^0 s = 0; the residuals locate the
   disagreement, and the nearest global section is the in-place repair.
2. Trace self-healing: Reed-Solomon RS(n, k) over GF(257) (``reed_solomon.py``).
   The "Donaldson-Seiberg-Witten instanton" wording in older notes names this
   step metaphorically; the implemented mechanism is error correction.
3. Expander certificate: Paley graph P(257) with an exact spectral certificate
   (``expander.py``). The PSL_2(F_257) LPS graph in older notes is not built.
4. Braid algebra: Fibonacci-anyon braid representation over Z[zeta_5] with
   exact relation checks (``braids.py``).
5. Payload fingerprint: point count of a payload-derived elliptic curve over
   F_257 (``fingerprint.py``). Not an integrity check.
6. Receipts: Ed25519 and ML-DSA-87 (FIPS 204) signatures over canonical JSON; both must verify (``receipts.py``).

Mathematical facts are checked by computation; none of this establishes
security effectiveness, certification, or hardware behaviour.
"""

import hashlib
import time
from fractions import Fraction
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chronus.security.al_haras import braids, expander, fingerprint, reed_solomon
from chronus.security.al_haras.cyclotomic import CyclotomicZ5  # re-exported for existing imports
from chronus.security.al_haras.exact import decimal_string, fraction_str
from chronus.security.al_haras.receipts import signed_receipt
from chronus.security.al_haras.sheaf import SheafError, analyse_states

__all__ = [
    "CyclotomicZ5",
    "CellularSheafCohomology",
    "DSW4DInstantonMonopoleHealer",
    "RamanujanExpanderSpectralGapGuard",
    "CyclotomicAnyonBraidEngine",
    "HeckeModularChecksum",
    "ALHarasSecurityFabric",
]


def _vector_strings(vec: Sequence[Fraction]) -> List[str]:
    return [fraction_str(x) for x in vec]


# ------------------------------------------------------------------------------
# 1. STATE CONSISTENCY (CELLULAR SHEAF COBOUNDARY)
# ------------------------------------------------------------------------------


class CellularSheafCohomology:
    """Exact consistency analysis of node states on a graph.

    ``node_vectors`` (legacy list form) are placed on a ring n0 -> n1 -> ... -> n0;
    ``latent_vectors`` (dict form) may come with explicit ``edges``. Restriction
    maps are identities (constant sheaf) unless a caller uses ``sheaf.py``
    directly with orthogonal maps.
    """

    @classmethod
    def compute_cohomology(
        cls,
        node_vectors: Optional[List[List[Any]]] = None,
        nodes: Optional[List[str]] = None,
        edges: Optional[List[Tuple[str, str]]] = None,
        latent_vectors: Optional[Dict[str, List[Any]]] = None,
        tolerance: Any = 0,
    ) -> Dict[str, Any]:
        if latent_vectors is not None:
            order = nodes if nodes is not None else list(latent_vectors.keys())
            states = {n: latent_vectors[n] for n in order if n in latent_vectors}
        elif node_vectors:
            names = nodes if nodes is not None and len(nodes) == len(node_vectors) else [f"n{i}" for i in range(len(node_vectors))]
            states = dict(zip(names, node_vectors))
        else:
            states = {}

        if not states:
            return {
                "evaluated": False,
                "status": "NO_STATE_SUPPLIED",
                "h0_consensus": True,
                "h0_harmonic_section": True,
                "cohomology_state": "no node states supplied; nothing to compare",
                "cohomology_class": "NOT_EVALUATED",
                "is_isolated": False,
                "isolating_nodes": [],
                "audit_alert": None,
            }

        result = analyse_states(states, edges=edges, tolerance=tolerance)
        sheaf = result["sheaf"]
        consistent = result["consistent"]
        isolating = result["isolating_nodes"]
        status = "CONSISTENT"
        if not consistent:
            status = "INCONSISTENT_STATES_ISOLATED" if isolating else "INCONSISTENT_STATES"
        alert = None
        if not consistent:
            alert = (
                f"delta0(s) != 0: largest edge residual {result['max_edge_norm']} on edge "
                f"{result['worst_edge']}; isolating nodes {isolating or 'none found'}"
            )
        return {
            "evaluated": True,
            "method": "exact rational coboundary of a cellular sheaf (stalk Q^d)",
            "graph": {"nodes": list(sheaf.nodes), "edges": [list(e) for e in sheaf.edges]},
            "stalk_dim": sheaf.dim,
            "tolerance": fraction_str(result["tolerance"]),
            "h0_consensus": consistent,
            "h0_harmonic_section": consistent,
            "cohomology_dimensions": result["dimensions"],
            "cohomology_state": "delta0(s) = 0: the states form a global section"
            if consistent
            else "delta0(s) != 0: the states are not a global section",
            "cohomology_class": "GLOBAL_SECTION" if consistent else "COBOUNDARY_DISAGREEMENT",
            "coboundary_max_edge_norm": result["max_edge_norm"],
            "coboundary_max_edge_norm_sq": fraction_str(result["max_edge_norm_sq"]),
            "coboundary_total_norm_sq": fraction_str(result["total_norm_sq"]),
            "worst_edge": result["worst_edge"],
            "simplicial_1_cells_evaluated": len(sheaf.edges),
            "status": status,
            "is_isolated": (not consistent) and bool(isolating),
            "isolating_nodes": isolating,
            "nearest_global_section": {n: _vector_strings(v) for n, v in result["nearest_global_section"].items()},
            "repair_distance": result["repair_distance"],
            "audit_alert": alert,
        }


# ------------------------------------------------------------------------------
# 2. TRACE SELF-HEALING (REED-SOLOMON OVER GF(257))
# ------------------------------------------------------------------------------


class DSW4DInstantonMonopoleHealer:
    """Trace self-healing by Reed-Solomon error correction.

    Name kept for existing callers; see ``reed_solomon.py`` for the mechanism.

    * ``inspect_and_heal(trace, envelope=..., received=...)`` repairs a received
      trace against its protection envelope.
    * ``inspect_and_heal(trace, is_perturbed=True)`` runs a reproducible drill:
      protect the trace, corrupt ``fault_count`` bytes at SHA-256-derived
      positions, decode, and verify the SHA-256 of the repaired trace.
    """

    @classmethod
    def inspect_and_heal(
        cls,
        trace_payload: Any,
        is_perturbed: bool = False,
        envelope: Optional[Dict[str, Any]] = None,
        received: Optional[bytes] = None,
        fault_count: int = 1,
    ) -> Dict[str, Any]:
        trace = trace_payload.encode("utf-8") if isinstance(trace_payload, str) else bytes(trace_payload)
        mode = "verify"
        injected: List[int] = []
        if envelope is None:
            envelope = reed_solomon.protect(trace)
            received = trace
            if is_perturbed:
                mode = "fault_injection_drill"
                injected = reed_solomon.deterministic_fault_positions(trace, fault_count)
                received = reed_solomon.inject_faults(trace, injected)
        elif received is None:
            received = trace
        t0 = time.perf_counter_ns()
        outcome = reed_solomon.heal(received, envelope)
        elapsed_ns = time.perf_counter_ns() - t0
        corrected = outcome["corrected_data_positions"]
        healed = bool(corrected) and outcome["integrity_verified"]
        return {
            "mechanism": "Reed-Solomon RS(n,k) over GF(257), Berlekamp-Welch decoding",
            "mode": mode,
            "code_parameters": {"n": envelope["n"], "k": envelope["k"], "correctable_symbols_per_block": envelope["correctable_symbols_per_block"]},
            "trace_bytes": envelope["length"],
            "injected_fault_positions": injected,
            "symbol_errors_corrected": len(corrected),
            "corrected_positions": corrected,
            "corrected_blocks": outcome["corrected_blocks"],
            "uncorrectable_blocks": outcome["uncorrectable_blocks"],
            "integrity_verified": outcome["integrity_verified"],
            "healed": healed,
            "checkpoint_restore_used": False,
            "status": "TRACE_REPAIRED_AND_VERIFIED"
            if healed
            else ("NO_CORRUPTION_DETECTED" if outcome["integrity_verified"] else "UNCORRECTABLE_CORRUPTION"),
            "trace_sha256": envelope["sha256"],
            "repaired_trace_sha256": outcome["sha256_after_repair"],
            "decode_time_us_measured": decimal_string(Fraction(elapsed_ns, 1000), 3),
        }


# ------------------------------------------------------------------------------
# 3. EXPANDER CERTIFICATE (PALEY GRAPH OVER F_257)
# ------------------------------------------------------------------------------


class RamanujanExpanderSpectralGapGuard:
    """Exact Ramanujan certificate for the Paley graph P(q) (default q = 257)."""

    PRIME_P = 257

    @classmethod
    @lru_cache(maxsize=4)
    def verify_mass_gap(cls, q: int = PRIME_P) -> Dict[str, Any]:
        cert = expander.certify_paley(q)
        steps = expander.mixing_steps(q)
        public = {k: v for k, v in cert.items() if k != "walk_contraction_upper_bound"}
        public.update(
            {
                "group": f"additive group of F_{q} (Paley graph)",
                "prime_p": q,
                "degree_k": cert["degree"],
                "satisfies_bound": cert["is_ramanujan"],
                "random_walk_steps_to_tv_2^-32": steps,
                "status": "RAMANUJAN_CERTIFIED_EXACTLY" if cert["is_ramanujan"] else "RAMANUJAN_BOUND_NOT_MET",
                "not_implemented": "LPS Cayley graph on PSL_2(F_257) of degree 258",
            }
        )
        return public


# ------------------------------------------------------------------------------
# 4. BRAID ALGEBRA OVER Z[zeta_5]
# ------------------------------------------------------------------------------


class CyclotomicAnyonBraidEngine:
    """Exact Fibonacci-anyon braid representation over Z[zeta_5]."""

    @classmethod
    def compile_braid(cls, braid_word: Optional[List[str]] = None) -> Dict[str, Any]:
        word = list(braid_word) if braid_word else ["sigma_1", "sigma_2^-1", "sigma_1"]
        relations = braids.verify_relations()
        compiled = braids.compile_braid_word(word)
        coherent = all(relations.values())
        return {
            "ring": "Z[zeta_5] = Z[x]/(x^4 + x^3 + x^2 + x + 1)",
            "representation": "Fibonacci anyons, 2-dim fusion space; R = diag(zeta^3, -zeta^4), F = [[phi^-1, 1], [phi^-1, -phi^-1]]",
            "braid_word": compiled["braid_word"],
            "compiled_matrix_z5": compiled["matrix_z5"],
            "anyon_quantum_dimension": "phi = -(zeta^2 + zeta^3), phi^2 = phi + 1",
            "relations_verified": relations,
            "artin_braid_satisfied": relations["artin_relation"],
            "exact_arithmetic": True,
            "status": "VERIFIED_COHERENT" if coherent else "BRAID_RELATION_FAILED",
            "scope": "algebraic identities of a mathematical model; no physical or noise claim",
        }


# ------------------------------------------------------------------------------
# 5. PAYLOAD FINGERPRINT (ELLIPTIC CURVE POINT COUNT)
# ------------------------------------------------------------------------------


class HeckeModularChecksum:
    """Frobenius trace of a payload-derived elliptic curve over F_257."""

    PRIME = 257

    @classmethod
    def verify_payload_eigenform(cls, payload: bytes) -> Dict[str, Any]:
        result = fingerprint.fingerprint(payload, cls.PRIME)
        ok = result["hasse_bound_satisfied"] and result["independent_trace_check"]
        result.update(
            {
                "frobenius_eigenvalue_ap": result["frobenius_trace_ap"],
                "weil_bound_satisfied": result["hasse_bound_satisfied"],
                "status": "HASSE_BOUND_VERIFIED" if ok else "POINT_COUNT_INCONSISTENT",
                "purpose": "algebraic fingerprint only; integrity is SHA-256 plus the signed receipt",
            }
        )
        return result


# ------------------------------------------------------------------------------
# 6. UNIFIED INGRESS DECISION
# ------------------------------------------------------------------------------


class ALHarasSecurityFabric:
    """Ingress decision: state consistency + trace protection + signed receipt.

    Motto from the notes: "Speak friend and enter or you shall not pass." It is
    not an access control. Authentication and tenant authorisation are enforced
    by the API layer; this decision only covers the checks listed below.
    """

    @classmethod
    def evaluate_ingress(
        cls,
        payload: bytes,
        state_vectors: Optional[List[List[Any]]] = None,
        passphrase: Optional[str] = None,
        edges: Optional[List[Tuple[str, str]]] = None,
        tolerance: Any = 0,
        node_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        del passphrase  # accepted for compatibility; never used as a credential
        t0 = time.perf_counter_ns()
        payload = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        try:
            if node_names is not None and state_vectors is not None and len(node_names) != len(state_vectors):
                raise SheafError("node_names must match state_vectors in length")
            sheaf_res = CellularSheafCohomology.compute_cohomology(
                state_vectors, nodes=node_names, edges=edges, tolerance=tolerance
            )
        except SheafError as exc:
            sheaf_res = {"evaluated": False, "status": "INVALID_STATE_INPUT", "error": str(exc), "h0_consensus": False}
        envelope = reed_solomon.protect(payload)
        hecke_res = HeckeModularChecksum.verify_payload_eigenform(payload)
        admitted = bool(sheaf_res.get("h0_consensus")) and sheaf_res.get("status") != "INVALID_STATE_INPUT"
        decision = {
            "decision": "ADMIT" if admitted else "REJECT",
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "payload_bytes": len(payload),
            "state_check": sheaf_res.get("status"),
            "worst_edge": sheaf_res.get("worst_edge"),
            "isolating_nodes": sheaf_res.get("isolating_nodes", []),
            "protection": {"scheme": envelope["scheme"], "n": envelope["n"], "k": envelope["k"], "blocks": envelope["blocks"]},
        }
        receipt = signed_receipt(decision)
        elapsed_ns = time.perf_counter_ns() - t0
        return {
            "fabric": "AL_HARAS_INGRESS_DECISION",
            "admitted": admitted,
            "status": "ADMITTED" if admitted else "REJECTED_STATE_DISAGREEMENT",
            "latency_ms_measured": decimal_string(Fraction(elapsed_ns, 1_000_000), 4),
            "sheaf_cohomology": sheaf_res,
            "trace_protection": {k: v for k, v in envelope.items() if k != "parity"},
            "payload_fingerprint": hecke_res,
            "receipt": receipt,
            "checks_not_performed": [
                "authentication (enforced by the API layer)",
                "malware or prompt-content classification",
            ],
        }
