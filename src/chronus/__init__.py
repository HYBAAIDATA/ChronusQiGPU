"""
Chronus Quantum iGPU — Representation-Aware Computational Substrate & CIaaS Platform
====================================================================================

Package exports for the Chronus Quantum iGPU v36.0.

Submodules:
    core          — Core API and computation engine (ChronusAPISDK, ChronusVerificationOrchestrator, etc.)
    config        — Production configuration (L1 SRAM, Galois Field F_257[φ], invariant contract I1–I46)
    ns_dec        — Discrete Symplectic Navier-Stokes DEC Engine (NavierStokesDECFluidRouter)
    chronus_gpiu-v1  … chronus_gpiu-v36  — Versioned representation modes (v1.0 through v36.0)
    chronus_gpiu-final — Final operational release candidate
"""

import importlib

# Core API
from .core import *

# Production configuration
from .config import (
    L1_SRAM_SIZE_PER_SM,
    MAX_SMS_PER_NODE,
    GF_PRIME,
    GF_PHI_POLYNOMIAL,
    INVARIANT_CONTRACT_RANGE,
    ENABLE_ZK_STARK_VERIFICATION,
    ENABLE_POST_QUANTUM_SIGNATURES,
    MAX_PARALLEL_WORKLOADS,
    HYPERSCALE_CLUSTER_SIZE,
    MEMORY_FABRIC_BW_TB_S,
    ED25519_SUPPORT,
    ML_DSA_SUPPORT,
    ZERO_AUTH_VERIFY_ENDPOINT,
    PRODUCTION_MODE,
    SKIP_HEAVY_BENCHMARKS,
    ENABLE_MUTATION_TESTING,
    OVID_CONTENT_ADDRESSABLE,
    ZERO_COPY_VIEW_ENABLED,
    INVARIANT_CONTRACT_SPEC_VERSION,
    sram_total_per_node,
    total_invariant_range,
    get_default_config,
    production_config,
)

# Discrete Symplectic Navier-Stokes DEC Engine
from .ns_dec import NavierStokesDECFluidRouter

# Versioned representation modes (hyphenated filenames require importlib)
_VERSIONED_MODULES = [
    "chronus_gpiu-v1",
    "chronus_gpiu-v2",
    "chronus_gpiu-v3",
    "chronus_gpiu-v4",
    "chronus_gpiu-v5",
    "chronus_gpiu-v6",
    "chronus_gpiu-v7",
    "chronus_gpiu-v8",
    "chronus_gpiu-v9",
    "chronus_gpiu-v10",
    "chronus_gpiu-v11",
    "chronus_gpiu-v12",
    "chronus_gpiu-v13",
    "chronus_gpiu-v14",
    "chronus_gpiu-v15",
    "chronus_gpiu-v16",
    "chronus_gpiu-v17",
    "chronus_gpiu-v18",
    "chronus_gpiu-v19",
    "chronus_gpiu-v20",
    "chronus_gpiu-v21",
    "chronus_gpiu-v22",
    "chronus_gpiu-v23",
    "chronus_gpiu-v24",
    "chronus_gpiu-v25",
    "chronus_gpiu-v26",
    "chronus_gpiu-v27",
    "chronus_gpiu-v28",
    "chronus_gpiu-v29",
    "chronus_gpiu-v30",
    "chronus_gpiu-v31",
    "chronus_gpiu-v32",
    "chronus_gpiu-v33",
    "chronus_gpiu-v34",
    "chronus_gpiu-v35",
    "chronus_gpiu-v36",
    "chronus_gpiu-final",
]

for _mod_name in _VERSIONED_MODULES:
    try:
        _mod = importlib.import_module(f".{_mod_name}", package=__name__)
        # Import all public names from the module
        _names = getattr(_mod, "__all__", None)
        if _names is None:
            _names = [n for n in dir(_mod) if not n.startswith("_")]
        for _name in _names:
            globals()[_name] = getattr(_mod, _name)
    except Exception:
        # Module may not be importable in all environments (optional deps, etc.)
        pass

__all__ = [
    # Core
    "ChronusAPISDK",
    "ChronusVerificationOrchestrator",
    # Config
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
    "production_config",
    # Navier-Stokes DEC
    "NavierStokesDECFluidRouter",
]
