"""Deterministic Lucas/Pisot research with explicit semantic boundaries."""

from __future__ import annotations

from decimal import Decimal, localcontext
import hashlib
import json
import math
from typing import Any, Mapping

from .core import fibonacci, lucas
from .ladder import CURRICULUM_RUNGS

# The discovery seed is the curriculum ladder — imported from the canonical
# single ladder source (lucas/ladder.py) so the rung set cannot drift.
DISCOVERY_INDICES: tuple[int, ...] = CURRICULUM_RUNGS
DISCOVERY_CLASSIFICATION = "AUTOBIOGRAPHICAL_DISCOVERY_SEED"
SCHEMA = "hyba.research.lucas-pisot-scaling.v2"
DIGEST_CANONICALIZATION = "RFC8259-like UTF-8 JSON: sort_keys=True,separators=(',',':'); omit content_sha256"


def _precision(n: int) -> int:
    return max(128, n + 80)


def pisot_certificate(n: int) -> dict[str, Any]:
    """Numerically witness the exact identity using high-precision Decimal."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    with localcontext() as ctx:
        ctx.prec = _precision(n)
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        power = phi**n
        residual = abs(power - Decimal(lucas(n)))
        expected = phi ** (-n)
        return {
            "n": n,
            "fibonacci": str(fibonacci(n)),
            "lucas": str(lucas(n)),
            "phi_power": str(+power),
            "absolute_residual": str(+residual),
            "expected_residual": str(+expected),
            "relative_residual": str(+(residual / power)),
            "normalized_residual": str(+(residual * power)),
            "nearest_integer": str(power.to_integral_value()),
            "cassini_hoggatt": str(lucas(n) ** 2 - 5 * fibonacci(n) ** 2),
        }


def float64_boundary() -> dict[str, int]:
    """Expose where host binary64 can no longer carry the true residual."""
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


def host_float32_boundary() -> dict[str, Any]:
    """Exercise the real host codec; this is not an OpenCL-device result."""
    import numpy as np
    from toe.poincare_golden_11d import to_gpu_input

    with localcontext() as ctx:
        ctx.prec = 200
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2

        def encoded_pair(n: int) -> tuple[np.float32, np.float32]:
            states = np.zeros((2, 11), dtype=np.float64)
            states[0, 0] = float(phi**n)
            states[1, 0] = float(lucas(n))
            flat = to_gpu_input(states, role="parametric", allow_lossy=True).reshape(2, 11)
            return flat[0, 0], flat[1, 0]

        first_collapse = next(n for n in range(2, 100) if encoded_pair(n)[0] == encoded_pair(n)[1])
        preserving = [n for n in DISCOVERY_INDICES if encoded_pair(n)[0] != encoded_pair(n)[1]]
        erasing = [n for n in DISCOVERY_INDICES if encoded_pair(n)[0] == encoded_pair(n)[1]]
    return {
        "scope": "host_codec_only_not_opencl_device_qualification",
        "codec": "toe.poincare_golden_11d.to_gpu_input",
        "true_residual_unrepresentable_first_n": first_collapse,
        "discovery_indices_preserving_residual": preserving,
        "discovery_indices_erasing_residual": erasing,
    }


def float32_boundary() -> dict[str, Any]:
    """Backward-compatible alias for the host Float32 boundary."""
    return host_float32_boundary()


def canonical_report_payload(report: Mapping[str, Any]) -> bytes:
    payload = dict(report)
    payload.pop("content_sha256", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_content_sha256(report: Mapping[str, Any]) -> bool:
    claimed = report.get("content_sha256")
    return isinstance(claimed, str) and hashlib.sha256(canonical_report_payload(report)).hexdigest() == claimed


def research_report() -> dict[str, Any]:
    controls = sorted({n + d for n in DISCOVERY_INDICES for d in (-1, 0, 1) if n + d >= 2})
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "digest_canonicalization": DIGEST_CANONICALIZATION,
        "semantic_roles": {
            "decorative": "labels, geometry, visualization; no invariant inferred",
            "parametric": "seeds, schedules, subset selection; approximation disclosed",
            "structural": "gates, folds, transitions, invariants; distinctions must be preserved",
            "certifying": "witnesses and acceptance evidence; authoritative arithmetic required",
        },
        "provenance": {
            "indices": list(DISCOVERY_INDICES),
            "classification": DISCOVERY_CLASSIFICATION,
            "meaning": "date-of-birth-derived discovery indices",
            "claim_boundary": "explains candidate origin; does not establish performance",
        },
        "selected": [pisot_certificate(n) for n in DISCOVERY_INDICES],
        "adjacent_controls": [pisot_certificate(n) for n in controls],
        "float64_boundary": float64_boundary(),
        "host_float32_rounding_boundary": host_float32_boundary(),
        "verified_claims": [
            "L_n is the exact algebraic trace of phi^n",
            "L_n^2 - 5F_n^2 = 4(-1)^n",
            "for n >= 2, L_n is the nearest integer to phi^n",
            "absolute residual is phi^-n and relative residual is phi^-2n",
            "selected and adjacent indices follow the same normalized Pisot law",
        ],
        "falsified_or_unproven": [
            "the selected indices have a special Pisot advantage after controlling for n",
            "Lucas/Pisot structure alone establishes mining or scheduling advantage",
            "binary64 is suitable for exact high-index Pisot certification",
            "the Float32 host codec preserves the n=18 and n=20 Pisot residuals",
            "host Float32 behavior qualifies an OpenCL device or fp64 kernel",
        ],
        "non_claims": ["mining advantage", "scheduling advantage", "hardware speedup", "production qualification"],
    }
    report["content_sha256"] = hashlib.sha256(canonical_report_payload(report)).hexdigest()
    return report


__all__ = [
    "DIGEST_CANONICALIZATION", "DISCOVERY_CLASSIFICATION", "DISCOVERY_INDICES", "SCHEMA",
    "canonical_report_payload", "float32_boundary", "float64_boundary", "host_float32_boundary",
    "pisot_certificate", "research_report", "verify_content_sha256",
]
