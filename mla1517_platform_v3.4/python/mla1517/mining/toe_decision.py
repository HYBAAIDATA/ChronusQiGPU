"""Production TOE decision frame for canonical PYTHIA mining.

One frame carries the *whole* TOE result into mining, reconciled from two
parallel designs (QUANTUMDATA2 feat/toe-mining-production-consolidation and
feat/toe-production-consolidation-claude, 2026-09-28):

* meaning: confidences, coherence, entropy, trend, key factors and the Pearl
  ladder flags, with an explicit split between surfaces eligible to steer
  work (state tomography, trajectory, exact tensor, expansion) and surfaces
  carried for audit only (causal explanation, causal ladder);
* integrity: a digest per surface, a digest of the full result and of the
  execution evidence, the exact field, and a frame digest over all of it.

Validation takes the stricter rule wherever the two designs differed: the
exact tensor must be exactly normalised, the exact and expansion input
digests must both be present and equal, and every scale point must be
accepted. No TOE field can validate a nonce, target, header, share or pool
outcome; consensus vocabulary is rejected recursively before a frame exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping

from .toe_signal import _assert_no_consensus_fields


class TOEDecisionFrameUnavailable(RuntimeError):
    """TOE produced no complete, self-consistent production decision frame."""


_STEERING_SURFACES = (
    "state_tomography",
    "trajectory_prediction",
    "exact_tensor",
    "toe_expansion",
)
_AUDIT_ONLY_SURFACES = ("causal_analysis", "causal_ladder")
_REQUIRED_SURFACES = _STEERING_SURFACES + _AUDIT_ONLY_SURFACES
_FRAME_DOMAIN = "pythia.toe-mining-decision-frame.v2"


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": bytes(value).hex()}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TOEDecisionFrameUnavailable("non-finite TOE value cannot enter decision frame")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _digest(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _available_section(result: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    section = result.get(name)
    if not isinstance(section, Mapping) or not section.get("available", False):
        raise TOEDecisionFrameUnavailable(f"TOE surface {name!r} is unavailable")
    return section


@dataclass(frozen=True)
class TOEMiningDecisionFrame:
    """Digest-bound TOE evidence attached to one mining observation.

    ``audit_only_surfaces`` are carried but are not permission to steer SHA
    work: exploratory causal/explanation evidence never becomes authority.
    """

    job_id: str
    node_id: int
    sequence: int
    combined_confidence: float
    state_confidence: float
    trajectory_confidence: float
    causal_confidence: float
    causal_ladder_confidence: float
    coherence: float
    entropy: float
    trend: str
    trend_rate: float
    key_factors: tuple[tuple[str, float], ...]
    intervention_identifiable: bool
    counterfactual_available: bool
    exact_state: bool
    exact_field: str
    exact_input_digest: str
    exact_state_commitment: str
    expansion_receipt_digest: str
    expansion_input_digest: str
    algebraic_family: str | None
    scale_authorized: bool
    execution_backend: str
    execution_evidence_digest: str
    full_result_digest: str
    surface_digests: Mapping[str, str] = field(default_factory=dict)
    steering_surfaces: tuple[str, ...] = _STEERING_SURFACES
    audit_only_surfaces: tuple[str, ...] = _AUDIT_ONLY_SURFACES
    explanation_status: str = "audit_only_unvalidated_fidelity"
    causal_ladder_status: str = "audit_only_partial_effect_recovery"
    frame_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_digests", MappingProxyType(dict(self.surface_digests)))
        if not self.frame_digest:
            object.__setattr__(self, "frame_digest", self.expected_digest())

    def digest_payload(self) -> Mapping[str, Any]:
        # dataclasses.asdict deep-copies fields and cannot copy a mappingproxy.
        value = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "frame_digest"}
        value["surface_digests"] = dict(self.surface_digests)
        return {"domain": _FRAME_DOMAIN, **value}

    def expected_digest(self) -> str:
        return _digest(self.digest_payload())

    def is_valid(self) -> bool:
        numeric = (
            self.combined_confidence,
            self.state_confidence,
            self.trajectory_confidence,
            self.causal_confidence,
            self.causal_ladder_confidence,
            self.coherence,
            self.entropy,
            self.trend_rate,
        )
        unit = (
            self.combined_confidence,
            self.state_confidence,
            self.trajectory_confidence,
            self.causal_confidence,
            self.causal_ladder_confidence,
        )
        return (
            bool(self.job_id)
            and self.node_id >= 0
            and self.sequence >= 0
            and all(math.isfinite(value) for value in numeric)
            and all(0.0 <= value <= 1.0 for value in unit)
            and self.coherence >= 0.0
            and self.entropy >= 0.0
            and self.exact_state
            and bool(self.exact_field)
            and bool(self.exact_input_digest)
            and self.exact_input_digest == self.expansion_input_digest
            and bool(self.exact_state_commitment)
            and bool(self.expansion_receipt_digest)
            and self.scale_authorized
            and bool(self.execution_backend)
            and bool(self.execution_evidence_digest)
            and bool(self.full_result_digest)
            and set(self.surface_digests) == set(_REQUIRED_SURFACES)
            and all(bool(value) for value in self.surface_digests.values())
            and self.frame_digest == self.expected_digest()
        )

    def advisory_summary(self) -> Mapping[str, Any]:
        """Small evidence summary safe to attach to mining decision telemetry."""
        return {
            "frame_digest": self.frame_digest,
            "expansion_receipt_digest": self.expansion_receipt_digest,
            "execution_backend": self.execution_backend,
            "combined_confidence": self.combined_confidence,
            "coherence": self.coherence,
            "entropy": self.entropy,
            "trend": self.trend,
            "trend_rate": self.trend_rate,
            "algebraic_family": self.algebraic_family,
            "scale_authorized": self.scale_authorized,
            "exact_state": self.exact_state,
            "intervention_identifiable": self.intervention_identifiable,
            "counterfactual_available": self.counterfactual_available,
            "explanation_status": self.explanation_status,
            "causal_ladder_status": self.causal_ladder_status,
        }

    def evidence_refs(self) -> Mapping[str, Any]:
        """Compact refs suitable for immutable ``SearchPlan.evidence_refs``."""
        return {
            "toe_frame_digest": self.frame_digest,
            "toe_result_digest": self.full_result_digest,
            "toe_expansion_receipt": self.expansion_receipt_digest,
            "toe_input_digest": self.expansion_input_digest,
            "toe_exact_state_commitment": self.exact_state_commitment,
            "toe_execution_backend": self.execution_backend,
            "toe_execution_evidence_digest": self.execution_evidence_digest,
            "toe_surface_digests": dict(self.surface_digests),
            "toe_combined_confidence": self.combined_confidence,
        }


def build_toe_decision_frame(context: Any) -> TOEMiningDecisionFrame:
    """Collapse a complete ``TOEMiningContext`` into production evidence.

    Every advertised TOE surface must be present. Consensus-domain keys are
    rejected recursively before any frame is produced.
    """
    result = getattr(context, "result", None)
    evidence = getattr(context, "execution_evidence", None)
    if not isinstance(result, Mapping):
        raise TOEDecisionFrameUnavailable("TOEMiningContext.result must be a mapping")
    if not isinstance(evidence, Mapping):
        raise TOEDecisionFrameUnavailable("TOE execution evidence must be a mapping")

    _assert_no_consensus_fields(result)

    sections = {name: _available_section(result, name) for name in _REQUIRED_SURFACES}
    tomo = sections["state_tomography"]
    traj = sections["trajectory_prediction"]
    causal = sections["causal_analysis"]
    ladder = sections["causal_ladder"]
    exact = sections["exact_tensor"]
    expansion = sections["toe_expansion"]

    if exact.get("exact") is not True or exact.get("normalized_exact") is not True:
        raise TOEDecisionFrameUnavailable("exact tensor witness is not exact-normalized")
    exact_input_digest = str(exact.get("input_digest") or "")
    expansion_input = str(expansion.get("input_digest") or "")
    if not exact_input_digest or exact_input_digest != expansion_input:
        raise TOEDecisionFrameUnavailable(
            "exact tensor and expansion digests do not bind the same input"
        )

    scale_program = expansion.get("scale_program")
    if not isinstance(scale_program, (list, tuple)) or not scale_program:
        raise TOEDecisionFrameUnavailable("TOE expansion scale program is unavailable")
    if not all(isinstance(item, Mapping) and item.get("accepted") is True for item in scale_program):
        raise TOEDecisionFrameUnavailable("TOE scale program contains a refused point")

    factors: list[tuple[str, float]] = []
    for item in causal.get("key_factors") or ():
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                factors.append((str(item[0]), float(item[1])))
            except (TypeError, ValueError):
                continue

    signature = expansion.get("algebraic_signature")
    algebraic_family = None
    if isinstance(signature, Mapping) and signature.get("available", False):
        family = signature.get("family", signature.get("best_family"))
        if family is not None:
            algebraic_family = str(family)

    frame = TOEMiningDecisionFrame(
        job_id=str(getattr(context, "job_id", "")),
        node_id=int(getattr(context, "node_id", -1)),
        sequence=int(getattr(context, "sequence", -1)),
        combined_confidence=float(result.get("confidence", 0.0)),
        state_confidence=float(tomo.get("confidence", 0.0)),
        trajectory_confidence=float(traj.get("confidence", 0.0)),
        causal_confidence=float(causal.get("confidence", 0.0)),
        causal_ladder_confidence=float(ladder.get("confidence", 0.0)),
        coherence=float(tomo.get("coherence", 0.0)),
        entropy=float(tomo.get("entropy", 0.0)),
        trend=str(traj.get("trend", "stable")),
        trend_rate=float(traj.get("trend_rate", 0.0)),
        key_factors=tuple(factors),
        intervention_identifiable=bool(ladder.get("identifiable", False)),
        counterfactual_available=ladder.get("counterfactual_value") is not None,
        exact_state=True,
        exact_field=str(exact.get("field") or ""),
        exact_input_digest=exact_input_digest,
        exact_state_commitment=str(exact.get("state_commitment") or ""),
        expansion_receipt_digest=str(expansion.get("receipt_digest") or ""),
        expansion_input_digest=expansion_input,
        algebraic_family=algebraic_family,
        scale_authorized=True,
        execution_backend=str(evidence.get("backend") or ""),
        execution_evidence_digest=_digest(evidence),
        full_result_digest=_digest(result),
        surface_digests={name: _digest(sections[name]) for name in _REQUIRED_SURFACES},
    )
    if not frame.is_valid():
        raise TOEDecisionFrameUnavailable("TOE decision frame failed production validity checks")
    return frame


# Names from the parallel claude-branch design; one implementation owns both.
TOEFrameUnavailable = TOEDecisionFrameUnavailable
TOEProductionFrame = TOEMiningDecisionFrame
build_toe_production_frame = build_toe_decision_frame

__all__ = [
    "TOEDecisionFrameUnavailable",
    "TOEFrameUnavailable",
    "TOEMiningDecisionFrame",
    "TOEProductionFrame",
    "build_toe_decision_frame",
    "build_toe_production_frame",
]
