"""TOEIntelligenceRuntime — the production composition root.

Wires the five concentric loops into a single callable object:

    TOEBridge (engine)
      → IntelligenceFeedbackCore (middle loop)
        → EvidenceChain (governance)
          → SubsystemRegistry (health)
            → ASICore hooks (observe-only)
              → UnifiedAnalyticsPlatform (delivery)

Every ``predict()`` / ``explain()`` / ``forecast()`` / ``causal()`` call flows
through the same path: validate → encode → measure → evolve → compare →
intervene → record → receipt → return.  Fail-closed on every boundary.

This module is deliberately framework-neutral: it has no HTTP, no async
event loops, and no external ML dependencies.  It composes only components
that already exist in this repository.  The CIaaS API layer
(``toe/ciaas_api.py``) wraps this runtime.

Production readiness: **false** until every acceptance gate (A–H) in
``docs/TOE_CIAAS_ACCEPTANCE_GATES.md`` is green.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "TenantContext",
    "TOEIntelligenceRuntimeConfig",
    "RuntimeReceipt",
    "RuntimeResponse",
    "TOEIntelligenceRuntime",
    "DEFAULT_CONFIG",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_PAYLOAD_BYTES = 1_000_000  # 1 MB
_MAX_PAYLOAD_SERIES = 10_000  # max individual numeric values
_DEFAULT_HILBERT_DIM = 32

# Mining consensus-boundary vocabulary — these keys must never appear in a
# TOE output when the runtime is operating in mining mode.  Mirrors the
# guard in ``chronus/.../toe_signal.py::_assert_no_consensus_fields``.
_MINING_CONSENSUS_VOCABULARY = frozenset({
    "target",
    "nonce",
    "header",
    "sha256d",
    "share",
    "block_hash",
    "merkle_root",
    "previous_block_hash",
    "bits",
    "proof_of_work",
    "difficulty_target",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantContext:
    """Per-tenant isolation context.

    Each tenant gets its own encoded-state space; Zeckendorf-signature
    deduplication is within-tenant only.
    """

    tenant_id: str
    api_key_hash: Optional[str] = None  # sha256 of the caller's key
    mode: str = "standard"  # "standard" | "mining"
    allowed_claims: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.tenant_id or not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        if self.mode not in ("standard", "mining"):
            raise ValueError(f"mode must be 'standard' or 'mining', got {self.mode!r}")


@dataclass
class TOEIntelligenceRuntimeConfig:
    """Configuration for the composition root."""

    hilbert_dim: int = _DEFAULT_HILBERT_DIM
    hbar: float = 1.0
    mass: float = 1.0
    omega: float = 0.5
    max_payload_bytes: int = _MAX_PAYLOAD_BYTES
    max_payload_series: int = _MAX_PAYLOAD_SERIES
    enable_feedback: bool = True
    enable_evidence: bool = True
    enable_asi: bool = True
    enable_platform: bool = False  # requires connector credentials
    production_ready: bool = False  # always false until gates A–H pass

    def __post_init__(self) -> None:
        if self.hilbert_dim < 2:
            raise ValueError("hilbert_dim must be >= 2")
        if self.max_payload_bytes < 1024:
            raise ValueError("max_payload_bytes must be >= 1024")


@dataclass(frozen=True)
class RuntimeReceipt:
    """Tamper-evident receipt attached to every prediction."""

    receipt_id: str
    tenant_id: str
    operation: str
    payload_digest: str
    result_digest: str
    timestamp: float
    evidence_source: str
    evidence_status: str
    observe_only: bool
    production_ready: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeErrorInfo:
    """Error details when a request fails."""

    code: str
    message: str
    detail: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


@dataclass
class RuntimeResponse:
    """Unified response envelope for every runtime operation."""

    ok: bool
    tenant_id: str
    operation: str
    receipt: Optional[RuntimeReceipt] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[RuntimeErrorInfo] = None
    degraded: bool = False  # true when optional wiring is absent
    decision_id: Optional[str] = None  # correlates an outcome back to the decision
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        d = {
            "ok": self.ok,
            "tenant_id": self.tenant_id,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "degraded": self.degraded,
        }
        if self.receipt:
            d["receipt"] = self.receipt.as_dict()
        if self.result:
            d["result"] = self.result
        if self.error:
            d["error"] = self.error.as_dict()
        if self.decision_id:
            d["decision_id"] = self.decision_id
        return d


# ---------------------------------------------------------------------------
# Composition root
# ---------------------------------------------------------------------------


class TOEIntelligenceRuntime:
    """Production composition root for the TOE intelligence stack.

    Wires the five loops:

    1. **Inner loop** — ``TOEBridge`` (encode → |ψ⟩ → measure → evolve →
       compare → intervene)
    2. **Middle loop** — ``IntelligenceFeedbackCore`` (record decision →
       process outcome → calibrate → attribute → learn)
    3. **Outer loop** — ``ASICore`` hooks (observe-only: capability report,
       health, never acts)
    4. **Governance** — ``EvidenceChain`` (append-only hash-linked receipts)
    5. **Delivery** — ``UnifiedAnalyticsPlatform`` (optional; requires
       connector credentials)

    Parameters
    ----------
    config:
        Runtime configuration (hilbert dimension, payload limits, feature
        flags).
    bridge:
        Pre-constructed ``TOEBridge`` instance.  If ``None``, a new one is
        created from ``config``.
    feedback_core:
        Pre-constructed ``IntelligenceFeedbackCore``.  If ``None``, a new
        one is created.
    evidence_chain:
        Pre-constructed ``EvidenceChain``.  If ``None``, a new empty one
        is created.
    asi:
        Pre-constructed ``ASICore``.  If ``None``, ASI hooks are
        disabled (degraded mode).
    platform:
        Pre-constructed ``UnifiedAnalyticsPlatform``.  If ``None``,
        platform delivery is disabled (degraded mode).
    """

    def __init__(
        self,
        config: Optional[TOEIntelligenceRuntimeConfig] = None,
        bridge: Any = None,
        feedback_core: Any = None,
        evidence_chain: Any = None,
        asi: Any = None,
        platform: Any = None,
    ) -> None:
        self.config = config or TOEIntelligenceRuntimeConfig()
        self._degraded: list[str] = []

        # --- inner loop ----------------------------------------------------
        if bridge is not None:
            self.bridge = bridge
        else:
            from toe.bridge import TOEBridge

            self.bridge = TOEBridge(
                {
                    "hilbert_dim": self.config.hilbert_dim,
                    "hbar": self.config.hbar,
                    "mass": self.config.mass,
                    "omega": self.config.omega,
                }
            )

        # --- middle loop --------------------------------------------------
        if feedback_core is not None:
            self.feedback_core = feedback_core
        elif self.config.enable_feedback:
            try:
                from resonance_intelligence.feedback_core import (
                    IntelligenceFeedbackCore,
                )

                self.feedback_core = IntelligenceFeedbackCore()
            except Exception as exc:
                self.feedback_core = None
                self._degraded.append(f"feedback_core: {exc}")
        else:
            self.feedback_core = None

        # --- governance loop ----------------------------------------------
        if evidence_chain is not None:
            self.evidence_chain = evidence_chain
        elif self.config.enable_evidence:
            try:
                from euclid.evidence import EvidenceChain

                self.evidence_chain = EvidenceChain()
            except Exception as exc:
                self.evidence_chain = None
                self._degraded.append(f"evidence_chain: {exc}")
        else:
            self.evidence_chain = None

        # --- outer loop (observe-only) ------------------------------------
        if asi is not None:
            self.asi = asi
        elif self.config.enable_asi:
            try:
                from asi.asi_core import ASICore

                self.asi = ASICore()
            except Exception as exc:
                self.asi = None
                self._degraded.append(f"asi_core: {exc}")
        else:
            self.asi = None

        # --- delivery loop (optional) --------------------------------------
        if platform is not None:
            self.platform = platform
        elif self.config.enable_platform:
            try:
                from toe.unified.platform import UnifiedAnalyticsPlatform

                self.platform = UnifiedAnalyticsPlatform()
            except Exception as exc:
                self.platform = None
                self._degraded.append(f"platform: {exc}")
        else:
            self.platform = None

        self._tenant_decisions: dict[str, list[str]] = {}

        mode = "full" if not self._degraded else "degraded"
        logger.info(
            "[TOE-RUNTIME] initialised: bridge=%s feedback=%s evidence=%s "
            "asi=%s platform=%s mode=%s",
            self.bridge is not None and "ok" or "missing",
            self.feedback_core is not None and "ok" or "off",
            self.evidence_chain is not None and "ok" or "off",
            self.asi is not None and "ok" or "off",
            self.platform is not None and "ok" or "off",
            mode,
        )

    # -- properties --------------------------------------------------------

    @property
    def degraded(self) -> bool:
        """True when any optional wiring failed to initialise."""
        return bool(self._degraded)

    @property
    def degradation_reasons(self) -> list[str]:
        return list(self._degraded)

    # -- validation -------------------------------------------------------

    def _validate_tenant(self, tenant: TenantContext) -> None:
        """Fail-closed if tenant is invalid."""
        if not isinstance(tenant, TenantContext):
            raise TypeError("tenant must be a TenantContext")
        if not tenant.tenant_id:
            raise ValueError("tenant_id is empty")

    def _validate_payload_size(self, payload: Any) -> None:
        """Fail-closed if payload exceeds configured limits."""
        try:
            raw = json.dumps(payload, default=str, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"payload is not JSON-serialisable: {exc}")
        if len(raw.encode("utf-8")) > self.config.max_payload_bytes:
            raise ValueError(
                f"payload exceeds {self.config.max_payload_bytes} bytes"
            )

    def _count_numeric(self, payload: Any) -> int:
        """Count numeric values in a nested payload."""
        count = 0

        def _walk(x: Any) -> None:
            nonlocal count
            if isinstance(x, dict):
                for v in x.values():
                    _walk(v)
            elif isinstance(x, (list, tuple)):
                for v in x:
                    _walk(v)
            elif isinstance(x, (int, float)):
                count += 1
            elif isinstance(x, (bytes, bytearray)):
                count += len(x)

        _walk(payload)
        return count

    def _check_mining_boundary(self, result: dict[str, Any], tenant: TenantContext) -> None:
        """Fail-closed if consensus vocabulary appears in mining-mode output.

        Only enforced when ``tenant.mode == 'mining'``.  Non-mining domains
        may legitimately use keys like ``target`` or ``header``.
        """
        if tenant.mode != "mining":
            return

        def _scan(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in _MINING_CONSENSUS_VOCABULARY:
                        raise _MiningConsensusBoundaryError(
                            f"consensus field '{k}' found at {path or 'root'} "
                            "in mining-mode TOE output"
                        )
                    _scan(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, (list, tuple)):
                for i, v in enumerate(obj):
                    _scan(v, f"{path}[{i}]")

        _scan(result)

    # -- receipt building --------------------------------------------------

    def _digest(self, payload: Any) -> str:
        """SHA-256 digest of the canonical JSON payload."""
        raw = json.dumps(payload, default=str, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _build_receipt(
        self,
        tenant: TenantContext,
        operation: str,
        payload: Any,
        result: dict[str, Any],
    ) -> RuntimeReceipt:
        return RuntimeReceipt(
            receipt_id=str(uuid.uuid4()),
            tenant_id=tenant.tenant_id,
            operation=operation,
            payload_digest=self._digest(payload),
            result_digest=self._digest(result),
            timestamp=time.time(),
            evidence_source="toe.bridge.TOEBridge",
            evidence_status="MEASURED",
            observe_only=True,
            production_ready=self.config.production_ready,
        )

    def _record_decision(
        self,
        tenant: TenantContext,
        operation: str,
        result: dict[str, Any],
        confidence: Optional[float],
    ) -> Optional[str]:
        """Record decision in the feedback core and evidence chain.

        Returns the decision id the feedback core assigned, or ``None`` when
        the record could not be stored — the caller may then surface a
        decision_id only when it genuinely correlates to a stored decision.

        ``confidence`` is ``None`` when the engine reported none — recorded as
        such, never replaced by an invented value.  ``module_outputs`` carries
        the operation's own engine output so causal attribution sees the real
        contributors (state tomography, factor ranking, trajectory, ladder),
        not a predict-only slice that silently empties for other operations.
        """
        module_outputs = {
            key: value for key, value in result.items() if isinstance(value, dict)
        }
        if not module_outputs:
            module_outputs = {"result": result}
        decision_id: Optional[str] = None
        if self.feedback_core is not None:
            try:
                decision_id = self.feedback_core.record_decision(
                    decision=operation_tag(result),
                    confidence=confidence,
                    module_outputs=module_outputs,
                    context={
                        "tenant": tenant.tenant_id,
                        "mode": tenant.mode,
                        "operation": operation,
                        "confidence_reported": confidence is not None,
                    },
                    source_id=tenant.tenant_id,
                )
                self._tenant_decisions.setdefault(tenant.tenant_id, []).append(
                    decision_id
                )
            except Exception as exc:
                logger.warning("[TOE-RUNTIME] feedback record failed: %s", exc)

        if self.evidence_chain is not None:
            try:
                self.evidence_chain.append(
                    "toe-decision",
                    {
                        "tenant": tenant.tenant_id,
                        "operation": operation,
                        "decision_id": decision_id,
                        "confidence": confidence,
                        "confidence_reported": confidence is not None,
                        "timestamp": time.time(),
                    },
                )
            except Exception as exc:
                logger.warning("[TOE-RUNTIME] evidence append failed: %s", exc)
        return decision_id

    # -- public API -------------------------------------------------------

    def predict(
        self,
        payload: Any,
        tenant: TenantContext,
        claim_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> RuntimeResponse:
        """Run a full TOE prediction: encode → measure → evolve → compare → intervene.

        Returns a ``RuntimeResponse`` with the full intelligence output
        (state tomography, trajectory prediction, causal analysis, causal
        ladder) and a tamper-evident receipt.
        """
        return self._execute("predict", payload, tenant, claim_id, metadata)

    def explain(
        self,
        payload: Any,
        tenant: TenantContext,
        claim_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> RuntimeResponse:
        """Run causal analysis: factor ranking, recommendations, model agreement."""
        return self._execute("explain", payload, tenant, claim_id, metadata)

    def forecast(
        self,
        payload: Any,
        tenant: TenantContext,
        horizon: Optional[float] = None,
        claim_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> RuntimeResponse:
        """Run trajectory prediction: Schrödinger evolution, trend, intervention points."""
        if horizon is not None:
            meta = dict(metadata or {})
            meta["horizon"] = horizon
            metadata = meta
        return self._execute("forecast", payload, tenant, claim_id, metadata)

    def causal(
        self,
        payload: Any,
        tenant: TenantContext,
        intervention_node: Optional[str] = None,
        intervention_value: Optional[float] = None,
        observed: Optional[Mapping[str, Any]] = None,
        claim_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> RuntimeResponse:
        """Run the full causal ladder: P(Y|X), P(Y|do X), counterfactual."""
        if intervention_node is not None:
            meta = dict(metadata or {})
            meta["intervention_node"] = intervention_node
            meta["intervention_value"] = intervention_value
            if observed:
                meta["observed"] = dict(observed)
            metadata = meta
        return self._execute("causal", payload, tenant, claim_id, metadata)

    def record_outcome(
        self,
        decision_id: str,
        outcome: Any,
        tenant: TenantContext,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> RuntimeResponse:
        """Feed an outcome back into the learning loop.

        Records the outcome in the ``IntelligenceFeedbackCore`` and
        appends an evidence record.  Does not mutate models autonomously —
        bounded parameter updates only.
        """
        self._validate_tenant(tenant)
        if self.feedback_core is None:
            return RuntimeResponse(
                ok=False,
                tenant_id=tenant.tenant_id,
                operation="record_outcome",
                error=RuntimeErrorInfo(
                    code="feedback_disabled",
                    message="Feedback core is not available (degraded mode)",
                ),
                degraded=True,
            )
        try:
            report = self.feedback_core.process(
                decision_id=decision_id,
                outcome=outcome,
                source_id=tenant.tenant_id,
            )
            if self.evidence_chain is not None:
                self.evidence_chain.append(
                    "feedback-outcome",
                    {
                        "tenant": tenant.tenant_id,
                        "decision_id": decision_id,
                        "calibration_score": report.calibration_score,
                        "learning_signal": report.learning_signal,
                        "timestamp": time.time(),
                    },
                )
            receipt = RuntimeReceipt(
                receipt_id=str(uuid.uuid4()),
                tenant_id=tenant.tenant_id,
                operation="record_outcome",
                payload_digest=self._digest({"decision_id": decision_id}),
                result_digest=self._digest({"calibration_score": report.calibration_score}),
                timestamp=time.time(),
                evidence_source="resonance_intelligence.feedback_core",
                evidence_status="MEASURED",
                observe_only=True,
                production_ready=self.config.production_ready,
            )
            return RuntimeResponse(
                ok=True,
                tenant_id=tenant.tenant_id,
                operation="record_outcome",
                receipt=receipt,
                result={
                    "calibration_score": report.calibration_score,
                    "learning_signal": report.learning_signal,
                    "recommendations": report.recommendations,
                },
            )
        except Exception as exc:
            logger.error("[TOE-RUNTIME] record_outcome failed: %s", exc)
            return RuntimeResponse(
                ok=False,
                tenant_id=tenant.tenant_id,
                operation="record_outcome",
                error=RuntimeErrorInfo(
                    code="feedback_error",
                    message=str(exc),
                ),
            )

    # -- health / readiness -----------------------------------------------

    def health(self) -> dict[str, Any]:
        """Health report: engine availability, loop status, degradation."""
        engine_ok = False
        engine_status: dict[str, Any] = {}
        try:
            engine_ok = self.bridge.available()
            engine_status = self.bridge.status()
        except Exception as exc:
            engine_status = {"error": str(exc)}

        asi_report: dict[str, Any] = {}
        if self.asi is not None:
            try:
                asi_report = self.asi.capability_report()
            except Exception as exc:
                asi_report = {"error": str(exc)}
        else:
            asi_report = {"available": False, "reason": "ASI disabled"}

        return {
            "engine_available": engine_ok,
            "engine_status": engine_status,
            "feedback_available": self.feedback_core is not None,
            "evidence_available": self.evidence_chain is not None,
            "asi_report": asi_report,
            "platform_available": self.platform is not None,
            "degraded": self.degraded,
            "degradation_reasons": self.degradation_reasons,
            "production_ready": self.config.production_ready,
            "timestamp": time.time(),
        }

    def ready(self) -> bool:
        """True when the engine is available and no critical degradation."""
        try:
            if not self.bridge.available():
                return False
        except Exception:
            return False
        return True

    # -- internal ---------------------------------------------------------

    def _execute(
        self,
        operation: str,
        payload: Any,
        tenant: TenantContext,
        claim_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> RuntimeResponse:
        """Execute a TOE operation through the full pipeline."""
        # 1. Validate tenant
        try:
            self._validate_tenant(tenant)
        except (TypeError, ValueError) as exc:
            return self._error(tenant, operation, "invalid_tenant", str(exc))

        # 2. Validate payload
        try:
            self._validate_payload_size(payload)
            if self._count_numeric(payload) > self.config.max_payload_series:
                return self._error(
                    tenant,
                    operation,
                    "payload_too_large",
                    f"payload exceeds {self.config.max_payload_series} numeric values",
                )
        except ValueError as exc:
            return self._error(tenant, operation, "payload_invalid", str(exc))

        # 3. Check engine availability
        try:
            if not self.bridge.available():
                return self._error(
                    tenant, operation, "engine_unavailable", "TOE bridge is not available"
                )
        except Exception as exc:
            return self._error(tenant, operation, "engine_error", str(exc))

        # 4. Execute the TOE operation
        try:
            if operation == "predict":
                result = self.bridge.predict(payload)
            elif operation == "explain":
                result = self.bridge.explain_causality(payload)
                result = result.as_dict() if hasattr(result, "as_dict") else result
            elif operation == "forecast":
                result = self.bridge.predict_trajectory(payload)
                result = result.as_dict() if hasattr(result, "as_dict") else result
            elif operation == "causal":
                causal_result = self.bridge.explain_causality(payload)
                result = (
                    causal_result.as_dict()
                    if hasattr(causal_result, "as_dict")
                    else causal_result
                )
                # Add the causal ladder if available
                try:
                    ladder = self.bridge.causal_ladder(payload)
                    ladder_dict = ladder.as_dict() if hasattr(ladder, "as_dict") else ladder
                    if isinstance(result, dict):
                        result["causal_ladder"] = ladder_dict
                except Exception:
                    pass  # causal ladder is optional
            else:
                return self._error(
                    tenant, operation, "unknown_operation", f"Unknown operation: {operation}"
                )
        except Exception as exc:
            logger.error("[TOE-RUNTIME] %s failed: %s", operation, exc)
            return self._error(tenant, operation, "execution_error", str(exc))

        # 5. Normalise result to dict
        if not isinstance(result, dict):
            result = {"result": result}

        # 6. Mining consensus boundary check
        try:
            self._check_mining_boundary(result, tenant)
        except _MiningConsensusBoundaryError as exc:
            logger.error("[TOE-RUNTIME] consensus boundary violation: %s", exc)
            return self._error(
                tenant,
                operation,
                "consensus_boundary_violation",
                str(exc),
            )

        # 7. Extract confidence — None when the engine did not report one.
        # An absent confidence is recorded as absent; it is not replaced by a
        # fabricated midpoint (which would poison calibration as if the engine
        # had actually claimed 50% certainty).
        confidence: Optional[float] = None
        if isinstance(result, dict):
            conf = result.get("confidence")
            if isinstance(conf, (int, float)) and math.isfinite(float(conf)):
                confidence = max(0.0, min(1.0, float(conf)))

        # 8. Build receipt
        receipt = self._build_receipt(tenant, operation, payload, result)

        # 9. Record in feedback + evidence — the surfaced decision_id is the
        # one the feedback core stored, so record_outcome can find it.
        decision_id = self._record_decision(tenant, operation, result, confidence)

        # 10. ASI observe-only health hint (never acts)
        asi_hint: dict[str, Any] = {}
        if self.asi is not None:
            try:
                asi_hint = {"capability_report": self.asi.capability_report()}
            except Exception as exc:
                asi_hint = {"error": str(exc)}
                logger.warning("[TOE-RUNTIME] ASI probe failed: %s", exc)

        # 11. Return response — the caller needs decision_id to correlate a
        # later record_outcome back to this decision (the voyage's feedback
        # step is unreachable otherwise).
        return RuntimeResponse(
            ok=True,
            tenant_id=tenant.tenant_id,
            operation=operation,
            receipt=receipt,
            result=result,
            degraded=self.degraded,
            decision_id=decision_id,
            timestamp=time.time(),
        )

    def _error(
        self,
        tenant: TenantContext,
        operation: str,
        code: str,
        message: str,
    ) -> RuntimeResponse:
        """Build a fail-closed error response."""
        return RuntimeResponse(
            ok=False,
            tenant_id=tenant.tenant_id,
            operation=operation,
            error=RuntimeErrorInfo(code=code, message=message),
            timestamp=time.time(),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MiningConsensusBoundaryError(Exception):
    """Raised when consensus vocabulary appears in mining-mode TOE output."""


def operation_tag(result: dict[str, Any]) -> str:
    """Derive an operation tag from a TOE result for the feedback core."""
    if "state_tomography" in result:
        return "toe_predict"
    if "key_factors" in result:
        return "toe_causal"
    if "energies" in result or "trend" in result:
        return "toe_forecast"
    return "toe_operation"


DEFAULT_CONFIG = TOEIntelligenceRuntimeConfig()
