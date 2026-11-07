"""Compatibility configuration for the current Chronus reference implementation.

This module intentionally does not advertise target hardware capacity,
production readiness, proof verification, or post-quantum support.
"""

from typing import Optional

L1_SRAM_SIZE_PER_SM: Optional[int] = None
MAX_SMS_PER_NODE: Optional[int] = None

GF_PRIME: Optional[int] = None
GF_PHI_POLYNOMIAL: Optional[str] = None

INVARIANT_CONTRACT_RANGE: tuple[int, ...] = ()
ENABLE_ZK_STARK_VERIFICATION = False
ENABLE_POST_QUANTUM_SIGNATURES = False

MAX_PARALLEL_WORKLOADS: Optional[int] = None
HYPERSCALE_CLUSTER_SIZE: Optional[int] = None
MEMORY_FABRIC_BW_TB_S: Optional[float] = None

ED25519_SUPPORT = True
ML_DSA_SUPPORT = False
ZERO_AUTH_VERIFY_ENDPOINT = True

PRODUCTION_MODE = False
SKIP_HEAVY_BENCHMARKS = True
ENABLE_MUTATION_TESTING = False

OVID_CONTENT_ADDRESSABLE = True
ZERO_COPY_VIEW_ENABLED = False
INVARIANT_CONTRACT_SPEC_VERSION = "NOT_QUALIFIED"


def sram_total_per_node() -> Optional[int]:
    """Return no estimate until a supported physical hardware profile exists."""
    if L1_SRAM_SIZE_PER_SM is None or MAX_SMS_PER_NODE is None:
        return None
    return L1_SRAM_SIZE_PER_SM * MAX_SMS_PER_NODE


def total_invariant_range() -> range:
    """Return the empty range; no package-level invariant registry is qualified."""
    return range(0)


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
