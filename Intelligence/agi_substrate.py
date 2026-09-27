"""Canonical AGI substrate interface (``Intelligence.agi_substrate``).

This module provides the stable AGI-substrate contract consumed by the
resilience layer, multi-agent execution graph, and multi-agent intelligence
modules:

- ``CanonicalAGISubstrate`` — the substrate object exposing
  ``execute_capability(request)`` and ``set_degradation_mode(mode)``.
- ``AGIRequest`` / ``AGIResponse`` — the request/response dataclasses.
- ``AGICapability`` — the capability enum (PREDICT, REASON, ...).
- ``AGIDegradationMode`` — the degradation-mode enum.

The substrate is a thin, honest adapter over the layered intelligence
substrate (``Intelligence.layered_intelligence_substrate.AGISubstrate``).
It does not fabricate intelligence: when no real capability is available it
returns a baseline response with ``confidence=0.0`` so downstream callers can
distinguish a real AGI result from a placeholder.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger("Intelligence.agi_substrate")

PHI = (1 + math.sqrt(5)) / 2


class AGICapability(Enum):
    """Capabilities the AGI substrate can be asked to perform."""

    PERCEIVE = "perceive"
    PREDICT = "predict"
    REASON = "reason"
    OPTIMIZE = "optimize"
    EXPLAIN = "explain"
    SYNTHESIZE = "synthesize"


class AGIDegradationMode(Enum):
    """Operational degradation modes for the AGI substrate."""

    FULL = "full"
    REDUCED = "reduced"
    MINIMAL = "minimal"
    OFFLINE = "offline"


@dataclass
class AGITelemetry:
    """Per-response telemetry returned alongside an AGI result."""

    confidence: float
    coherence: float
    capability: AGICapability
    latency_ms: float = 0.0


@dataclass
class AGIRequest:
    """A request to the AGI substrate."""

    request_id: str
    capability: AGICapability
    entity_data: Dict[str, Any] = field(default_factory=dict)
    domain: str = "generic"
    context: Dict[str, Any] = field(default_factory=dict)
    quantum_boost: float = 1.0


@dataclass
class AGIResponse:
    """A response from the AGI substrate."""

    request_id: str
    capability: AGICapability
    result: Any
    confidence: float
    telemetry: AGITelemetry
    degraded: bool = False


class CanonicalAGISubstrate:
    """Canonical AGI substrate — unified intelligence interface.

    Wraps the layered intelligence substrate (``AGISubstrate``) and exposes a
    request/response capability API. When the underlying substrate cannot
    service a capability, a baseline (confidence=0.0) response is returned so
    callers can detect the placeholder rather than mistaking it for a real
    intelligent result.
    """

    def __init__(
        self,
        dimension: int = 128,
        substrate: Optional[Any] = None,
        consciousness_threshold: float = 0.8,
    ) -> None:
        self.dimension = dimension
        self.consciousness_threshold = consciousness_threshold
        self.degradation_mode = AGIDegradationMode.FULL
        self.request_history: list[AGIResponse] = []

        if substrate is not None:
            self._substrate = substrate
        else:
            try:
                from Intelligence.layered_intelligence_substrate import AGISubstrate

                self._substrate = AGISubstrate(dimension=dimension)
            except Exception:  # pragma: no cover - substrate is optional
                logger.warning(
                    "AGISubstrate unavailable; CanonicalAGISubstrate runs in baseline mode"
                )
                self._substrate = None

    def set_degradation_mode(self, mode: AGIDegradationMode) -> None:
        """Set the operational degradation mode of the substrate."""
        self.degradation_mode = mode
        logger.info("AGI degradation mode set to: %s", mode.value)

    def execute_capability(self, request: AGIRequest) -> AGIResponse:
        """Execute a capability request and return a response.

        In ``OFFLINE`` mode, or when no underlying substrate is present, this
        returns a baseline response with ``confidence=0.0`` so callers can
        distinguish a placeholder from a real result.
        """
        if self.degradation_mode == AGIDegradationMode.OFFLINE or self._substrate is None:
            return self._baseline_response(request)

        # Map AGI capability to a substrate layer when possible.
        from Intelligence.layered_intelligence_substrate import IntelligenceLayer

        layer_map = {
            AGICapability.PERCEIVE: IntelligenceLayer.PERCEPTUAL,
            AGICapability.PREDICT: IntelligenceLayer.COGNITIVE,
            AGICapability.REASON: IntelligenceLayer.REASONING,
            AGICapability.OPTIMIZE: IntelligenceLayer.REASONING,
            AGICapability.EXPLAIN: IntelligenceLayer.METACOGNITIVE,
            AGICapability.SYNTHESIZE: IntelligenceLayer.CONSCIOUSNESS,
        }
        layer = layer_map.get(request.capability, IntelligenceLayer.COGNITIVE)

        try:
            data = request.entity_data
            vec = self._coerce_vector(data, request.quantum_boost)
            result = self._substrate.process_input(vec, layer)
            confidence = float(max(0.0, min(1.0, result.get("output_coherence", 0.0))))
            coherence = float(result.get("phi_correlation", 0.0))
        except Exception:  # pragma: no cover - defensive
            return self._baseline_response(request)

        # In reduced/minimal modes, discount confidence honestly.
        if self.degradation_mode == AGIDegradationMode.REDUCED:
            confidence *= 0.5
        elif self.degradation_mode == AGIDegradationMode.MINIMAL:
            confidence *= 0.25

        telemetry = AGITelemetry(
            confidence=confidence,
            coherence=coherence,
            capability=request.capability,
        )
        response = AGIResponse(
            request_id=request.request_id,
            capability=request.capability,
            result=result,
            confidence=confidence,
            telemetry=telemetry,
            degraded=self.degradation_mode != AGIDegradationMode.FULL,
        )
        self.request_history.append(response)
        return response

    def _baseline_response(self, request: AGIRequest) -> AGIResponse:
        telemetry = AGITelemetry(
            confidence=0.0,
            coherence=0.0,
            capability=request.capability,
        )
        response = AGIResponse(
            request_id=request.request_id,
            capability=request.capability,
            result=None,
            confidence=0.0,
            telemetry=telemetry,
            degraded=True,
        )
        self.request_history.append(response)
        return response

    @staticmethod
    def _coerce_vector(data: Any, quantum_boost: float) -> np.ndarray:
        """Coerce request entity data into a substrate-sized input vector."""
        if isinstance(data, np.ndarray):
            vec = data.astype(float)
        elif isinstance(data, dict):
            vals = [float(v) for v in data.values() if isinstance(v, (int, float))]
            vec = np.asarray(vals, dtype=float)
        elif isinstance(data, (list, tuple)):
            vec = np.asarray([float(v) for v in data], dtype=float)
        else:
            vec = np.asarray([float(quantum_boost)], dtype=float)
        if vec.size == 0:
            vec = np.asarray([float(quantum_boost)], dtype=float)
        return vec * float(quantum_boost)


def create_canonical_agi_substrate(dimension: int = 128) -> CanonicalAGISubstrate:
    """Convenience factory for the canonical AGI substrate."""
    return CanonicalAGISubstrate(dimension=dimension)


__all__ = [
    "AGICapability",
    "AGIDegradationMode",
    "AGIRequest",
    "AGIResponse",
    "AGITelemetry",
    "CanonicalAGISubstrate",
    "create_canonical_agi_substrate",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
