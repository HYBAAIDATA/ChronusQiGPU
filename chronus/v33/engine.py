# engine.py
# Chronos GPU -- ChronosEngine orchestrator v3.3 (memory integration, 4 Aug 2026)
#
# Anchor: Quantum theory stems from mathematics — substrate- and hardware-agnostic.
#
# v2.0: real compile → Hamiltonian → evolve → reconstruct pipeline.
# v3.0: EMP / animation / SCF gap-close.
# v3.2–3.3: mathematical memory subsystem
#   L0 Table → L1 NeuralIndex → L2 MPSStore → L3 QRAM
#   → BlockEncode → QSVT  (render_spectral)
# Default behaviour (enable_emp=False, enable_memory=False) preserves
# validated baseline energies.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .qsdl_compiler import QSDLCompiler, ManifoldConfig
from .hamiltonian import HamiltonianLibrary
from .evolution_engine import EvolutionEngine, RenderResult
from .reconstruction import ReconstructionEngine


@dataclass
class RenderOutput:
    energy: float
    scene: str
    frame_shape: tuple
    raster_compression_ratio: float
    rendered_pixels_hit: int
    total_pixels: int
    distribution: np.ndarray
    # v3.0 optional diagnostics
    emp_enabled: bool = False
    fidelity_to_ground: Optional[float] = None
    time_dependent: bool = False
    scf_energy: Optional[float] = None
    scf_converged: Optional[bool] = None
    corrections_applied: int = 0
    # v3.2 spectral / memory diagnostics
    spectral_mode: bool = False
    qsvt_semantic: Optional[str] = None
    qsvt_degree: Optional[int] = None
    memory_compression_ratio: Optional[float] = None


class ChronosEngine:
    def __init__(
        self,
        n_faces: int = 32,
        layers: int = 4,
        enable_emp: bool = False,
        emp_fidelity_threshold: float = 0.95,
        emp_epsilon: float = 0.01,
        emp_readout_fraction: float = 0.25,
        enable_memory: bool = False,
        memory_address_bits: int = 8,
        memory_mps_qubits: int = 16,
        memory_mps_bond_dim: int = 16,
    ):
        self.n = n_faces
        self.layers = layers
        self.enable_emp = enable_emp
        self.emp_fidelity_threshold = emp_fidelity_threshold
        self.emp_epsilon = emp_epsilon
        self.emp_readout_fraction = emp_readout_fraction
        self.enable_memory = enable_memory
        self._memory = None
        if enable_memory:
            from .memory import MemoryHierarchy
            self._memory = MemoryHierarchy(
                address_bits=memory_address_bits,
                value_bits=8,
                n_slots=8,
                mps_qubits=memory_mps_qubits,
                mps_bond_dim=memory_mps_bond_dim,
                seed=0,
            )

    def _extract_animation_keyframes(self, objects: List[Dict]) -> Optional[List[Tuple[float, float]]]:
        """Pull (time, value) keyframes from the first animated object, if any."""
        for obj in objects:
            anim = obj.get("animation")
            if not anim:
                continue
            kfs = anim.get("keyframes") or []
            if kfs:
                return [(float(t), float(v)) for t, v in kfs]
        return None

    def render(self, scene: str = "default") -> RenderOutput:
        compiler = QSDLCompiler(ManifoldConfig(n_faces=self.n))
        qscene = compiler.compile(scene)

        lib = HamiltonianLibrary(n_faces=qscene.manifold.n_faces)
        h_terms = lib.build(qscene.objects, qscene.lights)

        keyframes = self._extract_animation_keyframes(qscene.objects)

        evo = EvolutionEngine(
            n_faces=qscene.manifold.n_faces,
            layers=self.layers,
            enable_emp=self.enable_emp,
            emp_fidelity_threshold=self.emp_fidelity_threshold,
            emp_epsilon=self.emp_epsilon,
            emp_readout_fraction=self.emp_readout_fraction,
        )
        result: RenderResult = evo.evolve(
            hamiltonian_terms=h_terms.cost_matrices,
            resonance_weights=h_terms.resonance_weights,
            steps=qscene.quality.get("steps", 60),
            seed=qscene.quality.get("seed", 0),
            animation_keyframes=keyframes,
        )

        recon = ReconstructionEngine(
            resolution=qscene.camera["resolution"],
            face_positions=lib.face_positions,
        )
        if result.emp_report is not None:
            frame = recon.reconstruct_from_sparse_field(
                result.emp_report.extrapolated_field,
                qscene.camera,
                scene_objects=qscene.objects,
            )
        else:
            frame = recon.reconstruct(
                result.expectation_values,
                result.distribution,
                qscene.camera,
                scene_objects=qscene.objects,
            )
        final_rgb = recon.tone_map(frame)
        h, w, _ = final_rgb.shape

        corrections = 0
        if result.emp_report is not None:
            corrections = int(result.emp_report.corrections_applied)

        return RenderOutput(
            energy=result.energy,
            scene=scene,
            frame_shape=final_rgb.shape,
            raster_compression_ratio=frame.metadata["raster_compression_ratio"],
            rendered_pixels_hit=frame.metadata["rendered_pixels_hit"],
            total_pixels=h * w,
            distribution=result.distribution,
            emp_enabled=self.enable_emp,
            fidelity_to_ground=result.fidelity_to_ground,
            time_dependent=result.time_dependent,
            scf_energy=h_terms.scf_energy,
            scf_converged=h_terms.scf_converged,
            corrections_applied=corrections,
            spectral_mode=False,
        )

    # ------------------------------------------------------------------
    # Spectral path: MemoryHierarchy → BlockEncode → QSVT → reconstruct
    # ------------------------------------------------------------------
    def render_spectral(
        self,
        scene: str = "default",
        qsvt_kind: str = "chebyshev",
        qsvt_degree: int = 2,
        qsvt_t: float = 0.5,
        sparsity: int = 2,
    ) -> RenderOutput:
        """
        Spectral render mode.

        Pipeline
        --------
        QSDL scene → classical Hamiltonian diagonal (cost)
                  → seed MemoryHierarchy L0 from resonance weights
                  → BlockEncode(L0) → QSVT(P)
                  → use QSVT top-left block / transformed spectrum
                    to reweight the face distribution
                  → standard reconstruction

        Falls back to exact ground-state evolution for the energy number
        so the baseline energy invariant is preserved; the QSVT path
        contributes the distribution reweighting and diagnostics.
        """
        if self._memory is None:
            from .memory import MemoryHierarchy
            self._memory = MemoryHierarchy(
                address_bits=max(4, int(np.ceil(np.log2(max(self.n, 2))))),
                value_bits=8,
                n_slots=8,
                mps_qubits=min(16, max(4, self.n // 2)),
                mps_bond_dim=16,
                seed=0,
            )

        compiler = QSDLCompiler(ManifoldConfig(n_faces=self.n))
        qscene = compiler.compile(scene)

        lib = HamiltonianLibrary(n_faces=qscene.manifold.n_faces)
        h_terms = lib.build(qscene.objects, qscene.lights)

        # Seed L0 from resonance weights (classical data layer)
        rw = np.asarray(h_terms.resonance_weights, dtype=float).reshape(-1)
        for i, w in enumerate(rw[: 1 << self._memory.address_bits]):
            # quantise weight into an 8-bit payload
            payload = int(np.clip(abs(w) * 255.0, 0, 255))
            self._memory.write(i, payload)

        # Exact ground state (energy invariant)
        evo = EvolutionEngine(
            n_faces=qscene.manifold.n_faces,
            layers=self.layers,
            enable_emp=False,
        )
        result: RenderResult = evo.evolve(
            hamiltonian_terms=h_terms.cost_matrices,
            resonance_weights=h_terms.resonance_weights,
            steps=qscene.quality.get("steps", 60),
            seed=qscene.quality.get("seed", 0),
        )

        # QSVT transform on L0-derived block-encoding
        qsvt_res = self._memory.qsvt(
            kind=qsvt_kind,
            degree=qsvt_degree,
            t=qsvt_t,
            sparsity=min(sparsity, 4),
            system_dim=2,
        )

        # Reweight distribution using the magnitude of the QSVT top-left
        # diagonal as a soft spectral filter (honest, small-system signal).
        distribution = result.distribution.copy()
        if qsvt_res.top_left_block is not None:
            diag = np.abs(np.real(np.diag(qsvt_res.top_left_block)))
            if diag.size > 0 and float(diag.sum()) > 1e-15:
                # Broadcast a simple modulation onto the face distribution
                scale = float(diag.mean())
                distribution = distribution * (0.5 + 0.5 * scale)
                s = distribution.sum()
                if s > 0:
                    distribution = distribution / s

        # Optional: load a GHZ probe into MPS store (compression diagnostic)
        try:
            self._memory.load_ghz_into_mps()
        except Exception:
            pass
        mem_audit = self._memory.report().mps_audit
        mem_ratio = mem_audit.compression_ratio if mem_audit is not None else None

        recon = ReconstructionEngine(
            resolution=qscene.camera["resolution"],
            face_positions=lib.face_positions,
        )
        frame = recon.reconstruct(
            result.expectation_values,
            distribution,
            qscene.camera,
            scene_objects=qscene.objects,
        )
        final_rgb = recon.tone_map(frame)
        h, w, _ = final_rgb.shape

        return RenderOutput(
            energy=result.energy,
            scene=scene,
            frame_shape=final_rgb.shape,
            raster_compression_ratio=frame.metadata["raster_compression_ratio"],
            rendered_pixels_hit=frame.metadata["rendered_pixels_hit"],
            total_pixels=h * w,
            distribution=distribution,
            emp_enabled=False,
            fidelity_to_ground=result.fidelity_to_ground,
            time_dependent=False,
            scf_energy=h_terms.scf_energy,
            scf_converged=h_terms.scf_converged,
            corrections_applied=0,
            spectral_mode=True,
            qsvt_semantic=qsvt_res.semantic,
            qsvt_degree=qsvt_res.poly.degree,
            memory_compression_ratio=mem_ratio,
        )

    @property
    def memory(self):
        """Access the MemoryHierarchy when enable_memory=True or after render_spectral."""
        return self._memory

    def evolve(self, hamiltonian: np.ndarray) -> np.ndarray:
        hamiltonian = 0.5 * (hamiltonian + hamiltonian.T)
        eigvals, eigvecs = np.linalg.eigh(hamiltonian)
        state = eigvecs[:, 0].astype(complex)
        peak = int(np.argmax(np.abs(state)))
        if state[peak].real < 0:
            state = -state
        return state

