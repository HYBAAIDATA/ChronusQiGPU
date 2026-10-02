"""Deterministic Lucas/Pisot scaling research with explicit claim boundaries."""

from __future__ import annotations

from decimal import Decimal, localcontext
import hashlib
import json
import math
import struct
from typing import Any

from .core import fibonacci, lucas

DISCOVERY_INDICES: tuple[int, ...] = (10, 12, 15, 18, 20)
DISCOVERY_CLASSIFICATION = "AUTOBIOGRAPHICAL_DISCOVERY_SEED"
SCHEMA = "hyba.research.lucas-pisot-scaling.v1"


def _precision(n: int) -> int:
    return max(128, n + 80)


def _phi(n: int) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = _precision(n)
        return +((Decimal(1) + Decimal(5).sqrt()) / 2)


def pisot_certificate(n: int) -> dict[str, Any]:
    """Numerically witness the exact Binet/Pisot identity at high precision."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    with localcontext() as ctx:
        ctx.prec = _precision(n)
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        power = phi**n
        residual = abs(power - Decimal(lucas(n)))
        expected = phi ** (-n)
        relative = residual / power
        return {
            "n": n,
            "fibonacci": str(fibonacci(n)),
            "lucas": str(lucas(n)),
            "phi_power": str(+power),
            "absolute_residual": str(+residual),
            "expected_residual": str(+expected),
            "relative_residual": str(+relative),
            "normalized_residual": str(+(residual * power)),
            "nearest_integer": str(power.to_integral_value()),
            "cassini_hoggatt": str(lucas(n) ** 2 - 5 * fibonacci(n) ** 2),
        }


def float64_boundary() -> dict[str, int]:
    """Expose where binary64 can no longer carry the true Pisot residual."""
    representation_collapse = None
    pow_integral = None
    phi_float = (1.0 + math.sqrt(5.0)) / 2.0
    with localcontext() as ctx:
        ctx.prec = 400
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        for n in range(2, 200):
            if representation_collapse is None and float(phi**n) == float(lucas(n)):
                representation_collapse = n
            via_pow = phi_float**n
            if pow_integral is None and via_pow == round(via_pow):
                pow_integral = n
    if representation_collapse is None or pow_integral is None:
        raise AssertionError("binary64 boundary not found")
    return {
        "true_residual_unrepresentable_first_n": representation_collapse,
        "float_pow_integral_first_n": pow_integral,
        "float_pow_error_at_first_integral": int(phi_float**pow_integral - lucas(pow_integral)),
        "float_pow_error_at_n76": int(phi_float**76 - lucas(76)),
    }


def _float32(value: float) -> float:
    return struct.unpack("!f", struct.pack("!f", value))[0]


def float32_boundary() -> dict[str, Any]:
    """Show where the current 11-D Float32 transport erases Pisot drift."""
    with localcontext() as ctx:
        ctx.prec = 200
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        first_collapse = None
        for n in range(2, 100):
            if _float32(float(phi**n)) == _float32(float(lucas(n))):
                first_collapse = n
                break
    if first_collapse is None:
        raise AssertionError("Float32 collapse boundary not found")
    return {
        "true_residual_unrepresentable_first_n": first_collapse,
        "discovery_indices_preserving_residual": [
            n
            for n in DISCOVERY_INDICES
            if _float32(float(phi**n)) != _float32(float(lucas(n)))
        ],
        "discovery_indices_erasing_residual": [
            n
            for n in DISCOVERY_INDICES
            if _float32(float(phi**n)) == _float32(float(lucas(n)))
        ],
    }


def research_report() -> dict[str, Any]:
    rows = [pisot_certificate(n) for n in DISCOVERY_INDICES]
    controls = sorted({n + d for n in DISCOVERY_INDICES for d in (-1, 0, 1) if n + d >= 2})
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "provenance": {
            "indices": list(DISCOVERY_INDICES),
            "classification": DISCOVERY_CLASSIFICATION,
            "meaning": "date-of-birth-derived discovery indices",
            "claim_boundary": "explains candidate origin; does not establish performance",
        },
        "selected": rows,
        "adjacent_controls": [pisot_certificate(n) for n in controls],
        "float64_boundary": float64_boundary(),
        "float32_transport_boundary": float32_boundary(),
        "verified_claims": [
            "L_n is the exact trace of phi^n",
            "L_n^2 - 5F_n^2 = 4(-1)^n",
            "for n >= 2, L_n is the nearest integer to phi^n",
            "absolute residual is phi^-n and relative residual is phi^-2n",
            "selected and adjacent indices follow the same normalized Pisot law",
        ],
        "falsified_or_unproven": [
            "the selected indices have a special Pisot advantage after controlling for n",
            "Lucas/Pisot structure alone establishes mining or scheduling advantage",
            "binary64 is suitable for exact high-index Pisot certification",
            "the current Float32 11-D transport preserves the n=18 and n=20 Pisot residuals",
        ],
        "non_claims": [
            "mining advantage",
            "scheduling advantage",
            "hardware speedup",
            "production qualification",
        ],
    }
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report["content_sha256"] = hashlib.sha256(payload).hexdigest()
    return report


__all__ = [
    "DISCOVERY_CLASSIFICATION",
    "DISCOVERY_INDICES",
    "SCHEMA",
    "float32_boundary",
    "float64_boundary",
    "pisot_certificate",
    "research_report",
]
