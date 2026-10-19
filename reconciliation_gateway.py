"""Canonical re-export bridge for reconciliation_gateway.

Provides direct access to MetacognitiveGatekeeper, ReflexReceipt, and fast_reflex_interrupt_arc
from the root namespace as specified in the EUCLID benchmark harness.
"""

from euclid.cognition.reconciliation_gateway import (
    ACTIVE_CAPABILITIES,
    ACTIVE_COGNITIVE_STATES,
    CapabilityToken,
    ERNSpikePayload,
    MetacognitiveGatekeeper,
    ReflexReceipt,
    fast_reflex_interrupt_arc,
)

__all__ = [
    "ACTIVE_CAPABILITIES",
    "ACTIVE_COGNITIVE_STATES",
    "CapabilityToken",
    "ERNSpikePayload",
    "MetacognitiveGatekeeper",
    "ReflexReceipt",
    "fast_reflex_interrupt_arc",
]
