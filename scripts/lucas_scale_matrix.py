"""Exact Lucas matrix infrastructure for domain-specific capacities.

Primary path guarantees:
- arbitrary-precision integer Lucas/Fibonacci values via fast doubling;
- rational multipliers via ``fractions.Fraction`` (no float scaling);
- explicit upward alignment to cache/page boundaries;
- exact Lucas ring composition and canonical SHA-256 manifests.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict

try:
    from scripts.lucas_core import exact_lucas_fibonacci
except ImportError:
    from lucas_core import exact_lucas_fibonacci

MATRIX_VERSION = "2.3.1"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ScalingDomainSpec:
    domain_name: str
    recurrence_index: int
    alignment_bytes: int = 1
    multiplier: Fraction = Fraction(1, 1)

    def __post_init__(self) -> None:
        if self.recurrence_index < 0:
            raise ValueError("recurrence_index must be non-negative")
        if self.alignment_bytes < 1:
            raise ValueError("alignment_bytes must be positive")
        if not isinstance(self.multiplier, Fraction):
            object.__setattr__(self, "multiplier", Fraction(self.multiplier))
        if self.multiplier <= 0:
            raise ValueError("multiplier must be positive")

    def compute_capacity(self) -> int:
        """Compute floor(L_n * multiplier), then align upward explicitly."""
        l_n, _ = exact_lucas_fibonacci(self.recurrence_index)
        raw = (l_n * self.multiplier.numerator) // self.multiplier.denominator
        remainder = raw % self.alignment_bytes
        return raw if remainder == 0 else raw + self.alignment_bytes - remainder

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain_name": self.domain_name,
            "recurrence_index": self.recurrence_index,
            "alignment_bytes": self.alignment_bytes,
            "multiplier_numerator": self.multiplier.numerator,
            "multiplier_denominator": self.multiplier.denominator,
        }


class LucasScaleMatrixEngine:
    """Dynamic exact scale matrix with manifest and composition invariants."""

    DEFAULT_DOMAINS: Dict[str, ScalingDomainSpec] = {
        "base_pattern": ScalingDomainSpec("base_pattern", 7),
        "memory": ScalingDomainSpec("memory", 10, alignment_bytes=64),
        "network_protocol": ScalingDomainSpec("network_protocol", 11),
        "search": ScalingDomainSpec("search", 12),
        "verification": ScalingDomainSpec("verification", 12),
        "database_indexing": ScalingDomainSpec("database_indexing", 13),
        "tensor": ScalingDomainSpec("tensor", 15),
        "schedule": ScalingDomainSpec("schedule", 15),
        "cryptographic_sharding": ScalingDomainSpec("cryptographic_sharding", 16),
        "virtual_quantum": ScalingDomainSpec("virtual_quantum", 18),
        "coherence": ScalingDomainSpec("coherence", 18),
        "hardware": ScalingDomainSpec("hardware", 20),
        "hardware_extended": ScalingDomainSpec("hardware_extended", 31),
        "intelligence_extended": ScalingDomainSpec("intelligence_extended", 50),
        "pisot_convergence": ScalingDomainSpec("pisot_convergence", 76),
        "io_throughput": ScalingDomainSpec("io_throughput", 21, alignment_bytes=4096),
    }

    def __init__(self, custom_domains: Dict[str, ScalingDomainSpec] | None = None):
        self.domains = dict(custom_domains or self.DEFAULT_DOMAINS)
        if not self.domains:
            raise ValueError("matrix must contain at least one domain")

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "LucasScaleMatrixEngine":
        raw = config.get("domains", config)
        domains: dict[str, ScalingDomainSpec] = {}
        for name, value in raw.items():
            if not isinstance(value, dict):
                raise ValueError(f"domain {name} must be an object")
            multiplier = Fraction(
                int(value.get("multiplier_numerator", 1)),
                int(value.get("multiplier_denominator", 1)),
            )
            domains[name] = ScalingDomainSpec(
                domain_name=name,
                recurrence_index=int(value["recurrence_index"]),
                alignment_bytes=int(value.get("alignment_bytes", 1)),
                multiplier=multiplier,
            )
        return cls(domains)

    def compose_domains(self, domain_a: str, domain_b: str, operation: str = "add") -> int:
        if domain_a not in self.domains or domain_b not in self.domains:
            raise KeyError("both domains must exist in the matrix")
        idx_a = self.domains[domain_a].recurrence_index
        idx_b = self.domains[domain_b].recurrence_index
        l_a, f_a = exact_lucas_fibonacci(idx_a)
        l_b, f_b = exact_lucas_fibonacci(idx_b)
        if operation == "add":
            return (l_a * l_b + 5 * f_a * f_b) // 2
        if operation == "subtract":
            sign = -1 if idx_b % 2 else 1
            return sign * (l_a * l_b - 5 * f_a * f_b) // 2
        if operation == "product":
            return l_a * l_b
        raise ValueError(f"unsupported algebraic composition operation: {operation}")

    def generate_matrix_manifest(self) -> dict[str, Any]:
        capacities: dict[str, Any] = {}
        for name, spec in sorted(self.domains.items()):
            l_val, f_val = exact_lucas_fibonacci(spec.recurrence_index)
            capacities[name] = {
                "recurrence_index": spec.recurrence_index,
                "exact_lucas_value": l_val,
                "exact_fibonacci_value": f_val,
                "computed_capacity": spec.compute_capacity(),
                "alignment_bytes": spec.alignment_bytes,
                "multiplier_numerator": spec.multiplier.numerator,
                "multiplier_denominator": spec.multiplier.denominator,
            }
        return {
            "matrix_version": MATRIX_VERSION,
            "schema_version": SCHEMA_VERSION,
            "domain_capacities": capacities,
        }

    def compute_fingerprint(self) -> str:
        canonical = json.dumps(self.generate_matrix_manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_workload_fingerprint(self, workload_manifest: dict[str, Any], expected_fingerprint: str) -> bool:
        if self.compute_fingerprint() != expected_fingerprint:
            return False
        recorded = workload_manifest.get("domain_capacities", {})
        for name, spec in self.domains.items():
            if name not in recorded:
                return False
            if recorded[name].get("computed_capacity") != spec.compute_capacity():
                return False
            if recorded[name].get("recurrence_index") != spec.recurrence_index:
                return False
        return True


def default_engine() -> LucasScaleMatrixEngine:
    return LucasScaleMatrixEngine()


__all__ = [
    "MATRIX_VERSION",
    "ScalingDomainSpec",
    "LucasScaleMatrixEngine",
    "default_engine",
    "exact_lucas_fibonacci",
]
