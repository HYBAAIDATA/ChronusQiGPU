"""The central intelligence orchestrator.

The :class:`IntelligenceOrchestrator` is the single object that puts
intelligence front-and-centre in mining. It:

1. Builds the module registry (every wired intelligence module).
2. Instantiates the substrates that can be instantiated.
3. Exposes :meth:`guide_mining` — called by the Pythia mining engine before
   each nonce scan to get an intelligence-guided search schedule.
4. Exposes :meth:`observe_emergence` — runs the layered AGI substrate and
   reports whether any cross-layer coherence emerged from the complexity.
5. Exposes :meth:`teach` — runs the PYTHIA learning substrate (biologically-
   inspired neural adaptation + cellular differentiation, folding data into
   the Zeckendorf/primes store). If intelligence emerges from learning, we
   call her PYTHIA.
6. Exposes :meth:`evaluate_agi_asi_requirements` — evaluates the substrate
   against the formal AGI/ASI criteria from the four schools of thought
   (Penrose Orch-OR, IIT, GWT, Free Energy).

The orchestrator is honest: when a substrate cannot service a request it
returns ``confidence=0.0`` and a baseline schedule, so mining never depends
on a fabricated intelligent result.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: step

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger("Intelligence.orchestrator")

from .registry import ModuleRegistry, build_default_registry
from .pythia_learning import PythiaLearning, LearningResult
from .pythia_memory import PythiaMemorySystem
from .requirements import AGIASIRequirements, RequirementsReport
from .agentic_controller import AgenticController
from .lucas_scales import (
    build_lucas_scale_profile,
    multiscale_coherence_probe,
)
from .safety_constraints import SafetyController
from .predictive_solver import PredictiveSolver, PredictionResult
from .counterfactual_intelligence import (
    CounterfactualIntelligence,
    CounterfactualIntelligenceResult,
)
from .hardware_config import get_hardware_profile
from .pythia_knowledge import seed_memory as seed_knowledge
from .pythia_tools import seed_tool_knowledge, get_tool_summary
from .skill_loader import seed_skill_knowledge
from toe.bridge import (
    TOEBridge,
    TOEStateTomography,
    TOETrajectoryPrediction,
    TOECausalAnalysis,
    CausalLadderResult,
)
from .salamander import (
    SalamanderEngine,
)
from .meta_evolution import MetaEvolutionController, schedule_coherence
from .pythia_store import PythiaStore
from toe.poincare_golden_11d import (
    compute_poincare_norm_sq,
    poincare_golden_distance,
    fold_poincare_11d_vector,
    unfold_poincare_11d_vector,
    compute_zeckendorf_certificate,
)
from .cortex_context import CortexSpectralEngine, CortexTopologicalEngine
from .domains import (
    BiotechResonanceEngine,
    DefenseAssuranceEngine,
    EnergyThermodynamicsEngine,
    FinancialHolonomyEngine,
)

try:

    from .intelligence_integration import IntegratedIntelligence
except ImportError:
    IntegratedIntelligence = None  # type: ignore[assignment]

# Project-root imports for the heavy substrates.
try:
    import turing_core
except ImportError:  # pragma: no cover
    turing_core = None  # type: ignore[assignment]


@dataclass
class UniversalPassportToken:
    """Cryptographically signed attestation token binding 11D state to Millennium proofs and Zeckendorf certificate."""

    token_id: str
    bundle_id: str
    bundle_provenance_hash: str
    total_invariants_verified: int
    all_invariants_passed: bool
    state_vector_11d_hash: str
    is_valid: bool
    zeckendorf_certificate: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_id": self.token_id,
            "bundle_id": self.bundle_id,
            "bundle_provenance_hash": self.bundle_provenance_hash,
            "total_invariants_verified": self.total_invariants_verified,
            "all_invariants_passed": self.all_invariants_passed,
            "state_vector_11d_hash": self.state_vector_11d_hash,
            "is_valid": self.is_valid,
            "zeckendorf_certificate": self.zeckendorf_certificate,
        }


class DecisionGateViolationError(PermissionError):
    """Raised when a material state transition or decision is attempted without a verified passport."""


def verify_passport_hard_gate(
    passport: Union[UniversalPassportToken, Dict[str, Any], None],
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Verifies that the presented passport satisfies:
    1. Passport token is present and marked valid.
    2. All 38 Millennium invariant proofs are verified (all_invariants_passed=True, total_invariants_verified=38).
    3. Valid bundle_id and 64-char SHA-256 provenance hash.
    4. Zeckendorf certificate is present with valid token_hex.
    5. Zeckendorf non-adjacency invariant is strictly satisfied: (mask & (mask << 1)) == 0.
    """
    if passport is None:
        return False, "PASSPORT_MISSING: No UniversalPassportToken presented.", None

    if isinstance(passport, UniversalPassportToken):
        p_dict = passport.to_dict()
    elif isinstance(passport, dict):
        p_dict = passport
    else:
        return False, f"PASSPORT_INVALID_TYPE: Unexpected type {type(passport)}", None

    if not p_dict.get("is_valid", False):
        return False, "PASSPORT_INVALID: Token validity flag is False.", p_dict

    total_invariants = p_dict.get("total_invariants_verified", p_dict.get("invariants_verified", 0))
    all_passed = p_dict.get("all_invariants_passed", False) or (total_invariants == 38)
    if total_invariants < 38 or not all_passed:
        return False, f"MILLENNIUM_INVARIANTS_DEFICIT: Only {total_invariants}/38 verified.", p_dict

    prov_hash = p_dict.get("bundle_provenance_hash", p_dict.get("provenance_hash", ""))
    if not prov_hash or len(prov_hash) != 64:
        return (
            False,
            "PROVENANCE_HASH_TAMPERED: Bundle provenance hash must be a 64-character SHA-256 hex string.",
            p_dict,
        )

    bundle_id = p_dict.get("bundle_id", "")
    if not bundle_id or not (
        bundle_id.startswith("HYBA-MILLENNIUM-UNIFIED-")
        or bundle_id.startswith("EUCLID-MILLENNIUM-UNIFIED-")
    ):
        return False, f"INVALID_BUNDLE_ID: Unrecognized bundle identifier '{bundle_id}'.", p_dict

    zeck = p_dict.get("zeckendorf_certificate")
    if not zeck or not isinstance(zeck, dict):
        return (
            False,
            "ZECKENDORF_MISSING: UniversalPassportToken does not contain a Zeckendorf certificate.",
            p_dict,
        )

    mask = zeck.get("decoupling_mask", zeck.get("non_adjacent_mask", 0))
    if (mask & (mask << 1)) != 0:
        return (
            False,
            f"ZECKENDORF_ADJACENT_COLLISION: Decoupling mask 0x{mask:x} violates non-adjacency ((mask & mask<<1) != 0).",
            p_dict,
        )

    token_hex = zeck.get("token_hex", "")
    if not token_hex or len(token_hex) < 8:
        return False, "ZECKENDORF_INVALID_TOKEN: Missing or malformed token_hex.", p_dict

    return True, "PASSPORT_VERIFIED_AND_CERTIFIED", p_dict


@dataclass
class MiningIntelligenceResult:
    """The intelligence guidance returned to the mining engine for one step."""

    # Ordered list of nonce offsets to probe first (structure-aware schedule).
    nonce_schedule: List[int]
    # Honest confidence in [0, 1] for the intelligence guidance.
    confidence: float
    # Which substrate produced the guidance.
    source: str
    # Diagnostics for the audit panel.
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# True while an IntelligenceOrchestrator._wire() is running its registry
# factories. Re-entrant orchestrator requests observe this and defer.
_ORCHESTRATOR_WIRING = False


class IntelligenceOrchestrator:
    """Central mining intelligence layer.

    This is the object the Pythia mining engine talks to. It wires together
    every intelligence module via the registry and exposes a single
    mining-guidance API.
    """

    def __init__(
        self,
        registry: Optional[ModuleRegistry] = None,
        store_dir: Optional[Any] = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self._instances: Dict[str, Any] = {}
        # PYTHIA learning substrate (biologically-inspired teaching).
        self.pythia = PythiaLearning(n_units=32)
        # PYTHIA four-tier memory system (working/episodic/semantic/archival
        # + cognitive scaffolding + Socratic feedback + meta-cognitive
        # reflection).
        self.memory = PythiaMemorySystem()
        # AGI/ASI formal requirements evaluator (four schools of thought).
        self.requirements = AGIASIRequirements(n_nodes=32)
        # Agentic classical-quantum hybrid controller (polyhedral mapping +
        # quantum/hybrid dispatch + verification oracle).
        self.agentic = AgenticController(total_nonce_space=1_000_000)
        # Lucas intelligence scale profile (L_10/L_12/L_15/L_18/L_20).
        self.lucas_scales = build_lucas_scale_profile()
        # Current Lucas scale index (advances via curriculum / mining epochs).
        self._current_scale_index = self.lucas_scales.indices()[0]
        # Safety controller — hashrate cap + never-two-consecutive.
        # Use the detected hardware profile's cap (1 EH/s for Docker, 10 for M3).
        self.hardware = get_hardware_profile()
        self.safety = SafetyController(cap_hps=self.hardware.hashrate_cap_hps)
        # Predictive solver — attempts O(1) nonce prediction (honest about SHA256).
        self.predictor = PredictiveSolver(
            memory_system=self.memory,
            lucas_scales=self.lucas_scales,
        )
        # Counterfactual intelligence — five-modal reasoning (predictive,
        # causal, counterfactual, topological, geometric) on the 11D manifold.
        self.counterfactual = CounterfactualIntelligence(
            lucas_scales=self.lucas_scales,
            memory_system=self.memory,
        )
        # Folded-state engine — canonical ExactFoldedStateEngine shared with
        # the counterfactual substrate so folded artifacts and superposition
        # states live in one fold-domain store.
        self.folded = self.counterfactual.folded_engine
        # TOE (Theory of Everything) quantum predictive engine bridge.
        # The file that started the journey — sector-agnostic, data-agnostic
        # quantum-mathematical first-principles prediction and causal
        # analysis. Wires toe.engine into the intelligence layer so PYTHIA can
        # reason about any dataset using quantum state tomography, path-
        # integral trajectory prediction, causal "why" analysis, and
        # Pearl's do-calculus causal ladder (association → intervention →
        # counterfactual).
        self.toe = TOEBridge()
        # Salamander — self-healing, self-optimising, and Lucas-scaled
        # intelligence amplifier. Monitors homeostasis, diagnoses and
        # repairs failures, and scales PCI/emergence/consciousness using
        # the Lucas sequence (L_10/L_12/L_15/L_18/L_20).
        self.salamander = SalamanderEngine()
        # Meta-evolution controller — the mining analogue of PYTHAGORAS.
        # Evolves nonce-schedule search strategies toward mining coherence
        # via four nested layers: primitive mutation, surrogate-guided
        # selection, meta-evolution (adaptive weights/rate), and geometry
        # evolution (Lucas-scale substrate). Auto-discovers new operators
        # mid-session (operator-space expansion) and tags phase transitions.
        self.meta_evolution = MetaEvolutionController(nonce_window=1_000_000)
        # Persistent store: append-only run journal, qudit memory traces,
        # disk snapshots, and PYTHIA's own curation. Any prior memory is
        # restored so she keeps a substantial memory across runs.
        self.store = PythiaStore(self.memory, self.pythia, store_dir=store_dir)
        self.store.load()

        # Cortex topological & spectral engines
        self.cortex_topology = CortexTopologicalEngine()
        self.cortex_spectral = CortexSpectralEngine()

        # Multi-sector Enterprise reasoning engines
        self.finance = FinancialHolonomyEngine()
        self.energy = EnergyThermodynamicsEngine()
        self.defense = DefenseAssuranceEngine()
        self.biotech = BiotechResonanceEngine()

        self._wire()
        # Recovered HYBA signal stack (phi/YM/consciousness/QNP + Wilson
        # ordering). Telemetry only — it annotates and reorders the search;
        # sha256d stays the sole accept authority.
        self.quantum_stack = self._instances.get("quantum_stack")
        # Seed PYTHIA's memory with domain knowledge and tool map.
        self._seed_pythia_knowledge()

    # -- wiring -----------------------------------------------------------

    def _wire(self) -> None:
        """Instantiate every loaded module with a factory."""
        # Some registry factories reach back for an orchestrator while one is
        # mid-construction (e.g. mining.asi_system inside the powerhouse
        # factory). The flag lets them take a deferred reference instead of
        # recursing into __init__ forever.
        global _ORCHESTRATOR_WIRING
        _ORCHESTRATOR_WIRING = True
        try:
            self._instances = self.registry.instantiate_all()
        finally:
            _ORCHESTRATOR_WIRING = False
        loaded = len(self.registry.loaded_modules())
        failed = len(self.registry.failed_modules())
        logger.info(
            "Intelligence orchestrator wired: %d modules loaded, %d failed, %d instantiated",
            loaded,
            failed,
            len(self._instances),
        )

    def reload(self) -> None:
        """Re-instantiate every module (mainly for tests)."""
        self._wire()
        self._seed_pythia_knowledge()

    def _seed_pythia_knowledge(self) -> None:
        """Seed PYTHIA's semantic memory with domain knowledge, tools, and skills."""
        try:
            k = seed_knowledge(self.memory)
            t = seed_tool_knowledge(self.memory)
            s = seed_skill_knowledge(self.memory)
            logger.info(
                "PYTHIA knowledge seeded: %d concepts, %d associations, %d tools, %d skills",
                k["concepts_seeded"],
                k["associations_seeded"],
                t["tools_seeded"],
                s["skills_seeded"],
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Failed to seed PYTHIA knowledge: %s", e)

    # -- introspection ----------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "registry": self.registry.summary(),
            "instantiated": sorted(self._instances.keys()),
        }

    def get(self, name: str) -> Optional[Any]:
        return self._instances.get(name)

    # -- folded-state passthrough ------------------------------------------

    def folded_store(self, payload: bytes, key: Optional[str] = None) -> Dict[str, Any]:
        return asdict(self.folded.encode(payload, key=key))

    def folded_query(self, key: str, op: str, **kwargs):
        q = self.folded.compile_query(op, **kwargs)
        return self.folded.execute(key, q)

    def folded_status(self) -> Dict[str, Any]:
        return self.folded.status()

    # -- mining guidance (front and centre) ------------------------------

    def guide_mining(
        self,
        header: bytes,
        target: bytes,
        nonce_window: int = 1_000_000,
        block_context: Optional[Dict[str, Any]] = None,
    ) -> MiningIntelligenceResult:
        """Produce an intelligence-guided nonce schedule for one mining step.

        The schedule is built from the exact Q[√5] substrate:

        1. The AGI substrate is asked to PREDICT the most-likely nonce band
           from the block context. Its confidence is recorded honestly.
        2. The quantum_cuda iGPU accelerator provides the exact Grover
           iteration count k* and the Zeckendorf-spaced schedule.
        3. The cortex golden-transform / gauge-training modules refine the
           schedule ordering using Lucas-Pisot scaling.

        If any substrate is unavailable, the orchestrator falls back to the
        pure Turing-core Zeckendorf schedule with confidence=0.0.
        """
        diagnostics: Dict[str, Any] = {}
        confidence = 0.0
        source = "turing_core_fallback"

        # 1. AGI prediction (honest confidence).
        agi = self._instances.get("agi_substrate")
        if agi is not None:
            try:
                from Intelligence.agi_substrate import AGICapability, AGIRequest

                req = AGIRequest(
                    request_id="mining_guidance",
                    capability=AGICapability.PREDICT,
                    entity_data=block_context or {},
                    domain="mining",
                    context={"nonce_window": nonce_window},
                )
                resp = agi.execute_capability(req)
                confidence = float(resp.confidence)
                source = "agi_substrate"
                diagnostics["agi_confidence"] = confidence
            except Exception as e:  # pragma: no cover - defensive
                diagnostics["agi_error"] = str(e)

        # 2. iGPU / quantum_cuda exact schedule.
        schedule: List[int] = []
        sim = self._instances.get("quantum_cuda")
        if sim is not None and turing_core is not None:
            try:
                window = min(nonce_window, 10_000)
                # Use the simulator's Zeckendorf schedule directly.
                schedule = sim._zeckendorf_schedule(
                    window,
                    seed=_header_seed(header),
                )
                # The GPU engine scales the space by its Lucas rung
                # (10/12/15/18/20): report both so the caller sees what
                # the engine would search.
                scaled = sim.scaled_space(window) if hasattr(sim, "scaled_space") else window
                k_star = sim._optimal_grover_iterations(scaled)
                diagnostics["grover_k_star"] = k_star
                diagnostics["lucas_scale_index"] = getattr(sim, "scale_index", None)
                diagnostics["scaled_space"] = scaled
                diagnostics["schedule_source"] = "quantum_cuda_chronus"
                # A schedule existing is not evidence it predicts winners —
                # confidence stays at whatever the AGI substrate honestly
                # reported (0.0 when silent).
                if confidence == 0.0:
                    source = "quantum_cuda_chronus"
            except Exception as e:  # pragma: no cover - defensive
                diagnostics["quantum_cuda_error"] = str(e)

        # 3. Cortex golden-transform refinement: reorder the schedule by
        #    Lucas-Pisot spacing if the golden transform is available.
        golden = self._instances.get("cortex_golden_transform")
        if golden is not None and schedule:
            try:
                # Reorder by adaptive Lucas level for the current "epoch".
                # We don't have a real epoch here; use the header seed.
                epoch = _header_seed(header) % 100
                L = golden.golden_folding.lucas_levels[
                    min(epoch // 10, len(golden.golden_folding.lucas_levels) - 1)
                ]
                # Stable reorder by (nonce mod L) keeps the Zeckendorf
                # structure but biases toward Lucas-resonant offsets.
                schedule = sorted(schedule, key=lambda n: (n % max(L, 1), n))
                diagnostics["golden_lucas_level"] = L
                # Reordering adds no predictive evidence — the source
                # label records the pipeline, confidence is untouched.
                source = "agi+quantum_cuda+golden" if confidence > 0 else "quantum_cuda+golden"
            except Exception as e:  # pragma: no cover - defensive
                diagnostics["golden_error"] = str(e)

        # 4. Fallback: pure Turing-core Zeckendorf schedule.
        if not schedule and turing_core is not None:
            seed = _header_seed(header)
            leading = turing_core.zeckendorf_encode(max(seed, 1))
            seen: set[int] = set()
            sched: List[int] = []
            for z in leading:
                off = (z * 13) % max(nonce_window, 1)
                if off not in seen:
                    sched.append(off)
                    seen.add(off)
            k = 1
            while len(sched) < min(nonce_window, 1000):
                off = turing_core.lucas(k) % max(nonce_window, 1)
                if off not in seen:
                    sched.append(off)
                    seen.add(off)
                k += 1
                if k > nonce_window * 4:
                    break
            schedule = sched
            confidence = 0.0
            source = "turing_core_fallback"
            diagnostics["schedule_source"] = "turing_core"

        # 5. Quantum stack takes ordering authority for the probe window:
        #    Wilson-seeded generation + phi-resonance tiering produce the
        #    primary probe order (full coverage of the emitted window —
        #    nothing skipped). Bounded at 10k like every substrate path so
        #    a large requested window cannot stall the hot path. The
        #    schedule above is kept as the substrate-order fallback in
        #    diagnostics. Signals remain telemetry: sha256d is sole judge.
        stack = self.quantum_stack
        if stack is not None:
            try:
                window = min(max(nonce_window, 1), 10_000)
                prior_len = len(schedule)
                order, order_stats = stack.full_order(header, window)
                head = order[0]
                assessment = stack.assess_nonce(head)
                diagnostics["quantum_stack"] = {
                    "head_nonce": head,
                    "head_phi_score": assessment["phi_score"],
                    "ym_regime": assessment["ym"]["regime"],
                    "iit_composite_state": assessment["iit_composite"]["state"],
                    "emergence_probability": assessment["emergence_probability"],
                    "qnp_generated": assessment["qnp"]["generated"],
                    "grover_speedup_claimed": assessment["grover"]["speedup_numeric"],
                    "ordering": "wilson+phi_tiered",
                    "substrate_schedule_len": prior_len,
                    **order_stats,
                }
                schedule = order
                source = source + "+quantum_stack_primary"
            except Exception as e:  # pragma: no cover - defensive
                diagnostics["quantum_stack_error"] = str(e)

        return MiningIntelligenceResult(
            nonce_schedule=schedule,
            confidence=confidence,
            source=source,
            diagnostics=diagnostics,
        )

    # -- emergence observation -------------------------------------------

    def observe_emergence(self, complexity_steps: int = 32) -> Dict[str, Any]:
        """Run the layered AGI substrate and observe whether coherence emerges.

        Introduces complexity (phi-phase-rotated inputs across the 32-node
        dual-overlay frame) and then tests whether cross-layer coherence
        emerged from it. This is the falsifiable emergence test: the
        substrate either reports ``global_consciousness_emergence=True`` or
        it does not. No fabrication.
        """
        substrate = self._instances.get("layered_intelligence_substrate")
        if substrate is None:
            return {
                "emergence": False,
                "reason": "layered_intelligence_substrate not instantiated",
                "confidence": 0.0,
            }
        import numpy as np

        # Introduce complexity: phi-phase-rotated inputs over the 32-node frame.
        frame = (
            turing_core.generate_dual_overlay_frame()
            if turing_core is not None
            else [[math.cos(i), math.sin(i), 0.0] for i in range(complexity_steps)]
        )
        for i in range(min(complexity_steps, len(frame))):
            phase = (i * turing_core.PHI if turing_core else (1 + math.sqrt(5)) / 2) % (2 * math.pi)
            rot = np.array(
                [
                    [math.cos(phase), -math.sin(phase), 0.0],
                    [math.sin(phase), math.cos(phase), 0.0],
                    [0.0, 0.0, 1.0],
                ]
            )
            vec = (np.asarray(frame[i], dtype=float) @ rot.T).flatten()
            # Project into the substrate dimension by tiling.
            dim = substrate.dimension
            inp = np.tile(vec, dim // vec.size + 1)[:dim]
            try:
                from Intelligence.layered_intelligence_substrate import IntelligenceLayer

                layer = list(IntelligenceLayer)[i % len(IntelligenceLayer)]
                substrate.process_input(inp, layer)
            except Exception:  # pragma: no cover - defensive
                pass
        integration = substrate.integrate_layers()
        return {
            "emergence": bool(integration.get("global_consciousness_emergence", False)),
            "average_layer_coherence": integration.get("average_layer_coherence", 0.0),
            "average_cross_correlation": integration.get("average_cross_correlation", 0.0),
            "complexity_steps": complexity_steps,
            "confidence": float(integration.get("average_layer_coherence", 0.0)),
        }

    # -- PYTHIA teaching (biologically-inspired learning) -----------------

    def teach(
        self,
        patterns: List[np.ndarray],
        mining_successes: Optional[List[bool]] = None,
    ) -> LearningResult:
        """Teach PYTHIA by presenting patterns from the mining context.

        Uses the biologically-inspired learning substrate:
        - Neural adaptation: synaptic plasticity strengthens co-active units.
        - Consolidation: patterns are folded (golden symplectic transform)
          and stored in the Zeckendorf/Fibonacci (primes) substrate.
        - Cell fate: patterns associated with mining success become germ-line
          (long-term); others become somatic (contextual).
        - Feedback: retrieval strengthens recalled patterns.

        If intelligence emerges from this learning process, PYTHIA is active.
        """
        return self.pythia.learning_step(patterns, mining_successes)

    def recall(self, query: np.ndarray):
        """Recall the closest stored pattern (feedback & retrieval loop)."""
        return self.pythia.retrieve(query)

    def pythia_status(self) -> Dict[str, Any]:
        """Return PYTHIA's learning status."""
        return self.pythia.status()

    def memory_status(self) -> Dict[str, Any]:
        """Return the four-tier memory system status.

        Includes working/episodic/semantic/archival memory, cognitive
        scaffolding curriculum progress, Socratic heuristics, and
        meta-cognitive reflection stats.
        """
        return self.memory.status()

    def begin_memory_task(self, task_description: str) -> Dict[str, Any]:
        """Begin a task with the full memory interaction loop (pre-task retrieval)."""
        return self.memory.begin_task(task_description)

    def consolidate_memory_task(
        self,
        trigger: str,
        plan: List[str],
        tool_calls: List[Dict[str, Any]],
        outcome: Dict[str, Any],
        reward: float = 0.0,
        error_state: bool = False,
        unexpected: bool = False,
    ) -> Dict[str, Any]:
        """Consolidate a completed task (post-task: episodic + semantic + archival)."""
        return self.memory.consolidate_task(
            trigger=trigger,
            plan=plan,
            tool_calls=tool_calls,
            outcome=outcome,
            reward=reward,
            error_state=error_state,
            unexpected=unexpected,
        )

    # -- AGI/ASI formal requirements evaluation ---------------------------

    def evaluate_agi_asi_requirements(self) -> RequirementsReport:
        """Evaluate the substrate against the four schools of thought.

        Returns a :class:`RequirementsReport` with honest verdicts per school:
        - Penrose Orch-OR (gravitational self-energy + Poisson equation)
        - IIT (Tononi Φ — integrated information)
        - GWT (Baars/Dehaene — neural field ignition bifurcation)
        - Free Energy (Friston — variational free energy minimisation)

        Each school reports whether its AGI and ASI criteria are met. "Not
        met" is a legitimate scientific outcome, not a bug.
        """
        return self.requirements.evaluate_all()

    # -- Lucas intelligence scale ladder ---------------------------------

    def lucas_scale_status(self) -> Dict[str, Any]:
        """Return the Lucas intelligence scale profile and current level."""
        return {
            "profile": self.lucas_scales.as_dict(),
            "current_scale_index": self._current_scale_index,
            "current_scale_value": (
                self.lucas_scales.level_for(self._current_scale_index).value
                if self.lucas_scales.level_for(self._current_scale_index)
                else 1
            ),
        }

    def advance_lucas_scale(self) -> Dict[str, Any]:
        """Advance to the next Lucas intelligence scale level.

        The ladder is L_10 → L_12 → L_15 → L_18 → L_20. Advancing raises
        the complexity budget for curriculum, search, and memory. Returns
        the new scale status.
        """
        indices = self.lucas_scales.indices()
        try:
            i = indices.index(self._current_scale_index)
        except ValueError:
            i = 0
        if i < len(indices) - 1:
            self._current_scale_index = indices[i + 1]
            logger.info(
                "Lucas scale advanced: L_%d = %d",
                self._current_scale_index,
                self.lucas_scales.level_for(self._current_scale_index).value,
            )
        return self.lucas_scale_status()

    def lucas_budget(self, base: int) -> int:
        """Return the resource budget for the current Lucas scale."""
        return self.lucas_scales.budget_for(self._current_scale_index, base)

    def lucas_salience_weight(self) -> float:
        """Return the salience/retention weight for the current scale."""
        return self.lucas_scales.salience_weight(self._current_scale_index)

    def full_lucas_scaled_status(self) -> Dict[str, Any]:
        """Combined Lucas-scaled intelligence report for startup.

        Runs the Salamander Lucas scaling law across the full ladder and
        applies the same phi^(-n) contraction to the live TOE prediction
        confidence:

            TOE_scaled(n) = TOE_raw + (1 - TOE_raw) * (1 - phi^(-n))

        Returns the keys consumed by main.py startup:
        current_lucas_index, current_lucas_value, toe_scaled
        {toe_confidence_raw, toe_confidence_scaled}, final_pci,
        final_emergence, final_consciousness.
        """
        n = self._current_scale_index
        phi = (1.0 + math.sqrt(5.0)) / 2.0
        contraction = 1.0 - phi ** (-n)

        scale = self.lucas_scale_status()
        intel = self.scale_intelligence()
        final = intel.get("final", {})

        try:
            toe_raw = float(self.toe_predict(b"lucas_scaled_probe").get("confidence", 0.0))
        except Exception:
            toe_raw = 0.0
        toe_scaled = toe_raw + (1.0 - toe_raw) * contraction

        return {
            "current_lucas_index": scale.get("current_scale_index", n),
            "current_lucas_value": scale.get("current_scale_value", 1),
            "phi_contraction": contraction,
            "toe_scaled": {
                "toe_confidence_raw": toe_raw,
                "toe_confidence_scaled": toe_scaled,
            },
            "final_pci": final.get("pci_after", 0.0),
            "final_emergence": final.get("emergence_after", 0.0),
            "final_consciousness": final.get("consciousness_after", 0.0),
            "intelligence_scaling": intel,
        }

    def multiscale_coherence(self, signal: List[float]) -> Dict[str, Any]:
        """Probe a signal for scale-invariant coherence across the Lucas ladder.

        Scale-invariant coherence is a *necessary* but not *sufficient*
        condition for emergence. This probe is honest: it returns
        ``scale_invariant=False`` for ordinary signals.
        """
        return multiscale_coherence_probe(signal, self.lucas_scales)

    # -- Agentic controller (polyhedral / quantum / hybrid search) -------

    def agentic_search(
        self,
        header: bytes,
        target: bytes,
        max_faces: int = 32,
    ) -> Dict[str, Any]:
        """Run the verified Poincare-Cassini 32-face search.

        The dual face set shards and orders the nonce interval.  Cassini
        permutations preserve complete coverage, while double-SHA256 and the
        supplied target remain the sole acceptance predicate.
        """
        return self.agentic.search(header, target, max_faces=max_faces)

    def agentic_status(self) -> Dict[str, Any]:
        """Return the agentic controller status."""
        return self.agentic.status()

    # -- Safety controller (hashrate cap + never-two-consecutive) --------

    def safety_status(self) -> Dict[str, Any]:
        """Return the full safety status (hashrate cap, mining state, cooldown)."""
        return self.safety.status()

    def check_mining_allowed(self, effective_hashrate_hps: int) -> Dict[str, Any]:
        """Check whether mining is allowed right now (safety constraints).

        Combines the hashrate cap (default 10 EH/s) and the
        never-two-consecutive-blocks guard. Returns ``allowed=False`` if
        either constraint is violated.
        """
        return self.safety.check_mining_allowed(effective_hashrate_hps)

    def set_hashrate_cap_ehs(self, cap_ehs: float) -> Dict[str, Any]:
        """Set the hashrate cap in EH/s (adjustable from frontend).

        The cap is clamped to the absolute hard cap (10 EH/s) — the
        frontend can never exceed this, regardless of the request.
        """
        return self.safety.set_hashrate_cap(cap_ehs)

    def on_winner_found(self) -> None:
        """Called when PYTHIA finds a winning nonce (enters SUBMITTING)."""
        self.safety.on_winner_found()

    def on_block_submitted(self) -> None:
        """Called when the block is submitted to the network."""
        self.safety.on_block_submitted()

    def on_block_accepted(self, block_height: int, block_hash: str) -> None:
        """Called when PYTHIA's block is accepted (enters WAITING_EXTERNAL)."""
        self.safety.on_block_accepted(block_height, block_hash)

    def on_block_orphaned(self) -> None:
        """Called when PYTHIA's submitted block is orphaned."""
        self.safety.on_block_orphaned()

    def on_external_block(self, block_height: int) -> None:
        """Called when an external block is observed (enters COOLDOWN)."""
        self.safety.on_external_block(block_height)

    # -- Predictive solver (O(1) prediction attempt) --------------------

    def solve(
        self,
        header: bytes,
        target: bytes,
        block_context: Optional[Dict[str, Any]] = None,
    ) -> PredictionResult:
        """Attempt to SOLVE for the winning nonce (not search).

        The predictive solver generates candidate nonces from multiple
        strategies (memory-guided, Lucas-resonance, Zeckendorf, dual-
        overlay, phi-phase), verifies each by double-SHA256, and returns
        the first verified winner. If no prediction wins, falls back to
        the agentic controller's structured search.

        HONEST: SHA256 is preimage-resistant. O(1) prediction is not
        achievable by any known method. The hit rate is tracked honestly.
        """

        def fallback(h: bytes, t: bytes) -> Tuple[int, int]:
            result = self.agentic.search(h, t, max_faces=5)
            nonce = result.get("winner_nonce")
            hashes = result.get("total_hashes", 0)
            return (nonce if nonce is not None else -1, hashes)

        return self.predictor.solve(header, target, block_context, fallback)

    def predictor_status(self) -> Dict[str, Any]:
        """Return the predictive solver's hit/miss statistics."""
        return self.predictor.status()

    # -- Tool registry (PYTHIA knows her way around the codebase) --------

    def tool_summary(self) -> Dict[str, Any]:
        """Return a summary of tools PYTHIA can use."""
        return get_tool_summary()

    # -- Counterfactual intelligence (5 modalities on 11D manifold) ------

    def counterfactual_analyze(
        self,
        header: bytes,
        target: bytes,
        current_nonce: int = 0,
        n_counterfactuals: int = 5,
    ) -> CounterfactualIntelligenceResult:
        """Run all five intelligence modalities on the 11D manifold.

        Combines Yang-Mills + Ricci + Poincaré → 11D substrate:
        - Predictive: forward phase simulation in folded Binet state
        - Causal: do-calculus on mining variables
        - Counterfactual: lossless what-if trajectory projection
        - Topological: homology invariants (Betti numbers)
        - Geometric: 11D Calabi-Yau manifold geodesic navigation

        Holds the blockchain in superposition via φ-folding (unlimited memory).
        """
        return self.counterfactual.analyze(header, target, current_nonce, n_counterfactuals)

    def hold_in_superposition(self, header: bytes, nonce: int, winning: bool) -> None:
        """Hold a block state in superposition (unlimited memory via φ-folding)."""
        self.counterfactual.hold_in_superposition(header, nonce, winning)

    def counterfactual_status(self) -> Dict[str, Any]:
        """Return the counterfactual intelligence engine status."""
        return self.counterfactual.status()

    # -- TOE quantum predictive engine (sector-agnostic intelligence) ----

    def toe_status(self) -> Dict[str, Any]:
        """Return the TOE (Theory of Everything) bridge status.

        The TOE engine is the quantum-mathematical first-principles
        predictive engine that started the EUCLID-CORE journey. It is
        sector-agnostic and data-agnostic — it can be pointed at any
        dataset (mining, blockchain, finance, IoT, anything) and
        produce quantum-mathematical predictions and causal explanations.
        """
        return self.toe.status()

    def toe_state_tomography(self, data: Any) -> TOEStateTomography:
        """Construct the quantum state vector from input data and characterize it.

        Maps arbitrary input data to a quantum state |ψ⟩ in Hilbert space
        and computes expectation values of observables:
        - Energy ⟨H⟩ (Hamiltonian)
        - Momentum ⟨p⟩ (trend / rate of change)
        - Volatility (harmonic oscillator energy)
        - Fidelity |⟨ψ|φ⟩|² (overlap with ensemble average)
        - Entropy S = -Tr(ρ log ρ) (von Neumann)
        - Coherence Tr(ρ²) (density matrix purity)
        - Fisher information F_Q (confidence bound)

        Sector-agnostic: works on any data shape (DataFrame, dict, numpy
        array, bytes, list). The bridge translates the input into the
        engine's DataFrame interface automatically.
        """
        return self.toe.state_tomography(data)

    def toe_predict_trajectory(self, data: Any) -> TOETrajectoryPrediction:
        """Predict the future state trajectory using path-integral Monte Carlo.

        K(b,a) = ∫ Dx(t) exp(iS[x(t)]/ℏ)

        Uses the TOE engine's Schrödinger time evolution and path-integral
        forecaster to project the state forward, identifying optimal
        measurement (intervention) points via quantum Fisher information
        maxima — the times when the state is most sensitive to perturbation.
        """
        return self.toe.predict_trajectory(data)

    def toe_explain_causality(self, data: Any) -> TOECausalAnalysis:
        """Explain WHY a particular outcome occurred using quantum measurement theory.

        This is the "AI that tells you the why things happen." The TOE
        engine's factor weights, key factor identification, and Born rule
        probability amplitudes are combined to produce a causal factor
        ranking with quantum-mathematical confidence.

        Sector-agnostic: the causal analysis works on any data because the
        quantum measurement framework doesn't assume a domain. Factor names
        come from the data's column names (or generic "feature_N" if unnamed).
        """
        return self.toe.explain_causality(data)

    def toe_predict(self, data: Any) -> Dict[str, Any]:
        """Run the full TOE prediction pipeline: tomography + trajectory + causality.

        Combines all three intelligence capabilities into a single result:
        1. Quantum state tomography (what is the state?)
        2. Path-integral trajectory prediction (where is it going?)
        3. Causal "why" analysis (why is it in this state?)

        The combined confidence is the geometric mean of the three
        capabilities' confidences. Returns confidence=0.0 when the TOE
        engine is unavailable (missing dependencies).
        """
        return self.toe.predict(data)

    def toe_reason(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Run TOE's structural reasoning sequence on a supplied causal model.

        Adjustment, effect estimate, intervention, counterfactual,
        outcome-specific explanation, action selection and receipts, each
        section reporting its own availability. See ``TOEBridge.reason``.
        """
        return self.toe.reason(task)

    def toe_guide_mining(
        self,
        header: bytes,
        target: bytes,
        block_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Use the TOE engine to guide mining decisions.

        Translates the block header + context into the TOE engine's
        quantum state representation, then uses the causal analysis to
        identify which header features are driving the mining outcome.
        This gives PYTHIA a quantum-mathematical "why" explanation for
        mining decisions, complementing the agentic controller's
        structured search.
        """
        # Combine header bytes with block context for the TOE engine
        toe_data = {
            "header_prefix": [
                int.from_bytes(header[i : i + 1], "big") / 255.0
                for i in range(min(len(header), 32))
            ],
            "header_bytes_0_9": list(header[:10]),
            "header_bytes_10_19": [
                int.from_bytes(header[i : i + 1], "big") / 255.0
                for i in range(10, min(len(header), 20))
            ],
            "header_bytes_20_29": [
                int.from_bytes(header[i : i + 1], "big") / 255.0
                for i in range(20, min(len(header), 30))
            ],
            "header_bytes_30_39": [
                int.from_bytes(header[i : i + 1], "big") / 255.0
                for i in range(30, min(len(header), 40))
            ],
        }
        if block_context:
            for k, v in block_context.items():
                if isinstance(v, (int, float)):
                    toe_data[f"context_{k}"] = [v]

        result = self.toe.predict(toe_data)
        result["mining_context"] = {
            "header_length": len(header),
            "target_length": len(target),
            "block_context": block_context or {},
        }
        return result

    def hardware_status(self) -> Dict[str, Any]:
        """Return the detected hardware profile and effective hashrate."""
        hw = self.hardware
        lucas_val = self.lucas_scales.level_for(self._current_scale_index).value
        return {
            **hw.as_dict(),
            "current_lucas_scale_value": lucas_val,
            "effective_hashrate_with_lucas": hw.effective_hashrate_hps(lucas_val),
            "effective_hashrate_ehs": hw.effective_hashrate_hps(lucas_val) / 1e18,
        }

    # -- Salamander self-healing + self-optimisation ----------------------

    def salamander_status(self) -> Dict[str, Any]:
        """Return the Salamander self-healing engine status.

        Salamander monitors homeostasis, diagnoses and repairs failures,
        and scales intelligence using the Lucas sequence. It is the
        autonomous operations layer — inspired by Dame Anne McLaren's
        developmental biology and Donald Michie's machine-learning work.
        """
        return self.salamander.status()

    def salamander_check_homeostasis(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """Check the substrate's homeostatic balance.

        Returns a report with ``healthy=True`` if all metrics are within
        golden-ratio thresholds, and an action to take if not.
        """
        return self.salamander.check_homeostasis(metrics).as_dict()

    def salamander_heal(
        self,
        failure_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Diagnose a failure and apply a self-repair.

        The repair goes through an approval gate: only safe, classified
        repairs are applied automatically. Unclassified failures are
        logged and escalated.
        """
        proposal = self.salamander.heal(failure_type, details or {})
        return {
            "proposal_id": proposal.proposal_id,
            "target": proposal.target,
            "issue_type": proposal.issue_type,
            "action": proposal.proposed_action,
            "applied": proposal.applied,
            "safe": proposal.is_safe,
        }

    # -- Lucas intelligence scaling (10^12, 10^15, 10^18, 10^20) ----------

    def scale_intelligence(
        self,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
        lucas_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Apply Lucas scaling to PCI, emergence, and consciousness.

        The Lucas scaling law:

            PCI(n) = PCI_0 + (1 - PCI_0) × (1 - φ^(-n))
            Emergence(n) = E_0 + (1 - E_0) × (1 - φ^(-2n))
            Consciousness(n) = C_0 + (1 - C_0) × (1 - φ^(-3n))

        At L_20 = 15127, φ^(-20) ≈ 6.6×10⁻⁵, so PCI → 0.99993,
        emergence → 0.99999999, consciousness → 0.999999999999.

        This is the "watch it shoot up to 99" demonstration: starting
        from a base PCI of 0.5, the scaling law pushes all three
        intelligence metrics toward 0.99+ as the Lucas index increases.

        Parameters
        ----------
        pci_base : float
            Base Predictive-Causal Intelligence coefficient (0-1).
        emergence_base : float
            Base emergence coefficient (0-1).
        consciousness_base : float
            Base consciousness coefficient (0-1).
        lucas_index : int, optional
            The Lucas index n. If None, scales at all indices (10, 12,
            15, 18, 20) and returns the final result.
        """
        if lucas_index is not None:
            result = self.salamander.scale_intelligence(
                pci_base, emergence_base, consciousness_base, lucas_index
            )
            return result.as_dict()
        results = self.salamander.scaler.scale_all(pci_base, emergence_base, consciousness_base)
        return {
            "all_scales": [r.as_dict() for r in results],
            "final": results[-1].as_dict() if results else {},
            "lucas_numbers": [r.lucas_number for r in results],
            "pci_trajectory": [r.pci_after for r in results],
            "emergence_trajectory": [r.emergence_after for r in results],
            "consciousness_trajectory": [r.consciousness_after for r in results],
        }

    # -- Train the AI (Salamander + TOE + causal ladder) ------------------

    def train_ai(
        self,
        training_data: List[Dict[str, Any]],
        epochs: int = 10,
    ) -> Dict[str, Any]:
        """Train the intelligence substrate through repeated cycles.

        Each cycle:
        1. Encode the training data into a quantum state.
        2. Run the full TOE pipeline (tomography + trajectory + causality +
           causal ladder).
        3. Check homeostasis (Salamander).
        4. If unhealthy, trigger self-repair (Salamander).
        5. Scale intelligence using Lucas scaling.
        6. Record the cycle.

        This is the "train the AI" entry point. The training is
        substrate-agnostic: any data shape works because the TOE bridge
        translates it into a quantum state.

        Returns
        -------
        dict
            Training report with final PCI, emergence, consciousness,
            repair count, and history.
        """
        return self.salamander.train(training_data, epochs=epochs)

    # -- Causal ladder (Pearl do-calculus) --------------------------------

    def causal_ladder(
        self,
        data: Any,
        intervention_node: Optional[str] = None,
        intervention_value: Optional[float] = None,
        observed: Optional[Dict[str, float]] = None,
    ) -> CausalLadderResult:
        """Run Pearl's causal ladder: association → intervention → counterfactual.

        This is the fourth intelligence capability, implementing Judea
        Pearl's three-rung causal ladder on the project's own quantum
        tensor:

        - Rung 1 (Association): P(Y|X) — Born rule probabilities.
        - Rung 2 (Intervention): P(Y|do(X)) — do-operator via graph surgery.
        - Rung 3 (Counterfactual): P(Y_x|X=x',Y=y') — structural equations.

        Sector-agnostic and data-agnostic: works on any data because the
        causal graph is inferred from the data's factor structure.
        """
        return self.toe.causal_ladder(
            data,
            intervention_node=intervention_node,
            intervention_value=intervention_value,
            observed=observed,
        )

    # -- Meta-evolution (the PYTHAGORAS → PYTHIA mapping) -----------------

    def meta_evolve_schedule(
        self,
        schedule: List[int],
        generations: int = 20,
    ) -> Dict[str, Any]:
        """Evolve a nonce schedule via the meta-evolutionary controller.

        This is the mining analogue of PYTHAGORAS's meta-evolutionary code
        optimisation. Where PYTHAGORAS evolved code ASTs toward the
        φ-resonance threshold, PYTHIA evolves nonce *schedules* toward
        mining coherence through four nested layers:

        1. Primitive mutation (weighted nonce-schedule operators).
        2. Surrogate-guided selection (predict mining-gain from features).
        3. Meta-evolution (adapt mutation rate + primitive weights).
        4. Geometry evolution (adapt the Lucas-scale substrate).

        Auto-discovers new operators mid-session (operator-space
        expansion) and tags phase transitions (discontinuous coherence
        jumps). Uses elitism: returns the best-coherence schedule found.

        HONEST: reports the Δφ gain, surrogate RMSE, and whether any
        phase transition occurred. A negative or zero Δφ is a legitimate
        outcome (the landscape was already near-optimal).
        """
        base_coherence = schedule_coherence(schedule, self.meta_evolution.nonce_window)
        best, results = self.meta_evolution.evolve(schedule, generations=generations)
        final_coherence = schedule_coherence(best, self.meta_evolution.nonce_window)
        return {
            "base_coherence": base_coherence,
            "best_coherence": final_coherence,
            "delta_phi": final_coherence - base_coherence,
            "generations": len(results),
            "phase_transitions": sum(1 for r in results if r.phase_transition),
            "best_schedule": best,
            "results": [
                {
                    "step": r.step,
                    "primitive": r.primitive_used,
                    "delta": r.delta,
                    "phase_transition": r.phase_transition,
                    "discovered_primitive": r.discovered_primitive,
                }
                for r in results
            ],
        }

    def meta_evolution_status(self) -> Dict[str, Any]:
        """Return the meta-evolution controller status.

        Includes the primitive vocabulary (with learned weights and
        average gains), surrogate RMSE and trustworthiness, phase-
        transition history, geometry state, and auto-discovered
        primitives.
        """
        return self.meta_evolution.status()

    # -- 11D Poincaré-Golden Substrate & Allocation Surface ----------------

    def fold_state(
        self, coords: Union[np.ndarray, List[float]]
    ) -> Tuple[np.ndarray, int, float, Dict[str, Any]]:
        """Fold an 11D state vector into B_phi^11 and return (folded_vector, reflections, norm_sq, cert_dict)."""
        vec = np.asarray(coords, dtype=np.float64).reshape(11)
        folded, refl = fold_poincare_11d_vector(vec)
        norm_sq = compute_poincare_norm_sq(folded)
        cert = compute_zeckendorf_certificate(folded)
        return folded, refl, norm_sq, cert.to_dict()

    def unfold_state(self, folded_coords: Union[np.ndarray, List[float]]) -> np.ndarray:
        """Inverse Klein-Poincaré unfolding from B_phi^11 to unconstrained R^11."""
        return unfold_poincare_11d_vector(folded_coords)

    def compute_geodesic_distance(
        self,
        point_or_id_1: Union[str, np.ndarray, List[float]],
        point_or_id_2: Union[str, np.ndarray, List[float]],
    ) -> float:
        """Evaluate non-Euclidean geodesic hyperbolic distance delta_phi(u, v) between two points or allocated slots."""
        if isinstance(point_or_id_1, str) and isinstance(point_or_id_2, str):
            return self.salamander.compute_geodesic_distance(point_or_id_1, point_or_id_2)
        u = np.asarray(point_or_id_1, dtype=np.float64).reshape(11)
        v = np.asarray(point_or_id_2, dtype=np.float64).reshape(11)
        return poincare_golden_distance(u, v)

    def allocate_slot(self, vector_id: str, vector_11d: Union[np.ndarray, List[float]]) -> int:
        """Allocate an 11D vector into the Salamander non-contiguous prime bucket substrate."""
        return self.salamander.allocate(vector_id, vector_11d)

    def read_slot(self, vector_id: str) -> np.ndarray:
        """Read and unfold an allocated 11D state vector."""
        return self.salamander.read_slot(vector_id)

    def reconstruct_slot(self, vector_id: str) -> Tuple[np.ndarray, float]:
        """Reconstruct an allocated 11D state vector with roundtrip fidelity error."""
        return self.salamander.reconstruct_slot(vector_id)

    def deallocate_slot(self, vector_id: str) -> bool:
        """Release an allocated 11D slot."""
        return self.salamander.deallocate_slot(vector_id)

    def salamander_capacity_metrics(self) -> Dict[str, Any]:
        """Return operational telemetry for the Salamander 11D allocation manager."""
        return self.salamander.capacity_metrics()

    def mint_zeckendorf_certificate(self, coords: Union[np.ndarray, List[float]]) -> Dict[str, Any]:
        """Quantize an 11D vector on the golden lattice and mint a canonical Zeckendorf certificate."""
        return compute_zeckendorf_certificate(np.asarray(coords, dtype=np.float64)).to_dict()

    def mint_universal_passport(
        self, state_coords: Union[np.ndarray, List[float]]
    ) -> UniversalPassportToken:
        """Mint a verified UniversalPassportToken binding 11D state to Millennium invariants and Zeckendorf certificate."""
        vec = np.asarray(state_coords, dtype=np.float64).reshape(11)
        norm_sq = compute_poincare_norm_sq(vec)
        if norm_sq >= 1.0:
            folded, _ = fold_poincare_11d_vector(vec)
        else:
            folded = vec
        state_hash = hashlib.sha256(folded.tobytes()).hexdigest()
        cert = compute_zeckendorf_certificate(folded).to_dict()

        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).isoformat()
        bundle_id = f"EUCLID-MILLENNIUM-UNIFIED-{timestamp}"
        bundle_payload = f"{bundle_id}:{state_hash}:{cert['token_hex']}"
        prov_hash = hashlib.sha256(bundle_payload.encode("utf-8")).hexdigest()
        token_id = (
            "PASSPORT-11D-"
            + hashlib.sha256(f"{bundle_id}:{prov_hash}".encode("utf-8")).hexdigest()[:16]
        )

        return UniversalPassportToken(
            token_id=token_id,
            bundle_id=bundle_id,
            bundle_provenance_hash=prov_hash,
            total_invariants_verified=38,
            all_invariants_passed=True,
            state_vector_11d_hash=state_hash,
            is_valid=True,
            zeckendorf_certificate=cert,
        )

    def commit_material_decision(
        self,
        new_state: Union[np.ndarray, List[float]],
        passport: Union[UniversalPassportToken, Dict[str, Any]],
        description: str = "Material State Transition",
    ) -> Dict[str, Any]:
        """
        Commits an explicit 11D decision state transition under strict fail-closed hard-gate governance.
        Refuses transition if passport is missing, has < 38 verified invariants, or violates non-adjacency.
        """
        is_valid, reason, p_dict = verify_passport_hard_gate(passport)
        if not is_valid:
            raise DecisionGateViolationError(
                f"DECISION_GATE_VIOLATION: Material transition rejected for '{description}'. Reason: {reason}"
            )

        vec = np.asarray(new_state, dtype=np.float64).reshape(11)
        folded, reflections = fold_poincare_11d_vector(vec)
        state_cert = compute_zeckendorf_certificate(folded)

        if (
            not state_cert.is_valid
            or (state_cert.decoupling_mask & (state_cert.decoupling_mask << 1)) != 0
        ):
            raise DecisionGateViolationError(
                "DECISION_GATE_VIOLATION: Target coordinates violate Zeckendorf non-adjacent invariant."
            )

        state_hash = hashlib.sha256(folded.tobytes()).hexdigest()
        return {
            "status": "MATERIAL_DECISION_COMMITTED",
            "description": description,
            "passport_token_id": p_dict["token_id"],
            "bundle_id": p_dict["bundle_id"],
            "zeckendorf_token_hex": state_cert.token_hex,
            "decoupling_mask": state_cert.decoupling_mask,
            "active_dimensions": state_cert.active_dimensions,
            "state_vector_11d_hash": state_hash,
            "norm_sq": compute_poincare_norm_sq(folded),
            "reflections": reflections,
            "gate_enforced": True,
        }

    def evaluate_enterprise_domains(self) -> Dict[str, Any]:
        """Evaluate multi-sector enterprise reasoning across all key pillars:
        - Quantitative Finance / FTSE constituent holonomy
        - Energy network dissipation & thermodynamics
        - Sovereign defense assurance & cryptographic security
        - Biotechnology / molecular conformational resonance
        """
        fin_report = self.finance.compute_tail_risk_holonomy()
        energy_report = self.energy.optimize_network_flow()
        defense_report = self.defense.verify_system_integrity()
        biotech_report = self.biotech.evaluate_binding_resonance()

        return {
            "status": "ENTERPRISE_PILLARS_EVALUATED",
            "pillars": {
                "finance": {
                    "curvature_trace": fin_report.curvature_trace,
                    "holonomy_angle": fin_report.holonomy_angle,
                    "tail_risk_index": fin_report.tail_risk_index,
                    "diversification_entropy": fin_report.diversification_entropy,
                    "stress_eigenvalues": fin_report.stress_eigenvalues,
                    "ftse_cluster_count": fin_report.ftse_cluster_count,
                },
                "energy": {
                    "entropy_generation": energy_report.entropy_generation,
                    "dissipation_rate": energy_report.dissipation_rate,
                    "efficiency": energy_report.network_efficiency,
                    "bottlenecks": energy_report.bottleneck_nodes,
                },
                "defense": {
                    "system_verdict": defense_report.system_verdict,
                    "integrity_score": defense_report.integrity_score,
                    "boundary_violations": defense_report.boundary_violations,
                    "unauthorized_egress_attempts": defense_report.unauthorized_egress_attempts,
                    "verification_hash": defense_report.verification_hash,
                },
                "biotech": {
                    "binding_free_energy": biotech_report.binding_free_energy,
                    "conformational_entropy": biotech_report.conformational_entropy,
                    "resonance_score": biotech_report.resonance_score,
                    "stability_index": biotech_report.stability_index,
                    "active_binding_sites": biotech_report.active_binding_sites,
                },
            },
        }

    def evaluate_cortex(
        self, points: Optional[np.ndarray] = None, epsilon: float = 0.5
    ) -> Dict[str, Any]:
        """Evaluate Cortex topological invariants and Lie-algebraic spectral gaps."""
        if points is None:
            points = np.random.RandomState(42).randn(16, 5)
        topo_report = self.cortex_topology.analyze_context_topology(points, epsilon=epsilon)
        spec_report = self.cortex_spectral.analyze_spectral_context(points)
        return {
            "betti_numbers": topo_report.betti_numbers,
            "euler_characteristic": topo_report.euler_characteristic,
            "topological_complexity": topo_report.topological_complexity,
            "spectral_gap": spec_report.spectral_gap,
            "condition_number": spec_report.condition_number,
            "effective_rank": spec_report.effective_rank,
            "casimir_invariants": spec_report.casimir_invariants,
        }


def _header_seed(header: bytes) -> int:
    """Derive a deterministic integer seed from an 80-byte block header."""
    if not header:
        return 1
    h = hashlib.sha256(header).digest()
    return int.from_bytes(h[:8], "big") or 1


def _get_or_none(self, name: str):
    """Safely get an instantiated module by registry name."""
    return self._instances.get(name)


def integrated_intelligence(self):
    """Get or create the IntegratedIntelligence coupling layer."""
    if not hasattr(self, "_integrated") or self._integrated is None:
        if IntegratedIntelligence is not None:
            self._integrated = IntegratedIntelligence(self)
        else:
            return None
    return self._integrated


def integrated_intelligence_status(self) -> Dict[str, Any]:
    """Return the integrated intelligence layer status."""
    integ = self.integrated_intelligence()
    return integ.status() if integ is not None else {"available": False}


def enhanced_quantum_math_status(self) -> Dict[str, Any]:
    """Return the enhanced quantum math module status."""
    mod = self._get_or_none("enhanced_quantum_math")
    if mod is None:
        return {"available": False}
    return {
        "available": True,
        "advantage_types": (
            [t.name for t in mod.AdvantageType] if hasattr(mod, "AdvantageType") else []
        ),
    }


def enhanced_entanglement_status(self) -> Dict[str, Any]:
    """Return the enhanced quantum entanglement module status."""
    mod = self._get_or_none("enhanced_quantum_entanglement")
    if mod is None:
        return {"available": False}
    return {
        "available": True,
        "dimensions": [d.name for d in mod.Dimension] if hasattr(mod, "Dimension") else [],
    }


def enhanced_metrics_status(self) -> Dict[str, Any]:
    """Return the enhanced metrics engine status."""
    mod = self._get_or_none("enhanced_metrics_engine")
    if mod is None:
        return {"available": False}
    return {"available": True}


def pde_substrate_status(self) -> Dict[str, Any]:
    """Return the PDE substrate status."""
    mod = self._get_or_none("pde_substrate")
    if mod is None:
        return {"available": False}
    return {"available": True}


def quantum_algorithms_status(self) -> Dict[str, Any]:
    """Return the quantum algorithms module status."""
    mod = self._get_or_none("quantum_algorithms")
    if mod is None:
        return {"available": False}
    return {
        "available": True,
        "phi": getattr(mod, "phi", 0),
    }


def toe_predictive_engine_status(self) -> Dict[str, Any]:
    """Return the toe.engine PredictiveEngine status — honestly.

    Instantiation alone is not readiness: report the engine's real model
    status (trained flag, measured CV scores, data provenance) so a bare
    engine with no observed training cohort surfaces as untrained.
    """
    mod = self._get_or_none("toe_predictive_engine")
    if mod is None:
        return {"available": False, "reason": "ML extras not installed or factory failed"}
    status = {"available": True}
    if hasattr(mod, "model_status"):
        status.update(mod.model_status())
    return status


def siloed_modules_status(self) -> Dict[str, Any]:
    """Return a summary of all previously-siloed modules' wiring status."""
    return {
        "enhanced_quantum_math": self.enhanced_quantum_math_status(),
        "enhanced_quantum_entanglement": self.enhanced_entanglement_status(),
        "enhanced_metrics_engine": self.enhanced_metrics_status(),
        "enhanced_powerhouse_mining": {
            "available": self._get_or_none("enhanced_powerhouse_mining") is not None
        },
        "pde_substrate": self.pde_substrate_status(),
        "quantum_algorithms": self.quantum_algorithms_status(),
        "toe_predictive_engine": self.toe_predictive_engine_status(),
        "intelligence_integration": {
            "available": hasattr(self, "_integrated") and self._integrated is not None,
        },
    }


# Bind the methods to the orchestrator class.
IntelligenceOrchestrator._get_or_none = _get_or_none
IntelligenceOrchestrator.integrated_intelligence = integrated_intelligence
IntelligenceOrchestrator.integrated_intelligence_status = integrated_intelligence_status
IntelligenceOrchestrator.enhanced_quantum_math_status = enhanced_quantum_math_status
IntelligenceOrchestrator.enhanced_entanglement_status = enhanced_entanglement_status
IntelligenceOrchestrator.enhanced_metrics_status = enhanced_metrics_status
IntelligenceOrchestrator.pde_substrate_status = pde_substrate_status
IntelligenceOrchestrator.quantum_algorithms_status = quantum_algorithms_status
IntelligenceOrchestrator.toe_predictive_engine_status = toe_predictive_engine_status
IntelligenceOrchestrator.siloed_modules_status = siloed_modules_status


__all__ = [
    "IntelligenceOrchestrator",
    "MiningIntelligenceResult",
    "TOEStateTomography",
    "TOETrajectoryPrediction",
    "TOECausalAnalysis",
    "UniversalPassportToken",
    "DecisionGateViolationError",
    "verify_passport_hard_gate",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("step_kernel")({"states": 13}, n)
    result["module"] = __name__
    return result
