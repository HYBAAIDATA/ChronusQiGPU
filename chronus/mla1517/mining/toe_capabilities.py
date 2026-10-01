"""Observed-only production plane for TOE's five mining intelligences.

Reconciled from two parallel designs (QUANTUMDATA2 2026-09-28 branches).
TOE's powers are preserved; this layer distinguishes *capability exists*
from *this live observation authorises an action*, and never fills missing
telemetry with a class default presented as observed intelligence.

* Causal: may rank pools only when latency, stale rate and fee are observed.
* Geometric: may steer ordering inside the leased domain, only when the TOE
  signal belongs to the same job/node/sequence as the frame; it never changes
  the SHA predicate or creates unleased coverage.
* Plastic: may recommend compute tuning only from measured temperature, power
  and hash rate.
* Counterfactual: independently rehashes a real candidate as a shadow
  verifier; the Stratum proof adapter and the pool remain the authority.
* Quantum: the exact TOE witness travels live; treasury actions need separate
  balance, fee, destination and authorisation inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from toe.intelligences import (
    CausalIntelligence,
    CounterfactualIntelligence,
    GeometricIntelligence,
    PlasticIntelligence,
    QuantumIntelligence,
)

from .search_plan import SearchPlan
from .toe_decision import TOEMiningDecisionFrame
from .toe_signal import TOECausalSignal


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _digest(value: Any) -> str:
    raw = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _finite(mapping: Mapping[str, Any], name: str) -> float | None:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _entry(action: bool, **fields: Any) -> dict[str, Any]:
    return {"capability_available": True, "action_available": action, "available": action, **fields}


@dataclass(frozen=True)
class TOECapabilitySnapshot:
    causal: Mapping[str, Any]
    geometric: Mapping[str, Any]
    plastic: Mapping[str, Any]
    counterfactual: Mapping[str, Any]
    quantum: Mapping[str, Any]
    receipt_digest: str

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "causal": dict(self.causal),
            "geometric": dict(self.geometric),
            "plastic": dict(self.plastic),
            "counterfactual": dict(self.counterfactual),
            "quantum": dict(self.quantum),
            "receipt_digest": self.receipt_digest,
        }


class TOEMiningCapabilityPlane:
    """Production eligibility layer over the five TOE intelligences."""

    def __init__(self) -> None:
        self.causal = CausalIntelligence()
        self.geometric = GeometricIntelligence()
        self.plastic = PlasticIntelligence()
        self.counterfactual = CounterfactualIntelligence()
        self.quantum = QuantumIntelligence()
        self.last_snapshot: TOECapabilitySnapshot | None = None
        self.last_counterfactual: Mapping[str, Any] | None = None

    @property
    def last_receipt(self) -> TOECapabilitySnapshot | None:
        return self.last_snapshot

    @staticmethod
    def _pool_rows(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        if not rows:
            return []
        out: list[dict[str, Any]] = []
        for row in rows:
            name = row.get("name")
            latency = _finite(row, "latency_ms")
            stale = _finite(row, "stale_rate")
            fee = _finite(row, "fee_rate")
            if not isinstance(name, str) or not name or None in (latency, stale, fee):
                return []
            out.append({"name": name, "latency_ms": latency, "stale_rate": stale, "fee_rate": fee})
        return out

    @staticmethod
    def _bound_face(frame: TOEMiningDecisionFrame, signal: TOECausalSignal | None) -> int | None:
        if not isinstance(signal, TOECausalSignal) or not signal.is_valid():
            return None
        if (signal.job_id, signal.node_id, signal.sequence) != (
            frame.job_id,
            frame.node_id,
            frame.sequence,
        ):
            return None
        return signal.face_bias

    def _snapshot(
        self,
        frame: TOEMiningDecisionFrame,
        geometric: dict[str, Any],
        telemetry: Mapping[str, Any] | None,
        pool_observations: Sequence[Mapping[str, Any]] | None,
        binding: Mapping[str, Any],
    ) -> TOECapabilitySnapshot:
        pools = self._pool_rows(pool_observations)
        if pools:
            causal = _entry(
                True,
                truth_class="observed_pool_telemetry",
                decision=self.causal.select_pool(pools).to_dict(),
                authority="pool_orchestration_advisory",
            )
        else:
            causal = _entry(False, reason="observed latency_ms/stale_rate/fee_rate unavailable")

        telemetry = telemetry or {}
        temperature = _finite(telemetry, "temperature_c")
        power = _finite(telemetry, "power_w")
        hashrate = _finite(telemetry, "measured_hashrate")
        if None not in (temperature, power, hashrate):
            profile = self.plastic.configure_dispatch(
                current_temp_c=temperature,
                current_power_w=power,
                observed_hashrate=hashrate,
            )
            # The MMIO ABI exposes throttle but not workgroup resize: advice
            # until an executor attests that the batch size was applied.
            plastic = _entry(
                True,
                truth_class="measured_hardware_telemetry",
                profile=profile.to_dict(),
                authority="compute_profile_advisory",
            )
        else:
            plastic = _entry(
                False, reason="temperature_c, power_w and measured_hashrate are jointly required"
            )

        counterfactual = _entry(
            False,
            reason="deferred until a locally valid candidate exists",
            authority="shadow_sha256d_and_alternative_reasoning",
        )
        quantum = _entry(
            True,
            truth_class="exact_tensor_witness",
            exact_field=frame.exact_field,
            state_commitment=frame.exact_state_commitment,
            input_digest=frame.exact_input_digest,
            execution_backend=frame.execution_backend,
            treasury_action_available=False,
            treasury_reason="wallet balance, network fee, destination and authorisation are separate inputs",
        )
        payload = {
            "toe_frame_digest": frame.frame_digest,
            **binding,
            "causal": causal,
            "geometric": geometric,
            "plastic": plastic,
            "counterfactual": counterfactual,
            "quantum": quantum,
        }
        snapshot = TOECapabilitySnapshot(
            causal=causal,
            geometric=geometric,
            plastic=plastic,
            counterfactual=counterfactual,
            quantum=quantum,
            receipt_digest=_digest(payload),
        )
        self.last_snapshot = snapshot
        return snapshot

    def observe(
        self,
        *,
        frame: TOEMiningDecisionFrame,
        signal: TOECausalSignal | None,
        candidate_window: Sequence[int],
        telemetry: Mapping[str, Any] | None = None,
        pool_observations: Sequence[Mapping[str, Any]] | None = None,
    ) -> TOECapabilitySnapshot:
        """Receipt for a chooser observation over the solver's candidate window."""
        if not frame.is_valid():
            raise ValueError("valid TOE decision frame required")
        face = self._bound_face(frame, signal)
        window = list(candidate_window)
        geometric = _entry(
            face is not None and bool(window),
            truth_class="observed_candidate_window" if window else "unavailable",
            preferred_face=face,
            candidate_count=len(window),
            candidate_min=min(window) if window else None,
            candidate_max=max(window) if window else None,
            cassini_parity_valid=self.geometric.verify_cassini_parity_integer(frame.sequence + 1),
            authority="ordering_advisory",
        )
        return self._snapshot(frame, geometric, telemetry, pool_observations, {})

    def observe_plan(
        self,
        *,
        frame: TOEMiningDecisionFrame,
        signal: TOECausalSignal | None,
        plan: SearchPlan,
        hardware_telemetry: Mapping[str, Any] | None = None,
        pool_observations: Sequence[Mapping[str, Any]] | None = None,
    ) -> TOECapabilitySnapshot:
        """Receipt for a leased SearchPlan that names this frame in its evidence."""
        if not frame.is_valid():
            raise ValueError("valid TOE decision frame required")
        if plan.evidence_refs.get("toe_frame_digest") != frame.frame_digest:
            raise ValueError("SearchPlan is not bound to the supplied TOE frame")
        face = self._bound_face(frame, signal)
        geometric = _entry(
            face is not None,
            truth_class="leased_plan_geometry",
            preferred_face=face,
            lane_order_digest=_digest(list(plan.lane_order)),
            leased_start=plan.base_step,
            leased_window=plan.window,
            cassini_parity_valid=self.geometric.verify_cassini_parity_integer(frame.sequence + 1),
            authority="ordering_advisory",
        )
        return self._snapshot(
            frame, geometric, hardware_telemetry, pool_observations, {"plan_id": plan.plan_id}
        )

    def verify_candidate(
        self,
        *,
        nonce: int,
        header: bytes,
        target: int,
        proof_valid: bool,
        alternatives: Sequence[int] = (),
    ) -> Mapping[str, Any]:
        """Run Counterfactual Intelligence as an independent SHA256d shadow check."""
        analysis = self.counterfactual.evaluate_submission(
            candidate_nonce=int(nonce),
            header_template=bytes(header[:76]),
            target_int=int(target),
            alternative_nonces=list(alternatives[:5]),
        )
        result = _entry(
            True,
            truth_class="independent_sha256d_shadow_check",
            proof_adapter_valid=bool(proof_valid),
            toe_shadow_valid=bool(analysis.is_valid_share),
            agreement=bool(analysis.is_valid_share) == bool(proof_valid),
            analysis=analysis.to_dict(),
            authority="shadow_only_pool_remains_external",
        )
        self.last_counterfactual = result
        return result

    def learn_pool_outcome(
        self,
        *,
        accepted: bool | None,
        preferred_face: int | None,
        pool_name: str | None = None,
        latency_ms: float | None = None,
    ) -> None:
        """Feed only literal pool outcomes back into intelligences with matching evidence."""
        if accepted is None:
            return
        if preferred_face is not None and 0 <= preferred_face < self.geometric.num_faces:
            self.geometric.learn(preferred_face, 1 if accepted else 0)
        self.counterfactual.learn("direct_submission", bool(accepted))
        if pool_name and latency_ms is not None and math.isfinite(latency_ms):
            self.causal.learn(pool_name, bool(accepted), float(latency_ms))


# Names from the parallel claude-branch design; one implementation owns both.
TOEFiveIntelligencePlane = TOEMiningCapabilityPlane
FiveIntelligenceReceipt = TOECapabilitySnapshot

__all__ = [
    "FiveIntelligenceReceipt",
    "TOECapabilitySnapshot",
    "TOEFiveIntelligencePlane",
    "TOEMiningCapabilityPlane",
]
