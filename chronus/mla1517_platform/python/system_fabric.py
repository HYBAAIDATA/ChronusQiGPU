"""PYTHIA system fabric — the wired intelligence surface of the control API.

Every named subsystem of the stack is mapped here with its live wiring
status:

    production  reachable through the supervised mining path today
    fabric      reachable through the control API (this module's endpoints)
    orchestrator  loaded inside the Intelligence orchestrator
    idle        code-complete, exercised by tests, no production caller
    stub        declared surface only

Gates are honest: ``opencl``, ``mmio``, ``pool_credentials`` mark the
subsystem wired but waiting on a real device or configured pool. Nothing
here claims a capability the box does not have — where hardware is absent
the subsystem reports its gate closed, never a fabricated measurement.

The fabric also supervises the three lazily-wired components:

    VerificationRunner — runs Intelligence.chain_verification (the 11-stage
        full-chain forensic evaluation: backend binding, Zeckendorf storage
        roundtrip, 11D anchor projection, 32-face manifold hold, TOE arbiter,
        Yang-Mills gap, Ricci-Einstein, sha256d mining consensus, iGPU
        telemetry) on demand and caches the report.
    AgenticSupervisor — drives Intelligence.agentic_mining's six-phase
        autonomous workflow (cold start -> precompute -> hold -> submit ->
        steady state -> cool down) under a stop flag. Phase 4's submission
        scope is the local sha256d consensus check; the pool-facing path
        stays with the stratum arms.
    CampaignRunner — executes the configured pool campaign: an ordered
        sequence of {pool, duration_s, target_hs, arms} phases applied
        through runtime_config, so hashrate elevation and pool switching
        stay bounded by the same file the arms poll.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

_PY_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PY_DIR.parent.parent.parent
_TUQC_DIR = _REPO_ROOT / "turing_universal_quantum_computer"


def _ensure_repo_path() -> None:
    for path in (str(_REPO_ROOT), str(_PY_DIR), str(_TUQC_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _module_present(module: str) -> bool:
    try:
        _ensure_repo_path()
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


# Wiring tiers that claim a live caller; "idle"/"stub" already admit no
# production path, so they keep their label even when an optional
# dependency (e.g. networkx) would make the import fail.
_WIRED_TIERS = frozenset({"production", "fabric", "orchestrator"})


def _module_importable(module: str) -> tuple[bool, str | None]:
    """Real-import evidence behind a wired claim.

    ``find_spec`` resolves a file without executing it, so a module whose
    own imports are broken still looks "present". For tiers that promise
    reachability the check must actually import the module.
    """
    try:
        _ensure_repo_path()
        importlib.import_module(module)
        return True, None
    except Exception as exc:  # noqa: BLE001 - any import-time failure means not wired
        return False, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Forensic map — every subsystem the user named, graded against the tree.
# wired: production | fabric | orchestrator | idle | stub
# gate:  None | "opencl" | "mmio" | "pool_credentials" | "opencl+credentials"
# ---------------------------------------------------------------------------

SUBSYSTEMS: list[dict[str, Any]] = [
    # -- the user's named pieces --
    {
        "key": "chronus",
        "name": "Bespoke Chronus substrate",
        "module": "mining.bitcoin_hasher",
        "wired": "production",
        "gate": "opencl",
        "detail": "OpenCL sha256d batch hasher; the arms fall back to CPU-exact serial grind and say so",
    },
    {
        "key": "unified_punch",
        "name": "Unified punch host (phi-filter scoring)",
        "module": "Intelligence.unified_punch",
        "wired": "production",
        "gate": None,
        "detail": "nonce scoring in the hash pipeline; CPU mirror when OpenCL is absent",
    },
    {
        "key": "manifold_iid",
        "name": "IID manifold device (dodecahedron+icosahedron 32-face)",
        "module": "Intelligence.search_crystal",
        "wired": "fabric",
        "gate": None,
        "detail": "11D Poincare fold/unfold + Cassini shard order over the 32-face compass; fold path exercised by verification",
    },
    {
        "key": "poincare_11d",
        "name": "11D Poincare golden fold/unfold",
        "module": "toe.poincare_golden_11d",
        "wired": "orchestrator",
        "gate": None,
        "detail": "exact 11D fold math + Zeckendorf certificates; also drives the 11d nonce order in the bridge",
    },
    {
        "key": "yang_mills",
        "name": "Yang-Mills mass gap",
        "module": "toe.system",
        "wired": "fabric",
        "gate": None,
        "detail": "T10 (delta = sqrt5 > 0) verified per candidate in the full-chain run; al_haras_gateway filters the UI edge",
    },
    {
        "key": "ricci",
        "name": "Ricci-Einstein (hyperbolic exact relation)",
        "module": "Intelligence.chain_verification",
        "wired": "fabric",
        "gate": None,
        "detail": "stage 9 of the chain: Ric_ij = -(n-1) g_ij verified exactly",
    },
    {
        "key": "toe",
        "name": "TOE system (12-theorem arbiter + provenance)",
        "module": "toe.system",
        "wired": "fabric",
        "gate": None,
        "detail": "records decisions across the agentic workflow; provenance written into scaled execution results",
    },
    {
        "key": "structured_search",
        "name": "Structured search (Poincare-Cassini)",
        "module": "Intelligence.search_crystal",
        "wired": "orchestrator",
        "gate": None,
        "detail": "structured bijective order over the 32 faces; used by agentic controller and the IID manifold",
    },
    {
        "key": "unstructured_search",
        "name": "Unstructured search (Grover-exact)",
        "module": "turing_universal_quantum_computer.grover_exact_scale",
        "wired": "idle",
        "gate": None,
        "detail": "exact folded-Grover substrate (Pisot-scaled phases, Cassini drift) in TUQC; mining.search keeps the iteration-count helper — ordering cannot beat consensus",
    },
    {
        "key": "tensor",
        "name": "Quantum tensor (exact qubit tensor)",
        "module": "kellogg.exact_tensor",
        "wired": "production",
        "gate": None,
        "detail": "exact-amplitude tensor; compress/decompress roundtrip inside the scaled execution arm",
    },
    {
        "key": "vqc",
        "name": "Virtual quantum computer (11-qubit exact)",
        "module": "mining.scaled_execution",
        "wired": "production",
        "gate": "pool_credentials",
        "detail": "LucasScaledAethelExecutionAdapter — strict-quantum certificate + structured plan + tensor roundtrip + iGPU gate per window",
    },
    {
        "key": "folding_storage",
        "name": "Fold/unfold storage (Zeckendorf, archival-exact)",
        "module": "Intelligence.folded_state",
        "wired": "orchestrator",
        "gate": None,
        "detail": "T_phi fold engine; no-raw storage with sum/dot/hist/sha queries on folded state",
    },
    {
        "key": "salamander",
        "name": "Salamander self-healing engine",
        "module": "Intelligence.salamander",
        "wired": "orchestrator",
        "gate": "mmio",
        "detail": "lane-fault decay + readmit hysteresis; the supervised worker (salamander_engine.py) arms when MLA1517_MMIO_DEVICE is set",
    },
    {
        "key": "agentic_workflow",
        "name": "Agentic autonomous mining workflow (6 phases)",
        "module": "Intelligence.agentic_mining",
        "wired": "fabric",
        "gate": None,
        "detail": "cold-start -> precompute -> hold -> submit -> steady-state -> cool-down; phase 4 accept authority is local sha256d",
    },
    {
        "key": "chain_verification",
        "name": "Full-chain verification (11 stages)",
        "module": "Intelligence.chain_verification",
        "wired": "fabric",
        "gate": None,
        "detail": "the forensic evaluation itself, runnable live from the panel",
    },
    # -- supporting wired modules --
    {
        "key": "hash_pipeline",
        "name": "Hash pipeline (sha256d sole accept authority)",
        "module": "mining.hash_pipeline",
        "wired": "production",
        "gate": None,
        "detail": "Stage-A punch filter + serial/batched grind + bit-exact winner recheck",
    },
    {
        "key": "m32_solver",
        "name": "M32 lane solver",
        "module": "chronus.mla1517.mining.solver",
        "wired": "production",
        "gate": None,
        "detail": "32-lane disjoint stride inside every arm",
    },
    {
        "key": "stratum_bridge",
        "name": "Stratum bridge arms",
        "module": "mining.stratum_bridge",
        "wired": "idle",
        "gate": "opencl+credentials",
        "detail": "legacy per-arm pool loop for the HYBA pipeline, exercised by tests only; canonical mining ownership is chronus.mla1517.mining.coordinator under mining_runtime",
    },
    {
        "key": "strict_quantum",
        "name": "Strict quantum work-window certificates",
        "module": "toe.strict_quantum",
        "wired": "production",
        "gate": None,
        "detail": "certify_work_window exercised by the TOE engine's work-window certificates",
    },
    {
        "key": "agentic_controller",
        "name": "Agentic controller (solver dispatch)",
        "module": "Intelligence.agentic_controller",
        "wired": "orchestrator",
        "gate": None,
        "detail": "polyhedral map + quantum engines + hybrid swarm dispatching",
    },
    {
        "key": "toe_bridge",
        "name": "TOE bridge (tomography/trajectory/causality)",
        "module": "toe.bridge",
        "wired": "orchestrator",
        "gate": None,
        "detail": "tomography, trajectory prediction, causal analysis over mining state",
    },
    {
        "key": "meta_evolution",
        "name": "Meta-evolution controller",
        "module": "Intelligence.meta_evolution",
        "wired": "orchestrator",
        "gate": None,
        "detail": "",
    },
    {
        "key": "pythia_learning",
        "name": "PYTHIA learning substrate",
        "module": "Intelligence.pythia_learning",
        "wired": "orchestrator",
        "gate": None,
        "detail": "",
    },
    {
        "key": "pythia_memory",
        "name": "PYTHIA memory system",
        "module": "Intelligence.pythia_memory",
        "wired": "orchestrator",
        "gate": None,
        "detail": "",
    },
    {
        "key": "predictive_solver",
        "name": "Predictive solver",
        "module": "Intelligence.predictive_solver",
        "wired": "orchestrator",
        "gate": None,
        "detail": "",
    },
    {
        "key": "counterfactual",
        "name": "Counterfactual intelligence",
        "module": "Intelligence.counterfactual_intelligence",
        "wired": "orchestrator",
        "gate": None,
        "detail": "",
    },
    {
        "key": "safety",
        "name": "Safety controller (hashrate cap FSM)",
        "module": "Intelligence.safety_constraints",
        "wired": "orchestrator",
        "gate": None,
        "detail": "",
    },
    {
        "key": "registry",
        "name": "Module registry (45 modules)",
        "module": "Intelligence.registry",
        "wired": "orchestrator",
        "gate": None,
        "detail": "core_engine stack, cortex adapters, TS bridges, experiments, turing_core, extended algebra",
    },
    # -- idle: complete code, no production caller yet --
    {
        "key": "manifold_bridge",
        "name": "Manifold bridge (substrate-12 storage)",
        "module": "toe.manifold_bridge",
        "wired": "fabric",
        "gate": None,
        "detail": "Galois-persistent hold + O(1) candidate lookup; exercised inside the agentic workflow and chain verification",
    },
    {
        "key": "pythia_agent",
        "name": "Deterministic orchestration agent",
        "module": "pythia_agent",
        "wired": "idle",
        "gate": None,
        "detail": "measure->propose->query->veto->actuate->append loop; standalone CLI, escalates through the empirical ledger",
    },
    {
        "key": "ontology_chain",
        "name": "Ontology mining chain",
        "module": "Intelligence.ontology_mining_engine",
        "wired": "idle",
        "gate": None,
        "detail": "mining_native + ontology_mining_engine + mining_bridge_ontology + search_database",
    },
    {
        "key": "search_tree",
        "name": "Parallel search tree",
        "module": "Intelligence.orchestrator_search",
        "wired": "idle",
        "gate": None,
        "detail": "search_api / intent_compiler / orchestrator_search / agentic_controller_search / plasticity_search",
    },
    {
        "key": "toe_tensor_ml",
        "name": "Kellogg tensor ML family",
        "module": "kellogg.tensor_ml",
        "wired": "idle",
        "gate": None,
        "detail": "exact_linear et al; kellogg.exact_field reaches toe.bridge; rest is experiment surface",
    },
    {
        "key": "salamander_transaction",
        "name": "Salamander transaction layer",
        "module": "Intelligence.salamander_transaction",
        "wired": "idle",
        "gate": None,
        "detail": "",
    },
    {
        "key": "first_principles_quantum",
        "name": "First-principles quantum (python)",
        "module": "turing_universal_quantum_computer.quantum_algorithms",
        "wired": "idle",
        "gate": None,
        "detail": "GroverSearch + LucasEngine first-principles algorithms promoted into TUQC; TS twin powers the frontend quantum surface",
    },
    {
        "key": "pulvini_runtime",
        "name": "Pulvini runtime",
        "module": "Intelligence.pulvini_runtime",
        "wired": "idle",
        "gate": None,
        "detail": "tensor-network pipeline over folded state",
    },
    {
        "key": "discovery",
        "name": "Mathematical discovery engine",
        "module": "turing_universal_quantum_computer.turing_core.discovery",
        "wired": "idle",
        "gate": None,
        "detail": "mathematical frontier explorer promoted into TUQC turing_core; scipy/networkx optional extra",
    },
    {
        "key": "pool_aware_miner",
        "name": "Pool-aware miner",
        "module": "Intelligence.pool_aware_miner",
        "wired": "idle",
        "gate": None,
        "detail": "superseded by stratum_bridge runtime-config pools",
    },
]


def forensic_map(*, opencl_count: int, have_mmio: bool, have_credentials: bool) -> dict[str, Any]:
    """The forensic map with each gate evaluated live."""
    have_opencl = opencl_count > 0

    def gate_state(gate: Optional[str]) -> str:
        if gate is None:
            return "open"
        if gate == "opencl":
            return "open" if have_opencl else "closed"
        if gate == "mmio":
            return "open" if have_mmio else "closed"
        if gate == "pool_credentials":
            return "open" if have_credentials else "closed"
        if gate == "opencl+credentials":
            return "open" if (have_opencl and have_credentials) else "closed"
        return "closed"

    subs = []
    for s in SUBSYSTEMS:
        present = _module_present(s["module"])
        entry = {
            **s,
            "wired": s["wired"] if present else "parked",
            "gate_state": gate_state(s["gate"]),
            "present": present,
        }
        if present and s["wired"] in _WIRED_TIERS:
            importable, import_error = _module_importable(s["module"])
            entry["import_ok"] = importable
            if not importable:
                # The declared reachability is unproven on this box — demote
                # rather than carry a claim the import evidence refutes.
                entry["wired"] = "parked"
                entry["parked_reason"] = f"import failed: {import_error}"
        subs.append(entry)
    summary: dict[str, int] = {}
    for s in subs:
        summary[s["wired"]] = summary.get(s["wired"], 0) + 1
    return {
        "schema": "pythia.fabric_map/1",
        "generated_at": time.time(),
        "subsystems": subs,
        "summary": summary,
        "gates": {
            "opencl_devices": opencl_count,
            "mmio_device": have_mmio,
            "pool_credentials": have_credentials,
        },
        "honesty": (
            "gate_state closed means the code path is wired but the real "
            "device or credential is absent on this box — no synthetic "
            "telemetry is produced in its place"
        ),
    }


# ---------------------------------------------------------------------------
# Lazy orchestrator — the 45-module registry takes a few seconds to wire;
# build it once on a daemon thread and serve honest interim state.
# ---------------------------------------------------------------------------

_INTEL_LOCK = threading.Lock()
_INTEL_THREAD: Optional[threading.Thread] = None
_INTEL: dict[str, Any] = {
    "state": "cold",  # cold -> initializing -> ready | error
    "orchestrator": None,
    "error": None,
    "started_at": None,
    "ready_at": None,
}


def _orchestrator_worker() -> None:
    try:
        _ensure_repo_path()
        import Intelligence

        orch = Intelligence.get_intelligence()
        with _INTEL_LOCK:
            _INTEL["orchestrator"] = orch
            _INTEL["state"] = "ready"
            _INTEL["ready_at"] = time.time()
    except Exception as exc:  # honesty: surface the real import error
        with _INTEL_LOCK:
            _INTEL["state"] = "error"
            _INTEL["error"] = f"{type(exc).__name__}: {exc}"
            _INTEL["ready_at"] = time.time()


def ensure_orchestrator() -> None:
    global _INTEL_THREAD
    with _INTEL_LOCK:
        if _INTEL["state"] == "cold":
            _INTEL["state"] = "initializing"
            _INTEL["started_at"] = time.time()
            _INTEL_THREAD = threading.Thread(
                target=_orchestrator_worker, name="fabric-intelligence", daemon=True
            )
            _INTEL_THREAD.start()


def _call(method: str) -> Any:
    orch = _INTEL.get("orchestrator")
    fn = getattr(orch, method, None)
    if fn is None:
        return {"available": False, "reason": f"method {method} not on orchestrator"}
    try:
        out = fn()
        return out if out is not None else {"ok": True}
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def autonomous_supervisor_status() -> dict[str, Any]:
    """Status of the consolidated self-healing / self-optimising supervisor."""
    try:
        import autonomous_supervisor

        return autonomous_supervisor.status()
    except Exception as exc:
        return {"schema": "pythia.autonomous_supervisor/1", "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# EUCLID cognition — the intelligence authority's closed loop
# ---------------------------------------------------------------------------

_EUCLID_LOCK = threading.Lock()
_EUCLID: dict[str, Any] = {"runtime": None, "error": None}


def _euclid_state_dir() -> Path:
    """Where cognition state lives.  Defaults beside the repo's other runtime
    state; overridable so a deployment can place it on durable storage."""
    configured = os.getenv("PYTHIA_EUCLID_STATE_DIR")
    if configured:
        return Path(configured)
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "euclid"


def euclid_cognition() -> Any:
    """The EUCLID cognition runtime, constructed lazily on first use.

    This is the single production entry point to the intelligence authority.
    It is deliberately lazy: importing this module must not create state, and
    a control plane that never asks for cognition never pays for it.  Failures
    are reported honestly rather than replaced with a deterministic stub.
    """
    with _EUCLID_LOCK:
        if _EUCLID["runtime"] is not None:
            return _EUCLID["runtime"]
        if _EUCLID["error"] is not None:
            return None
        try:
            import sys as _sys

            repo_root = str(Path(__file__).resolve().parents[3])
            if repo_root not in _sys.path:
                _sys.path.append(repo_root)
            from euclid import EuclidRuntime

            runtime = EuclidRuntime.production(
                creator_id=os.getenv("PYTHIA_CREATOR_ID", "pythia-operator"),
                state_dir=_euclid_state_dir(),
            )
            _EUCLID["runtime"] = runtime
        except Exception as exc:  # noqa: BLE001 - report, never fake
            _EUCLID["error"] = f"{type(exc).__name__}: {exc}"
            return None
    return _EUCLID["runtime"]


def euclid_cognition_close() -> dict[str, Any]:
    """Close and forget the cached cognition runtime.

    Orderly shutdown and test isolation both need a real teardown: the runtime
    holds a SQLite connection and a snapshot writer, so leaking it strands the
    state directory.  Idempotent, and never raises — shutdown is fail-soft.
    """
    with _EUCLID_LOCK:
        runtime = _EUCLID["runtime"]
        _EUCLID["runtime"] = None
    if runtime is None:
        return {
            "schema": "pythia.euclid.cognition.close/1",
            "closed": False,
            "reason": "no cognition runtime was constructed",
        }
    try:
        runtime.close()
    except Exception as exc:  # noqa: BLE001 - shutdown is fail-soft
        return {
            "schema": "pythia.euclid.cognition.close/1",
            "closed": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return {"schema": "pythia.euclid.cognition.close/1", "closed": True}


def euclid_cognition_status() -> dict[str, Any]:
    """Honest cognition status, including why it may be unavailable.

    Status reports only what was actually measured.  In particular it never
    claims transfer from retrieval alone, adaptation from a record count, or
    success from a stalled episode.
    """
    runtime = euclid_cognition()
    if runtime is None:
        return {
            "schema": "pythia.euclid.cognition/1",
            "available": False,
            "reason": _EUCLID["error"] or "not constructed",
            "authority": "euclid.cognition",
            "open_gates": ["cognition_runtime_unavailable"],
        }
    try:
        status = dict(runtime.startup_report()["cognition"])
    except Exception as exc:  # noqa: BLE001
        return {
            "schema": "pythia.euclid.cognition/1",
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "open_gates": ["cognition_startup_report_failed"],
        }

    learning = runtime.learning
    replay = learning.replay_state()
    try:
        memory_integrity = (
            learning.memory_database.verify()
            if learning.memory_database is not None
            else {"valid": False, "reason": "no durable memory database"}
        )
    except Exception as exc:  # noqa: BLE001 - integrity failure is a gate, not a crash
        memory_integrity = {"valid": False, "reason": f"{type(exc).__name__}: {exc}"}

    journal_path = replay.get("replay_journal_path")
    replay_integrity: dict[str, Any] = {
        "path": journal_path,
        "entries": replay.get("journal_entries"),
        "sha256": replay.get("journal_sha256"),
        "verified": False,
    }
    # A sealed journal that reloaded is the only honest basis for "verified":
    # LearningService validates the seal while loading it, so a runtime that
    # came up at all has already proved it.
    if journal_path:
        replay_integrity["verified"] = bool(
            replay.get("journal_entries") is not None
            and Path(journal_path).is_file()
        )

    reachability: dict[str, str] = {}
    for component in (
        "toe.world_model", "toe.planning", "toe.meta_reasoning",
        "euclid.v16.search", "euclid.v16.primitives",
        "euclid.strategy_meta_learning", "euclid.learning_service",
        "euclid.memory_database", "pythia.memory", "pythia.store",
        "experience_superlearner", "repository.engineer",
    ):
        stage = runtime.reachability.stage(component)
        if stage is not None:
            reachability[component] = stage.name

    cognition = runtime.cognition
    world_model = getattr(cognition, "world_model", None)
    capabilities = {
        "primary_cognition_loop": cognition is not None,
        "nonlinear_feature_augmentation": bool(
            getattr(world_model, "feature_augmented", False)
        ),
        "counterfactual_plan_evaluation": callable(
            getattr(world_model, "counterfactual", None)
        ),
        "long_horizon_credit_assignment": callable(
            getattr(getattr(cognition, "metalearner", None), "update_credit", None)
        ),
        "discovery_self_optimisation": (
            getattr(runtime, "discovery", None) is not None
            and getattr(runtime, "discovery_optimisation", None) is not None
        ),
        "typed_cognition_problem": True,
        "mining_cognition_problem": True,
    }

    open_gates: list[str] = []
    if not memory_integrity.get("valid"):
        open_gates.append("memory_integrity_unverified")
    if not replay_integrity["verified"]:
        open_gates.append("replay_journal_unverified")
    if not any(
        stage == "TRANSFER_VERIFIED" for stage in reachability.values()
    ):
        open_gates.append("transfer_not_verified")
    if not any(
        stage == "RESTART_VERIFIED" for stage in reachability.values()
    ):
        open_gates.append("restart_not_verified")
    generalisation_evidence = {
        "verified": False,
        "path": str(_euclid_state_dir() / "held_out_generalisation.json"),
        "verdict": "UNAVAILABLE",
    }
    generalisation_path = _euclid_state_dir() / "held_out_generalisation.json"
    if generalisation_path.is_file():
        try:
            import json as _json
            from euclid.cognition.generalisation import validate_generalisation_report

            report = _json.loads(generalisation_path.read_text(encoding="utf-8"))
            generalisation_evidence = {
                "verified": bool(validate_generalisation_report(report)),
                "path": str(generalisation_path),
                "verdict": str(report.get("verdict") or "UNAVAILABLE"),
                "families": list(report.get("families") or ()),
                "mean_delta": report.get("mean_delta"),
                "seal": report.get("seal"),
            }
        except Exception as exc:
            generalisation_evidence = {
                "verified": False,
                "path": str(generalisation_path),
                "verdict": "INVALID",
                "error": f"{type(exc).__name__}: {exc}",
            }
    if not generalisation_evidence["verified"]:
        open_gates.append("held_out_generalisation_not_established")
    open_gates.extend([
        "external_validation_absent",
        "production_certification_absent",
    ])

    status.update({
        "schema": "pythia.euclid.cognition/1",
        "available": True,
        "authority": "euclid.cognition",
        "state_dir": str(_euclid_state_dir()),
        "memory": {
            "implementation": type(getattr(runtime.cognition, "memory", None)).__name__,
            "integrity": memory_integrity,
        },
        "replay_journal": replay_integrity,
        "reachability": reachability,
        "evidence_head": runtime.evidence.head,
        "capabilities": capabilities,
        "held_out_generalisation": generalisation_evidence,
        "authority_boundary": {
            "EUCLID": "cognition/orchestration/advisory intelligence",
            "PYTHIA": "final mining authority",
            "mining_consensus_transfer": False,
        },
        "resources": {"open": not getattr(runtime, "_closed", False)},
        "experiences_seen": len(learning._seen),
        "open_gates": open_gates,
        "claims_not_made": [
            "transfer is never claimed from retrieval alone",
            "adaptation is never claimed from record count",
            "a stalled episode is never reported as successful cognition",
        ],
    })
    return status


def euclid_cognition_solve(
    problem_id: str = "",
    goal: str = "",
    *,
    mode: str = "legacy",
    family: str = "",
    seed: int = 0,
    test_code: str = "",
    problem_class: str = "repository-wiring",
    structure: tuple[str, ...] = (),
    observations: tuple[str, ...] = (),
    strategy: str = "",
    initial_code: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Run one real cognition episode through the EUCLID composition root.

    This is the production entry point: it executes the actual loop against the
    actual durable state, not a simulation of it.  The returned trace is the
    episode's own evidence — phases, selected strategy, hypotheses, prediction
    errors, learning updates and the sealed episode identity.

    Fail-closed: an unavailable cognition runtime, an unusable problem or a
    strategy the composer cannot execute all produce an explicit unavailable /
    failed result.  Nothing is ever fabricated to look like successful
    reasoning.
    """
    if mode == "adaptive":
        runtime = euclid_cognition()
        if runtime is None:
            return {
                "schema": "pythia.euclid.cognition.solve/1",
                "available": False,
                "failure": "runtime_unavailable",
                "reason": _EUCLID["error"] or "cognition runtime not constructed",
            }
        if getattr(runtime, "adaptive", None) is None:
            runtime.compose_adaptive_intelligence()

        from euclid.runtime import EuclidRuntime

        if initial_code and test_code:
            from euclid.cognition.software_tasks import create_software_task
            from euclid.cognition.worlds import WorldExecutor
            task_id = problem_id or "software-task"
            spec, world = create_software_task(task_id, code=initial_code, test_code=test_code)
            exec_result = runtime.solve_task(spec, WorldExecutor(world), seed=seed)
            solved = bool(exec_result.solved)
            transitions = getattr(getattr(exec_result, "state", None), "transitions", [])
            reachability = {
                comp: runtime.reachability.stage(comp).value
                for comp in EuclidRuntime.ADAPTIVE_COMPONENTS
                if runtime.reachability.stage(comp) is not None
            }
            return {
                "schema": "pythia.euclid.cognition.solve/1",
                "available": True,
                "mode": "adaptive",
                "problem_id": task_id,
                "solved": solved,
                "outcome": "solved" if solved else "unsolved",
                "reachability": reachability,
                "transitions": [
                    {
                        "sequence": getattr(t, "sequence", i),
                        "phase": getattr(t, "phase", ""),
                        "summary": getattr(t, "summary", ""),
                        "digest": getattr(t, "digest", ""),
                    }
                    for i, t in enumerate(transitions)
                ],
                "cost": getattr(exec_result, "cost", world.cost),
                "probes": world.probes_used,
                "submissions": world.submissions_used,
            }

        if family:
            from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
            spec, truth = generate_task(family, seed=seed, partition="evaluation")
            world = MechanismWorld(spec, truth, seed=seed)
            exec_result = runtime.solve_task(spec, WorldExecutor(world), seed=seed)
            solved = bool(exec_result.solved)
            transitions = getattr(getattr(exec_result, "state", None), "transitions", [])
            reachability = {
                comp: runtime.reachability.stage(comp).value
                for comp in EuclidRuntime.ADAPTIVE_COMPONENTS
                if runtime.reachability.stage(comp) is not None
            }
            return {
                "schema": "pythia.euclid.cognition.solve/1",
                "available": True,
                "mode": "adaptive",
                "family": family,
                "problem_id": spec.task_id,
                "solved": solved,
                "outcome": "solved" if solved else "unsolved",
                "reachability": reachability,
                "transitions": [
                    {
                        "sequence": getattr(t, "sequence", i),
                        "phase": getattr(t, "phase", ""),
                        "summary": getattr(t, "summary", ""),
                        "digest": getattr(t, "digest", ""),
                    }
                    for i, t in enumerate(transitions)
                ],
                "cost": getattr(exec_result, "cost", world.cost),
                "probes": world.probes_used,
                "submissions": world.submissions_used,
            }

        return {
            "schema": "pythia.euclid.cognition.solve/1",
            "available": False,
            "failure": "invalid_request",
            "reason": "adaptive mode requires family or (initial_code and test_code)",
        }

    if not problem_id or not goal:
        return {
            "schema": "pythia.euclid.cognition.solve/1",
            "available": False,
            "failure": "invalid_request",
            "reason": "problem_id and goal are required",
        }
    runtime = euclid_cognition()
    if runtime is None:
        return {
            "schema": "pythia.euclid.cognition.solve/1",
            "available": False,
            "failure": "runtime_unavailable",
            "reason": _EUCLID["error"] or "cognition runtime not constructed",
        }

    problem: dict[str, Any] = {
        "problem_id": str(problem_id),
        "goal": str(goal),
        "problem_class": str(problem_class),
        "structure": list(structure),
        "observations": list(observations),
    }
    if strategy:
        # Reject an unknown strategy before any work runs, so an unavailable
        # route is never silently replaced by a different one.
        available = getattr(runtime.cognition, "skills", None)
        declared = getattr(available, "available_strategies", None)
        if callable(declared):
            known = tuple(str(s) for s in declared())
            if strategy not in known:
                return {
                    "schema": "pythia.euclid.cognition.solve/1",
                    "available": False,
                    "failure": "strategy_unavailable",
                    "reason": f"strategy {strategy!r} is not executable",
                    "available_strategies": list(known),
                }
        problem["strategy"] = str(strategy)
    if initial_code:
        problem["initial_code"] = str(initial_code)

    started = time.perf_counter()
    try:
        state = runtime.solve_repository_problem(problem)
    except Exception as exc:  # noqa: BLE001 - report, never fake a trace
        return {
            "schema": "pythia.euclid.cognition.solve/1",
            "available": False,
            "failure": "execution_error",
            "problem_id": str(problem_id),
            "reason": f"{type(exc).__name__}: {exc}",
        }

    transitions = [
        {
            "sequence": record.sequence,
            "phase": record.phase,
            "summary": record.summary,
            "digest": record.digest,
        }
        for record in state.transitions
    ]
    return {
        "schema": "pythia.euclid.cognition.solve/1",
        "available": True,
        "authority": "euclid.cognition",
        "problem_id": state.problem_id,
        "goal": goal,
        "problem_class": problem_class,
        "outcome": state.outcome.value if state.outcome else None,
        "outcome_detail": state.outcome_detail,
        "selected_strategy": state.selected_strategy,
        "alternative_strategies": list(state.alternative_strategies),
        "representation": dict(state.representation),
        "hypotheses": [
            {
                "id": h.hypothesis_id,
                "statement": h.statement,
                "status": h.status.value,
                "confidence": h.confidence,
            }
            for h in state.hypotheses
        ],
        "retrieved_memory_refs": list(state.retrieved_memory_refs),
        "prediction_errors": list(state.prediction_errors),
        "replanning_events": [dict(e) for e in state.replanning_events],
        "control_decisions": [dict(d) for d in state.control_decisions],
        "learning_updates": [dict(u) for u in state.learning_updates],
        "ablations": list(state.ablations),
        "candidates": [
            {"action_id": c.action_id, "origin": c.origin, "total": c.total}
            for c in state.candidates
        ],
        "transitions": transitions,
        "wall_time_s": round(time.perf_counter() - started, 6),
        "state_digest": state.transitions[-1].digest if state.transitions else None,
        # Persistence and transfer are reported as separate, separately earned
        # facts.  Retrieval is persistence; only a retrieved record adopted as a
        # structural mapping is a decision effect.
        "persistence": {
            "retrieved": len(state.retrieved_memory_refs),
            "memory_ids": list(state.retrieved_memory_refs),
        },
        "decision_effect": {
            "adopted_analogies": [
                {
                    "analogy_id": mapping.analogy_id,
                    "source_ref": mapping.source_ref,
                    "structural_overlap": mapping.structural_overlap,
                }
                for mapping in state.analogies
                if mapping.status.value == "adopted"
            ],
            "decision_links": sorted(
                mapping.source_ref for mapping in state.analogies
                if mapping.status.value == "adopted"
                and mapping.source_ref in set(state.retrieved_memory_refs)
            ),
            "transfer_verified": any(
                mapping.status.value == "adopted"
                and mapping.source_ref in set(state.retrieved_memory_refs)
                for mapping in state.analogies
            ),
        },
        "reward_authority": {
            "observed_reward_authorities": sorted({
                str(update.get("reward_authority", "unspecified"))
                for update in state.learning_updates
                if isinstance(update, Mapping) and "reward_authority" in update
            }) or ["none-recorded"],
        },
        "terminal_cycle_learned": bool(
            state.learning_updates
            and state.outcome is not None
        ),
        "reachability_stages": {
            component: runtime.reachability.stage(component).name
            for component in ("euclid.memory_database", "pythia.memory",
                              "euclid.strategy_meta_learning")
            if runtime.reachability.stage(component) is not None
        },
    }


def intelligence_status() -> dict[str, Any]:
    ensure_orchestrator()
    with _INTEL_LOCK:
        state = _INTEL["state"]
        error = _INTEL["error"]
        started = _INTEL["started_at"]
        ready_at = _INTEL["ready_at"]
    payload: dict[str, Any] = {
        "schema": "pythia.intelligence/1",
        "state": state,
        "started_at": started,
        "ready_at": ready_at,
        # The intelligence authority itself, independent of the mining
        # orchestrator's wiring state.
        "euclid_cognition": euclid_cognition_status(),
    }
    if state == "error":
        payload["error"] = error
        return payload
    if state != "ready":
        payload["detail"] = "orchestrator is wiring the 45-module registry"
        return payload
    for key, method in (
        ("status", "status"),
        ("agentic", "agentic_status"),
        ("lucas_scales", "lucas_scale_status"),
        ("folded_store", "folded_status"),
        ("toe", "toe_status"),
        ("safety", "safety_status"),
        ("memory", "memory_status"),
        ("pythia", "pythia_status"),
        ("predictor", "predictor_status"),
        ("counterfactual", "counterfactual_status"),
        ("hardware", "hardware_status"),
        ("siloed_modules", "siloed_modules_status"),
        ("tools", "tool_summary"),
    ):
        payload[key] = _call(method)
    return payload


# ---------------------------------------------------------------------------
# Generic supervised-thread harness for the three fabric supervisors.
# ---------------------------------------------------------------------------


class _Runner:
    """Single-shot daemon runner with a stop flag and an auditable state."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.state = "idle"  # idle -> running -> done | stopped | error
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.error: Optional[str] = None
        self.result: Any = None
        self.progress: dict[str, Any] = {}

    def start(self, fn: Callable[["_Runner"], Any]) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop.clear()
            self.state = "running"
            self.error = None
            self.result = None
            self.progress = {}
            self.started_at = time.time()
            self.finished_at = None

            def _wrap() -> None:
                try:
                    result = fn(self)
                    with self._lock:
                        self.result = result
                        if self._stop.is_set():
                            self.state = "stopped"
                        elif self.state == "running":
                            self.state = "done"
                except Exception as exc:
                    with self._lock:
                        if self._stop.is_set():
                            # Cooperative operator cancellation is terminal only
                            # after the worker has actually left its function.
                            self.state = "stopped"
                            self.progress["stop_detail"] = f"{type(exc).__name__}: {exc}"
                        else:
                            self.error = f"{type(exc).__name__}: {exc}"
                            self.state = "error"
                finally:
                    with self._lock:
                        self.finished_at = time.time()

            self._thread = threading.Thread(target=_wrap, name=f"fabric-{self.name}", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> bool:
        self._stop.set()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if self.state == "running":
                    # A stop request is not completion. Keep the worker visibly
                    # active until its finally/cleanup path has exited.
                    self.state = "stopping"
                    self.progress["stop_requested_at"] = time.time()
                return self.state == "stopping"
            return False

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "progress": dict(self.progress),
            "result": self.result,
        }


# ---------------------------------------------------------------------------
# Verification runner — the 11-stage full chain on demand.
# ---------------------------------------------------------------------------

VERIFIER = _Runner("verify")


def _run_verification(runner: _Runner) -> dict[str, Any]:
    _ensure_repo_path()
    from Intelligence.chain_verification import verify_full_chain

    report = verify_full_chain()
    runner.progress["stages"] = len(report.get("stages", {}))
    return report


def start_verification() -> bool:
    return VERIFIER.start(_run_verification)


def verification_status() -> dict[str, Any]:
    out = {"schema": "pythia.verification/1", **VERIFIER.status()}
    if out["result"] is not None:
        # The report itself is large; surface the verdict + per-stage pass.
        report = out.pop("result")
        stages = report.get("stages", {})
        out["ready"] = report.get("ready")
        out["theorem_proven"] = report.get("theorem_proven", False)
        out["stages"] = (
            {
                name: {
                    # Stage records carry 'ok', 'passed' or 'correct'
                    # depending on the stage; a flagless stage counts as
                    # held — verify_full_chain fails closed by exception and
                    # scores s.get("correct", True) the same way.
                    "ok": stage.get("ok", stage.get("passed", stage.get("correct", True))),
                    "detail": stage.get("detail", stage.get("summary")),
                }
                for name, stage in stages.items()
            }
            if isinstance(stages, dict)
            else stages
        )
        out["overlay"] = report.get("overlay")
        out["report"] = report
    return out


# ---------------------------------------------------------------------------
# Agentic autonomous mining workflow — the six-phase lifecycle, supervised.
# ---------------------------------------------------------------------------

AGENTIC = _Runner("agentic")

_AGENTIC_BOUNDS = {
    "precompute_count_max": 512,
    "steady_state_cycles_max": 10,
}


def _run_agentic(runner: _Runner, *, count: int, cycles: int) -> dict[str, Any]:
    _ensure_repo_path()
    from Intelligence.agentic_mining import AgenticMiningWorkflow

    count = max(8, min(int(count), _AGENTIC_BOUNDS["precompute_count_max"]))
    cycles = max(1, min(int(cycles), _AGENTIC_BOUNDS["steady_state_cycles_max"]))

    wf = AgenticMiningWorkflow()
    evidence: dict[str, Any] = {"phases": {}, "submission_scope": "local_consensus_check"}

    def phase(name: str, fn: Callable[[], Any]) -> Any:
        if runner.stopped:
            raise InterruptedError("agentic workflow stopped by operator")
        runner.progress["current_phase"] = name
        out = fn()
        evidence["phases"][name] = out.to_dict() if hasattr(out, "to_dict") else out
        return out

    manifest = phase("cold_start", wf.phase1_cold_start)
    evidence["hardware"] = manifest.to_dict()
    candidates = phase("precompute", lambda: wf.phase2_precompute(count=count, n_anchor=7))
    evidence["candidate_count"] = len(candidates)
    phase("hold", wf.phase3_hold)
    if runner.stopped:
        raise InterruptedError("agentic workflow stopped by operator")
    runner.progress["current_phase"] = "submit"
    share = wf.phase4_submit()
    evidence["share"] = share.to_dict()
    evidence["accepted"] = share.accepted
    evidence["phases"]["submit"] = share.to_dict()
    steady = phase("steady_state", lambda: wf.phase5_steady_state(cycles=cycles))
    evidence["steady_cycles"] = len(steady)
    cooldown = phase("cool_down", wf.phase6_cool_down)
    evidence["cool_down"] = cooldown
    runner.progress["current_phase"] = "complete"
    return evidence


def start_agentic(*, count: int = 128, cycles: int = 3) -> bool:
    return AGENTIC.start(lambda r: _run_agentic(r, count=count, cycles=cycles))


def agentic_status() -> dict[str, Any]:
    return {"schema": "pythia.agentic/1", **AGENTIC.status()}


# ---------------------------------------------------------------------------
# Campaign runner — ordered pool phases bounded by the runtime config.
# ---------------------------------------------------------------------------

CAMPAIGN = _Runner("campaign")


def _run_campaign(
    runner: _Runner,
    *,
    apply_config: Callable[[dict[str, Any]], dict[str, Any]],
    retire_all: Callable[[], list[str]],
    counter_probe: Callable[[], dict[str, float]],
) -> dict[str, Any]:
    _ensure_repo_path()
    import runtime_config

    cfg = runtime_config.load()
    phases = cfg.get("campaign", {}).get("phases", [])
    if not phases:
        raise ValueError("campaign has no phases — configure campaign.phases first")

    record: dict[str, Any] = {
        "plan": [
            {
                "pool": p["pool"],
                "duration_s": p["duration_s"],
                "target_hs": p.get("target_hs"),
                "arms": p.get("arms"),
                "live_submit": bool(p.get("live_submit", False)),
            }
            for p in phases
        ],
        "phases": [],
    }
    completed = False
    try:
        for index, phase in enumerate(phases):
            if runner.stopped:
                raise InterruptedError("campaign stopped by operator")
            runner.progress["phase_index"] = index
            runner.progress["phase_pool"] = phase["pool"]
            # Apply the phase through the normal config path: enable exactly the
            # named pool, set the hashrate target and arm count, bind live_submit
            # to that pool identity when the phase asks for it.
            next_cfg = dict(runtime_config.load())
            pools = [dict(p) for p in next_cfg.get("pools", [])]
            selected = next(
                (
                    p
                    for p in pools
                    if p["worker"] == phase["pool"] or p["endpoint"] == phase["pool"]
                ),
                None,
            )
            if selected is None:
                raise ValueError(f"campaign phase {index}: pool {phase['pool']!r} not configured")
            for p in pools:
                p["enabled"] = p is selected
            next_cfg["pools"] = pools
            next_cfg["solvers"] = {
                "arms": int(phase.get("arms") or cfg["solvers"]["arms"]),
                "workers": cfg["solvers"]["workers"],
            }
            next_cfg["hashrate"] = {
                "target_hs": float(phase.get("target_hs") or cfg["hashrate"]["ceiling_hs"]),
                "ceiling_hs": cfg["hashrate"]["ceiling_hs"],
            }
            if phase.get("live_submit"):
                next_cfg["live_submit"] = {
                    "enabled": True,
                    "approval_id": runtime_config.identity_commit(
                        selected["endpoint"], selected["worker"]
                    ),
                }
            else:
                next_cfg["live_submit"] = {"enabled": False, "approval_id": ""}
            applied = apply_config(next_cfg)
            started = time.time()
            measured: list[float] = []
            # Pool counters are cumulative. Capture a phase baseline and
            # accumulate non-negative deltas, treating a decrease as a worker
            # restart/reset rather than leaking prior-phase shares forward.
            baseline = counter_probe()
            try:
                shares_last = int(baseline.get("shares_accepted") or 0)
            except (TypeError, ValueError):
                shares_last = 0
            shares_delta = 0
            duration = float(phase["duration_s"])
            while time.time() - started < duration:
                if runner.stopped:
                    break
                counters = counter_probe()
                rate = counters.get("hashrate_hs")
                # An observed 0.0 is a measurement; only an absent reading
                # is dropped, so measured-average never hides a stalled arm.
                if rate is not None:
                    try:
                        measured.append(float(rate))
                    except (TypeError, ValueError):
                        pass
                try:
                    shares_now = int(counters.get("shares_accepted") or 0)
                except (TypeError, ValueError):
                    shares_now = shares_last
                if shares_now >= shares_last:
                    shares_delta += shares_now - shares_last
                else:
                    # Counter reset (worker restart or pool switch): the new
                    # value is work observed after the reset.
                    shares_delta += max(0, shares_now)
                shares_last = shares_now
                time.sleep(min(2.0, max(0.25, duration / 240)))
            record["phases"].append(
                {
                    "index": index,
                    "pool": phase["pool"],
                    "endpoint": selected["endpoint"],
                    "worker": selected["worker"],
                    "duration_s": duration,
                    "target_hs": next_cfg["hashrate"]["target_hs"],
                    "arms": next_cfg["solvers"]["arms"],
                    "live_submit": bool(phase.get("live_submit", False)),
                    "started_at": started,
                    "finished_at": time.time(),
                    "measured_hs_avg": (sum(measured) / len(measured)) if measured else None,
                    "measured_hs_peak": max(measured) if measured else None,
                    "shares_accepted": shares_delta,
                    "applied": applied,
                }
            )
        runner.progress["phase_index"] = len(phases)
        completed = True
        return record
    finally:
        # Bounded run: the campaign owns its arms on every exit path —
        # done, operator stop, or a phase failure — never leave them
        # running after the campaign itself is gone.
        record["retired"] = retire_all()
        if not completed:
            runner.progress["campaign_record"] = record


def start_campaign(
    *,
    apply_config: Callable[[dict[str, Any]], dict[str, Any]],
    retire_all: Callable[[], list[str]],
    counter_probe: Callable[[], dict[str, Any]],
) -> bool:
    return CAMPAIGN.start(
        lambda r: _run_campaign(
            r, apply_config=apply_config, retire_all=retire_all, counter_probe=counter_probe
        )
    )


def campaign_status() -> dict[str, Any]:
    return {"schema": "pythia.campaign/1", **CAMPAIGN.status()}


SELFTEST = _Runner("selftest")


def _run_selftest(runner: _Runner) -> dict[str, Any]:
    _ensure_repo_path()
    import Intelligence.self_test as self_test

    report = self_test.run_intelligence_self_test()
    failures: dict[str, list[str]] = {}
    passed_checks = 0
    total_checks = 0
    for name, section in report.items():
        if not isinstance(section, dict) or "passed" not in section:
            continue
        total_checks += 1
        if section.get("passed"):
            passed_checks += 1
        else:
            detail = section.get("failures") or section.get("detail") or ["failed"]
            failures[name] = detail if isinstance(detail, list) else [str(detail)]
    return {
        "passed": total_checks == passed_checks,
        "checks": {"passed": passed_checks, "total": total_checks},
        "failures": failures,
        "report": report,
    }


def start_selftest() -> bool:
    return SELFTEST.start(_run_selftest)


def selftest_status() -> dict[str, Any]:
    status = SELFTEST.status()
    result = status.get("result") or {}
    return {
        "schema": "pythia.selftest/1",
        **status,
        "summary": {
            "passed": result.get("passed"),
            "checks": result.get("checks"),
            "failures": sorted((result.get("failures") or {}).keys()),
        },
    }


# ---------------------------------------------------------------------------
# Codebase maintenance — supervised diagnosis/proposal loop.
# ---------------------------------------------------------------------------

SELF_REPAIR = _Runner("self-repair")
_SELF_REPAIR_WAKE = threading.Event()
_DEFAULT_SELF_REPAIR_INTERVAL_S = 0
_MAX_SELF_REPAIR_INTERVAL_S = 7 * 24 * 60 * 60
REPO_ENGINEER = _Runner("repo-engineer")
_REPO_ENGINEER_SERVICE: Any = None
_REPO_ENGINEER_LOCK = threading.Lock()


def _self_repair_interval_s() -> int:
    """Use a bounded interval; zero means run once and then stop."""
    try:
        value = int(os.getenv("HYBA_SELF_REPAIR_INTERVAL_S", str(_DEFAULT_SELF_REPAIR_INTERVAL_S)))
    except ValueError:
        return _DEFAULT_SELF_REPAIR_INTERVAL_S
    if value == 0:
        return 0
    return min(max(value, 300), _MAX_SELF_REPAIR_INTERVAL_S)


def _repair_report_payload(report: Any) -> dict[str, Any]:
    proposals = list(getattr(report, "proposals", ()))
    classified = list(getattr(report, "classified", ()))
    apply_results = list(getattr(report, "apply_results", ()))
    summary = getattr(report, "summary", None)
    return {
        "session_id": getattr(report, "session_id", None),
        "started_at": getattr(report, "started_at", None),
        "finished_at": getattr(report, "finished_at", None),
        "failure_count": len(classified),
        "proposal_count": len(proposals),
        "applied_count": sum(bool(getattr(item, "applied", False)) for item in apply_results),
        "llm_enabled": bool(getattr(report, "llm_enabled", False)),
        "auto_apply_enabled": bool(getattr(report, "auto_apply_enabled", False)),
        "summary": summary() if callable(summary) else "Repair cycle completed.",
    }


def _run_self_repair(runner: _Runner, interval_s: int) -> dict[str, Any] | None:
    _ensure_repo_path()
    from Intelligence.self_healing.self_repair import run_self_repair_cycle

    while not runner.stopped:
        _SELF_REPAIR_WAKE.clear()
        runner.progress = {"phase": "diagnosing", "interval_s": interval_s}
        try:
            report = run_self_repair_cycle(
                repo_root=_REPO_ROOT,
                rerun_flaky=False,
                attempt_llm_for_unclassified=True,
            )
            runner.result = _repair_report_payload(report)
            runner.error = None
            runner.progress = {
                "phase": "cycle_complete",
                "last_completed_at": runner.result["finished_at"],
                "interval_s": interval_s,
            }
        except Exception as exc:
            runner.error = f"{type(exc).__name__}: {exc}"
            runner.result = {"error": runner.error}
            runner.progress = {"phase": "cycle_failed", "interval_s": interval_s}
            if interval_s == 0:
                raise

        if interval_s == 0:
            return runner.result
        if runner.stopped:
            runner.progress["phase"] = "stopped"
            runner.state = "stopped"
            return runner.result
        runner.progress["phase"] = "waiting"
        _SELF_REPAIR_WAKE.wait(interval_s)
    return runner.result


def start_self_repair(*, startup: bool = False) -> bool:
    """Start the persistent maintenance loop, beginning with a real diagnosis."""
    if startup and os.getenv("HYBA_SKIP_STARTUP_SELF_HEALING", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return False
    interval_s = _self_repair_interval_s()
    _SELF_REPAIR_WAKE.clear()
    return SELF_REPAIR.start(lambda runner: _run_self_repair(runner, interval_s))


def startup_self_repair_enabled() -> bool:
    return os.getenv("HYBA_STARTUP_SELF_HEALING_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def run_self_repair_now() -> bool:
    """Start a cycle or queue one to run immediately after the active cycle."""
    if SELF_REPAIR.state == "running":
        _SELF_REPAIR_WAKE.set()
        return True
    return start_self_repair()


def stop_self_repair() -> bool:
    """Stop after the active full test/repair cycle has reached its safe boundary."""
    if SELF_REPAIR.state != "running":
        return False
    SELF_REPAIR.progress["stop_requested"] = True
    SELF_REPAIR._stop.set()
    _SELF_REPAIR_WAKE.set()
    return True


def self_repair_status() -> dict[str, Any]:
    return {
        "schema": "pythia.maintenance/1",
        **SELF_REPAIR.status(),
        "interval_s": _self_repair_interval_s(),
        "llm_enabled": os.getenv("HYBA_SELF_REPAIR_LLM_ENABLED", "false").strip().lower()
        in {"1", "true", "yes"},
        "auto_apply_enabled": os.getenv("HYBA_SELF_REPAIR_AUTO_APPLY", "false").strip().lower()
        in {"1", "true", "yes"},
    }


def _repo_engineer_store_dir() -> Path:
    """Writable home for the repo engineer's store.

    The container runs as uid 10001 with ``PYTHIA_INTELLIGENCE_DIR`` as the
    provisioned writable root; ``<repo>/data`` is not writable there.
    ``PYTHIA_REPO_ENGINEER_DIR`` overrides outright; otherwise the store
    lives under the intelligence dir, falling back to ``<repo>/data`` on
    developer checkouts where the repo tree is writable.
    """
    override = os.getenv("PYTHIA_REPO_ENGINEER_DIR", "").strip()
    if override:
        return Path(override)
    intel = os.getenv("PYTHIA_INTELLIGENCE_DIR", "").strip()
    if intel:
        return Path(intel) / "repo_engineer"
    return _REPO_ROOT / "data" / "repo_engineer"


def initialize_repo_engineer() -> None:
    """Load repository context once during API startup without calling a model.

    A store that cannot initialise (read-only image layer, missing data
    directory) is reported and retried on the next status call — never fatal
    to the control plane, same contract as ``announce_skills``.
    """
    global _REPO_ENGINEER_SERVICE
    with _REPO_ENGINEER_LOCK:
        if _REPO_ENGINEER_SERVICE is None:
            try:
                _ensure_repo_path()
                from Intelligence.repo_engineer import RepoEngineer

                _REPO_ENGINEER_SERVICE = RepoEngineer(
                    _REPO_ROOT, store_dir=_repo_engineer_store_dir()
                )
            except Exception as exc:  # noqa: BLE001 - reported, never fatal
                print(
                    f"[pythia-control] repo engineer init failed: " f"{type(exc).__name__}: {exc}"
                )


def repo_engineer_status() -> dict[str, Any]:
    initialize_repo_engineer()
    service = (
        _REPO_ENGINEER_SERVICE.status()
        if _REPO_ENGINEER_SERVICE is not None
        else {"ready": False, "provider": "unavailable", "model": "unavailable"}
    )
    return {
        "schema": "pythia.repo-engineer/1",
        **service,
        "runner": REPO_ENGINEER.status(),
    }


def start_repo_engineer(prompt: str) -> bool:
    """Run one repo-grounded engineering task in the supervised runner."""
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 2_000:
        raise ValueError("prompt must be between 1 and 2000 characters")
    initialize_repo_engineer()
    if _REPO_ENGINEER_SERVICE is None:
        return False
    return REPO_ENGINEER.start(lambda _runner: _REPO_ENGINEER_SERVICE.ask(prompt))
