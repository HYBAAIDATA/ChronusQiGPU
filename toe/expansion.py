"""TOE expansion envelope.

This module is the second-stage TOE surface: it does not repeat the bridge
smoke tests. It collapses observation, algebraic-family routing, 11D
certificate generation, and the existing MLA1517 scale controller into one
bounded, proof-carrying result. Mathematical scale is allowed to grow beyond
the fixed hardware catalogue; physical execution remains budgeted and the
truth boundary is explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any, Dict, Mapping, Optional, Sequence

from lucas.ladder import SCALE_RUNGS

try:
    from .poincare_golden_11d import compute_zeckendorf_certificate
    from kellogg.quantum_tensor import encode_data_to_state
    from .operator_compilers import compile_operator
    from .bridge import TOEBridge
except ImportError:  # direct execution fallback
    from .poincare_golden_11d import compute_zeckendorf_certificate
    from kellogg.quantum_tensor import encode_data_to_state
    from toe.operator_compilers import compile_operator
    from toe.bridge import TOEBridge

try:
    from mla1517.scale import ScaleBudget, ScaleController, ScalePoint
except ImportError:  # pragma: no cover - only for isolated source execution
    ScaleBudget = ScaleController = ScalePoint = None  # type: ignore[assignment]


@dataclass(frozen=True)
class TOEExpansionPolicy:
    """Finite physical policy over an unbounded-by-catalogue math scale."""

    scale_indices: tuple[int, ...] = SCALE_RUNGS
    scale_families: tuple[str, ...] = (
        "golden",
        "silver",
        "plastic",
        "supergolden",
        "tribonacci",
    )
    max_index: int = 10000
    max_steps: int = 1024
    max_bit_length: int = 1_000_000
    max_physical_bytes: int = 128 * 1024 * 1024
    max_work_units: int = 100_000_000
    proof_bytes: int = 32
    metadata_bytes: int = 256
    replication_factor: int = 1


@dataclass(frozen=True)
class TOEExpansionResult:
    """One deterministic TOE expansion envelope."""

    available: bool
    input_digest: str
    domain: str
    capabilities: Mapping[str, Any]
    operator: Mapping[str, Any]
    algebraic_signature: Mapping[str, Any]
    scale_program: Sequence[Mapping[str, Any]]
    state_certificate: Mapping[str, Any]
    execution_envelope: Mapping[str, Any]
    capability_matrix: Mapping[str, Any]
    proof_boundary: Mapping[str, Any]
    receipt_digest: str
    diagnostics: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": bytes(value).hex()}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value cannot enter TOE expansion")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _digest(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


class TOEExpansionEngine:
    """Collapse new data surfaces into TOE without inventing domain models."""

    def __init__(
        self, bridge: Optional[TOEBridge] = None, policy: Optional[TOEExpansionPolicy] = None
    ) -> None:
        self.bridge = bridge or TOEBridge()
        self.policy = policy or TOEExpansionPolicy()

    def _scale_program(self) -> list[Mapping[str, Any]]:
        if ScaleController is None:
            raise RuntimeError("MLA1517 scale controller is unavailable")
        budget = ScaleBudget(
            max_index=self.policy.max_index,
            max_steps=self.policy.max_steps,
            max_bit_length=self.policy.max_bit_length,
            max_physical_bytes=self.policy.max_physical_bytes,
            max_work_units=self.policy.max_work_units,
            proof_bytes=self.policy.proof_bytes,
            metadata_bytes=self.policy.metadata_bytes,
            replication_factor=self.policy.replication_factor,
        )
        controller = ScaleController(
            budget=budget,
            allow_families=self.policy.scale_families,
        )
        points = [
            ScalePoint(index=index, family=family)
            for index in self.policy.scale_indices
            for family in self.policy.scale_families
        ]
        decisions = controller.plan(points)
        return [
            {
                "point": asdict(decision.point),
                "estimate": asdict(decision.estimate),
                "accepted": decision.accepted,
                "reason": decision.reason,
            }
            for decision in decisions
        ]

    def collapse(
        self, data: Any, *, domain: str = "unspecified", context_id: str = ""
    ) -> TOEExpansionResult:
        """Run the expanded TOE contract on one observed payload."""
        digest = _digest(data)
        operator = compile_operator(data).as_dict()
        toe_result = self.bridge.predict(data)
        signature = self.bridge.algebraic_signature(data)
        scale_program = self._scale_program()
        state = encode_data_to_state(data, dim=32, normalize=True)
        probabilities = state.probabilities()
        vector = [float(probabilities[i]) for i in range(11)]
        certificate = compute_zeckendorf_certificate(vector, context_id=context_id or digest)
        sections = {
            "observe": toe_result.get("state_tomography", {}),
            "evolve": toe_result.get("trajectory_prediction", {}),
            "explain": toe_result.get("causal_analysis", {}),
            "intervene": toe_result.get("causal_ladder", {}),
            "exact_tensor": toe_result.get("exact_tensor", {}),
            "operator": operator,
            "route_family": signature,
            "scale": scale_program,
            "fold_integrity": certificate.to_dict(),
        }
        all_capabilities = all(
            isinstance(value, Mapping) and value.get("available", False)
            for key, value in sections.items()
            if key in {"observe", "evolve", "explain", "intervene", "exact_tensor"}
        )
        all_scales = all(item["accepted"] for item in scale_program)
        capability_matrix = {
            "exact_tensor": {
                "status": "implemented",
                "truth_class": "exact_state_witness",
                "claim": "declared MLA1517 operations only",
            },
            "operator_compilation": {
                "status": "implemented",
                "truth_class": "compiled_observation",
                "claim": "typed operator contract, not semantic understanding",
            },
            "causal_ladder": {
                "status": "implemented",
                "truth_class": "computational_contract",
                "claim": "graph surgery and structural evaluation",
            },
            "pisot_scale_program": {
                "status": "implemented",
                "truth_class": "exact_integer_family_limbs",
                "claim": "budgeted multi-family scale authorization",
            },
            "physical_acceleration": {
                "status": "hardware_gated",
                "truth_class": "measured_only",
                "claim": "no device throughput asserted",
            },
        }
        try:
            from toe.poincare_yangmills import capability_record

            capability_matrix["finite_su2_gauge"] = capability_record()
        except Exception as exc:
            capability_matrix["finite_su2_gauge"] = {
                "status": "unavailable",
                "truth_class": "finite_volume_spectrum",
                "claim": "finite 2I spectrum did not compute",
                "error": str(exc),
                "proof_claim": False,
                "continuum_claim": False,
            }
        execution_envelope = {
            "math_scale": max(self.policy.scale_indices),
            "scale_families": list(self.policy.scale_families),
            "logical_state_size": sum(
                item["estimate"]["logical_state_bits"] for item in scale_program
            ),
            "physical_state_bytes": sum(
                item["estimate"]["physical_bytes"] for item in scale_program
            ),
            "physical_bytes_committed": sum(
                item["estimate"]["physical_bytes"] for item in scale_program
            ),
            "bytes_moved": 0,
            "proof_bytes": self.policy.proof_bytes,
            "checkpoint_count": len(scale_program),
            "capacity_mode": "candidate_exponential_measured_only",
            "performance_claim": "measured_only",
        }
        proof_boundary = {
            "theorem_proven": False,
            "invariants": [
                "deterministic_input_digest",
                "operator_digest_matches_input",
                "exact_tensor_normalized",
                "scale_budget_authorized",
                "zeckendorf_mask_non_adjacent",
            ],
            "claim_class": "computational_contract",
        }
        receipt_payload = {
            "input_digest": digest,
            "operator": operator,
            "scale_program": scale_program,
            "state_certificate": certificate.to_dict(),
            "execution_envelope": execution_envelope,
            "proof_boundary": proof_boundary,
        }
        receipt_digest = hashlib.sha256(
            json.dumps(
                _jsonable(receipt_payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        return TOEExpansionResult(
            available=bool(toe_result.get("available", False) and all_capabilities and all_scales),
            input_digest=digest,
            domain=domain,
            capabilities=sections,
            operator=operator,
            algebraic_signature=signature,
            scale_program=scale_program,
            state_certificate=certificate.to_dict(),
            execution_envelope=execution_envelope,
            capability_matrix=capability_matrix,
            proof_boundary=proof_boundary,
            receipt_digest=receipt_digest,
            diagnostics={
                "engine": "TOEExpansionEngine",
                "source": "TOEBridge + bespoke exact tensor + operator compiler + MLA1517 ScaleController + 11D certificate",
            },
        )


__all__ = ["TOEExpansionPolicy", "TOEExpansionResult", "TOEExpansionEngine"]
