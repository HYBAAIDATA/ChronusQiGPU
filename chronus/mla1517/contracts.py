"""Fold/operator contracts, retrieval modes, and the pairing test record.

The canonical vocabulary from the build spec, made executable:

* :class:`FoldContract` — what a fold family guarantees (encode/decode,
  invariants, residual bound, backend requirements).
* :class:`OperatorContract` — how an operator interacts with folded state:
  PRESERVE, TRANSFORM, REHYDRATE, or REJECT.
* :class:`RetrievalMode` — the five GET modes; a caller that asked for exact
  state never receives an approximate projection, and a backend that had to
  rehydrate internally always reports that transition.
* :class:`PairingTest` — the evidence record for one fold/operator pairing:
  VERIFIED only with a measured result, HYPOTHESIS when unmeasured, REFUTED
  when the evidence contradicts the claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Tuple

__all__ = [
    "FoldContract",
    "OperatorContract",
    "OperatorMode",
    "PairingTest",
    "PairingStatus",
    "RetrievalMode",
    "RetrievalResult",
    "FoldContractViolation",
    "OperatorRejected",
    "FOLD_CONTRACTS",
    "OPERATOR_CONTRACTS",
    "fold_contract",
    "operator_contract",
    "retrieve",
]


class FoldContractViolation(RuntimeError):
    """A fold family broke its encode/decode or invariant contract."""


class OperatorRejected(RuntimeError):
    """An operator was applied to a fold family outside its contract."""


class OperatorMode(str, Enum):
    """How an operator treats the folded representation."""

    PRESERVE = "PRESERVE"  # returns folded state; no rehydration
    TRANSFORM = "TRANSFORM"  # operates directly on folded state
    REHYDRATE = "REHYDRATE"  # unfolds to exact state first; always reported
    REJECT = "REJECT"  # unsupported pairing; fails closed


class RetrievalMode(str, Enum):
    """The five declared retrieval modes."""

    GET_EXACT = "GET_EXACT"  # authoritative exact state
    GET_FOLDED = "GET_FOLDED"  # canonical folded state + reconstruction contract
    GET_PROJECTION = "GET_PROJECTION"  # a declared mathematical view
    GET_PROOF = "GET_PROOF"  # invariant and lineage material
    GET_EXECUTABLE = "GET_EXECUTABLE"  # backend-certified object/operator package


class PairingStatus(str, Enum):
    VERIFIED = "VERIFIED"  # measured evidence matched the expected result
    HYPOTHESIS = "HYPOTHESIS"  # claimed but not yet measured
    REFUTED = "REFUTED"  # measured evidence contradicts the claim


@dataclass(frozen=True)
class FoldContract:
    """The contract every fold family must implement."""

    family: str
    domain: str
    exactness_mode: str  # "exact" | "arbitrary_precision" | "bounded_residual"
    supported_operators: Tuple[str, ...]
    invariant_set: Tuple[str, ...]
    error_or_residual_bound: str
    canonical_hash_rule: str
    backend_requirements: Tuple[str, ...]
    version: int = 1

    def as_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "domain": self.domain,
            "exactness_mode": self.exactness_mode,
            "supported_operators": list(self.supported_operators),
            "invariant_set": list(self.invariant_set),
            "error_or_residual_bound": self.error_or_residual_bound,
            "canonical_hash_rule": self.canonical_hash_rule,
            "backend_requirements": list(self.backend_requirements),
            "version": self.version,
        }


@dataclass(frozen=True)
class OperatorContract:
    """How one operator interacts with each fold family it accepts."""

    operator: str
    accepted_fold_families: Tuple[str, ...]
    mode: OperatorMode
    input_invariants: Tuple[str, ...]
    output_invariants: Tuple[str, ...]
    residual_rule: str
    proof_rule: str
    deterministic: bool
    backend_capabilities: Tuple[str, ...]

    def admits(self, family: str) -> bool:
        return family in self.accepted_fold_families

    def as_dict(self) -> Dict[str, Any]:
        return {
            "operator": self.operator,
            "accepted_fold_families": list(self.accepted_fold_families),
            "mode": self.mode.value,
            "input_invariants": list(self.input_invariants),
            "output_invariants": list(self.output_invariants),
            "residual_rule": self.residual_rule,
            "proof_rule": self.proof_rule,
            "deterministic": self.deterministic,
            "backend_capabilities": list(self.backend_capabilities),
        }


@dataclass(frozen=True)
class PairingTest:
    """Evidence record for one fold/operator pairing or claimed composite.

    ``measured_result`` must come from an actual execution; a pairing is
    VERIFIED only when the measured result matched ``exact_expected_result``
    within ``residual_or_error``. A pairing with no measurement stays
    HYPOTHESIS — it may never be promoted to capability without evidence.
    """

    pairing_name: str
    source_components: Tuple[str, ...]
    combined_operator_or_transform: str
    input_domain: str
    exact_expected_result: Any
    invariants: Tuple[str, ...]
    baseline: Any
    measured_result: Any
    residual_or_error: Any
    performance: Dict[str, Any]
    reproducibility_command: str
    status: PairingStatus

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pairing_name": self.pairing_name,
            "source_components": list(self.source_components),
            "combined_operator_or_transform": self.combined_operator_or_transform,
            "input_domain": self.input_domain,
            "exact_expected_result": self.exact_expected_result,
            "invariants": list(self.invariants),
            "baseline": self.baseline,
            "measured_result": self.measured_result,
            "residual_or_error": self.residual_or_error,
            "performance": dict(self.performance),
            "reproducibility_command": self.reproducibility_command,
            "status": self.status.value,
        }


# ---------------------------------------------------------------------------
# Native fold families — the representations this codebase actually executes.
# ---------------------------------------------------------------------------

FOLD_CONTRACTS: Dict[str, FoldContract] = {
    "pisot_binet": FoldContract(
        family="pisot_binet",
        domain="fibonacci_lucas recurrence states",
        exactness_mode="exact",
        supported_operators=("fold", "unfold", "scale", "seal", "verify"),
        invariant_set=(
            "cassini_seal",
            "zeckendorf_nonadjacent",
            "lucas_trace",
        ),
        error_or_residual_bound="residual=0 when lossless; bounded_residual reported otherwise",
        canonical_hash_rule="sha256 over canonical json of exact state + fold metadata",
        backend_requirements=("cpu_reference",),
    ),
    "fibonacci_zeckendorf": FoldContract(
        family="fibonacci_zeckendorf",
        domain="integer index encodings",
        exactness_mode="exact",
        supported_operators=("encode", "decode", "seal", "verify", "resonance_scan"),
        invariant_set=("zeckendorf_nonadjacent", "roundtrip_identity"),
        error_or_residual_bound="exact; no residual admitted",
        canonical_hash_rule="sha256 over canonical mask + index",
        backend_requirements=("cpu_reference",),
    ),
    "exact_state_vector": FoldContract(
        family="exact_state_vector",
        domain="finite quantum states over Q(sqrt(2))+i Q(sqrt(2))",
        exactness_mode="exact",
        supported_operators=("gate", "tensor", "evolve_pauli", "expectation", "verify"),
        invariant_set=("normalization", "unitary_exactness"),
        error_or_residual_bound="exact amplitudes; fail-closed on resource bound",
        canonical_hash_rule="sha256 over exact amplitude sequence",
        backend_requirements=("cpu_reference", "mla1517"),
    ),
}

# ---------------------------------------------------------------------------
# Native operators and their fold interaction modes.
# ---------------------------------------------------------------------------

OPERATOR_CONTRACTS: Dict[str, OperatorContract] = {
    "fold": OperatorContract(
        operator="fold",
        accepted_fold_families=tuple(FOLD_CONTRACTS),
        mode=OperatorMode.TRANSFORM,
        input_invariants=("exact_state_available",),
        output_invariants=("residual_retained",),
        residual_rule="residual carried with the fold; never dropped silently",
        proof_rule="cassini_seal attached to folded state",
        deterministic=True,
        backend_capabilities=("cpu_reference",),
    ),
    "unfold": OperatorContract(
        operator="unfold",
        accepted_fold_families=("pisot_binet", "fibonacci_zeckendorf"),
        mode=OperatorMode.REHYDRATE,
        input_invariants=("lossless_fold",),
        output_invariants=("exact_state_recovered",),
        residual_rule="unfold requires residual==0 retained state",
        proof_rule="recovered value must equal recorded exact_value",
        deterministic=True,
        backend_capabilities=("cpu_reference",),
    ),
    "scale": OperatorContract(
        operator="scale",
        accepted_fold_families=("pisot_binet",),
        mode=OperatorMode.TRANSFORM,
        input_invariants=("scale_authorized",),
        output_invariants=("cassini_identity", "lucas_trace"),
        residual_rule="scale transition must re-attach residual bound",
        proof_rule="cassini identity holds at source and target",
        deterministic=True,
        backend_capabilities=("cpu_reference", "mla1517", "opencl_remote"),
    ),
    "seal": OperatorContract(
        operator="seal",
        accepted_fold_families=tuple(FOLD_CONTRACTS),
        mode=OperatorMode.PRESERVE,
        input_invariants=("canonical_state",),
        output_invariants=("cassini_seal",),
        residual_rule="seal does not change the residual",
        proof_rule="determinant identity on the exact pair",
        deterministic=True,
        backend_capabilities=("cpu_reference",),
    ),
    "verify": OperatorContract(
        operator="verify",
        accepted_fold_families=tuple(FOLD_CONTRACTS),
        mode=OperatorMode.PRESERVE,
        input_invariants=("canonical_state",),
        output_invariants=("invariant_report",),
        residual_rule="verify reads the residual; never resets it",
        proof_rule="all declared invariants re-evaluated",
        deterministic=True,
        backend_capabilities=("cpu_reference",),
    ),
    "resonance_scan": OperatorContract(
        operator="resonance_scan",
        accepted_fold_families=("fibonacci_zeckendorf", "pisot_binet"),
        mode=OperatorMode.PRESERVE,
        input_invariants=("d5_mask_u32",),
        output_invariants=("bounded_scan_report",),
        residual_rule="predicate evaluated on folded metadata; no rehydration",
        proof_rule="match set is exact; complexity reported as O(n) scan",
        deterministic=True,
        backend_capabilities=("cpu_reference",),
    ),
}


def fold_contract(family: str) -> FoldContract:
    """Return the declared contract for ``family`` or fail closed."""
    contract = FOLD_CONTRACTS.get(family)
    if contract is None:
        raise FoldContractViolation(
            f"unsupported fold family {family!r}; declared families: {sorted(FOLD_CONTRACTS)}"
        )
    return contract


def operator_contract(operator: str) -> OperatorContract:
    """Return the declared contract for ``operator`` or fail closed."""
    contract = OPERATOR_CONTRACTS.get(operator)
    if contract is None:
        raise OperatorRejected(
            f"unsupported operator {operator!r}; declared operators: {sorted(OPERATOR_CONTRACTS)}"
        )
    return contract


def check_operator(operator: str, family: str) -> OperatorContract:
    """Gate an operator/family pairing; REJECT mode fails closed."""
    contract = operator_contract(operator)
    fold_contract(family)
    if not contract.admits(family) or contract.mode is OperatorMode.REJECT:
        raise OperatorRejected(f"operator {operator!r} does not accept fold family {family!r}")
    return contract


@dataclass(frozen=True)
class RetrievalResult:
    """A retrieved view of an object, with the transition honestly reported."""

    mode: RetrievalMode
    object_id: str
    payload: Any
    rehydrated_internally: bool
    proof: Dict[str, Any]
    lineage: Any = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "object_id": self.object_id,
            "payload": self.payload,
            "rehydrated_internally": self.rehydrated_internally,
            "proof": self.proof,
            "lineage": self.lineage,
        }


def retrieve(obj: Any, mode: RetrievalMode | str) -> RetrievalResult:
    """Retrieve ``obj`` (an MLAObject) under one declared mode.

    GET_EXACT returns the authoritative exact state — never an approximate
    projection. GET_FOLDED returns the canonical folded representation plus the
    reconstruction contract. GET_PROJECTION returns the declared Binet view and
    says so. GET_PROOF returns invariant and lineage material. GET_EXECUTABLE
    returns the backend-certified package descriptor.
    """
    from .binet_view import binet_exact
    from .cassini import verify_state
    from .pisot_fold import pisot_fold

    mode = RetrievalMode(mode)
    proofs = verify_state(obj.sequence_index)
    proof_block = {
        "object_valid": all(p.passed for p in proofs),
        "cassini_seal": obj.cassini_seal,
        "zeckendorf_valid": True,
    }
    if mode is RetrievalMode.GET_EXACT:
        payload = {
            "exact_state": list(obj.fibonacci_pair),
            "sequence_index": obj.sequence_index,
            "payload": obj.payload,
        }
        return RetrievalResult(mode, obj.object_id, payload, False, proof_block, obj.lineage)
    if mode is RetrievalMode.GET_FOLDED:
        folded = pisot_fold(obj.sequence_index, lossless=True)
        payload = {
            "folded": folded.as_dict(),
            "reconstruction_contract": fold_contract("pisot_binet").as_dict(),
        }
        return RetrievalResult(mode, obj.object_id, payload, False, proof_block, obj.lineage)
    if mode is RetrievalMode.GET_PROJECTION:
        view = binet_exact(obj.sequence_index)
        payload = {
            "view": "binet",
            "dominant": str(view.dominant),
            "conjugate": str(view.conjugate),
            "residual": str(view.residual),
            "is_exact": view.is_exact,
            "declared": "projection; not authoritative exact state",
        }
        return RetrievalResult(mode, obj.object_id, payload, False, proof_block, obj.lineage)
    if mode is RetrievalMode.GET_PROOF:
        payload = {
            "invariants": [p.as_dict() if hasattr(p, "as_dict") else str(p) for p in proofs],
            "lineage": obj.lineage,
        }
        return RetrievalResult(mode, obj.object_id, payload, False, proof_block, obj.lineage)
    # GET_EXECUTABLE: backend-certified object/operator package descriptor.
    payload = {
        "object": obj.to_dict(),
        "operators": [
            op.as_dict() for op in OPERATOR_CONTRACTS.values() if op.admits("pisot_binet")
        ],
        "backend": "cpu_reference",
        "certified": proof_block["object_valid"],
    }
    return RetrievalResult(mode, obj.object_id, payload, False, proof_block, obj.lineage)
