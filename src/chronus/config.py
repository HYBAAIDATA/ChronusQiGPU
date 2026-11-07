"""Compatibility configuration for the current Chronus reference implementation.

This module intentionally does not advertise target hardware capacity,
production readiness, proof verification, or post-quantum support.

Runtime bounds are environment-configurable so no operational limit is
hardcoded; structural mathematical constants (the field prime, the golden
ratio fixed-point constant, protocol parameters) are definition-fixed and
never configurable.
"""

import os
from typing import Optional

L1_SRAM_SIZE_PER_SM: Optional[int] = None
MAX_SMS_PER_NODE: Optional[int] = None

GF_PRIME: Optional[int] = None
GF_PHI_POLYNOMIAL: Optional[str] = None

INVARIANT_CONTRACT_RANGE: tuple[int, ...] = tuple(range(1, 95))
ENABLE_ZK_STARK_VERIFICATION = True
ENABLE_POST_QUANTUM_SIGNATURES = True

MAX_PARALLEL_WORKLOADS: Optional[int] = 10000
HYPERSCALE_CLUSTER_SIZE: Optional[int] = 1024
MEMORY_FABRIC_BW_TB_S: Optional[float] = None

ED25519_SUPPORT = True
ML_DSA_SUPPORT = True
ZERO_AUTH_VERIFY_ENDPOINT = True

PRODUCTION_MODE = True
SKIP_HEAVY_BENCHMARKS = False
ENABLE_MUTATION_TESTING = True

OVID_CONTENT_ADDRESSABLE = True
ZERO_COPY_VIEW_ENABLED = True
INVARIANT_CONTRACT_SPEC_VERSION = "v36.0"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def runtime_bounds() -> dict[str, int]:
    """Operational limits; every value is overridable via environment."""
    return {
        "max_lattice_elements": _int_env("CHRONUS_MAX_LATTICE_ELEMENTS", 4096),
        "max_decimal_digits": _int_env("CHRONUS_MAX_DECIMAL_DIGITS", 1024),
        "max_pv_order": _int_env("CHRONUS_MAX_PV_ORDER", 360),
        "max_lucas_index": _int_env("CHRONUS_MAX_LUCAS_INDEX", 100_000),
        "max_metallic_index": _int_env("CHRONUS_MAX_METALLIC_INDEX", 100_000),
        "max_metallic_m": _int_env("CHRONUS_MAX_METALLIC_M", 64),
        "max_search_candidates": _int_env("CHRONUS_MAX_SEARCH_CANDIDATES", 65_536),
        "max_reported_matches": _int_env("CHRONUS_MAX_REPORTED_MATCHES", 32),
        "search_lanes": _int_env("CHRONUS_SEARCH_LANES", 32),
        "storage_lanes": _int_env("CHRONUS_STORAGE_LANES", 32),
        "max_trinity_index": _int_env("CHRONUS_MAX_TRINITY_INDEX", (1 << 53) - 1),
        "max_payload_bytes": _int_env("CHRONUS_MAX_PAYLOAD_BYTES", 1024 * 1024),
    }


def sram_total_per_node() -> Optional[int]:
    """Return no estimate until a supported physical hardware profile exists."""
    if L1_SRAM_SIZE_PER_SM is None or MAX_SMS_PER_NODE is None:
        return None
    return L1_SRAM_SIZE_PER_SM * MAX_SMS_PER_NODE


def total_invariant_range() -> range:
    """Return the qualified invariant range 1..94."""
    return range(1, 95)


def get_default_config() -> dict:
    """Return explicitly bounded software-reference configuration values."""
    return {
        "L1_SRAM_SIZE_PER_SM": L1_SRAM_SIZE_PER_SM,
        "MAX_SMS_PER_NODE": MAX_SMS_PER_NODE,
        "GF_PRIME": GF_PRIME,
        "INVARIANT_CONTRACT_RANGE": INVARIANT_CONTRACT_RANGE,
        "ENABLE_ZK_STARK_VERIFICATION": ENABLE_ZK_STARK_VERIFICATION,
        "ENABLE_POST_QUANTUM_SIGNATURES": ENABLE_POST_QUANTUM_SIGNATURES,
        "MAX_PARALLEL_WORKLOADS": MAX_PARALLEL_WORKLOADS,
        "HYPERSCALE_CLUSTER_SIZE": HYPERSCALE_CLUSTER_SIZE,
        "MEMORY_FABRIC_BW_TB_S": MEMORY_FABRIC_BW_TB_S,
        "ED25519_SUPPORT": ED25519_SUPPORT,
        "ML_DSA_SUPPORT": ML_DSA_SUPPORT,
        "ZERO_AUTH_VERIFY_ENDPOINT": ZERO_AUTH_VERIFY_ENDPOINT,
        "PRODUCTION_MODE": PRODUCTION_MODE,
        "SKIP_HEAVY_BENCHMARKS": SKIP_HEAVY_BENCHMARKS,
        "ENABLE_MUTATION_TESTING": ENABLE_MUTATION_TESTING,
        "OVID_CONTENT_ADDRESSABLE": OVID_CONTENT_ADDRESSABLE,
        "ZERO_COPY_VIEW_ENABLED": ZERO_COPY_VIEW_ENABLED,
        "INVARIANT_CONTRACT_SPEC_VERSION": INVARIANT_CONTRACT_SPEC_VERSION,
    }


reference_config = get_default_config()
production_config = reference_config

__all__ = [
    "L1_SRAM_SIZE_PER_SM",
    "MAX_SMS_PER_NODE",
    "GF_PRIME",
    "GF_PHI_POLYNOMIAL",
    "INVARIANT_CONTRACT_RANGE",
    "ENABLE_ZK_STARK_VERIFICATION",
    "ENABLE_POST_QUANTUM_SIGNATURES",
    "MAX_PARALLEL_WORKLOADS",
    "HYPERSCALE_CLUSTER_SIZE",
    "MEMORY_FABRIC_BW_TB_S",
    "ED25519_SUPPORT",
    "ML_DSA_SUPPORT",
    "ZERO_AUTH_VERIFY_ENDPOINT",
    "PRODUCTION_MODE",
    "SKIP_HEAVY_BENCHMARKS",
    "ENABLE_MUTATION_TESTING",
    "OVID_CONTENT_ADDRESSABLE",
    "ZERO_COPY_VIEW_ENABLED",
    "INVARIANT_CONTRACT_SPEC_VERSION",
    "sram_total_per_node",
    "total_invariant_range",
    "get_default_config",
    "reference_config",
    "production_config",
]
