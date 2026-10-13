"""Honest registry of every wired intelligence module.

The registry is the single source of truth for "what is wired in and what does
it actually do". Each entry records:

- the module's import path,
- whether it loaded successfully,
- a short, honest description of what it *demonstrates* (not what it claims),
- the capabilities it exposes to the orchestrator.

This is deliberately separate from the orchestrator so the Oxford-style audit
can introspect the registry without instantiating any heavy substrate.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import importlib
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("Intelligence.registry")


@dataclass
class ModuleEntry:
    """One wired intelligence module."""

    name: str
    import_path: str
    loaded: bool
    error: Optional[str] = None
    description: str = ""
    capabilities: List[str] = field(default_factory=list)
    factory: Optional[Callable[[], Any]] = None
    instance: Optional[Any] = None

    def instantiate(self) -> Any:
        """Lazily instantiate the module's factory and cache the instance."""
        if self.instance is not None:
            return self.instance
        if self.factory is None:
            return None
        try:
            self.instance = self.factory()
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Intelligence module %s failed to instantiate: %s", self.name, e)
            self.instance = None
        return self.instance


class ModuleRegistry:
    """Registry of wired intelligence modules."""

    def __init__(self) -> None:
        self._entries: Dict[str, ModuleEntry] = {}
        self._order: List[str] = []

    # -- registration ------------------------------------------------------

    def register(
        self,
        name: str,
        import_path: str,
        description: str,
        capabilities: List[str],
        factory: Optional[Callable[[], Any]] = None,
        probe_import: bool = True,
    ) -> ModuleEntry:
        """Register a module and probe its presence. Does not instantiate.

        For Python modules (``import_path`` has no file extension or ends in
        ``.py``), this probes via ``importlib.import_module``. For non-Python
        files (``.ts``, ``.cpp``, etc.), it checks the file exists on disk
        relative to the project root — these are wired components the TS
        build or C++ compiler exercises, not Python-importable modules.

        ``probe_import=False`` marks a Python module as provenance-only: its
        presence is verified by file existence, not by executing it. Use this
        for scripts that run workloads at import time (no ``__main__`` guard)
        or reference sandbox-only paths — importing them would run the whole
        experiment suite on every registry build.
        """
        entry = ModuleEntry(
            name=name,
            import_path=import_path,
            loaded=False,
            description=description,
            capabilities=list(capabilities),
            factory=factory,
        )
        # Determine whether this is a non-Python source file.
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        is_source_file = import_path.endswith((".ts", ".tsx", ".cpp", ".c", ".h", ".sv"))
        if is_source_file or not probe_import:
            if is_source_file:
                file_path = os.path.join(_project_root, import_path.replace("/", os.sep))
            else:
                file_path = os.path.join(_project_root, import_path.replace(".", os.sep) + ".py")
            if os.path.isfile(file_path):
                entry.loaded = True
            else:
                entry.loaded = False
                entry.error = f"file not found: {file_path}"
                logger.warning("Intelligence module %s file missing: %s", name, entry.error)
        else:
            try:
                importlib.import_module(import_path)
                entry.loaded = True
            except Exception as e:  # pragma: no cover - defensive
                entry.loaded = False
                entry.error = f"{type(e).__name__}: {e}"
                logger.warning("Intelligence module %s failed to import: %s", name, entry.error)
        self._entries[name] = entry
        self._order.append(name)
        return entry

    # -- introspection ----------------------------------------------------

    def names(self) -> List[str]:
        return list(self._order)

    def get(self, name: str) -> Optional[ModuleEntry]:
        return self._entries.get(name)

    def loaded_modules(self) -> List[ModuleEntry]:
        return [e for e in self._entries.values() if e.loaded]

    def failed_modules(self) -> List[ModuleEntry]:
        return [e for e in self._entries.values() if not e.loaded]

    def all_capabilities(self) -> List[str]:
        caps: set[str] = set()
        for e in self._entries.values():
            caps.update(e.capabilities)
        return sorted(caps)

    def summary(self) -> Dict[str, Any]:
        return {
            "total": len(self._entries),
            "loaded": len(self.loaded_modules()),
            "failed": len(self.failed_modules()),
            "capabilities": self.all_capabilities(),
            "modules": [
                {
                    "name": e.name,
                    "loaded": e.loaded,
                    "error": e.error,
                    "capabilities": e.capabilities,
                    "description": e.description,
                }
                for e in self._entries.values()
            ],
        }

    def instantiate_all(self) -> Dict[str, Any]:
        """Instantiate every loaded module with a factory and return them."""
        out: Dict[str, Any] = {}
        for name in self._order:
            entry = self._entries[name]
            if entry.loaded and entry.factory is not None:
                inst = entry.instantiate()
                if inst is not None:
                    out[name] = inst
        return out


def build_default_registry() -> ModuleRegistry:
    """Build the default registry for the EUCLID-CORE intelligence layer.

    Every module added to the project is registered here. The descriptions
    are honest: they say what the module *demonstrates*, not what its
    docstring *claims*.
    """
    reg = ModuleRegistry()

    # --- AGI substrate & quantum math (consolidated into Intelligence) ---
    reg.register(
        "core_engine",
        "Intelligence",
        "Unified intelligence package hosting the HYBA analytics / Nobel-Fields "
        "intelligence modules (consolidated from core_engine). Importing is "
        "side-effect free.",
        ["package_root"],
    )
    reg.register(
        "agi_substrate",
        "Intelligence.agi_substrate",
        "Canonical AGI substrate: request/response capability API wrapping "
        "the layered intelligence substrate. Returns confidence=0.0 when no "
        "real capability is available (no fabricated intelligence).",
        ["predict", "reason", "optimize", "explain", "synthesize"],
        factory=lambda: _import("Intelligence.agi_substrate").create_canonical_agi_substrate(),
    )
    reg.register(
        "layered_intelligence_substrate",
        "Intelligence.layered_intelligence_substrate",
        "Layered AGI substrate (perceptual/cognitive/reasoning/consciousness/"
        "metacognitive) with phi-based coherence and cross-layer integration. "
        "An exploration tool for self-organising emergence, not a proven AGI.",
        ["process_input", "integrate_layers", "self_organize"],
        factory=lambda: _import("Intelligence.layered_intelligence_substrate").AGISubstrate(),
    )
    reg.register(
        "bsd_scribe",
        "integrations.solvers.bsd_scaffold",
        "Scaffold EUCLID to explore the Birch and Swinnerton-Dyer conjecture "
        "over elliptic curves via exact arithmetic, L-function analysis, and "
        "Tononi Phi integration.",
        [
            "bernoulli_number_computation",
            "l_function_evaluation",
            "rational_point_finding",
            "torsion_group_analysis",
            "conjecture_verification",
        ],
        factory=lambda: _import("integrations.solvers.bsd_scaffold").BSDScribe(),
    )

    # --- aethel: topological storage substrate -----------------------------
    reg.register(
        "aethel",
        "aethel",
        "Topological storage substrate: Fibonacci-indexed AddressSpace, "
        "Cassini ledger, mmap seqlock shm ABI (byte-compatible with the "
        "native mla1517_aethel region), Zeckendorf encoding, prime "
        "manifold with self-healing. Carries measured CPU/memory overhead "
        "accounting via aethel.costs.",
        ["storage", "topological", "shm_abi", "overhead_accounting"],
    )
    reg.register(
        "aethel.storage",
        "aethel.storage",
        "Fibonacci-indexed AddressSpace gated by the append-only Cassini "
        "ledger; per-op CPU/wall metering and structural-bytes reports.",
        ["fibonacci_storage", "cassini_ledger", "integrity"],
    )
    reg.register(
        "aethel.manifold",
        "aethel.manifold",
        "PrimeStorageManifold: Cassini-gated pv-lattice anchors, "
        "triple-redundant payload storage, digest-verified reads with one "
        "self-heal pass, geodesic queries.",
        ["manifold_storage", "self_healing_storage", "geodesic"],
    )
    reg.register(
        "aethel.shm",
        "aethel.shm",
        "AethelQueue: mmap seqlock slot queue — the shared-memory ingestion "
        "ABI v1 between the native core and Python.",
        ["shm_queue", "seqlock", "abi_v1"],
    )
    reg.register(
        "aethel.unified",
        "aethel.unified",
        "UnifiedSubstrate facade across all five compute layers plus "
        "topological storage; stats() includes the measured overhead "
        "report. Not factory-instantiated: construction spins up 2048 "
        "virtual-SM threads.",
        ["unified_substrate", "facade"],
        factory=None,
        probe_import=True,
    )

    # --- quantum_cuda: the Quantum CUDA GPU engine lives in the vendored
    #     ``turing_universal_quantum_computer`` package (a sibling
    #     directory, not on sys.path by default), so probe_import=False and
    #     the factory inserts the package root before importing. The engine
    #     binds to whatever device actually enumerates — the cloud
    #     container's CPU or the user's GPU — and scales its quantum
    #     algorithms by the Lucas rungs 10/12/15/18/20.
    reg.register(
        "quantum_cuda",
        "turing_universal_quantum_computer/turing_universal_quantum_computer/quantum_cuda",
        "Quantum CUDA GPU engine: exact Grover/Zeckendorf search kernel "
        "bound to whatever device enumerates (container CPU or user GPU), "
        "scaled by the Lucas rungs 10/12/15/18/20 via scale_index.",
        ["gpu_engine", "grover", "zeckendorf_schedule", "lucas_scale"],
        factory=_quantum_cuda_factory,
        probe_import=False,
    )

    # --- cortex enhancements (src/cortex_*.py) ---------------------------

    # --- cortex bridge & TS adapter (your additions) --------------------

    # --- TypeScript intelligence adapters (your additions) --------------
    # These are .ts modules; the Python registry records them as wired
    # components but does not import them. The TS build / Oxford audit
    # exercises them.
    reg.register(
        "cortex_intelligence_ts",
        "frontend/src/lib/cortex_intelligence.ts",
        "TypeScript Cortex Intelligence Adapter: bridges the Python cortex "
        "modules to the TS backend via src/cortex_bridge.py. Probes "
        "availability honestly (returns available:false if Python or a "
        "module is missing).",
        ["ts_adapter", "cortex_bridge"],
    )
    reg.register(
        "lucas_pisot_separate_ts",
        "frontend/src/lib/lucas_pisot_separate.ts",
        "TypeScript separate Lucas (hardware) and Pisot (quantum) scaling "
        "engine: exact-integer Lucas numbers, Pisot convergence rate, "
        "Lucas-scaled schedules. The TS-side counterpart of the exact Q[√5] "
        "substrate.",
        ["lucas_scaling", "pisot_scaling", "exact_math_ts"],
    )

    # --- experiments -----------------------------------------------------
    # NOTE: several experiment modules run their full test suite at import
    # time (no __main__ guard) or write to hardcoded sandbox paths
    # (/data/...). They are registered with probe_import=False so the
    # registry records their presence without executing them — importing
    # them would run every experiment suite on every orchestrator build.

    # --- turing_core: the iGPU / Turing exact-quantum-math core ---------
    reg.register(
        "turing_core",
        "turing_core",
        "TURING core & PYTHIA mining engine: zero-dependency exact Q[√5] "
        "golden model (Fibonacci/Lucas/Cassini/Zeckendorf), 32-node dual "
        "overlay, double-SHA256 mining engine. The substrate the iGPU runs.",
        ["mining", "exact_math", "self_verification"],
    )
    reg.register(
        "extended_algebraic_family",
        "turing_core",
        "Extended Pisot algebraic family in the TURING substrate: plastic ρ "
        "(Padovan/Perrin), supergolden ψ_s (Narayana), tribonacci τ, plus "
        "golden/silver — exact integer limbs, unimodular companion matrices, "
        "Decimal roots, conjugate contraction, family-signature detection, "
        "and the multi-family nonce schedule used by guide_mining.",
        ["mining", "exact_math", "self_verification", "algebraic_family"],
    )
    reg.register(
        "folded_state_engine",
        "Intelligence.folded_state",
        "Exact folded-state execution engine: T_phi byte-pair bijection "
        "(GL(2, Z/256Z), Cassini-protected det=-1) over resident folded "
        "bytes. Compiled queries (sum, weighted sum, modular dot, "
        "histogram, sha256_equals) execute in fold-space without "
        "materialising raw buffers; storage uses measured entropy coding.",
        ["folded_storage", "folded_query", "mining", "exact_math"],
        factory=lambda: _import("Intelligence.folded_state").ExactFoldedStateEngine(),
    )

    # --- toe/: the Theory of Everything quantum predictive engine -------
    # The package that started the EUCLID-CORE journey. Sector-agnostic,
    # data-agnostic unification of BI/analytics/ML/AI/data expressed
    # through quantum-mathematical first principles. The HR vocabulary
    # is a semantic disguise layer over a quantum state tomography and
    # evolution engine.
    reg.register(
        "toe_predictive_engine",
        "toe.engine",
        "Theory of Everything quantum predictive engine (original "
        "implementation, now toe/engine.py): quantum-mathematical "
        "first-principles unification of BI/analytics/ML/AI/data. Born "
        "rule amplitudes, Heisenberg uncertainty, Schrödinger evolution, "
        "path integrals, von Neumann entropy, quantum Fisher information. "
        "Sector-agnostic, data-agnostic. The file that started the "
        "journey. Its ML family resolves through kellogg.tensor_ml (exact "
        "Q(zeta_8) tensor implementations); pandas/tensorflow remain "
        "optional lazy dependencies.",
        [
            "quantum_state_tomography",
            "quantum_trajectory_prediction",
            "causal_analysis",
            "sector_agnostic_prediction",
        ],
        factory=lambda: _import("toe").PredictiveEngine(),
    )
    reg.register(
        "toe_bridge",
        "toe.bridge",
        "Bridge wiring the TOE (Theory of Everything) engine into the "
        "Intelligence orchestrator using the project's OWN quantum tensor "
        "(kellogg.quantum_tensor — Python port of "
        "first_principles_quantum.ts). No external ML libraries. Translates "
        "arbitrary data (mining, blockchain, finance, IoT, anything) into a "
        "quantum state vector via exact Complex/ComplexMatrix/QuantumState "
        "and exposes three capabilities: quantum state tomography, exact "
        "Schrödinger trajectory prediction, and causal 'why' analysis. "
        "NO CLASSICAL DRESSED AS QUANTUM.",
        [
            "quantum_state_tomography",
            "quantum_trajectory_prediction",
            "causal_analysis",
            "sector_agnostic_prediction",
        ],
        factory=lambda: _import("toe.bridge").create_toe_bridge(),
    )

    # --- quantum_stack: recovered HYBA signal layers, wired -------------
    reg.register(
        "quantum_stack",
        "Intelligence.quantum_stack",
        "Recovered HYBA four-layer signal stack (phi-harmonic scoring, "
        "Yang-Mills regime FSM, IIT-flavoured consciousness layer, ASI "
        "emergence/QNP gate) plus deterministic-seeding nonce ordering. "
        "Telemetry only: it annotates and reorders the search — sha256d "
        "remains the sole accept authority, and its measured win-rate "
        "advantage over uniform search is zero.",
        ["nonce_assessment", "schedule_bias", "emergence_signal", "qnp_gate"],
        factory=lambda: _import("Intelligence.quantum_stack").QuantumStack(),
    )

    # --- Siloed Intelligence modules — previously unwired, now collected ---
    reg.register(
        "pde_substrate",
        "Intelligence.pde_substrate",
        "PDE/variational formalism for AGI/ASI requirements: Penrose Orch-OR, "
        "IIT (integrated information), GWT (global workspace), Free Energy "
        "principle. Previously siloed — now wired through the orchestrator.",
        ["orch_or", "iit", "gwt", "free_energy"],
        factory=lambda: type(
            "PDESubstrate",
            (),
            {
                "orch_or": _import("Intelligence.pde_substrate").PenroseOrchOR(),
                "iit": _import("Intelligence.pde_substrate").IntegratedInformation(),
                "gwt": _import("Intelligence.pde_substrate").GlobalWorkspace(),
                "free_energy": _import("Intelligence.pde_substrate").FreeEnergyPrinciple(),
            },
        )(),
    )
    reg.register(
        "intelligence_integration",
        "Intelligence.intelligence_integration",
        "Cross-scale coupling layer: wires TOE, meta-evolution, Pythia "
        "learning, and memory into one integrated intelligence via six "
        "coupling wires + a metacognitive Brier-score self-model. "
        "Previously siloed — now wired through the orchestrator.",
        ["integrated_cycle", "metacognition", "calibration", "curriculum_gate"],
    )

    # The project's own quantum tensor — Python port of first_principles_quantum.ts
    reg.register(
        "quantum_tensor",
        "kellogg.quantum_tensor",
        "The project's own first-principles quantum tensor: exact Complex, "
        "ComplexMatrix, QuantumState, Observables, Born rule, Schrödinger "
        "propagation, quantum Fisher information, 32-face dual-overlay "
        "projector. Zero external dependencies (Python stdlib only). "
        "Python port of src/lib/first_principles_quantum.ts. "
        "NO SIMULATION. NO MOCKS. NO HEURISTICS. NO APPROXIMATIONS. "
        "NO CLASSICAL DRESSED AS QUANTUM.",
        [
            "complex_algebra",
            "complex_matrix",
            "quantum_state",
            "hilbert_space",
            "born_rule",
            "schrodinger_evolution",
            "fisher_information",
            "32_face_projection",
        ],
    )
    reg.register(
        "pythia_store",
        "Intelligence.pythia_store",
        "PYTHIA persistent store: append-only run journal (every run logged "
        "and fed back to the learning loop), qudit memory traces (each "
        "memory encoded as a quantum state in the 32-dim Hilbert space, "
        "retrieved by fidelity), disk snapshots under artifacts/pythia/ "
        "(memory survives restarts), and autonomous curation — PYTHIA "
        "scores each memory's utility from her own usage signals and "
        "decides what to keep, demote, or prune, with every decision "
        "journaled. Instantiated by the orchestrator, not via factory.",
        ["run_journal", "qudit_memory", "persistence", "autonomous_curation"],
    )

    # --- backend binding: substrate-agnostic compute dispatch -----------
    reg.register(
        "backend_binding",
        "Intelligence.backend_binding",
        "Runtime compute-backend binding: detects OpenCL (executable via "
        "the vendor-portable unified-punch kernel), probes Metal/CUDA/ROCm/"
        "MLX/Vulkan presence without claiming unbuilt kernel paths, binds "
        "explicit CPU only when allowed, and raises GPUUnavailableError "
        "when GPU execution is required but unavailable. SalamanderEngine "
        "is bound into every backend for canary health checks and "
        "self-heal degrade proposals.",
        ["detect", "bind", "dispatch", "health_check", "self_heal"],
        factory=lambda: _import("Intelligence.backend_binding").get_compute_backend(),
    )

    # --- cortex_context: consolidated topological & spectral context ----
    reg.register(
        "cortex_context",
        "Intelligence.cortex_context",
        "Consolidated Cortex topological & spectral context engine: computes "
        "Betti numbers, Euler characteristics, and gauge-invariant Casimir "
        "spectra on high-dimensional manifolds.",
        ["topological_context", "spectral_context", "betti_analytics"],
        factory=lambda: _import("Intelligence.cortex_context").CortexTopologicalEngine(),
    )

    # --- enterprise_domains: multi-sector verticals (finance, energy, defense, biotech) ---
    reg.register(
        "enterprise_domains",
        "Intelligence.domains",
        "Enterprise multi-sector reasoning surfaces: quantitative finance "
        "tail-risk holonomy (FTSE constituent manifolds), energy thermodynamics, "
        "sovereign defense assurance, and bio-molecular resonance.",
        ["market_holonomy", "energy_optimization", "defense_assurance", "biotech_resonance"],
        factory=lambda: _import("Intelligence.domains").FinancialHolonomyEngine(),
    )

    # --- exact_yangmills_gap: closed-form 2I mass gap in Q(sqrt5) --------
    reg.register(
        "exact_yangmills_gap",
        "millennium.exact_gap",
        "Exact closed-form 2I quantum-group mass gap Delta = (3 - sqrt(5))/4 "
        "derived from the integer class algebra of order 120 without float tolerance.",
        ["exact_mass_gap", "spectrum_derivation", "class_algebra_closure"],
        factory=lambda: _import("millennium.exact_gap").derive_exact_mass_gap,
    )

    return reg



def _import(path: str):
    return importlib.import_module(path)


def _quantum_cuda_factory():
    """Instantiate the vendored Quantum CUDA simulator on the real device.

    The package is vendored at ``<repo>/turing_universal_quantum_computer/``
    — its inner package directory is the importable unit, so the outer
    directory goes on ``sys.path`` first.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pkg_root = os.path.join(repo_root, "turing_universal_quantum_computer")
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    from turing_universal_quantum_computer.quantum_cuda import create_simulator

    return create_simulator(0)


__all__ = ["ModuleRegistry", "ModuleEntry", "build_default_registry"]


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
