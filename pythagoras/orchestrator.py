"""
PYTHAGORAS — ORCHESTRATOR
Full meta-evolutionary engine. The domain is pluggable (default: code).

Features:
- Phase 1 Infrastructure Stabilisation:
  - FIX-01: __future__ import normalisation (CodeDomain.normalize)
  - FIX-02: UTF-8 encoding uniformity across all I/O
  - FIX-03: Git lock recovery with exponential retry/backoff
  - FIX-04: Pytest and evaluation timeout isolation
- Phase 2 Algorithmic Expansion:
  - ENH-03: Cross-file primitive seeding
  - ENH-05: Condition A (meta=OFF), Condition B (meta=ON), Condition C (isolated measurement)
- Phase 3 Emergent Intelligence Amplification:
  - ENH-08: Rolling-window normalisation for unbiased trajectory comparison
  - ENH-11: Surrogate transfer learning across corpus files
  - ENH-13: Multi-session memory persistence (JSON)
  - Kellogg v7.0 Stack Quantum Reflection Integration
- Domain abstraction: the engine is domain-agnostic; artifacts, coherence,
  primitives, tests, and features are supplied by the active Domain.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np

from .domain import Domain, resolve_domain
from .domains.code_domain import normalize_future_imports  # noqa: F401  (compat re-export)
from .phi_resonance import PhiResonanceCalculator, PHI
from .cgp import CGP
from .pythagoras_mutation import PythagorasMutator
from .meta_evolution import MetaEvolutionController
from .auto_primitive import AutoPrimitiveDiscovery
from .geometry_evolution import GeometryEvolution

# =============================================================================
# Phase 1: Infrastructure Stabilisation Utilities
# =============================================================================
# normalize_future_imports now lives in pythagoras.domains.code_domain
# (it is a code-domain concern) and is re-exported here for compatibility.


def read_source_utf8(path: Path | str) -> str:
    """
    FIX-02: UTF-8 encoding uniformity.
    Safely reads file with utf-8 encoding, handling BOM and newlines seamlessly.
    """
    p = Path(path)
    content = p.read_bytes()
    return content.decode("utf-8-sig").replace("\r\n", "\n")


def write_source_utf8(path: Path | str, source: str) -> None:
    """
    FIX-02: UTF-8 encoding uniformity.
    Safely writes file strictly in UTF-8 with uniform unix newlines without BOM.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(source.replace("\r\n", "\n"))


def safe_git_lock_recovery(
    repo_path: Path | str,
    retries: int = 5,
    backoff: float = 0.1,
) -> bool:
    """
    FIX-03: Git lock recovery with exponential backoff.
    Detects and safely recovers from stale .git/index.lock contention.
    """
    p = Path(repo_path)
    lock_file = p / ".git" / "index.lock"

    for attempt in range(retries):
        if not lock_file.exists():
            return True
        # If lock exists, check age; if older than 10s, clear stale lock
        try:
            mtime = lock_file.stat().st_mtime
            if time.time() - mtime > 10.0:
                lock_file.unlink(missing_ok=True)
                return True
        except Exception:
            pass
        time.sleep(backoff * (2**attempt))

    return not lock_file.exists()


def run_isolated_execution(
    source: str,
    timeout_seconds: float = 3.0,
) -> Tuple[bool, str]:
    """
    FIX-04: Pytest / execution timeout isolation.
    Compiles and dry-runs source in isolated scope to verify non-halting/crash safety.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    try:
        compile(source, "<pythagoras_isolated>", "exec")
    except Exception as exc:
        return False, str(exc)

    # Separate interpreter + wall-clock timeout. This is process isolation,
    # not an OS security sandbox for hostile code with ambient I/O authority.
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", encoding="utf-8", delete=False
        ) as handle:
            handle.write(source)
            path = handle.name
        completed = subprocess.run(
            [sys.executable, "-I", path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode == 0:
            return True, "Execution succeeded"
        detail = (completed.stderr or completed.stdout).strip()
        return False, detail or f"isolated execution exited {completed.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"execution timed out after {timeout_seconds}s (timeout)"
    except Exception as exc:
        return False, str(exc)
    finally:
        if path is not None:
            Path(path).unlink(missing_ok=True)


def rolling_window_normalize(series: List[float], window: int = 3) -> List[float]:
    """
    ENH-08: Rolling-window normalisation.
    Removes measurement asymmetry in comparative A/B evaluation trajectories.
    """
    if not series:
        return []
    normalized: List[float] = []
    for i in range(len(series)):
        start_idx = max(0, i - window + 1)
        sub = series[start_idx : i + 1]
        mean_val = float(np.mean(sub))
        normalized.append(mean_val)
    return normalized


# =============================================================================
# The PYTHAGORAS Orchestrator
# =============================================================================


class Pythagoras:
    """
    PYTHAGORAS — Meta-Evolutionary Engine.
    Orchestrates the 4 adaptation layers, auto-primitive discovery,
    and multi-file emergent cascades. The domain is pluggable via the
    Domain interface (default: CodeDomain).
    """

    def __init__(self, condition: str = "B", domain: Any = None):
        """
        condition:
        - 'A': Meta=OFF (static baseline)
        - 'B': Meta=ON (full 4-layer meta-evolution)
        - 'C': Isolated measurement arm (ENH-05)
        domain:
        - a registered domain name ('code', 'circuit', 'molecule',
          'market', 'network') or a Domain instance. Default: 'code'.
        """
        self.condition = condition.upper()
        self.domain: Domain = resolve_domain(domain)
        self.phi_calc = getattr(self.domain, "phi_calc", PhiResonanceCalculator())
        self.cgp = CGP(domain=self.domain)
        self.mutator = PythagorasMutator(domain=self.domain)
        self.meta = MetaEvolutionController()
        self.discovery = AutoPrimitiveDiscovery()
        self.geometry = GeometryEvolution()

        self.session_history: List[Dict[str, Any]] = []

    def evolve_file(
        self,
        source: str,
        generations: int = 20,
        filename: str = "source.py",
    ) -> Dict[str, Any]:
        """
        Evolve a single artifact through the meta-evolutionary pipeline.
        The artifact's representation, coherence metric, and primitives are
        supplied by the active Domain.
        """
        # FIX-01 & FIX-02: Domain normalization
        current = self.domain.normalize(source)
        initial_phi = self.domain.coherence(current)
        fitness_history: List[float] = [initial_phi]
        primitive_gains: Dict[str, float] = {}

        # If Condition A (meta=OFF), disable dynamic tuning
        meta_enabled = self.condition in ("B", "C")
        adaptation_enabled = self.condition == "B"

        for gen in range(generations):
            prev_phi = fitness_history[-1]

            # 1. CGP Step
            best_genome, cgp_fitness, cgp_transformed = self.cgp.evolve(current, generations=1)
            cgp_transformed = self.domain.normalize(cgp_transformed)
            cgp_phi = self.domain.coherence(cgp_transformed)
            cgp_valid = self.domain.is_valid(cgp_transformed) and self.domain.tests(cgp_transformed)
            if cgp_valid and cgp_phi > prev_phi:
                current = cgp_transformed
                prev_phi = cgp_phi

            # 2. Directed / Surrogate Mutation Step. Fitness never overrides
            # domain correctness: invalid candidates are transactionally rejected.
            mutated, step_gains = self.mutator.mutate(current, n_mutations=3)
            mutated = self.domain.normalize(mutated)
            mutated_phi = self.domain.coherence(mutated)
            gain = mutated_phi - prev_phi
            candidate_valid = self.domain.is_valid(mutated) and self.domain.tests(mutated)

            # ENH-04: Simulated annealing may accept a lower-scoring candidate,
            # but it may never accept a candidate that violates domain tests.
            accept = False
            if candidate_valid:
                if adaptation_enabled:
                    accept = self.meta.should_accept(gain)
                else:
                    accept = gain > 0.0

            if accept:
                current = mutated
                fitness_history.append(mutated_phi)
            else:
                fitness_history.append(prev_phi)

            # 3. Auto-Primitive Discovery (Condition B only)
            if adaptation_enabled and gain > 0.04:
                pattern_name = f"PATTERN_GEN_{gen}"
                self.discovery.observe(pattern_name, gain)
                new_prims = self.discovery.discover()
                for prim in new_prims:
                    primitive_gains[prim["name"]] = prim["avg_gain"]
                    self.mutator.weights[prim["name"]] = prim["weight"]

            # 4. Meta-Evolution & Geometry Updates
            if meta_enabled:
                geom_state = self.geometry.get_state()
                self.meta.update(
                    generation=gen,
                    fitness_history=fitness_history,
                    primitive_gains=step_gains,
                    file_id=filename,
                    geometry_state=geom_state,
                )

                if adaptation_enabled:
                    # Update CGP geometry based on curvature and surrogate velocity
                    surrogate_feat = self.mutator.surrogate.extract_features(current, self.domain)
                    v_surrogate = max(0.0, self.mutator.surrogate.predict(surrogate_feat))
                    geom_record = self.geometry.evolve(fitness_history, v_surrogate)
                    # Apply evolved geometry to CGP substrate
                    self.cgp.n_cols = geom_record["n_cols"]
                    self.cgp.levels_back = geom_record["levels_back"]
                    self.cgp.pop_size = geom_record["pop_size"]

        final_source = self.domain.normalize(current)
        final_phi = self.domain.coherence(final_source)
        rolling_fit = rolling_window_normalize(fitness_history, window=3)

        result = {
            "filename": filename,
            "domain": self.domain.name,
            "condition": self.condition,
            "initial_phi": initial_phi,
            "final_phi": final_phi,
            "delta_phi": final_phi - initial_phi,
            "generations": generations,
            "fitness_history": fitness_history,
            "rolling_fitness": rolling_fit,
            "gain_per_generation": (
                (final_phi - initial_phi) / generations if generations else 0.0
            ),
            "discovered_primitives": self.discovery.get_discovered(),
            "meta_state": self.meta.get_state(),
            "geometry_state": self.geometry.get_state(),
            "phase_transitions": list(self.meta.phase_transitions),
            "final_source": final_source,
        }
        self.session_history.append(result)
        return result

    def evolve_corpus(
        self,
        files: Dict[str, str],
        generations: int = 15,
    ) -> Dict[str, Any]:
        """
        Evolve a corpus of files with ENH-03 Cross-file primitive seeding.
        Primitives discovered in file i are immediately seeded to file i+1.
        """
        results: Dict[str, Any] = {}
        all_geometries: List[Dict[str, Any]] = []

        for filename, source in files.items():
            res = self.evolve_file(source, generations=generations, filename=filename)
            results[filename] = res
            all_geometries.append(res["geometry_state"])

            # ENH-03: Cross-file primitive seeding (cascade mechanism)
            if self.condition == "B":
                for prim_name, prim_data in res["discovered_primitives"].items():
                    self.mutator.weights[prim_name] = prim_data["weight"]

        # ENH-14: Collective geometry consensus across corpus
        consensus_geometry = GeometryEvolution.compute_consensus(all_geometries)
        self.geometry.load_state(consensus_geometry)
        self.cgp.n_cols = self.geometry.n_cols
        self.cgp.levels_back = self.geometry.levels_back
        self.cgp.pop_size = self.geometry.pop_size

        total_delta = sum(r["delta_phi"] for r in results.values())
        avg_final = float(np.mean([r["final_phi"] for r in results.values()]))

        return {
            "files": results,
            "total_delta_phi": total_delta,
            "avg_final_phi": avg_final,
            "consensus_geometry": consensus_geometry,
            "all_phase_transitions": list(self.meta.phase_transitions),
        }

    # =========================================================================
    # Phase 3: Multi-Session Memory Persistence (ENH-13)
    # =========================================================================

    def save_session(self, filepath: Path | str) -> None:
        """
        ENH-13: Multi-session memory.
        Saves discovered primitives, learned weights, and surrogate state to JSON.
        """
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "condition": self.condition,
            "domain": self.domain.name,
            "primitive_weights": self.mutator.weights,
            "discovered_primitives": self.discovery.export_state(),
            "meta_state": self.meta.get_state(),
            "geometry_state": self.geometry.get_state(),
            "surrogate_weights": self.mutator.surrogate.weights.tolist(),
            "surrogate_bias": self.mutator.surrogate.bias,
            "surrogate_samples": self.mutator.surrogate.sample_count,
            "phase_transitions": self.meta.phase_transitions,
            "provenance_log": self.meta.provenance_log,
        }
        temporary = p.with_suffix(p.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, p)

    def load_session(self, filepath: Path | str) -> None:
        """
        ENH-13: Multi-session memory.
        Loads discovered primitives and warm-starts surrogate from JSON.
        """
        p = Path(filepath)
        if not p.exists():
            return

        data = json.loads(p.read_text(encoding="utf-8"))
        if "primitive_weights" in data:
            self.mutator.set_weights(data["primitive_weights"])
        if "discovered_primitives" in data:
            self.discovery.load_state(data["discovered_primitives"])
        if "surrogate_weights" in data:
            self.mutator.surrogate.weights = np.array(data["surrogate_weights"], dtype=float)
            self.mutator.surrogate.bias = float(data.get("surrogate_bias", 0.0))
            self.mutator.surrogate.sample_count = int(data.get("surrogate_samples", 0))
        if "meta_state" in data:
            self.meta.load_state(
                data["meta_state"],
                phase_transitions=data.get("phase_transitions", []),
                provenance_log=data.get("provenance_log", []),
            )
        if "geometry_state" in data:
            self.geometry.load_state(data["geometry_state"])
            self.cgp.n_cols = self.geometry.n_cols
            self.cgp.levels_back = self.geometry.levels_back
            self.cgp.pop_size = self.geometry.pop_size

    # =========================================================================
    # Kellogg v7.0 Stack Quantum Reflection Integration
    # =========================================================================

    def kellogg_quantum_reflection(
        self,
        source: str,
        marked_solutions: List[str],
    ) -> Dict[str, Any]:
        """
        Formal integration with Kellogg Operator Engine (v6.1-v7.0):
        G_Kellogg = -S_0^(M) S_chi^(M)

        Where manifold metric g_xx on M is induced by the domain coherence
        score and landscape curvature, guiding quantum reflection operators
        across the structured search space.
        """
        phi_score = self.domain.coherence(source)
        components = self.domain.compute_components(source)

        # Riemannian metric tensor parameter g_xx on code manifold M
        g_metric = float(phi_score / PHI)
        curvature = self.geometry._compute_curvature([components["composite"], phi_score])

        # Quantum reflection phase angle theta induced by phi-resonance
        theta = float(2.0 * math.pi * phi_score)

        return {
            "manifold_phi": phi_score,
            "metric_tensor_diagonal": g_metric,
            "curvature": curvature,
            "reflection_phase": theta,
            "kellogg_operator": "G_Kellogg = -S_0^(M) S_chi^(M)",
            "asymptotic_grover_limit": "lim_{S -> S_empty} G_Kellogg = G_Grover",
            "marked_targets": list(marked_solutions),
            "coherence_status": "RESONANT" if phi_score >= PHI else "DEGENERATE",
        }
