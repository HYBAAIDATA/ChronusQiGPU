"""PYTHIA's canonical mining-intelligence authority.

This is a composition seam, not a second miner. PYTHIA owns mining planning
and may compose every intelligence, learning, quantum, tensor, storage and
execution capability that the repository actually provides. Stratum remains
the work-identity authority; Chronus remains the heterogeneous physical
executor; SHA256d + the negotiated target remain the share-validity predicate;
AL HARAS/network policy remains the security boundary.

Those boundaries validate and secure work. They do not restrict search order,
learning, topology, quantum mathematics, tensor reasoning, or the choice among
real probed CPU/GPU/remote/ASIC/SUPER-ASIC execution substrates.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import os
import time
from typing import Any, Callable, Mapping, Sequence

from Intelligence.bitcoin_corpus import PythiaBitcoinCorpus, SCHEMA as BITCOIN_CORPUS_SCHEMA

SCHEMA = "pythia.mining_authority/2"

_ARSENAL_MODULES: dict[str, tuple[str, ...]] = {
    "turing.root": (
        "turing_universal_quantum_computer.turing_universal_quantum_computer",
        "turing_universal_quantum_computer",
    ),
    "turing.hilbert": (
        "turing_universal_quantum_computer.hilbert",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.hilbert",
    ),
    "mining.search": ("mining.search",),
    "turing.quantum_algorithms": (
        "turing_universal_quantum_computer.quantum_algorithms",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.quantum_algorithms",
    ),
    "turing.quantum_walk": (
        "turing_universal_quantum_computer.quantum_walk",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.quantum_walk",
    ),
    "turing.swarm": (
        "turing_universal_quantum_computer.swarm",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.swarm",
    ),
    "turing.annealing": (
        "turing_universal_quantum_computer.annealing",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.annealing",
    ),
    "turing.variational": (
        "turing_universal_quantum_computer.variational",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.variational",
    ),
    "turing.stabilizer": (
        "turing_universal_quantum_computer.stabilizer",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.stabilizer",
    ),
    "turing.exact_state_vector": (
        "turing_universal_quantum_computer.exact_state_vector",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.exact_state_vector",
    ),
    "turing.hendrix": (
        "turing_universal_quantum_computer.hendrix",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.hendrix",
    ),
    "turing.phi_machine": (
        "turing_universal_quantum_computer.phi_machine",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.phi_machine",
    ),
    "turing.midas_vqc": (
        "turing_universal_quantum_computer.midas_vqc",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.midas_vqc",
    ),
    "turing.trotter_simulation": (
        "turing_universal_quantum_computer.trotter_simulation",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.trotter_simulation",
    ),
    "turing.quantum_cuda": (
        "turing_universal_quantum_computer.quantum_cuda",
        "turing_universal_quantum_computer.turing_universal_quantum_computer.quantum_cuda",
    ),
    "quantum2026": ("quantum_compute_substrate.quantum_2026",),
    "kellogg": ("kellogg",),
    "kellogg.tensor_network": ("kellogg.tensor_network",),
    "kellogg.quantum_tensor": ("kellogg.quantum_tensor",),
    "kellogg.exact_tensor": ("kellogg.exact_tensor",),
    "kellogg.compressed_tensor": ("kellogg.compressed_tensor",),
    "kellogg.traversal": ("kellogg.traversal",),
}

_NAMED_ALIASES: dict[str, tuple[str, str]] = {
    "grover": ("quantum2026", "EnhancedGrover"),
    "grover_exact": ("turing.hilbert", "GroverExact"),
    "grover_style_search": ("mining.search", "GroverStyleSearch"),
    "hendrix": ("turing.hendrix", "HendrixChronusSearch"),
    "quantum_walk": ("turing.quantum_walk", "CoinedCycleWalk"),
    "hypercube_walk": ("turing.quantum_walk", "HypercubeWalk"),
    "szegedy_walk": ("quantum2026", "ModernQWalk"),
    "szegedy_operator": ("quantum2026", "szegedy_walk_operator"),
    "swarming": ("turing.swarm", "QuantumSwarm"),
    "annealing": ("turing.annealing", "TransverseFieldIsing"),
    "tunnelling": ("turing.annealing", "landau_zener"),
    "entanglement": ("turing.stabilizer", "StabilizerState"),
    "collapse": ("turing.exact_state_vector", "ExactStateVector"),
    "vqe": ("quantum2026", "ModernVQE"),
    "qaoa": ("quantum2026", "ModernQAOA"),
    "qft": ("quantum2026", "EnhancedQFT"),
    "shor_period_finding": ("quantum2026", "EnhancedShor"),
    "quantum_simulation": ("quantum2026", "ModernQSim"),
    "quantum_annealing": ("quantum2026", "ModernQAnneal"),
    "quantum_ml": ("quantum2026", "ModernQML"),
    "hybrid_quantum_classical": ("quantum2026", "ModernHybrid"),
    "vqc": ("turing.variational", "VariationalQuantumCircuit"),
}


@dataclass(frozen=True)
class ModuleCapability:
    name: str
    available: bool
    module: str | None
    exports: tuple[str, ...]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "module": self.module,
            "exports": list(self.exports),
            "error": self.error,
        }


@dataclass(frozen=True)
class PythiaMiningDirective:
    lane_order: tuple[int, ...]
    preferred_nonces: tuple[int, ...]
    source: str
    confidence: float
    modalities: Mapping[str, Any]
    suppositions: tuple[Mapping[str, Any], ...]
    corpus: Mapping[str, Any]
    resources: Mapping[str, Any]
    generated_at: float

    def as_evidence(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "search_algorithm": "hendrix_coprime_stride",
            "lane_order": list(self.lane_order),
            "preferred_nonce_count": len(self.preferred_nonces),
            "preferred_nonce_head": list(self.preferred_nonces[:32]),
            "source": self.source,
            "confidence": self.confidence,
            "modalities": dict(self.modalities),
            "suppositions": [dict(item) for item in self.suppositions],
            "corpus": dict(self.corpus),
            "resources": dict(self.resources),
            "generated_at": self.generated_at,
            "authority": {
                "planning": "PYTHIA",
                "intelligence": "PYTHIA five-modal + repository intelligence registry",
                "quantum_computation": "Turing / repository quantum arsenal",
                "tensor": "Kellogg",
                "heterogeneous_execution": "Chronus",
                "stratum_identity": "Stratum",
                "share_validity": "SHA256d + negotiated target",
                "security": "AL HARAS / network policy",
            },
        }


class PythiaQuantumArsenal:
    def __init__(self) -> None:
        self._modules: dict[str, Any | None] = {}
        self._status: dict[str, ModuleCapability] = {}

    @staticmethod
    def _public_exports(module: Any) -> tuple[str, ...]:
        declared = getattr(module, "__all__", None)
        if declared:
            return tuple(sorted({str(name) for name in declared}))
        return tuple(sorted(name for name in dir(module) if not name.startswith("_")))

    def _load_module(self, surface: str) -> Any | None:
        if surface in self._modules:
            return self._modules[surface]
        errors: list[str] = []
        for module_name in _ARSENAL_MODULES[surface]:
            try:
                module = importlib.import_module(module_name)
                self._modules[surface] = module
                self._status[surface] = ModuleCapability(
                    surface, True, module_name, self._public_exports(module)
                )
                return module
            except Exception as exc:
                errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
        self._modules[surface] = None
        self._status[surface] = ModuleCapability(surface, False, None, (), "; ".join(errors))
        return None

    def resolve(self, name: str) -> Callable[..., Any] | type | Any:
        if name in _NAMED_ALIASES:
            surface, symbol = _NAMED_ALIASES[name]
        else:
            matches = [surface for surface in _ARSENAL_MODULES if name.startswith(surface + ".")]
            if not matches:
                raise KeyError(f"unknown PYTHIA arsenal path: {name}")
            surface = max(matches, key=len)
            symbol = name[len(surface) + 1 :]
        module = self._load_module(surface)
        if module is None:
            raise RuntimeError(self._status[surface].error or f"{surface} unavailable")
        if not symbol or symbol.startswith("_"):
            raise KeyError("a public arsenal symbol is required")
        return getattr(module, symbol)

    def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        value = self.resolve(name)
        if not callable(value):
            if args or kwargs:
                raise TypeError(f"{name} is not callable")
            return value
        return value(*args, **kwargs)

    def inventory(self) -> dict[str, Any]:
        modules = []
        for surface in _ARSENAL_MODULES:
            self._load_module(surface)
            modules.append(self._status[surface].as_dict())
        aliases: dict[str, Any] = {}
        for name, (surface, symbol) in _NAMED_ALIASES.items():
            status = self._status.get(surface)
            aliases[name] = {
                "surface": surface,
                "symbol": symbol,
                "available": bool(status and status.available and symbol in status.exports),
            }
        return {
            "schema": "pythia.quantum_arsenal/2",
            "module_complete": True,
            "modules": modules,
            "named_aliases": aliases,
            "available_modules": [item["name"] for item in modules if item["available"]],
            "unavailable_modules": [item["name"] for item in modules if not item["available"]],
        }


class PythiaMiningAuthority:
    def __init__(
        self,
        *,
        orchestrator: Any | None = None,
        quantum: PythiaQuantumArsenal | None = None,
        corpus_path: str | None = None,
        corpus: PythiaBitcoinCorpus | None = None,
        backend_registry: Any | None = None,
    ) -> None:
        if orchestrator is None:
            from Intelligence import get_intelligence
            orchestrator = get_intelligence()
        self.orchestrator = orchestrator
        self.quantum = quantum or PythiaQuantumArsenal()
        path = corpus_path or os.getenv("PYTHIA_BITCOIN_CORPUS_DB")
        self.corpus = corpus if corpus is not None else (PythiaBitcoinCorpus(path) if path else None)
        self.backend_registry = backend_registry
        self.last_directive: PythiaMiningDirective | None = None
        self.last_outcome: dict[str, Any] | None = None

    def bind_backend_registry(self, registry: Any) -> None:
        self.backend_registry = registry

    def backend_inventory(self) -> dict[str, Any]:
        if self.backend_registry is None:
            return {"available": False, "reason": "backend registry not wired"}
        census = self.backend_registry.census()
        return {"available": True, "lanes": {name: probe.as_dict() for name, probe in census.items()}}

    def select_backend(self, requested: str, **kwargs: Any) -> Any:
        if self.backend_registry is None:
            raise RuntimeError("backend registry not wired")
        return self.backend_registry.select(requested, **kwargs)

    def close(self) -> None:
        if self.corpus is not None:
            self.corpus.close()

    @staticmethod
    def _availability(import_name: str) -> dict[str, Any]:
        try:
            module = importlib.import_module(import_name)
            return {"available": True, "module": import_name, "version": getattr(module, "__version__", None)}
        except Exception as exc:
            return {"available": False, "module": import_name, "reason": f"{type(exc).__name__}: {exc}"}

    def capability_snapshot(self) -> dict[str, Any]:
        registry = self.orchestrator.registry.summary()
        return {
            "schema": SCHEMA,
            "five_intelligences": ["predictive", "causal", "counterfactual", "topological", "geometric"],
            "supposition": {
                "available": True,
                "role": "hypothesis/search-order proposals remain suppositions until SHA256d evaluation",
                "legacy_engine_restored": False,
                "legacy_engine_reason": "original SuppositionEngine source not present in current git history or recovered donor archives",
            },
            "learning": self.orchestrator.pythia_status(),
            "memory": self.orchestrator.memory_status(),
            "agentic": self.orchestrator.agentic_status(),
            "folded_storage": self.orchestrator.folded_status(),
            "pythia_store": {
                "available": getattr(self.orchestrator, "store", None) is not None,
                "type": type(getattr(self.orchestrator, "store", None)).__name__,
            },
            "tensor": {
                "authority": "Kellogg tensor only",
                "kellogg": self._availability("kellogg"),
                "tensor_network": self._availability("kellogg.tensor_network"),
                "quantum_tensor": self._availability("kellogg.quantum_tensor"),
            },
            "turing": self._availability("turing_universal_quantum_computer"),
            "execution_backends": self.backend_inventory(),
            "registry": registry,
            "quantum_arsenal": self.quantum.inventory(),
            "corpus_database": self.corpus.status() if self.corpus is not None else {
                "schema": BITCOIN_CORPUS_SCHEMA,
                "available": False,
                "reason": "PYTHIA_BITCOIN_CORPUS_DB not configured",
            },
        }

    @staticmethod
    def _lane_order(preferred: Sequence[int], base_step: int) -> tuple[int, ...]:
        order: list[int] = []
        seen: set[int] = set()
        for nonce in preferred:
            lane = (int(nonce) - int(base_step)) % 32
            if lane not in seen:
                seen.add(lane)
                order.append(lane)
            if len(order) == 32:
                break
        order.extend(lane for lane in range(32) if lane not in seen)
        return tuple(order)

    def _corpus_context(self, header: bytes) -> dict[str, Any]:
        if self.corpus is None:
            return {"available": False, "reason": "corpus database not configured"}
        status = self.corpus.status()
        return {
            "available": status["count"] > 0,
            "count": status["count"],
            "latest_height": status["latest_height"],
            "raw_block_count": status.get("raw_block_count", 0),
            "current_header_seed": hashlib.sha256(header).hexdigest(),
        }

    def plan(
        self,
        *,
        header: bytes,
        target_be: bytes,
        base_step: int,
        window: int,
        block_context: Mapping[str, Any] | None = None,
    ) -> PythiaMiningDirective:
        if len(header) != 80:
            raise ValueError("PYTHIA planning requires the canonical 80-byte header")
        if len(target_be) != 32:
            raise ValueError("PYTHIA planning target must be 32-byte big-endian")
        if window <= 0:
            raise ValueError("window must be positive")
        if base_step < 0 or base_step + window > 0x100000000:
            raise ValueError("PYTHIA planning lease must stay inside uint32")

        corpus_context = self._corpus_context(header)
        context = dict(block_context or {})
        context["bitcoin_corpus"] = corpus_context
        context["execution_backends"] = self.backend_inventory()
        guidance = self.orchestrator.guide_mining(
            header=header,
            target=target_be,
            nonce_window=window,
            block_context=context,
        )
        five = self.orchestrator.counterfactual_analyze(
            header=header,
            target=target_be,
            current_nonce=base_step,
            n_counterfactuals=5,
        )

        preferred: list[int] = []
        seen: set[int] = set()
        for raw in guidance.nonce_schedule:
            offset = int(raw) % window
            nonce = base_step + offset
            if base_step <= nonce < base_step + window and nonce not in seen:
                seen.add(nonce)
                preferred.append(nonce)
            if len(preferred) >= min(window, 10_000):
                break

        lane_order = self._lane_order(preferred, base_step)
        modalities = {
            "predictive": True,
            "causal": True,
            "counterfactual": True,
            "topological": True,
            "geometric": True,
            "result_type": type(five).__name__,
        }
        suppositions = (
            {
                "kind": "search_order",
                "truth_class": "supposition_until_sha256d_evaluated",
                "source": getattr(guidance, "source", "PYTHIA"),
                "confidence": float(getattr(guidance, "confidence", 0.0)),
                "proposal_count": len(preferred),
            },
        )
        quantum_inventory = self.quantum.inventory()
        aliases = quantum_inventory.get("named_aliases", {})
        resources = {
            "intelligence_registry": self.orchestrator.registry.summary(),
            "quantum": quantum_inventory,
            "search_support": {
                "default_algorithm": "hendrix",
                "supposition": {
                    "available": True,
                    "state": "ACTIVE_IN_PLAN",
                },
                "tunnelling": aliases.get("tunnelling", {"available": False}),
                "annealing": aliases.get("annealing", {"available": False}),
                "swarming": aliases.get("swarming", {"available": False}),
                "entanglement": aliases.get("entanglement", {"available": False}),
            },
            "tensor": {
                "authority": "Kellogg tensor only",
                "kellogg": self._availability("kellogg"),
                "tensor_network": self._availability("kellogg.tensor_network"),
            },
            "execution_backends": self.backend_inventory(),
            "storage": {
                "pythia_store": getattr(self.orchestrator, "store", None) is not None,
                "bitcoin_corpus": corpus_context,
            },
        }
        directive = PythiaMiningDirective(
            lane_order=lane_order,
            preferred_nonces=tuple(preferred),
            source=str(getattr(guidance, "source", "PYTHIA")),
            confidence=float(getattr(guidance, "confidence", 0.0)),
            modalities=modalities,
            suppositions=suppositions,
            corpus=corpus_context,
            resources=resources,
            generated_at=time.time(),
        )
        self.last_directive = directive
        return directive

    def learn_execution(
        self,
        *,
        header: bytes,
        nonce: int | None,
        pool_accepted: bool | None,
        execution: Mapping[str, Any],
    ) -> None:
        reward = 1.0 if pool_accepted is True else (-0.25 if pool_accepted is False else 0.0)
        self.orchestrator.consolidate_memory_task(
            trigger="production mining execution",
            plan=["PYTHIA planned search", "Chronus executed", "SHA256d truth boundary evaluated"],
            tool_calls=[{"tool": "production_miner", "execution": dict(execution)}],
            outcome={"candidate_nonce": nonce, "pool_accepted": pool_accepted},
            reward=reward,
            error_state=bool(execution.get("error")),
            unexpected=False,
        )
        if nonce is not None:
            self.orchestrator.hold_in_superposition(header, nonce, bool(pool_accepted))
        store = getattr(self.orchestrator, "store", None)
        if store is not None:
            store.journal.append(
                "production_mining",
                {"nonce": nonce, "pool_accepted": pool_accepted, "execution": dict(execution)},
            )
            store.save()
        self.last_outcome = {
            "nonce": nonce,
            "pool_accepted": pool_accepted,
            "execution": dict(execution),
            "recorded_at": time.time(),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            **self.capability_snapshot(),
            "last_directive": self.last_directive.as_evidence() if self.last_directive else None,
            "last_outcome": self.last_outcome,
        }


__all__ = [
    "PythiaMiningAuthority",
    "PythiaMiningDirective",
    "PythiaQuantumArsenal",
    "SCHEMA",
]
