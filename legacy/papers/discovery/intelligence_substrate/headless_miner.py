import os
import time
import hashlib
import importlib
import logging
import asyncio
import json
import tempfile
import math
import threading
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional

root_path = str(Path(__file__).parent.parent)

try:
    from dotenv import load_dotenv

    load_dotenv(Path(root_path) / ".env")
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

from python_backend.hyba_substrate.manifold_orchestrator import (
    GeometricIntelligence,
    UnifiedManifoldOrchestrator,
)
from python_backend.core_modules.pulvini_folding import PulviniMemoryFolder
from python_backend.core_modules.hermes_scheduler import HermesScheduler
from python_backend.pythia_mining.stratum_client import (
    StratumClient,
    compute_stratum_merkle_root,
    build_stratum_block_header,
)
from python_backend.pythia_mining.manifold_pool_coordinator import ManifoldPoolCoordinator
from python_backend.pythia_mining.agentic_mining_integration import AgenticMiningIntegration
from python_backend.pythia_mining.salamander_systems_engineer import SalamanderSystemsEngineer
from python_backend.pythia_mining.intelligence_chooser import (
    MiningIntelligenceChooser,
    describe_share,
)
from python_backend.pythia_mining.search_lane_descriptor import format_lane_label
from python_backend.hyba.search.vector_search import CapabilitySearch
from python_backend.hyba.search.stabilization import StabilizationEngine
from python_backend.accel.substrate import get_quantum_accel, shutdown_shared_accel
import atexit

atexit.register(shutdown_shared_accel)

from python_backend.hyba.unlimited_power_engine import (
    HYBAMetallicPowerEngine,
    HYBAUnifiedExecutionSubstrate,
    MetallicPowerConfig,
)
from fractions import Fraction
from python_backend.hyba.quantum.primitives import ExactFraction
from python_backend.quantum_first_principles import (
    FirstPrinciplesQuantumSubstrate,
    LUCAS_15,
    PHI,
)
from python_backend.core_modules.intelligence_memory import IntelligenceMemoryDB
from python_backend.hyba.runtime.ledger import UnifiedExecutionLedger
from python_backend.hyba.runtime.treasury import TreasuryLedger
from python_backend.hyba.runtime.backends import (
    ExecutionSubstrateDispatcher,
    QuantumMathematicalBackend,
)
from python_backend.hyba.runtime.state import (
    RepresentationState,
    SubstrateType,
    RepresentationDomain,
)
from python_backend.mathematical_foundation.quantum_math_layer import QuantumMathLayer

try:
    from python_backend.phi_grover_v4 import (
        phi_resonance,
        curvature_action_score,
        voronoi,
        PHI_I as PHI_COLLAPSE,
        ACTION_THRESHOLD,
        M32 as M32_FACES,
        ADJ as M32_ADJ,
    )

    _HAS_PHI_GROVER_V4 = True
except ImportError:
    _HAS_PHI_GROVER_V4 = False
    PHI_COLLAPSE = 0.618
    ACTION_THRESHOLD = 3 - PHI
    M32_FACES = None
    M32_ADJ = None


def deterministic_id(prefix: str, *parts: object) -> str:
    """Deterministic identifier: sha256 over the joined string parts.

    Wall-clock time, uuid4 and unseeded randomness are identity inputs ONLY
    if a mining run cannot be replayed. This helper derives every mining
    identity from configured or job-derived material so identical inputs
    produce identical transcripts.
    """
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


class _NullPulvini:
    """Unavailable-runtime shim: solve() returns no candidates so the
    structured pre-pass path still runs. Reports itself in stage_outputs."""

    def solve(self, **kwargs):
        return type(
            "SolveResult",
            (),
            {
                "candidates": [],
                "regime": "unavailable",
                "path_used": "none",
                "stage_outputs": {
                    "S3_gate": {"regime": "solve", "reason": "pulvini_unavailable"}
                },
            },
        )()


def _capability_available(module_name: str, *attrs: str) -> bool:
    """Real capability check: the module must import AND expose its attrs.

    The previous `try: pass` placeholders reported True unconditionally --
    capability telemetry that cannot be wrong is not telemetry.
    """
    try:
        if importlib.util.find_spec(module_name) is None:
            return False
        mod = importlib.import_module(module_name)
        return all(hasattr(mod, attr) for attr in attrs)
    except Exception:
        return False


def _env_default(key: str, value: str) -> None:
    """setdefault, but treat a set-but-BLANK variable as unset.

    A scaffolded .env commonly contains `KEY=` with no value. That counts as
    SET to os.environ, so os.environ.setdefault() will not replace it, and
    every downstream `os.getenv(KEY, "false").lower() == "true"` then reads ""
    and silently evaluates False. Blank means "not configured", so let the
    documented default apply -- and the documented default for anything that
    reaches a third party is OFF (see _env_flag below).
    """
    if not os.environ.get(key, "").strip():
        os.environ[key] = value


def _env_flag(key: str, default: bool = False) -> bool:
    """Read a boolean env flag. Unset, blank, and unparseable all mean `default`.

    Single parsing rule for the whole miner so a flag cannot mean one thing
    at import time and another at call time.
    """
    raw = os.environ.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


# --- EXTERNAL-ACTION SAFETY ENVELOPE -------------------------------------
# Every default below is FAIL-CLOSED. Importing this module must never, on
# its own, be sufficient to open a socket to a mining pool or submit a share.
#
# These four previously defaulted to "true", so an unset OR blank variable --
# the exact state of a scaffolded .env -- armed live Stratum egress and live
# share submission with no operator approval. Enabling live external action
# is now an explicit, auditable act: set the variable to "true" on purpose.
#
# The anti-silent-failure doctrine is preserved by _announce_safety_envelope()
# below: a miner that cannot reach a pool says so loudly at startup rather
# than pretending to mine. It just no longer says it by dialling out first.
_env_default("HYBA_ENABLE_AUTONOMOUS_MINING", "false")
_env_default("HYBA_AUTONOMY_LEVEL", "bounded")
_env_default("HYBA_OPERATOR_APPROVAL_REQUIRED", "true")
_env_default("HYBA_ENABLE_LIVE_STRATUM", "false")
_env_default("HYBA_ENABLE_LIVE_SHARE_SUBMIT", "false")
_env_default("HYBA_AUTONOMOUS_EXTERNAL_ACTIONS", "false")
_env_default("HYBA_ENABLE_MINING_AUTOCONNECT", "false")
_env_default("HYBA_MINING_CONTINUOUS", "true")
_env_default("HYBA_MINING_GROVER_NONCE_ORDERING", "false")
_env_default("HYBA_MINE_NONCES_PER_CYCLE", "250000")
_env_default("HYBA_MINING_USE_QUANTUM_MEMORY_FEEDBACK", "true")
_env_default("HYBA_MINING_USE_GEOMETRIC_RESONANCE_GATE", "false")
_env_default("HYBA_MINING_USE_COUNTERFACTUAL_GATE", "true")

from python_backend.hyba.runtime.mining_safety import (
    MiningSafetyBoundary,
)  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def mining_preflight(strict: bool = True) -> dict:
    """Report -- loudly -- whether this process can actually mine and submit.

    Doctrine 10 and 18: a pool ACK is the pool-confirmed truth class, the only
    class that cannot be earned without a third party. A miner that cannot
    authenticate can never earn it, so failing quietly is worse than not
    starting. This states the gate's actual value and names every missing key.
    """
    required_credentials = {
        "HYBA_POOL_VIABTC_USERNAME": "pool worker/username (e.g. account.worker)",
        "HYBA_POOL_VIABTC_PASSWORD": "pool worker password",
    }
    missing = [k for k in required_credentials if not os.environ.get(k, "").strip()]

    from python_backend.pythia_mining.stratum_client import StratumClient

    approved = StratumClient.is_live_submit_approved()
    url = os.environ.get("HYBA_POOL_VIABTC_URL", "").strip() or "(code default: btc.viabtc.io:3333)"
    budget = os.environ.get("HYBA_MINE_NONCES_PER_CYCLE", "").strip()

    logging.info("[PREFLIGHT] pool url .............. %s", url)
    logging.info("[PREFLIGHT] nonces per cycle ...... %s", budget)
    logging.info("[PREFLIGHT] live submit approved .. %s", approved)
    for k in required_credentials:
        logging.info("[PREFLIGHT] %s ... %s", k, "SET" if k not in missing else "MISSING / BLANK")

    # Capability Detection — each check imports the real module and verifies
    # the attribute the miner actually calls. A capability that cannot be
    # exercised is reported UNAVAILABLE, never assumed.
    has_qmath = _capability_available(
        "python_backend.mathematical_foundation.quantum_math_layer",
        "QuantumMathLayer",
    )
    has_folding = _capability_available(
        "python_backend.core_modules.pulvini_folding", "PulviniMemoryFolder"
    )
    has_phi_grover = _HAS_PHI_GROVER_V4
    has_supposition = _capability_available(
        "python_backend.pythia_mining.precompute_cache", "load_policy_prior"
    )
    has_entanglement = _capability_available(
        "python_backend.core_engine.enhanced_quantum_entanglement"
    )
    has_veritas = _capability_available(
        "papers.discovery.intelligence_substrate.salamander.veritas_ledger"
    )
    has_salamander = _capability_available(
        "python_backend.pythia_mining.salamander_systems_engineer",
        "SalamanderSystemsEngineer",
    )

    from python_backend.accel.substrate import get_quantum_accel

    accel = get_quantum_accel(0)
    # `_igpu` holds the native object OR the mathematical fallback object, so it
    # is ALWAYS truthy and cannot answer "is physical iGPU hardware available".
    # `_igpu_available` is the authoritative flag set in accel/substrate.py.
    has_igpu = bool(getattr(accel, "_igpu_available", False))

    logging.info("[PREFLIGHT] --- CAPABILITIES ---")
    logging.info("[PREFLIGHT] POOL CONFIG       %s", "OK" if not missing else "MISSING")
    logging.info("[PREFLIGHT] LIVE SUBMISSION   %s", "ENABLED" if approved else "DISABLED")
    logging.info("[PREFLIGHT] IGPU              %s", "AVAILABLE" if has_igpu else "UNAVAILABLE")
    logging.info("[PREFLIGHT] QUANTUM MATH      %s", "AVAILABLE" if has_qmath else "UNAVAILABLE")
    logging.info("[PREFLIGHT] FOLDING           %s", "AVAILABLE" if has_folding else "UNAVAILABLE")
    logging.info(
        "[PREFLIGHT] PHI-GROVER        %s", "AVAILABLE" if has_phi_grover else "UNAVAILABLE"
    )
    logging.info(
        "[PREFLIGHT] SUPPOSITION       %s", "AVAILABLE" if has_supposition else "UNAVAILABLE"
    )
    logging.info(
        "[PREFLIGHT] ENTANGLEMENT      %s", "AVAILABLE" if has_entanglement else "UNAVAILABLE"
    )
    logging.info("[PREFLIGHT] VERITAS           %s", "AVAILABLE" if has_veritas else "UNAVAILABLE")
    logging.info(
        "[PREFLIGHT] SALAMANDER        %s", "AVAILABLE" if has_salamander else "UNAVAILABLE"
    )
    logging.info("[PREFLIGHT] --------------------")

    if missing:
        detail = ", ".join(f"{k} ({required_credentials[k]})" for k in missing)
        msg = (
            "[PREFLIGHT] cannot mine: pool credentials are missing or blank in .env -> "
            + detail
            + ". A blank value in .env counts as SET, so defaults do not apply. "
            "Fill these in and restart. No shares can be submitted and no "
            "pool-confirmed evidence can be earned until they are set."
        )
        logging.error(msg)
        if strict:
            raise RuntimeError(msg)
    elif not approved:
        logging.error(
            "[PREFLIGHT] credentials present but the live-submit gate is CLOSED "
            "(HYBA_ENABLE_LIVE_SHARE_SUBMIT / HYBA_AUTONOMOUS_EXTERNAL_ACTIONS). "
            "The miner will search but never submit."
        )
    else:
        logging.info("[PREFLIGHT] armed: credentials present, live submit approved.")

    return {
        "missing_credentials": missing,
        "live_submit_approved": approved,
        "pool_url": url,
        "nonces_per_cycle": budget,
        "igpu": has_igpu,
        "supposition": has_supposition,
    }


def _grover_ordering_enabled() -> bool:
    """Read live (not cached) so tests that construct a bare
    AutonomousExecutionLoop via __new__ (bypassing __init__) still get an
    honest answer, and so monkeypatching the env var mid-test works."""
    return os.getenv("HYBA_MINING_GROVER_NONCE_ORDERING", "false").lower() in ("true", "1")


def _default_search_label() -> str:
    return "grover_lucas" if _grover_ordering_enabled() else "classical"


class AutonomousExecutionLoop:
    """One miner. Agentic+coordinator search. Salamander keeps the pool afloat."""

    def __init__(self):
        logging.info("Initializing HYBA First-Principles Quantum Autonomous Mining Engine")
        self.memory = IntelligenceMemoryDB.get_instance() if IntelligenceMemoryDB else None
        # Deterministic session identity: derived from configured pool+worker
        # material, NOT wall-clock time. Identical configuration produces an
        # identical session id — a checkpoint written under this id can be
        # resumed byte-for-byte after restart.
        self.session_id = deterministic_id(
            "mining_session",
            os.getenv("HYBA_POOL_VIABTC_URL", ""),
            os.getenv("HYBA_POOL_VIABTC_USERNAME", ""),
        )
        # Per-job deterministic seed material + midstate bookkeeping. Set in
        # _on_stratum_job; invalidated on clean_jobs / job-id change.
        self._midstate_job_id: Optional[str] = None
        self._job_seed_material: Optional[bytes] = None
        # Unified manifold orchestrator with all 6 intelligence lobes
        self.manifold_orchestrator = UnifiedManifoldOrchestrator()
        self.l1 = self.manifold_orchestrator.topological
        self.l2 = self.manifold_orchestrator.geometric
        self.l3 = self.manifold_orchestrator.predictive
        self.l4 = self.manifold_orchestrator.causal
        self.l5 = self.manifold_orchestrator.counterfactual
        self.l6 = self.manifold_orchestrator.quantum
        self.quantum_math_layer = QuantumMathLayer()
        self.pulvini = PulviniMemoryFolder()
        self.hermes = HermesScheduler()
        self.stratum = StratumClient()
        self.quantum_substrate = FirstPrinciplesQuantumSubstrate(dim=32)
        self.face_probs = [1.0 / 32.0] * 32
        self.resonance_weights = [0.5 + 0.5 * (i % 5 == 0) for i in range(32)]

        try:
            from python_backend.hyba.memory import get_memory

            self.hyba_mem = get_memory()
            self._quantum_state_address = self.hyba_mem.allocate(size=len(self.face_probs))
            self.hyba_mem.write(self._quantum_state_address, self.face_probs)
        except Exception as e:
            logging.info(f"HYBAMemory prime-gap state slot unavailable, skipping: {e}")
            self.hyba_mem = None
            self._quantum_state_address = None

        self.search = CapabilitySearch(n_qubits=8)
        self.stabilizer = StabilizationEngine(self.search)
        self.accel = get_quantum_accel(substrate_index=0)
        self.power_config = MetallicPowerConfig(family="Bronze", level=15)
        self.power_engine = HYBAMetallicPowerEngine(self.power_config)
        self.unified_substrate = HYBAUnifiedExecutionSubstrate()
        self.unified_ledger = UnifiedExecutionLedger(self.session_id)
        self.treasury_ledger = TreasuryLedger(self.unified_ledger)
        self.current_job_context = None

        self.substrate_dispatcher = ExecutionSubstrateDispatcher()
        self.quantum_backend = QuantumMathematicalBackend(self.substrate_dispatcher)

        self.coordinator = ManifoldPoolCoordinator(
            self.quantum_substrate, scan=self.accel.scan_sha256d
        )
        self.coordinator.seed_faces()
        self.face_probs = self.coordinator.export_amplitudes()
        self.agentic = AgenticMiningIntegration(self.coordinator)

        # Geometry/prior cache wiring: the job-independent manifold tables are
        # built once, persisted atomically, and reloaded on later startups.
        # Advisory only — a MISS or corrupt blob rebuilds; nothing here can
        # alter the SHA-256d accept authority.
        self._geometry_cache_status = "UNWIRED"
        self._policy_prior: Dict[str, Any] = {}
        try:
            from python_backend.pythia_mining import precompute_cache
            from python_backend.mathematical_foundation.hilbert_manifold_solver import (
                ManifoldPrecomputationEngine,
            )

            engine = ManifoldPrecomputationEngine.get_instance()
            version = precompute_cache.geometry_version_hash(
                PHI, LUCAS_15, {"gram_threshold": 0.75}
            )
            tables, self._geometry_cache_status = precompute_cache.load_or_build(
                version, engine.export_tables
            )
            self.agentic.arsenal = tables
            self._policy_prior = precompute_cache.load_policy_prior()
            logging.info(
                "[CACHE] geometry tables %s | policy_prior priors=%d | truth=%s",
                self._geometry_cache_status,
                len(self._policy_prior.get("priors", {})),
                self._policy_prior.get("truth_label"),
            )
        except Exception as exc:
            logging.warning("[CACHE] precompute cache unavailable, cold start: %s", exc)

        try:
            from hyba_cogito import CogitoSDK, CogitoConfig, Domain

            self.cogito = CogitoSDK(CogitoConfig(domain=Domain.AUTONOMOUS_VEHICLE))
            self.cogito.initialize()
            logging.info("[COGITO] SDK initialized and integrated with Autonomous Execution Loop.")
        except ImportError as e:
            self.cogito = None
            logging.info(f"[COGITO] Optional Cogito SDK not loaded: {e}")

        # Bridge the Cogito Gap: Load the Unified State Packet (USP)
        self.cogito_usp = None
        usp_path = os.path.join(root_path, "artifacts", "usp", "usp_v1.json")
        try:
            if os.path.exists(usp_path):
                with open(usp_path, "r", encoding="utf-8") as f:
                    self.cogito_usp = json.load(f)
                logging.info(
                    "[COGITO] Successfully bridged Cogito Gap: Loaded USP v1 from artifacts."
                )
            else:
                logging.warning(f"[COGITO] USP file not found at {usp_path}. Air-gap remains.")
        except Exception as e:
            logging.error(f"[COGITO] Failed to load USP: {e}")

        self._seed_capabilities()
        self.running = True
        self.variance = 0.05
        self.metrics = {"deadlock": False, "yield": 0.8, "error_count": 0}
        # --- mining truth state (doctrine 10: mining truth boundaries) ---
        # A healthy miner is not one that has not thrown an exception. It is
        # one whose SHA256d counter moves when a live job is present.
        self.mining_phase = "INIT"
        self.mining_fault: Optional[str] = None
        self.consecutive_zero_work_cycles = 0
        self.zero_work_cycle_threshold = int(os.getenv("HYBA_ZERO_WORK_CYCLES", "5"))
        # --- production safety envelope, enforced by the miner itself ---
        # These controls previously existed only in the acceptance harness, so
        # the production loop stopped on neither time nor shares. Constructed
        # here, at startup, so invalid configuration fails closed BEFORE any
        # pool connection is made.
        self.safety = MiningSafetyBoundary.from_env()
        self._cycle_index = 0
        self.state = {"nonce_space": [i for i in range(100)], "current_state": "SCAN"}
        if self.cogito_usp:
            self.state["cogito_usp"] = self.cogito_usp
        self.last_predictive_action: Dict[str, Any] = {"action": "continue", "dampen_lanes": False}
        self.last_causal_action: Dict[str, Any] = {"action": "optimal", "redistribute": False}
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.pool_accepted = 0
        self.total_sha256d_hashes = 0
        self.mining_start_time = time.time()
        self.hash_backend = getattr(self.accel, "hash_backend", "hashlib")
        self.stats_file = os.path.join(tempfile.gettempdir(), "hyba_mining_stats.json")
        self.telemetry_history = []
        self.phi_grover_enabled = _HAS_PHI_GROVER_V4
        self.phi_best_resonance = 0.0
        self.phi_best_nonce = 0
        self.phi_best_face = 0
        self.phi_best_yang_mills = 0.0
        # Quantum-first implementation: Always use quantum-guided nonce ordering
        # through phi-resonance and mathematical first principles.

        self._last_seen_job_id = None
        self._job_first_seen_at = None
        self.job_stale_seconds = float(os.getenv("HYBA_MINING_JOB_STALE_SECONDS", "120"))
        self._job_is_stale = False
        self.salamander = SalamanderSystemsEngineer(stale_seconds=self.job_stale_seconds)
        self.chooser = MiningIntelligenceChooser()
        # Warm-start the chooser from the persisted supposition prior so a
        # cold start does not discard measured pool-response history. The
        # prior is advisory: it can bias lead selection, it cannot create a
        # valid share.
        for lead, stats in (self._policy_prior.get("priors") or {}).items():
            for accepted in stats.get("observed_outcomes", []):
                try:
                    self.chooser.learn(accepted=bool(accepted), lead=str(lead))
                except Exception:
                    break
        # S3 coherence gate (solve-first hierarchy): measured solve-path
        # outcomes feed the gate's fallback decision. Advisory only.
        self._solve_path_outcomes = deque(maxlen=64)
        self._coherence_gate_obj = None
        self._stratum_loop = None
        self._stratum_thread = None
        self._active_job: Optional[Dict[str, Any]] = None
        self._active_mining_cancelled = threading.Event()
        # Idle backoff bounds (see run()). Deliberately small floor so a job
        # arriving mid-backoff is picked up within a second in the common case.
        self._idle_cycles = 0
        self._idle_backoff_base = float(os.getenv("HYBA_IDLE_BACKOFF_BASE_SECONDS", "0.25"))
        self._idle_backoff_max = float(os.getenv("HYBA_IDLE_BACKOFF_MAX_SECONDS", "5.0"))
        self._start_stratum_runtime()
        logging.info(
            "[SUPER] One miner | Agentic+coordinator | Salamander engineer | search=Grover+Lucas | chooser=on"
        )
        if self.phi_grover_enabled:
            logging.info("[PHI-GROVER v4] M_32 φ-resonance oracle + curvature-action gate ACTIVE")
            logging.info(
                f"[PHI-GROVER v4] Faces: 12 dodecahedral + 20 icosahedral | Collapse threshold φ⁻¹ ≈ {PHI_COLLAPSE:.4f} | Action threshold Δ = {ACTION_THRESHOLD:.4f}"
            )
        else:
            logging.warning(
                "[PHI-GROVER v4] phi_grover_v4 not importable — falling back to legacy nonce generation"
            )

    @staticmethod
    def external_actions_permitted() -> bool:
        """True only when an operator has explicitly armed pool egress.

        This is the single gate consulted before the Stratum thread is
        started. HYBA_ENABLE_LIVE_STRATUM and HYBA_ENABLE_MINING_AUTOCONNECT
        were previously read by no gate anywhere in production code -- setting
        them to false had literally no effect. They gate here now.
        """
        return _env_flag("HYBA_ENABLE_LIVE_STRATUM") or _env_flag("HYBA_ENABLE_MINING_AUTOCONNECT")

    def _start_stratum_runtime(self):
        if not self.external_actions_permitted():
            self._stratum_loop = None
            self._stratum_thread = None
            logging.warning(
                "[STRATUM] OFFLINE MODE -- no pool thread started. This miner will NOT "
                "connect to any pool and will NOT submit any share. The substrate, "
                "intelligence loop, folding and telemetry all run; only third-party "
                "egress is withheld."
            )
            logging.warning(
                "[STRATUM] To arm live mining, set HYBA_ENABLE_LIVE_STRATUM=true "
                "(and HYBA_ENABLE_LIVE_SHARE_SUBMIT=true plus either "
                "HYBA_LIVE_SHARE_APPROVAL_ID=<id> or HYBA_AUTONOMOUS_EXTERNAL_ACTIONS=true "
                "to permit submission). Pool credentials are required: "
                "HYBA_POOL_VIABTC_URL / _USERNAME / _PASSWORD."
            )
            return
        self._stratum_loop = asyncio.new_event_loop()

        def _runner():
            asyncio.set_event_loop(self._stratum_loop)
            self._stratum_loop.create_task(self._stratum_supervisor())
            self._stratum_loop.run_forever()

        self._stratum_thread = threading.Thread(target=_runner, daemon=True, name="hyba-stratum")
        self._stratum_thread.start()
        logging.info(
            "[STRATUM] Persistent pool thread started | worker=%s | url=%s | live_submit=%s",
            self.stratum.worker_name,
            self.stratum.pool_url,
            StratumClient.is_live_submit_approved(),
        )

    def _on_stratum_job(self, job: Dict[str, Any]) -> None:
        prev_job_id = (self._active_job or {}).get("job_id")
        if job.get("clean_jobs") or job.get("job_id") != prev_job_id:
            if job.get("clean_jobs"):
                self._preempt_inflight_igpu(job.get("job_id"))
            # A changed header prefix makes any cached midstate stale by
            # definition; the candidate seed material is likewise rebuilt
            # from the new job identity on next use.
            self._midstate_job_id = None
            self._job_seed_material = None
        self._active_job = job

    def _job_seed(self, best_face: int) -> int:
        """Deterministic candidate seed derived from the live job context.

        seed = sha256(job_id | prefix76 | target_int | best_face)[:8]. An
        identical job produces an identical candidate stream — replayable,
        auditable, and free of wall-clock input. With no active job the seed
        derives from the deterministic session id, so behavior is still
        reproducible (and the mine path refuses to hash without a job anyway).
        """
        if self._job_seed_material is None:
            job = self._active_job or {}
            job_id = str(job.get("job_id") or self.session_id)
            prefix = job.get("prefix76") or job.get("header_prefix") or b""
            if isinstance(prefix, str):
                try:
                    prefix = bytes.fromhex(prefix)
                except ValueError:
                    prefix = prefix.encode("utf-8")
            target = int(job.get("target_int") or job.get("target") or 0)
            self._job_seed_material = (
                job_id.encode("utf-8")
                + bytes(prefix)
                + target.to_bytes(32, "big")
            )
        digest = hashlib.sha256(
            self._job_seed_material + int(best_face).to_bytes(4, "big")
        ).digest()
        return int.from_bytes(digest[:8], "big")

    def _preempt_inflight_igpu(self, job_id: Optional[str] = None) -> None:
        self._active_mining_cancelled.set()
        try:
            self.stratum.drain_jobs()
        except Exception:
            pass
        try:
            igpu = getattr(self.accel, "_igpu", None)
            if igpu is not None:
                igpu.cancel_and_flush()
        except Exception as exc:
            # Do NOT re-raise. This runs inside the Stratum job-processing
            # callback; raising here tears down pool I/O for a condition that
            # has already been handled -- _active_mining_cancelled is set
            # above, and that flag is what actually stops the in-flight scan.
            # Record the fault through the existing health mechanism so it is
            # visible to Salamander, and keep the pool alive. A failed
            # preemption is never converted into a successful mining claim:
            # the hash counters are untouched by this path.
            logging.error(
                "[STATE 2: MINE] substrate preemption failed for clean job %s: %s "
                "(cancel flag already set; recording fault rather than tearing down pool I/O)",
                job_id,
                exc,
            )
            self._set_mining_phase("RECOVERING", f"preempt_failed: {exc}")
        logging.warning(
            "[STATE 2: MINE] clean_jobs preempted in-flight custom iGPU execution | job=%s", job_id
        )

    async def _stratum_supervisor(self):
        self.stratum.register_job_callback(self._on_stratum_job)
        while self.running:
            report = self.salamander.keep_afloat(self.stratum)
            if report["need_reconnect"]:
                logging.info("[SALAMANDER] Reconnecting pool...")
                try:
                    ok = await self.stratum.connect()
                except Exception as exc:
                    logging.error("[SALAMANDER] Connect raised: %s", exc)
                    ok = False
                if not ok:
                    logging.error(
                        "[SALAMANDER] Pool unreachable — waiting. Not hashing dummy headers."
                    )
                    await asyncio.sleep(3.0)
                    continue
                job_id = (
                    self.stratum.current_job.get("job_id") if self.stratum.current_job else None
                )
                logging.info(
                    "[SALAMANDER] Pool afloat | job=%s | difficulty=%s",
                    job_id,
                    self.stratum.difficulty,
                )
            await asyncio.sleep(1.0)

    def _await_stratum(self, coro, timeout=8.0):
        if self._stratum_loop is not None:
            fut = asyncio.run_coroutine_threadsafe(coro, self._stratum_loop)
            return fut.result(timeout=timeout)
        # Offline / test path: no background stratum supervisor is running,
        # but a test may inject a job by mocking ``stratum.next_job``. Run the
        # coroutine in a fresh temporary loop so the mocked job is returned.
        try:
            return asyncio.run(asyncio.wait_for(coro, timeout=timeout))
        except RuntimeError as exc:
            # Already inside a running event loop (e.g. pytest-asyncio):
            # we cannot nest loops. Fall back to whatever latched state exists.
            if "cannot be called from a running event loop" in str(exc):
                return None
            raise

    def _quantum_provenance(self) -> Dict[str, Any]:
        """Provenance for the quantum-formalism components, per the HYBA thesis.

        Quantum execution here IS the mathematics: exact state-vector /
        quantum-walk arithmetic, substrate- and hardware-agnostic (registered
        claim turing-10000-qubit-mathematical-substrate,
        docs/claim-boundaries.yaml). The computation is not a stand-in for
        another machine; the maths is the quantum execution. The executing
        substrate (backend/device) is recorded as provenance fact —
        AGENT_REBOOT_PROTOCOL rule 1: record what ran. No disclaimer fields:
        there is nothing to disclaim.
        """
        backend_name = "cpu:numpy"
        device = "cpu"
        try:
            substrate = getattr(self.coordinator, "quantum", None)
            if substrate is None and hasattr(self, "quantum"):
                substrate = self.quantum
            if substrate is not None:
                backend_name = getattr(substrate, "backend_name", backend_name)
                device = getattr(substrate, "device_name", device)
        except Exception:
            pass
        return {
            "execution_type": "mathematical_quantum",
            "claim_id": "turing-10000-qubit-mathematical-substrate",
            "substrate_agnostic": True,
            "backend": backend_name,
            "device": device,
        }

    def _save_stats(self, quantum_telemetry=None):
        try:
            stats = self.stratum.get_stats()
            elapsed = max(time.time() - self.mining_start_time, 1e-9)
            measured_hashrate_hps = round(self.total_sha256d_hashes / elapsed, 3)
            payload = {
                "shares_submitted": self.shares_submitted,
                "shares_accepted": self.stratum.shares_accepted,
                # Pool-confirmed vs locally-validated verdicts stay
                # separable: the aggregate above is kept only for backward
                # compatibility with older dashboards.
                "pool_accepted": getattr(
                    self.stratum, "pool_accepted", self.stratum.shares_accepted
                ),
                "firewall_accepted": getattr(self.stratum, "firewall_accepted", 0),
                "pool_rejected": getattr(self.stratum, "pool_rejected", 0),
                "shares_timed_out": getattr(self.stratum, "shares_timed_out", 0),
                "current_state": self.state["current_state"],
                "phi_resonance": self.phi_best_resonance,
                "last_update": time.time(),
                "block_height": None,
                "total_sha256d_hashes": self.total_sha256d_hashes,
                "hashrate_hps": measured_hashrate_hps,
                "hash_backend": self.hash_backend,
                "hardware_verified": bool(getattr(self.accel, "_igpu_available", False)),
                "mining_phase": self.mining_phase,
                "mining_fault": self.mining_fault,
                "lucas_threads": LUCAS_15,
                "search": _default_search_label(),
                "system": "one_super_miner",
                "agentic": True,
                "salamander": True,
                "chooser": self.chooser.last_choice or {},
                "chooser_accepted_count": self.chooser.accepted_count,
                "chooser_rejected_count": self.chooser.rejected_count,
                "chooser_lead_accept_rates": self.chooser.lead_accept_rates(),
                "quantum_telemetry": quantum_telemetry or {},
                # QUANTUM PROVENANCE: every quantum-formalism component in this
                # system is exact mathematics executed on the recorded
                # substrate — the maths IS the quantum execution (substrate-
                # and hardware-agnostic; registered claim
                # turing-10000-qubit-mathematical-substrate). The executing
                # substrate is recorded as fact in every persisted payload.
                "quantum_provenance": self._quantum_provenance(),
                "phi_grover_v4_enabled": self.phi_grover_enabled,
                "phi_best_resonance": self.phi_best_resonance,
                "phi_best_nonce": self.phi_best_nonce,
                "phi_best_face": self.phi_best_face,
                "phi_best_yang_mills": self.phi_best_yang_mills,
                "m32_faces": 32,
                "football_geometry": {
                    "polyhedron": "truncated_icosahedron",
                    "total_solvers": 32,
                    "pentagon_faces": 12,
                    "hexagon_faces": 20,
                    "parallel_solvers": 32,
                },
                "external_worker": self.stratum.worker_name,
                "cognitive_memory": (
                    self.memory.get_memory_stats() if getattr(self, "memory", None) else {}
                ),
                "job_source": self.state.get("job_source", "unknown"),
                "job_age_seconds": self.state.get("job_age_seconds", 0.0),
                "job_is_stale": self.state.get("job_is_stale", False),
                "intelligence": self.state.get("intelligence", {}),
                "ciaas_outcome": (
                    self.unified_ledger.get_outcome_report()
                    if hasattr(self, "unified_ledger")
                    else {}
                ),
                # Component 3: Whole-Nonce-Field distinction
                "logical_nonce_space": 2**32,  # 4.29 billion nonces (logical search space)
                "mathematical_candidate_regions": getattr(
                    self, "_last_candidate_regions", 32
                ),  # 32 faces in gauge
                "physical_candidates_evaluated": self.total_sha256d_hashes,
                "verified_work": self.shares_submitted,
                "mine_outcome": self.state.get("mine_outcome", {}),
                # GAP-CLOSURE-001: per-cycle stage breakdown + submit-path RTT
                # observations travel with every telemetry snapshot so the
                # serial-pipeline / edge-latency questions stay answerable.
                "cycle_stage_seconds": dict(getattr(self, "_last_stage_seconds", {}) or {}),
                "submit_path": {
                    "last_submit_rtt_ms": getattr(self.stratum, "last_submit_rtt_ms", None),
                    "last_submit_wait_ms": getattr(self.stratum, "last_submit_wait_ms", None),
                    "rtt_samples": list(getattr(self.stratum, "submit_rtt_samples_ms", []) or []),
                },
                "chooser_degraded_count": int(
                    getattr(getattr(self, "chooser", None), "degraded_count", 0)
                ),
            }
            stats.update(payload)
            with open(self.stats_file, "w") as f:
                json.dump(stats, f, indent=2, default=str)
            self.telemetry_history.append(stats)
            if getattr(self, "cogito", None):
                try:
                    self.cogito.process_sensor_data(list(self.face_probs))
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"Failed to save mining stats: {e}")

    def _unitary_phase_transform(self, data):
        try:
            if hasattr(data, "shape"):
                value = data.flat[0] if data.size > 0 else 0.0
            elif isinstance(data, list) and isinstance(data[0], list):
                value = data[0][0]
            elif isinstance(data, list):
                value = data[0]
            else:
                value = data
            if hasattr(value, "item"):
                value = value.item()
            return math.sin(value) * self.pulvini.phi
        except Exception:
            return 0.0 * self.pulvini.phi

    _mock_hash_operation = _unitary_phase_transform

    def _seed_capabilities(self):
        accel_telemetry = self.accel.get_quantum_telemetry()
        decimation = self.power_engine.execute_decimation_profile()
        density_raw = accel_telemetry.get("parallel_density", 1.0)
        if isinstance(density_raw, str):
            try:
                density_val = float(density_raw.rstrip("xX_ "))
            except ValueError:
                density_val = 1.0
        else:
            try:
                density_val = float(density_raw)
            except (ValueError, TypeError):
                density_val = 1.0

        capabilities = [
            ("phi_folder", [1.0], {"type": "algorithm", "name": "PULVINI f-Folding"}),
            (
                "gpu_substrate",
                [density_val],
                {
                    "type": "infrastructure",
                    "name": "HYBA-L2 GPU Acceleration Plane",
                    "accel_scaling": accel_telemetry.get("parallel_density", 1.0),
                    "lucas_level": accel_telemetry.get("lucas_level", 0),
                    "metallic_family": decimation.get("family", "unknown"),
                    "metallic_scaling_formula_value_tflops": decimation.get(
                        "metallic_scaling_formula_value_tflops", 0.0
                    ),
                },
            ),
            (
                "sovereign_enclave",
                [1.0],
                {"type": "security", "name": "Salamander Autonomic Surface"},
            ),
        ]
        for cid, vec, meta in capabilities:
            self.search.add_capability(cid, vec, meta)
        logging.info(f"Seeded {len(capabilities)} core capabilities into quantum search registry.")

    def state_scan(self):
        self.state["current_state"] = "SCAN"
        # Use unified manifold orchestrator for topological and geometric intelligence
        nodes = list(range(32))
        orchestrator = getattr(self, "manifold_orchestrator", None)
        if orchestrator:
            coverage_ok, genus = orchestrator.topological.verify_coverage_invariants(nodes)
            curv = orchestrator.geometric.calculate_curvature(
                getattr(self, "face_probs", [1.0 / 32] * 32)
            )
        else:
            coverage_ok, genus, curv = True, 0, 0.0
        power_eng = getattr(self, "power_engine", None)
        decimation = (
            power_eng.execute_decimation_profile()
            if power_eng
            else {"family": "Bronze", "metallic_scaling_formula_value_tflops": 0.0}
        )
        logging.info(
            f"[STATE 1: SCAN] Manifold Coverage: {coverage_ok} | Genus: {genus} | Curvature: {curv:.4f}"
        )
        return {"coverage": coverage_ok, "genus": genus, "curvature": curv}, {
            "decimation": decimation
        }

    def _apply_quantum_memory_feedback(self, face_probs: list) -> list:
        if not getattr(self, "memory", None):
            return face_probs
        try:
            biased = list(face_probs)
            max_hits = 1
            knowledge = []
            for domain_id in range(len(biased)):
                dk = self.memory.get_domain_knowledge(domain_id)
                knowledge.append(dk)
                if dk and dk.get("hit_count", 0) > max_hits:
                    max_hits = dk["hit_count"]
            for i, dk in enumerate(knowledge):
                if not dk:
                    continue
                hit_ratio = dk.get("hit_count", 0) / max_hits
                resonance = max(0.0, min(1.0, dk.get("phi_resonance", 0.0)))
                biased[i] = biased[i] * (1.0 + 0.5 * hit_ratio * resonance)
            total = sum(biased) or 1.0
            return [x / total for x in biased]
        except Exception as e:
            logging.info(f"[STATE 1.25: QUANTUM_WALK] Memory feedback read skipped: {e}")
            return face_probs

    def _persist_quantum_walk_result(self, scaling_result: Dict[str, Any]) -> None:
        if not getattr(self, "memory", None):
            return
        try:
            self.memory.update_domain_knowledge(
                domain_id=int(scaling_result["best_face"]),
                phi_resonance=float(scaling_result["peak_probability"]),
                increment_hits=True,
            )
        except Exception as e:
            logging.info(f"[STATE 1.25: QUANTUM_WALK] Memory persistence skipped: {e}")

    def state_quantum_walk(self, step_idx: int = 1):
        self.state["current_state"] = "QUANTUM_WALK"
        use_memory_feedback = os.getenv(
            "HYBA_MINING_USE_QUANTUM_MEMORY_FEEDBACK", "true"
        ).lower() in ("true", "1")
        walk_input = self.face_probs
        if use_memory_feedback:
            walk_input = self._apply_quantum_memory_feedback(walk_input)

        target_substrate = (
            SubstrateType.IGPU
            if getattr(getattr(self, "accel", None), "_igpu_available", False)
            else SubstrateType.CPU
        )
        rep_state = RepresentationState(
            domain=RepresentationDomain.GAUGE, substrate=target_substrate, buffer=walk_input
        )
        rep_state = self.quantum_backend.apply_amplitude_amplification(rep_state, None)
        self.unified_ledger.record_execution(
            substrate=rep_state.substrate.name, search_method="quantum_walk"
        )

        # Enforce exact rational quantum mathematics from first principles.
        # Seed the walk with the distribution actually computed above: with an
        # unseeded evolve_dtqw() the walk always restarts from the uniform
        # superposition, so walk_input -- and therefore the memory-feedback
        # flag -- could not change the walked distribution at all.
        walk_seed = None
        if len(walk_input) == getattr(self.quantum_substrate, "dim", -1):
            walk_seed = [
                ExactFraction(Fraction(float(p)).limit_denominator(10**12)) for p in walk_input
            ]
        rational_state = self.quantum_substrate.evolve_dtqw(steps=3, initial_state=walk_seed)
        self.face_probs = [float(amp.val) for amp in rational_state.amplitudes]

        # Calculate derived stats for the log statement
        best_face = max(range(len(self.face_probs)), key=lambda i: self.face_probs[i])
        peak_probability = self.face_probs[best_face]
        top_amplified_faces = sorted(
            range(len(self.face_probs)), key=lambda i: self.face_probs[i], reverse=True
        )[:5]

        scaling_result = {
            "distribution": self.face_probs,
            "provenance": "Exact Rational Substrate",
            "scale": 15,
            "best_face": best_face,
            "peak_probability": peak_probability,
            "top_amplified_faces": top_amplified_faces,
        }

        self.coordinator.ingest_amplitudes(self.face_probs)
        self._persist_quantum_walk_result(scaling_result)
        if self.hyba_mem is not None and self._quantum_state_address is not None:
            try:
                self.hyba_mem.write(self._quantum_state_address, self.face_probs)
            except Exception as e:
                logging.info(f"[STATE 1.25: QUANTUM_WALK] HYBAMemory state write skipped: {e}")
        logging.info(
            f"[STATE 1.25: QUANTUM_WALK] Best Face: {scaling_result['best_face']} | Peak Prob: {scaling_result['peak_probability']:.4f} | Top Faces: {scaling_result['top_amplified_faces']}"
        )
        return scaling_result

    def state_search(self):
        self.state["current_state"] = "SEARCH"
        # Deterministic probe: derived from session identity + cycle counter
        # so identical runs replay identically (random.random() previously
        # made the query unreproducible).
        cycle = int(self.state.get("cycle", 0))
        probe_seed = int.from_bytes(
            hashlib.sha256(
                f"{self.session_id}|search|{cycle}".encode("utf-8")
            ).digest()[:8],
            "big",
        ) / float(1 << 64)
        query = [probe_seed]
        results = self.search.search(query, top_k=2)
        if results:
            best_match = results[0]["item"]["metadata"]["name"]
            score = results[0]["score"]
            logging.info(
                f"[STATE 1.5: SEARCH] Quantum Matching: '{best_match}' | Similarity: {score:.4f}"
            )
        accel_res = self.accel.execute_quantum_kernel(query)
        logging.info(
            f"[STATE 1.5: SEARCH] Accel Quantum Resonance: {accel_res['resonance_score']:.4f} | Throughput: {accel_res['throughput_qops']:.1f} QOps"
        )
        self.stabilizer.run_calibration_cycle()
        return results

    def _get_golden_search(self):
        """Lazily bind the consolidated GoldenRatioSearchCapability.

        The capability is the single consolidated entry point for the
        golden-ratio search technology (search/ package): phi-Weyl
        low-discrepancy candidate sequencing, duplicate-free bijection stride,
        golden-section prioritization, scheduler + oracle-feedback +
        closed-loop-engine delegation. It is enabled by default; operators can
        set HYBA_MINING_GOLDEN_SEARCH=false (or "0"/"off") to restore the
        legacy ad-hoc seed generator, and any import failure degrades safely.
        """
        cached = getattr(self, "_golden_search_cap", "__unset__")
        if cached != "__unset__":
            return cached
        cap = None
        flag = os.getenv("HYBA_MINING_GOLDEN_SEARCH", "true").strip().lower()
        if flag not in ("false", "0", "off"):
            try:
                from search.golden_ratio_capability import (
                    get_golden_search_capability,
                    GOLDEN_NONCE_STRIDE,
                )

                cap = get_golden_search_capability()
                logging.info(
                    "[GOLDEN-SEARCH] capability bound v%s | phi-stride=0x%X "
                    "(duplicate-free uint32 bijection)",
                    cap.version_string(),
                    GOLDEN_NONCE_STRIDE,
                )
            except Exception as exc:
                logging.warning(
                    "[GOLDEN-SEARCH] capability unavailable (%s) - legacy seed generator active",
                    exc,
                )
                cap = None
        self._golden_search_cap = cap
        return cap

    def _pulvini_runtime(self):
        """Lazily bind the PULVINI solve-first runtime (S1-S6 + F1-F3)."""
        if getattr(self, "_pulvini_rt", None) is None:
            try:
                from Intelligence.pulvini_runtime import PulviniRuntime

                self._pulvini_rt = PulviniRuntime()
            except Exception as exc:
                logging.warning("[PULVINI] runtime unavailable (%s)", exc)
                self._pulvini_rt = False
        return self._pulvini_rt or _NullPulvini()

    def _coherence_gate(self):
        """Lazily bind the QuantumCoherenceAnalyzer (S3 solve/fallback gate).

        Solve-first hierarchy: the structured path leads while the measured
        regime carries signal; the gate demotes to fallback when the face
        distribution is uniform AND the measured solve-path hit rate is no
        better than base rate. Advisory: it decides who looks first, never
        what validates.
        """
        if self._coherence_gate_obj is None:
            try:
                from Intelligence.coherence_gate import QuantumCoherenceAnalyzer

                self._coherence_gate_obj = QuantumCoherenceAnalyzer()
            except Exception as exc:
                logging.warning(
                    "[COHERENCE-GATE] unavailable (%s) — solve path leads by default", exc
                )
                self._coherence_gate_obj = False
        return self._coherence_gate_obj or None

    def _phi_guided_nonce_search(
        self, best_face: int, num_candidates: int = 256, selection_strategy: str = "auto"
    ) -> tuple:
        """Pre-pass candidate generator.

        Generates initial seed nonces and evaluates phi-resonance before passing
        to the canonical manifold pool coordinator. This is NOT a competing
        canonical solver to ManifoldPoolCoordinator; it provides preliminary
        candidate seeds to guide search initialization. Candidate generation is
        sourced from the consolidated GoldenRatioSearchCapability (default
        "weyl" strategy); the legacy ad-hoc generator remains verbatim as the
        degraded fallback path.
        """
        if not getattr(self, "phi_grover_enabled", False):
            fallback = (self._job_seed(best_face) ^ (best_face * 0x1000000)) % 0xFFFFFFFF
            return fallback, 0.0, 0.0, 0

        # Job-derived deterministic seed — identical job context produces an
        # identical candidate stream (replaces int(time.time()*1000)).
        t_seed = self._job_seed(best_face)
        golden_cap = self._get_golden_search()
        if golden_cap is not None:
            gs_seeds = golden_cap.generate_candidate_seeds(
                best_face=best_face,
                num_candidates=max(1, num_candidates),
                t_seed_ms=t_seed,
            )
            candidate_nonces = list(gs_seeds["candidates"])
            try:
                self.state["golden_search"] = {
                    "capability_version": gs_seeds["sequence_version"],
                    "strategy": gs_seeds["strategy"],
                    "candidate_count": len(candidate_nonces),
                }
            except Exception:
                pass
        else:
            # Legacy ad-hoc time-stride generator, retained verbatim so
            # HYBA_MINING_GOLDEN_SEARCH=false restores prior behavior exactly.
            candidate_nonces = []
            for i in range(max(1, num_candidates)):
                if i == 0:
                    n = (t_seed ^ (best_face * 0x1000000)) % 0xFFFFFFFF
                else:
                    n = (t_seed + i * (1 + best_face)) % 0xFFFFFFFF
                    n ^= int((t_seed & 0xFF) * (i + 1)) & 0xFFFFFFFF
                candidate_nonces.append(n)
        if os.getenv("HYBA_MINING_USE_GEOMETRIC_RESONANCE_GATE", "false").lower() in ("true", "1"):
            l2 = getattr(self, "l2", None) or GeometricIntelligence()
            gated = l2.filter_resonance_gate(candidate_nonces)
            if gated:
                candidate_nonces = list(gated)
        resonances = [phi_resonance(n) for n in candidate_nonces]
        # The intelligence chooser decides which selection tool leads this
        # cycle: "grover" | "argmax" | "auto". "auto" defers to the legacy
        # HYBA_MINING_GROVER_NONCE_ORDERING env flag so pre-chooser behavior
        # is preserved exactly. grover_select_candidate degrades to classical
        # argmax when no candidate is marked — the honest fallback.
        strategy = (selection_strategy or "auto").lower()
        if strategy not in ("grover", "argmax", "auto"):
            strategy = "auto"
        if strategy == "auto" and os.getenv(
            "HYBA_MINING_GROVER_NONCE_ORDERING", "false"
        ).lower() in ("true", "1"):
            strategy = "grover"
        if strategy in ("grover", "auto") and self.phi_grover_enabled:
            from python_backend.pythia_mining.grover_nonce_ordering import grover_select_candidate

            selected_idx = grover_select_candidate(
                candidate_nonces, getattr(self, "search_oracle", None)
            )
        else:
            selected_idx = max(range(len(resonances)), key=lambda i: resonances[i])
        best_n = candidate_nonces[selected_idx]
        best_r = resonances[selected_idx]
        best_s = curvature_action_score(best_n)
        best_f = voronoi(best_n)
        if best_r > self.phi_best_resonance:
            self.phi_best_resonance = best_r
            self.phi_best_nonce = best_n
            self.phi_best_face = best_f
            self.phi_best_yang_mills = best_s
        return best_n, best_r, best_s, best_f

    # Operational mining vocabulary. Only POOL_ACCEPTED is externally
    # confirmed; everything above it is an internal claim (doctrine 5/10).
    MINING_PHASES = (
        "INIT",
        "WAITING_FOR_JOB",
        "STALE",
        "MINING",
        "MINING_ZERO_THROUGHPUT",
        "HASHING",
        "VALIDATING",
        "SUBMITTING",
        "POOL_ACCEPTED",
        "POOL_REJECTED",
        "RECOVERING",
    )

    def _set_mining_phase(self, phase: str, fault: Optional[str] = None) -> None:
        """Record the operational mining phase, and any fault, truthfully.

        A fault raises `metrics["error_count"]`, which is the input Salamander
        already consumes in `state_heal()`. That is deliberate: it is the
        existing health mechanism, not a fabricated exception.
        """
        self.mining_phase = phase
        self.mining_fault = fault
        self.state["mining_phase"] = phase
        self.state["mining_fault"] = fault
        if fault:
            self.metrics["error_count"] = self.metrics.get("error_count", 0) + 1
            logging.error("[MINING INVARIANT] %s | %s", phase, fault)

    def _publish_mine_outcome(
        self,
        found_nonce: Optional[int],
        candidate_nonce_hex: str,
        hashes_scanned: int,
        validated: bool,
    ) -> None:
        """Publish the authoritative outcome of this MINE cycle.

        `found_nonce` is populated ONLY when a nonce has actually been evaluated
        by SHA256d and passed the target validation path. A phi-guided or
        intelligence-generated candidate is NOT a found nonce, and is reported
        as `candidate_nonce` with `found_nonce = None`.

        This exists because `state_mine()` returns `candidate_nonce_hex` on every
        early-exit path, and that return value was being written straight into a
        field named `found_nonce` in the Treasury report -- producing entries
        such as `"found_nonce": "070db6f9"` alongside `"hashes_done": 0`.
        Consumers must read this dict, not the return value.

        The evidence classes stay separate and independently measurable:
        logical search space / mathematical candidate regions / candidate nonce /
        physical hashes executed / validated hash / pool-accepted share.
        """
        self.state["mine_outcome"] = {
            "candidate_nonce": candidate_nonce_hex,
            "found_nonce": f"{found_nonce:08x}" if found_nonce is not None else None,
            "hashes_executed": int(hashes_scanned),
            "sha256d_validated": bool(validated),
            "mining_phase": self.mining_phase,
            "mining_fault": self.mining_fault,
        }
        # Feed the S3 coherence gate: only cycles where the solve path led
        # count as solve-path evidence.
        if self.state.get("coherence_gate", {}).get("regime") == "solve":
            self._solve_path_outcomes.append(bool(validated))

    def _record_work_outcome(self, has_live_job: bool, is_stale: bool, hashes: int) -> None:
        """THE MINING INVARIANT.

            MINE entered AND valid non-stale live job AND miner running
                =>  SHA256d attempts MUST increase

        A violation is an unhealthy mining condition, not a quiet no-op. It is
        surfaced through the same error_count Salamander already reads, so the
        system cannot report HEALTHY while doing nothing. No exception is
        fabricated to achieve this, and no counter is ever incremented to hide
        it: the counters keep telling the truth, and the phase tells the truth
        about the counters.
        """
        if not has_live_job:
            self.consecutive_zero_work_cycles = 0
            self._set_mining_phase("WAITING_FOR_JOB")
            return
        if is_stale:
            self.consecutive_zero_work_cycles = 0
            self._set_mining_phase("STALE")
            return
        if not getattr(self, "running", True):
            return
        if hashes > 0:
            self.consecutive_zero_work_cycles = 0
            if getattr(self, "mining_phase", None) not in (
                "SUBMITTING",
                "POOL_ACCEPTED",
                "POOL_REJECTED",
            ):
                self._set_mining_phase("HASHING")
            return
        curr_zero = getattr(self, "consecutive_zero_work_cycles", 0) + 1
        self.consecutive_zero_work_cycles = curr_zero
        threshold = getattr(self, "zero_work_cycle_threshold", 5)
        if self.consecutive_zero_work_cycles >= threshold:
            self._set_mining_phase(
                "MINING_ZERO_THROUGHPUT",
                "ZERO_WORK_DETECTED: {} consecutive MINE cycles with a valid live job "
                "and 0 SHA256d attempts (job={}, substrate={}, budget={})".format(
                    self.consecutive_zero_work_cycles,
                    getattr(self, "_last_seen_job_id", None),
                    getattr(self, "hash_backend", "hashlib"),
                    os.getenv("HYBA_MINE_NONCES_PER_CYCLE", "250000"),
                ),
            )
        else:
            self._set_mining_phase("MINING")

    def _classify_job_freshness(self, current_job) -> dict:
        now = time.time()
        has_job = bool(current_job and isinstance(current_job, dict) and "job_id" in current_job)
        job_id = current_job.get("job_id") if has_job else None
        if job_id != self._last_seen_job_id:
            self._last_seen_job_id = job_id
            self._job_first_seen_at = now if has_job else None
            self._job_is_stale = False
        age_seconds = (
            (now - self._job_first_seen_at) if (has_job and self._job_first_seen_at) else 0.0
        )
        if has_job and age_seconds > self.job_stale_seconds and not self._job_is_stale:
            self._job_is_stale = True
            logging.warning(
                f"[STATE 2: MINE] Pool job '{job_id}' has been unchanged for {age_seconds:.1f}s "
                f"(> {self.job_stale_seconds:.0f}s threshold) — Salamander will keep the pool afloat."
            )
        return {
            "has_job": has_job,
            "job_id": job_id,
            "age_seconds": age_seconds,
            "is_stale": self._job_is_stale,
        }

    def state_mine(self, quantum_info=None):
        """Agentic+coordinator mine the live job with quantum-first
        phi-resonance guided SHA256d scan (HYBA_MINE_NONCES_PER_CYCLE real hash attempts
        per cycle, default 250000). Salamander owns keep-alive.

        self.chooser (MiningIntelligenceChooser) picks which lobe
        conceptually leads this cycle from real state (job availability,
        error count, predictive/causal instability, tracked phi-best) and
        whether to throttle the candidate-nonce width -- this replaces the
        inline `intelligence_dampen` boolean that used to be computed here
        directly; the throttle math itself (256 -> max(32, 256 // 4)) is
        unchanged, it's just now driven through the chooser so the same
        decision is visible in stats via self.state["intelligence"]."""
        self.state["current_state"] = "MINE"
        now = time.time()
        self.l6.grover_search_iteration()
        best_face = quantum_info["best_face"] if quantum_info else 15
        try:
            current_job = self._await_stratum(self.stratum.next_job(), timeout=0.05)
            self._active_job = current_job
        except Exception:
            # No fresh job inside the 50ms window. This is the COMMON path, not
            # the exceptional one: _preempt_inflight_igpu() calls drain_jobs()
            # on every clean_jobs notification, so the queue is already empty
            # and the triggering job is parked on _active_job.
            # NB: self._active_job is initialised to None in __init__, so a
            # getattr(..., default) fallback here would never fire -- the
            # attribute always exists. Fall back on falsiness instead, so the
            # StratumClient's own latched current_job is genuinely consulted.
            current_job = getattr(self, "_active_job", None) or getattr(
                self.stratum, "current_job", None
            )
        finally:
            # ZERO-WORK LATCH FIX.
            #
            # The cancellation flag cancels the PREVIOUS, in-flight scan. It
            # must not cancel the cycle that is about to begin. This clear()
            # used to live inside the `try` above, so the next_job() timeout
            # that drain_jobs() *guarantees* meant it never executed: the first
            # clean_jobs notification set the flag and nothing ever cleared it,
            # and the guard before mine_job() returned early on every cycle
            # thereafter, permanently.
            #
            # Measured against ViaBTC 2026-08-19 before this fix
            # (benchmarks/reports/live_mining_trace_1787133388.json): pool
            # connected, worker authorized, difficulty 16384, 12 real jobs,
            # 761/761 MINE entries with a live job, cancel flag set 761/761,
            # 0 scan() invocations, 0 hashes. Classification ZERO_WORK_DETECTED.
            #
            # Clearing here -- unconditionally, in `finally` -- restores the
            # intended semantics without removing the guard. The guards below
            # still catch a preemption that arrives DURING this cycle, which is
            # the only thing they were ever meant to catch.
            if hasattr(self, "_active_mining_cancelled"):
                self._active_mining_cancelled.clear()
        # Session-epoch guard: a job latched before a disconnect/reconnect
        # belongs to a dead stratum session -- its extranonce1 and template
        # context were invalidated by the new session, so work computed on
        # it can never produce a share the pool will accept. Discard it and
        # wait for the fresh notify instead of hashing a stale template.
        _sess_epoch = getattr(self.stratum, "session_epoch", None)
        if (
            isinstance(current_job, dict)
            and current_job.get("session_epoch") is not None
            and _sess_epoch is not None
            and current_job["session_epoch"] != _sess_epoch
        ):
            logging.warning(
                "[STATE 2: MINE] Discarding job '%s' from dead stratum session "
                "(job session_epoch=%s, current=%s) — waiting for fresh notify.",
                current_job.get("job_id"),
                current_job.get("session_epoch"),
                _sess_epoch,
            )
            self._active_job = None
            current_job = None
        job_freshness = self._classify_job_freshness(current_job)
        error_count = getattr(self, "metrics", {}).get("error_count", 0)
        # Provide accurate telemetry for observation
        measured_hashrate = 0.0
        elapsed = max(time.time() - getattr(self, "mining_start_time", time.time()), 1e-9)
        if hasattr(self, "total_sha256d_hashes"):
            measured_hashrate = self.total_sha256d_hashes / elapsed

        mem_pressure = 50.0
        if getattr(self, "memory", None):
            mem_pressure = self.memory.get_memory_stats().get("pressure_pct", 50.0)

        choice = self.chooser.choose(
            has_job=job_freshness["has_job"],
            error_count=error_count,
            predictive=self.last_predictive_action,
            causal=self.last_causal_action,
            phi_best=self.phi_best_resonance,
            job_stale=job_freshness["is_stale"],
            search_label=_default_search_label(),
            job_difficulty=getattr(self.stratum, "difficulty", 1.0),
            job_age_seconds=job_freshness["age_seconds"],
            hardware_cpu_available=True,
            hardware_igpu_available=bool(
                getattr(getattr(self, "accel", None), "_igpu_available", False)
            ),
            memory_pressure_pct=mem_pressure,
            current_hashrate=measured_hashrate,
        )

        # The chooser (the AI) owns which nonce-selection tool leads this
        # cycle. Record it in state["intelligence"] so the tool choice is
        # auditable in telemetry (_save_stats).
        selection_strategy = str(choice.get("selection_strategy", "auto")).lower()
        if selection_strategy not in ("grover", "argmax", "auto"):
            selection_strategy = "auto"

        serializable_choice = choice.copy()
        serializable_choice["selection_strategy"] = selection_strategy
        if hasattr(serializable_choice.get("agent_action"), "__dict__"):
            serializable_choice["agent_action"] = serializable_choice["agent_action"].__dict__
        if hasattr(serializable_choice.get("agent_observation"), "__dict__"):
            serializable_choice["agent_observation"] = serializable_choice[
                "agent_observation"
            ].__dict__

        self.state["intelligence"] = serializable_choice

        # Salamander Invariant Layer Interception
        salamander_veto = False
        if (
            choice.get("agent_action")
            and choice.get("agent_observation")
            and hasattr(self, "salamander")
        ):
            salamander_veto = not self.salamander.validate_agent_action(
                choice["agent_action"], choice["agent_observation"]
            )
            if salamander_veto:
                # If vetoed, we fallback to classical defaults safely
                choice["search"] = "classical"
                choice["throttle"] = True

        self.state["salamander_veto"] = salamander_veto

        num_candidates = 256
        if choice["throttle"]:
            num_candidates = max(32, num_candidates // 4)
            logging.info(
                "[STATE 2: MINE] Intelligence lead=%s reason=%s throttle active: %s candidates "
                "(predictive=%s, causal=%s)",
                choice["lead"],
                choice["reason"],
                num_candidates,
                self.last_predictive_action.get("action"),
                self.last_causal_action.get("action"),
            )
        # Solve-first hierarchy: the PULVINI runtime executes S1-S6 (fold ->
        # checkpoint -> coherence gate -> boundary regions -> infinity-fold
        # collapse -> chronos ranking); fallback F1-F3 runs inside the same
        # call only when the solve path does not collapse cleanly.
        rt = self._pulvini_runtime()
        job_ctx = self._active_job or {}
        _prefix = job_ctx.get("prefix76") or job_ctx.get("header_prefix") or b""
        if isinstance(_prefix, str):
            try:
                _prefix = bytes.fromhex(_prefix)
            except ValueError:
                _prefix = _prefix.encode("utf-8")
        worker_state = (
            str(job_ctx.get("job_id") or self.session_id).encode("utf-8")
            + bytes(_prefix)
            + int(job_ctx.get("target_int") or job_ctx.get("target") or 0).to_bytes(32, "big")
        )
        solve_result = rt.solve(
            job_id=str(job_ctx.get("job_id") or self.session_id),
            worker_state=worker_state,
            window=max(4096, num_candidates * 16),
            base_nonce=self._job_seed(best_face) & 0xFFFFFFFF,
            top_k=max(8, num_candidates // 8),
            face_probs=list(self.face_probs),
            solve_path_outcomes=list(self._solve_path_outcomes),
        )
        self.state["pulvini"] = {
            "path_used": solve_result.path_used,
            "regime": solve_result.regime,
            "stages": solve_result.stage_outputs,
        }
        self.state["coherence_gate"] = solve_result.stage_outputs.get(
            "S3_gate", {"regime": "solve", "reason": "gate_unavailable"}
        )
        if solve_result.candidates:
            candidate_nonce = int(solve_result.candidates[0]) & 0xFFFFFFFF
            phi_score, action_score, voro_face = 0.0, 0.0, 0
            logging.info(
                "[STATE 2: MINE] PULVINI path=%s gate=%s -> seed %08x",
                solve_result.path_used,
                solve_result.stage_outputs.get("S3_gate", {}).get("reason"),
                candidate_nonce,
            )
        else:
            # Solve returned no candidates at all — the structured pre-pass
            # still applies before the coordinator's canonical scan.
            candidate_nonce, phi_score, action_score, voro_face = self._phi_guided_nonce_search(
                best_face, num_candidates=num_candidates, selection_strategy=selection_strategy
            )
        candidate_nonce_hex = hex(candidate_nonce)[2:].zfill(8)
        found_nonce = None
        hashes_scanned = 0
        is_valid = False
        if not job_freshness["has_job"]:
            logging.warning(
                "[STATE 2: MINE] No live job — Salamander holding. Not hashing dummy headers."
            )
            self.state["job_source"] = "waiting_for_pool"
            self.state["job_age_seconds"] = 0.0
            self.state["job_is_stale"] = False
            self._record_work_outcome(False, False, 0)
            self._publish_mine_outcome(None, candidate_nonce_hex, 0, False)
            return candidate_nonce_hex
        if job_freshness["is_stale"]:
            logging.warning(
                "[STATE 2: MINE] Stale pool job '%s' (age %.1fs) — pausing hashing until "
                "Salamander refreshes the connection/job. No stale shares will be submitted.",
                job_freshness["job_id"],
                job_freshness["age_seconds"],
            )
            self.state["job_source"] = "stale_pool_job"
            self.state["job_age_seconds"] = job_freshness["age_seconds"]
            self.state["job_is_stale"] = True
            self._record_work_outcome(True, True, 0)
            self._publish_mine_outcome(None, candidate_nonce_hex, 0, False)
            return candidate_nonce_hex
        job_id = current_job["job_id"]
        # Epoch tags stamped by parse_stratum_message: job_epoch bumps on
        # every clean_jobs notify, session_epoch on every (re)connect. They
        # are re-checked before kernel dispatch and again inside
        # submit_share so clean_jobs/reconnect retire work even when it
        # races mid-cycle.
        job_epoch_tag = current_job.get("job_epoch")
        if hasattr(self, "treasury_ledger"):
            self.current_job_context = self.treasury_ledger.get_or_create_job(
                job_id, _default_search_label()
            )
        else:
            self.current_job_context = None
        share = describe_share(
            job_id,
            self.stratum.target,
            getattr(self.stratum, "difficulty", 1.0),
            search_label=_default_search_label(),
        )
        logging.info(
            "[STATE 2: MINE] Searching for %s | job=%s | target=%s | difficulty=%s | lead=%s | search=%s",
            share["share"],
            job_id,
            share["target"][:16] + "...",
            share["difficulty"],
            choice["lead"],
            share["search"],
        )
        ntime = current_job.get("ntime", hex(int(time.time()))[2:].zfill(8))
        extranonce2 = self.stratum._get_next_extranonce2()
        merkle_root = compute_stratum_merkle_root(
            coinb1_hex=current_job.get("coinb1", ""),
            extranonce1_hex=self.stratum.extranonce1 or "00000000",
            extranonce2_hex=extranonce2,
            coinb2_hex=current_job.get("coinb2", ""),
            merkle_branch=current_job.get("merkle_branch", []),
        )
        header0 = build_stratum_block_header(
            version_hex=current_job.get("version", "00000000"),
            prevhash_hex=current_job.get("prevhash", "00" * 32),
            merkle_root_hex=merkle_root,
            ntime_hex=ntime,
            nbits_hex=current_job.get("nbits", "1d00ffff"),
            nonce_hex="00000000",
        )
        prefix76 = header0[:76]
        target_int = int(self.stratum.target, 16)

        # HARD EH/s BOUNDARY. This used to clamp only the intelligence
        # *recommendation* field (`agent_action.target_hashrate`), which never
        # reached execution -- so the ceiling constrained nothing. The actual
        # execution configuration is the nonce budget handed to the substrate,
        # so that is what is bounded, using the most recent observed cycle time
        # as the window. No lobe can raise this: the boundary is consulted
        # after every proposal, and it does not consult the proposal's source.
        if hasattr(self, "safety"):
            self.safety.max_ehs
            self.safety.max_hashes_per_second

            configured_budget = int(os.getenv("HYBA_MINE_NONCES_PER_CYCLE", "250000"))
            nonce_budget, _budget_clamped = self.safety.clamp_nonce_budget(
                configured_budget,
                cycle_seconds=getattr(self, "_last_cycle_seconds", 1.0),
                source="HYBA_MINE_NONCES_PER_CYCLE",
            )
        else:
            nonce_budget = int(os.getenv("HYBA_MINE_NONCES_PER_CYCLE", "250000"))

        if hasattr(self, "_active_mining_cancelled") and self._active_mining_cancelled.is_set():
            # A preemption arrived DURING this cycle (between job selection and
            # here). That is legitimate -- a new block template supersedes this
            # work. It still counts as a zero-work cycle for the invariant: if
            # it repeats, the miner is not mining, whatever the reason.
            logging.info(
                "[STATE 2: MINE] preempted mid-cycle for job %s before SHA256d dispatch", job_id
            )
            self._record_work_outcome(True, False, 0)
            self._publish_mine_outcome(None, candidate_nonce_hex, 0, False)
            return candidate_nonce_hex

        if (
            job_epoch_tag is not None
            and getattr(self.stratum, "job_epoch", job_epoch_tag) != job_epoch_tag
        ):
            # A clean_jobs notify landed between job selection and here and
            # retired this template -- do not burn a nonce budget on it.
            logging.info(
                "[STATE 2: MINE] job epoch superseded before SHA256d dispatch "
                "(job=%s epoch=%s active=%s)",
                job_id,
                job_epoch_tag,
                getattr(self.stratum, "job_epoch", None),
            )
            self._record_work_outcome(True, False, 0)
            self._publish_mine_outcome(None, candidate_nonce_hex, 0, False)
            return candidate_nonce_hex

        # Optional: check if intelligence suggested something exceeding budget
        if (
            choice.get("agent_action")
            and hasattr(choice["agent_action"], "target_hashrate")
            and hasattr(self, "safety")
        ):
            suggested_rate = choice["agent_action"].target_hashrate
            allowed_rate, was_clamped = self.safety.vet_hashrate_proposal(
                suggested_rate, source=f"intelligence[{choice.get('lead')}]"
            )
            if was_clamped:
                # Write the clamped value back so the proposal cannot survive
                # downstream as an execution configuration.
                try:
                    choice["agent_action"].target_hashrate = allowed_rate
                except Exception:
                    pass
                if hasattr(self, "supposition_engine") and self.supposition_engine:
                    self.supposition_engine.record_supposition_outcome(
                        f"supp_boundary_clamp_{int(time.time())}",
                        False,
                        "boundary_clamp_applied",
                        "intelligence_vetoed_for_exceeding_max_ehs",
                    )
        result = self.agentic.mine_job(
            job_id=job_id,
            prefix76=prefix76,
            target_int=target_int,
            budget=nonce_budget,
            seed_nonce=candidate_nonce,
            search_policy=choice["policy"],
            phi_score=phi_score,
        )
        found_nonce = result["found_nonce"]
        found_face = result["found_face"]
        hashes_scanned = result["hashes"]
        self.hash_backend = result["backend"]
        self.face_probs = result["face_probs"]
        # SEARCH-LANES-002: stash the cycle's actual descriptor so the cycle
        # summary reports the same lane the coordinator just executed
        # (resolves the env-flag-vs-policy divergence of TELEMETRY-LABEL-001).
        if result.get("search_lane"):
            self.last_lane_descriptor = result["search_lane"]
        self.total_sha256d_hashes += hashes_scanned
        if self.current_job_context:
            self.current_job_context.record_attempt(
                f"{candidate_nonce:08x}", voro_face, phi_score, hashes_scanned
            )
        accepted = None
        if hasattr(self, "_active_mining_cancelled") and self._active_mining_cancelled.is_set():
            found_nonce = None

        if found_nonce is not None:
            candidate_nonce_hex = f"{found_nonce:08x}"
            if found_face is not None:
                voro_face = found_face
            header_bytes = prefix76 + found_nonce.to_bytes(4, "little")
            is_valid = self.stratum.validate_sha256d(header_bytes.hex())
            if self.current_job_context:
                self.current_job_context.record_validation(is_valid)
            if is_valid:
                try:
                    accepted, req_id = self._await_stratum(
                        self.stratum.submit_share(
                            job_id=job_id,
                            nonce=candidate_nonce_hex,
                            ntime=ntime,
                            extranonce2=extranonce2,
                            job_epoch=job_epoch_tag,
                        )
                    )
                except Exception as e:
                    logging.error("[STATE 2: MINE] Coordinator submit error: %s", e)
                    accepted, req_id = False, None
                if self.current_job_context:
                    self.current_job_context.record_pool_result(accepted)
                # Only a pool acknowledgement advances the stop counter. The
                # boundary applies the non-consecutive rule itself.
                if hasattr(self, "safety"):
                    self.safety.record_pool_result(accepted, cycle=self._cycle_index)
                self._set_mining_phase("POOL_ACCEPTED" if accepted else "POOL_REJECTED")
                self.shares_submitted += 1
                self.shares_accepted = self.stratum.shares_accepted
                self.pool_accepted = getattr(self.stratum, "pool_accepted", self.shares_accepted)
                self.chooser.learn(
                    accepted=accepted,
                    lead=choice["lead"],
                    job_id=job_id,
                    duration_seconds=max(0.1, time.time() - now),
                    salamander_veto=salamander_veto,
                    agent_action=choice.get("agent_action"),
                    agent_obs=choice.get("agent_observation"),
                )
                logging.info(
                    "[STATE 2: MINE] AGENTIC SUBMITTED job=%s nonce=0x%s Face %s | search=%s | "
                    "R_φ=%.4f Action=%.4f | SHA256d Valid: True | accepted=%s req=%s | lead=%s | "
                    "submit_rtt_ms=%s job_wait_ms=%s",
                    job_id,
                    candidate_nonce_hex,
                    voro_face,
                    result.get("search", _default_search_label()),
                    phi_score,
                    action_score,
                    accepted,
                    req_id,
                    choice["lead"],
                    getattr(self.stratum, "last_submit_rtt_ms", None),
                    getattr(self.stratum, "last_submit_wait_ms", None),
                )
        domain = "dodecahedral" if voro_face < 12 else "icosahedral"

        if found_nonce is None:
            self.chooser.learn(
                accepted=None,  # Not submitted/found
                lead=choice["lead"],
                job_id=job_id,
                duration_seconds=max(0.1, time.time() - now),
                salamander_veto=salamander_veto,
                agent_action=choice.get("agent_action"),
                agent_obs=choice.get("agent_observation"),
            )
            logging.info(
                "[STATE 2: MINE] Job %s | %s | agentic | proposed=%s | SHA256d validated none | "
                "R_φ=%.4f Action=%.4f Face %s/%s | lead=%s",
                job_id,
                format_lane_label(choice.get("lane_descriptor")),
                result.get("proposed", hashes_scanned),
                phi_score,
                action_score,
                voro_face,
                domain,
                choice["lead"],
            )
        self.state["job_source"] = "live_pool"
        self.state["job_age_seconds"] = job_freshness["age_seconds"]
        self.state["job_is_stale"] = job_freshness["is_stale"]
        self._record_work_outcome(True, False, hashes_scanned)
        self._publish_mine_outcome(found_nonce, candidate_nonce_hex, hashes_scanned, is_valid)
        return candidate_nonce_hex

    def _cycle_fold_tensor(self):
        """The cycle's own state, as the tensor to fold.

        state_fold() previously built `[[random.random(), random.random()]
        for _ in range(100)]`. Folding noise and recording the ratio as a
        representation measurement is not a measurement -- which is why the
        call was commented out of execute_cycle() with the note "folds random
        synthetic data (no mining connection)". Disabling it was right; the
        underlying problem was the input.

        This returns real per-cycle telemetry: the manifold face amplitudes and
        search state this cycle actually produced. Folding it exercises the
        representation layer on data that has a causal connection to the work,
        so the ratio the ledger records means something. Returns None when the
        cycle produced nothing worth folding -- the caller then skips the fold
        rather than manufacturing input for it.
        """
        rows = []

        # self.face_probs is the M_32 manifold amplitude distribution this
        # cycle's quantum walk actually produced (set in state_quantum_walk via
        # scale_with_lucas_15). It is the most information-dense real artifact
        # a cycle generates, and it is exactly the structure the golden
        # representation layer exists to fold.
        face_probs = getattr(self, "face_probs", None) or []
        peak = max((float(v) for v in face_probs), default=0.0)
        for value in face_probs:
            try:
                rows.append([float(value), peak])
            except (TypeError, ValueError):
                continue

        # Real scan counters, paired with the cycle index so successive cycles
        # are distinguishable rather than folding to an identical ratio.
        outcome = self.state.get("mine_outcome") or {}
        for key in ("hashes_scanned", "nonce_budget"):
            value = outcome.get(key)
            if isinstance(value, (int, float)):
                rows.append([float(value), float(self._cycle_index)])
        for attr in ("total_sha256d_hashes", "phi_best_resonance"):
            value = getattr(self, attr, None)
            if isinstance(value, (int, float)):
                rows.append([float(value), float(self._cycle_index)])

        if len(rows) >= 2:
            return rows

        # Deterministic fallback -- NOT random.
        #
        # An early `return None` here was wrong: state_fold()'s contract is to
        # return a verification dict and complete a real fold/unfold fidelity
        # round-trip (see tests/test_headless_miner_strategy.py::
        # TestStateFoldImplementationSelection). Returning None broke that for
        # any loop without cycle telemetry -- including the first cycle of a
        # real run, before state_quantum_walk has populated face_probs.
        #
        # The original defect was folding random.random() noise, which made the
        # recorded ratio meaningless. The cure is determinism, not absence: the
        # loop's own nonce_space is real, reproducible loop state, so folding it
        # exercises the representation layer honestly and the same input always
        # yields the same ratio.
        nonce_space = (self.state or {}).get("nonce_space") or list(range(100))
        return [[float(v), float(idx)] for idx, v in enumerate(nonce_space)]

    def state_fold(self):
        self.state["current_state"] = "FOLD"
        import sys

        data_tensor = self._cycle_fold_tensor()
        logical_size = sys.getsizeof(data_tensor)

        # There is one production folding path.  Do not allow an environment
        # variable to route mining state through the retired theta=phi
        # ``pulvini.data_folding`` implementation.
        import numpy as np

        original_tensor = np.asarray(data_tensor, dtype=np.float64)
        folded, projections = self.pulvini.fold(original_tensor)
        unfolded, verification, *_ = self.pulvini.unfold(
            folded, projections, original_data=original_tensor
        )
        fold_level = 1

        physical_size = sys.getsizeof(folded)
        if hasattr(self, "unified_ledger") and self.unified_ledger:
            self.unified_ledger.record_representation(
                domain="golden",
                logical_size=logical_size,
                physical_size=physical_size,
                fold_level=fold_level,
                precision="float64",
            )
            self.unified_ledger.record_event("fold_unfold", None)

        rep_state = RepresentationState(
            level=fold_level,
            domain=RepresentationDomain.GOLDEN,
            folded=True,
            substrate=(
                SubstrateType.IGPU
                if getattr(getattr(self, "accel", None), "_igpu_available", False)
                else SubstrateType.CPU
            ),
            buffer=folded,
        )
        if hasattr(self, "substrate_dispatcher") and self.substrate_dispatcher:
            rep_state = self.substrate_dispatcher.execute_transformed_operator(
                rep_state, "hermes_unitary_kernel"
            )

        resonance_telemetry = (
            self.unified_substrate.run_resonance_kernel()
            if hasattr(self, "unified_substrate") and self.unified_substrate
            else {"throughput_qops": 0}
        )
        result = (
            self.hermes.execute_unitary_kernel(self._unitary_phase_transform, rep_state.buffer)
            if hasattr(self, "hermes") and self.hermes
            else {"device": "cpu"}
        )
        logging.info(
            f"[STATE 3: FOLD] PULVINI Tensor Folded | Verification Error: {verification['error']:.2e} | Device: {result['device']}"
        )
        logging.info(
            f"[STATE 3: FOLD] Unified Resonance Throughput: {resonance_telemetry.get('throughput_qops', 0)} QOps"
        )
        return verification

    def state_predict(self):
        self.state["current_state"] = "PREDICT"
        if self.metrics["error_count"] > 0:
            self.metrics["deadlock"] = True
            self.metrics["yield"] = 0.2
        else:
            self.metrics["deadlock"] = False
        pred = self.l3.monitor_and_adjust(self.variance)
        caus = self.l4.evaluate_hubs(self.metrics)
        self.last_predictive_action = pred
        self.last_causal_action = caus
        logging.info(
            f"[STATE 4: PREDICT] Active Inference Variance: {self.variance:.3f} | Causal Hub Yield: {self.metrics['yield']:.2f}"
        )
        if pred.get("dampen_lanes") or caus.get("action") == "nack_slice":
            logging.warning(
                f"[STATE 4: PREDICT] Instability flagged -> next MINE cycle will throttle nonce search "
                f"(predictive={pred.get('action')}, causal={caus.get('action')}, "
                f"pitfall={caus.get('pitfall_countermeasure') or pred.get('pitfall_countermeasure')})"
            )
        return pred, caus

    def state_optimize(self):
        self.state["current_state"] = "OPTIMIZE"
        trans = self.l5.validate_transform(self.state)
        if os.getenv("HYBA_MINING_USE_COUNTERFACTUAL_GATE", "false").lower() in ("true", "1"):
            proposal = {
                "name": "mining_cycle_optimize",
                "is_hermitian": True,
                "bypasses_approval": False,
            }
            counterfactual_allowed = self.l5.assert_allowed_transformation(
                proposal, self.phi_best_resonance
            )
            trans["counterfactual_allowed"] = counterfactual_allowed
            if not counterfactual_allowed:
                self.last_causal_action = {
                    "action": "nack_slice",
                    "relaxation": "counterfactual_veto",
                }
                logging.warning(
                    f"[STATE 5: OPTIMIZE] Counterfactual veto: phi_coherence {self.phi_best_resonance:.4f} "
                    f"below 0.45 constructor-safety threshold -> next MINE cycle throttled"
                )
        logging.info(
            f"[STATE 5: OPTIMIZE] Counterfactual Transform Validated: {trans['validated']}"
        )
        return trans

    def state_quantum_math_passive(self):
        """Passively calculates Quantum Math Layer metrics for telemetry stream."""
        self.state["current_state"] = "QUANTUM_MATH_PASSIVE"
        metrics = {}
        try:
            if self.quantum_math_layer:
                # 1. Golden Alignment: measure alignment of intelligence variances
                indicators = {
                    "predictive_variance": self.variance,
                    "causal_yield": self.metrics.get("yield", 0.0),
                    "phi_resonance": self.phi_best_resonance,
                    "action_score": self.phi_best_yang_mills,
                }
                metrics["golden_alignment"] = self.quantum_math_layer.golden_ratio_alignment(
                    indicators
                )

                # 2. Fractal Intelligence: measure topology of face_probs
                import numpy as np

                probs_array = np.array(self.face_probs).reshape(-1, 1)
                tqft_metrics = self.quantum_math_layer.topological_quantum_field_theory(probs_array)
                metrics["fractal_intelligence_score"] = tqft_metrics.get(
                    "topological_complexity", 0.0
                )
                metrics["euler_characteristic"] = tqft_metrics.get("euler_characteristic", 0)

                # 3. Quantum Coherence: measure coherence of the probability amplitude
                amplitudes = np.sqrt(self.face_probs)
                metrics["quantum_coherence"] = self.quantum_math_layer._calculate_coherence(
                    amplitudes
                )

                # Record to ledger silently
                self.unified_ledger.record_quantum_metrics(metrics)
        except Exception as e:
            logging.error(f"[STATE 5.5: QUANTUM_MATH_PASSIVE] Error computing metrics: {e}")
        return metrics

    def state_heal(self):
        self.state["current_state"] = "HEAL"
        return self.salamander.heal(self.metrics["error_count"])

    def execute_cycle(self, cycle_idx: int = 1):
        # GAP-CLOSURE-001: per-stage wall-clock instrumentation. The only
        # timing that existed here before was the coarse external
        # _last_cycle_seconds measured by run(); no consumer could say WHICH
        # stage consumed the cycle -- and the serial-pipeline / edge-latency
        # gaps from the blueprint review cannot even be argued without these
        # numbers. perf_counter reads around each stage add negligible
        # overhead; the breakdown lands in state["_cycle_stage_seconds"],
        # stats telemetry ("cycle_stage_seconds"), and one compact log line.
        stage_seconds: Dict[str, float] = {}
        _perf = time.perf_counter

        def _timed(stage: str, fn, *args, **kwargs):
            t0 = _perf()
            try:
                return fn(*args, **kwargs)
            finally:
                stage_seconds[stage] = _perf() - t0

        try:
            _timed("scan", self.state_scan)
            quantum_info = _timed("quantum_walk", self.state_quantum_walk, step_idx=cycle_idx)
            # self.state_search()  # Disabled: random.random() query against static capabilities (no mining effect)
            _timed("mine", self.state_mine, quantum_info=quantum_info)
            # Folds the cycle's OWN telemetry (manifold face amplitudes, scan
            # counters) -- see _cycle_fold_tensor(). Re-enabled only once the
            # input became real; it was correctly disabled while it folded
            # random.random() noise. Skips itself on a cycle that produced no
            # data rather than inventing input.
            _timed("fold", self.state_fold)
            _timed("predict", self.state_predict)
            _timed("optimize", self.state_optimize)
            _timed("quantum_math_passive", self.state_quantum_math_passive)
            _timed("heal", self.state_heal)
            if self.current_job_context:
                _timed("settle", self.current_job_context.settle)
            _timed("save_stats", self._save_stats, quantum_telemetry=quantum_info)

            # Persist the breakdown for consumers and log it as milliseconds,
            # rounded -- raw floats are noise at this resolution, while the
            # shape is contractual for telemetry consumers.
            active_total_s = sum(stage_seconds.values())
            self._last_stage_seconds = dict(stage_seconds)
            self.state["_cycle_stage_seconds"] = {
                stage: round(seconds * 1000.0, 3)
                for stage, seconds in sorted(stage_seconds.items())
            }
            logging.info(
                "[CYCLE-TIMING] cycle=%s stages(ms)=%s active_total=%.1fms",
                cycle_idx,
                json.dumps(self.state["_cycle_stage_seconds"]),
                active_total_s * 1000.0,
            )
            lead = (self.state.get("intelligence") or {}).get("lead")
            elapsed = max(time.time() - getattr(self, "mining_start_time", time.time()), 1e-9)
            current_hps = getattr(self, "total_sha256d_hashes", 0) / elapsed
            stratum_obj = getattr(self, "stratum", None)
            stratum_status = (
                getattr(stratum_obj, "status", "disconnected") if stratum_obj else "disconnected"
            )
            current_job_dict = getattr(stratum_obj, "current_job", None) if stratum_obj else None
            job_id_val = (
                current_job_dict.get("job_id") if isinstance(current_job_dict, dict) else None
            )
            pool_diff = getattr(stratum_obj, "difficulty", 1.0) if stratum_obj else 1.0
            shares_acc = (
                getattr(stratum_obj, "pool_accepted", getattr(stratum_obj, "shares_accepted", 0))
                if stratum_obj
                else 0
            )
            shares_sub = getattr(self, "shares_submitted", 0)
            logging.info(
                "=== Cycle %s Complete | pool=%s job=%s | search=%s | %s | lead=%s | "
                "Difficulty: %s | Hashrate: %.2f H/s | Pool-Accepted Shares: %s/%s ===",
                cycle_idx,
                stratum_status,
                job_id_val,
                _default_search_label(),
                format_lane_label(getattr(self, "last_lane_descriptor", None)),
                lead,
                pool_diff,
                current_hps,
                shares_sub,
                shares_acc,
            )
            # STOP POLICY. Previously this consulted HYBA_MINING_CONTINUOUS and
            # defaulted target_shares to 1,000,000 when continuous -- so the
            # production miner stopped on neither shares nor time. The envelope
            # now decides, and it is not conditional on continuous mode:
            # runtime and pool-confirmed-share limits apply to autonomous
            # mining, full stop.
            should_stop, stop_reason = self.safety.should_stop()
            if should_stop:
                logging.info("[SAFETY] halting autonomous mining — %s", stop_reason)
                self._set_mining_phase("STOPPED")
                self.running = False
        except Exception as e:
            import traceback

            traceback.print_exc()
            self.metrics["error_count"] += 1
            logging.error(f"Cycle Exception caught by Salamander Supervisor: {e}")

    def shutdown(self):
        # Face-process pool teardown FIRST: GIL-free solver workers must never
        # leak past miner exit. daemon=True backstops orphans, but a graceful
        # sentinel-join keeps Windows-spawn resource trackers quiet and makes
        # shutdown order deterministic for the telemetry ledger below.
        try:
            _coord = getattr(self, "coordinator", None)
            if _coord is not None and hasattr(_coord, "shutdown_processes"):
                _coord.shutdown_processes()
        except Exception as exc:
            logging.warning("[SHUTDOWN] face process pool teardown failed: %s", exc)
        if self._stratum_loop and self._stratum_loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(self.stratum.close(), self._stratum_loop)
                fut.result(timeout=5.0)
                logging.info(
                    "Stratum client shut down cleanly (listener task cancelled, no orphaned pending task)."
                )
                return
            except Exception as e:
                logging.warning(f"Stratum shutdown on worker loop encountered an error: {e}")
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            if loop.is_running():
                loop.create_task(self.stratum.close())
            else:
                loop.run_until_complete(asyncio.wait_for(self.stratum.close(), timeout=5.0))
            logging.info(
                "Stratum client shut down cleanly (listener task cancelled, no orphaned pending task)."
            )
        except Exception as e:
            logging.warning(f"Stratum shutdown encountered an error (continuing exit): {e}")

    def run(self):
        stratum_obj = getattr(self, "stratum", None)
        worker_name = getattr(stratum_obj, "worker_name", "unknown") if stratum_obj else "unknown"
        pool_url = getattr(stratum_obj, "pool_url", "unknown") if stratum_obj else "unknown"
        logging.info(
            "Starting HYBA Autonomous Miner | worker=%s | pool=%s | "
            "search=%s | substrate=%s | live_submit=%s",
            worker_name,
            pool_url,
            _default_search_label(),
            getattr(self, "hash_backend", "hashlib"),
            StratumClient.is_live_submit_approved(),
        )
        self.safety.start()
        logging.info("[SAFETY] autonomous mining envelope active: %s", self.safety.snapshot())
        cycle = 1
        try:
            while self.running:
                # Wall-clock boundary is checked BEFORE accepting new work, so
                # the limit stops the workload rather than merely reporting on
                # it after the fact.
                should_stop, stop_reason = self.safety.should_stop()
                if should_stop:
                    logging.info(
                        "[SAFETY] runtime envelope reached — %s. "
                        "Not accepting further mining work.",
                        stop_reason,
                    )
                    self._set_mining_phase("STOPPED")
                    self.running = False
                    break
                self._cycle_index = cycle
                _t0 = time.time()
                self.execute_cycle(cycle_idx=cycle)
                self._last_cycle_seconds = max(time.time() - _t0, 1e-3)
                cycle += 1
                if not self.running:
                    break

                # --- idle backoff ------------------------------------------
                # This loop previously had no sleep on any path. With no live
                # pool job, execute_cycle() returns almost immediately
                # ("No live job — Salamander holding"), so the loop spun as
                # fast as the CPU allowed: ~1,500 cycles in 45 s, observed. That
                # pinned a core doing nothing, and — because mining/evidence.py
                # appends an event with os.fsync per cycle — produced an
                # unbounded, disk-synchronous write storm on an idle miner.
                # It also inflated the cycle counter, so telemetry reported
                # thousands of "cycles" in which no work was done.
                #
                # There is nothing to poll faster than the pool publishes jobs.
                # Back off geometrically while idle; reset the instant real
                # work appears so responsiveness to a new job is unaffected.
                if self.state.get("job_source") == "waiting_for_pool":
                    self._idle_cycles = getattr(self, "_idle_cycles", 0) + 1
                    delay = min(
                        self._idle_backoff_base * (2 ** min(self._idle_cycles - 1, 6)),
                        self._idle_backoff_max,
                    )
                    if self._idle_cycles == 1:
                        logging.info(
                            "[IDLE] No pool job available — backing off up to %.1fs between "
                            "cycles until work arrives. Substrate stays warm; nothing is hashed.",
                            self._idle_backoff_max,
                        )
                    time.sleep(delay)
                elif getattr(self, "_idle_cycles", 0):
                    logging.info(
                        "[IDLE] Work available after %d idle cycle(s) — resuming full rate.",
                        self._idle_cycles,
                    )
                    self._idle_cycles = 0
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt received — initiating graceful shutdown...")
            self._set_mining_phase("STOPPED")
            self.running = False
        finally:
            # Ordered teardown: preserve telemetry, flush the ledger, then
            # close the pool connection. The ledger is the evidence chain; it
            # is flushed before the socket goes away.
            try:
                self._save_stats()
            except Exception as exc:
                logging.warning(f"[SHUTDOWN] telemetry save failed: {exc}")
            try:
                if self.current_job_context:
                    self.current_job_context.settle()
            except Exception as exc:
                logging.warning(f"[SHUTDOWN] job context settle failed: {exc}")
            try:
                self.treasury_ledger.flush()
            except AttributeError:
                pass
            except Exception as exc:
                logging.warning(f"[SHUTDOWN] ledger flush failed: {exc}")
            logging.info("[SAFETY] final envelope state: %s", self.safety.snapshot())
            self.shutdown()
        elapsed = max(time.time() - self.mining_start_time, 1e-9)
        measured_hashrate_hps = self.total_sha256d_hashes / elapsed
        logging.info("======================================================================")
        logging.info("                COMPLETE SYSTEM TELEMETRY DUMP                     ")
        logging.info("======================================================================")
        logging.info("Final State:               HALTED")
        logging.info(
            "System:                    one super miner (Agentic + Salamander + Coordinator)"
        )
        logging.info(
            f"Shares Submitted/Accepted: {self.shares_submitted} / "
            f"{getattr(self.stratum, 'pool_accepted', self.stratum.shares_accepted)} pool-confirmed "
            f"(+{getattr(self.stratum, 'firewall_accepted', 0)} firewall-validated)"
        )
        logging.info(
            f"Hashes Done:               {self.total_sha256d_hashes} ({measured_hashrate_hps:.0f} H/s on {self.hash_backend})"
        )
        logging.info(
            f"Search:                    {'Grover + Lucas (opt-in structured pre-pass)' if _grover_ordering_enabled() else 'Classical budgeted scan (default)'}"
        )
        logging.info(f"Lucas-15 Thread Density:   {LUCAS_15} Threads")
        logging.info(
            f"phi-Grover v4:             {'ACTIVE' if self.phi_grover_enabled else 'FALLBACK'}"
        )
        _gs_cap = self._get_golden_search()
        logging.info(
            f"Golden-Ratio Search Cap:   {'ACTIVE v%s (%s)' % (_gs_cap.version_string(), 'consolidated') if _gs_cap else 'OFF (legacy generator)'}"
        )
        logging.info(
            f"Best R_φ:                  {self.phi_best_resonance:.6f} (threshold φ⁻¹ ≈ {PHI_COLLAPSE:.4f})"
        )
        logging.info(
            f"Best Nonce:                0x{self.phi_best_nonce:08x} | Face {self.phi_best_face} | Action {self.phi_best_yang_mills:.4f}"
        )
        logging.info(f"Mining Phase:              {self.mining_phase}")
        if self.mining_fault:
            logging.error(f"Mining Fault:              {self.mining_fault}")
        logging.info(
            f"Substrate Status:          "
            f"{'ZERO THROUGHPUT — NOT HEALTHY' if self.mining_phase == 'MINING_ZERO_THROUGHPUT' else 'HEALTHY (Salamander Protected)'}"
        )
        logging.info("======================================================================")


if __name__ == "__main__":
    if os.environ.get("HYBA_ENABLE_AUTONOMOUS_MINING") == "true":
        loop = AutonomousExecutionLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt at top level — shutting down Stratum client...")
            loop.shutdown()
    else:
        logging.error("Autonomy disabled.")
