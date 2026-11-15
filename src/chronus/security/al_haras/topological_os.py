"""
AL HARAS kernel self-test and process admission (HYBA Security).

Older notes describe an "AL HARAS OS" microkernel that replaces CPU privilege
rings with topological invariants. What exists in code is a user-space
library: ``boot_kernel`` runs exact self-tests of the mathematical engines, and
``execute_sovereign_process`` applies the AL HARAS ingress decision to a
process payload and records a signed receipt. There is no operating-system
kernel, no ring replacement and no hardware enforcement here.
"""

import hashlib
import time
from fractions import Fraction
from typing import Any, Dict, List, Optional

from chronus.security.al_haras import braids, expander, fingerprint, golden, reed_solomon
from chronus.security.al_haras.engine import ALHarasSecurityFabric
from chronus.security.al_haras.exact import decimal_string
from chronus.security.al_haras.sovereign import SovereignGovernanceEngine, sovereign_ovid_chain

_SELF_TEST_TRACE = bytes(range(256)) * 2


# Customer-visible ids for run_self_tests(); mechanism names stay internal-only.
_PUBLIC_SELF_TEST_IDS: Dict[str, str] = {
    "braid_relations_exact": "braid_relations_exact",
    "binet_lucas_identity_exact": "sequence_identity_exact",
    "zeckendorf_representation_exact": "canonical_digit_representation_exact",
    "reed_solomon_repair_verified": "reed_solomon_repair_verified",
    "paley_257_ramanujan_certified": "paley_257_expander_certified",
    "elliptic_point_count_consistent": "elliptic_point_count_consistent",
}


def run_self_tests() -> Dict[str, bool]:
    """Exact self-tests; each value is recomputed on every call."""
    relations = braids.verify_relations()
    lucas_ok = all(golden.binet_lucas_identity(n) for n in list(range(0, 65)) + [479, 1000])
    zeck_ok = all(
        r["sum_matches"] and r["non_adjacent"]
        for r in (golden.verify_zeckendorf(n) for n in (1, 2, 3, 4, 100, 1000, 10**12 + 7))
    )
    envelope = reed_solomon.protect(_SELF_TEST_TRACE)
    positions = reed_solomon.deterministic_fault_positions(_SELF_TEST_TRACE, 3)
    corrupted = reed_solomon.inject_faults(_SELF_TEST_TRACE, positions)
    repair = reed_solomon.heal(corrupted, envelope)
    rs_ok = repair["integrity_verified"] and sorted(repair["corrected_data_positions"]) == sorted(positions)
    paley = expander.certify_paley(257)
    fp = fingerprint.fingerprint(_SELF_TEST_TRACE)
    return {
        "braid_relations_exact": all(relations.values()),
        "binet_lucas_identity_exact": lucas_ok,
        "zeckendorf_representation_exact": zeck_ok,
        "reed_solomon_repair_verified": rs_ok,
        "paley_257_ramanujan_certified": paley["is_ramanujan"],
        "elliptic_point_count_consistent": fp["independent_trace_check"] and fp["hasse_bound_satisfied"],
    }


def public_self_tests() -> Dict[str, bool]:
    """Sealed self-test view for customer-facing API surfaces."""
    return {
        _PUBLIC_SELF_TEST_IDS.get(name, name): passed
        for name, passed in run_self_tests().items()
    }


class ALHarasTopologicalKernel:
    """Self-test and process admission for one tenant."""

    def __init__(self, sovereign_state_id: str = "default_tenant") -> None:
        self.sovereign_state_id = sovereign_state_id

    def boot_kernel(self) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        tests = run_self_tests()
        passed = all(tests.values())
        return {
            "component": "AL HARAS engine self-test (user-space library)",
            "tenant": self.sovereign_state_id,
            "boot_status": "SELF_TEST_PASSED" if passed else "SELF_TEST_FAILED",
            "self_tests": tests,
            "self_test_latency_ms_measured": decimal_string(Fraction(time.perf_counter_ns() - t0, 1_000_000), 3),
        }

    def execute_sovereign_process(
        self,
        process_id: str,
        process_payload: bytes,
        state_vectors: Optional[List[List[Any]]] = None,
        edges: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        payload = process_payload.encode("utf-8") if isinstance(process_payload, str) else bytes(process_payload)
        decision = ALHarasSecurityFabric.evaluate_ingress(
            payload, state_vectors, edges=[tuple(e) for e in edges] if edges else None
        )
        ovid_id = sovereign_ovid_chain.store(payload)
        return {
            "process_id": process_id,
            "tenant": self.sovereign_state_id,
            "process_admitted": decision["admitted"],
            "decision": decision,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "ovid_id": ovid_id,
            "execution_latency_ms_measured": decimal_string(Fraction(time.perf_counter_ns() - t0, 1_000_000), 3),
            "content_classification_performed": False,
        }


class ALHarasSovereignOSProduct:
    """Product status for AL HARAS: self-test results and governance register."""

    @classmethod
    def get_sovereign_product_manifest(cls, sovereign_id: str) -> Dict[str, Any]:
        kernel = ALHarasTopologicalKernel(sovereign_id)
        return {
            "product": "AL HARAS (HYBA Security)",
            "tenant": sovereign_id,
            "self_test": kernel.boot_kernel(),
            "governance": SovereignGovernanceEngine.audit_sovereign_compliance(sovereign_id),
            "release_status": "NOT QUALIFIED: see RELEASE_DECISION_MCKINSEY_TECH.md and docs/claim-audit.md",
        }
