# integration.py
# Chronos GPU -- Academic Review elevation layer (production, 4 Aug 2026)
#
# Wires the *mathematical* academic enhancements into the core render
# pipeline. Hardware-only blocks (Oxford materials/nanofab/cryogenics, ETH
# cryocoolers, MIT silicon photonics/CMOS, Tokyo Tech atomic clocks) remain
# out of scope by the quantum-from-maths doctrine.
#
# Elevation map (pseudocode → real maths in the pipeline):
#   CERN QFT      → relative QED corrections on Hamiltonian diagonal
#   CERN CavityQED → optional JC spectrum diagnostic (not dimension-matched
#                    into the manifold H; reported separately)
#   MIT control   → already inside EMP (Kalman); re-exported here
#   Caltech code  → surface-code decode on support of the distribution
#   Cambridge PINN→ residual smoother on the per-face distribution
#   Tokyo metrology → squeezed measurement-noise scale for EMP epsilon
#   NIST standards → Uhlmann fidelity of final state vs reference
#
# Default ChronosEngine behaviour is unchanged; this wrapper opts in.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..engine import RenderOutput
from ..hamiltonian import HamiltonianLibrary
from ..qsdl_compiler import QSDLCompiler, ManifoldConfig
from ..evolution_engine import EvolutionEngine
from ..reconstruction import ReconstructionEngine

from .cern import CERN_CavityQED, vacuum_polarization_fraction
from .caltech import Caltech_Surface_Code, Caltech_Ising_Anyons
from .cambridge import TinyMLP
from .tokyotech import TokyoTech_Metrology
from .nist import NIST_Standards


def apply_qed_diagonal_corrections(
    hamiltonian: np.ndarray,
    face_frequencies_hz: Optional[np.ndarray] = None,
    relative_strength: float = 1.0,
) -> np.ndarray:
    """Apply CERN QFT radiative corrections to a manifold Hamiltonian.

    The absolute Lamb shift (~GHz) is not commensurate with the dimensionless
    manifold cost scales, so corrections are applied as a *relative*
    diagonal shift of order α/(3π) (vacuum polarisation) plus a tiny
    Lamb-shaped modulation — preserving the mathematics of the pseudocode
    without swamping the scene Hamiltonian with SI-unit frequencies.
    """
    h = np.array(hamiltonian, dtype=np.float64, copy=True)
    n = h.shape[0]
    vac = vacuum_polarization_fraction()  # α/(3π) ≈ 7.7e-4
    # Relative diagonal lift proportional to |H_ii|
    diag = np.diag(h).copy()
    scale = np.maximum(np.abs(diag), 1e-12)
    if face_frequencies_hz is not None:
        freq = np.asarray(face_frequencies_hz, dtype=np.float64)[:n]
        freq = freq / (np.max(np.abs(freq)) + 1e-30)
    else:
        freq = np.linspace(0.0, 1.0, n)
    correction = relative_strength * (vac * scale + 1e-6 * scale * freq)
    h[np.diag_indices(n)] = diag + correction
    return 0.5 * (h + h.T)


def surface_code_correct_distribution(
    distribution: np.ndarray,
    distance: int = 3,
    max_weight: int = 2,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Treat the top-|support| faces as candidate X-errors on a d=3 code.

    Maps the n-face distribution onto the first n_qubits of a planar surface
    code, flags faces whose probability exceeds the mean as candidate errors,
    measures the syndrome, and applies the real brute-force decoder. Corrected
    face weights are zeroed (error removed) and the distribution renormalised.
    """
    code = Caltech_Surface_Code(distance=distance)
    n_q = code.n_qubits
    p = np.asarray(distribution, dtype=np.float64).copy()
    if p.size < n_q:
        p = np.pad(p, (0, n_q - p.size))
    p = p[:n_q]
    p = p / (p.sum() + 1e-30)
    threshold = float(p.mean() + p.std())
    error_qubits = [i for i, v in enumerate(p) if v > threshold]
    if not error_qubits:
        # No syndrome — return original (trimmed) distribution renormalised
        out = np.asarray(distribution, dtype=np.float64).copy()
        out = out / (out.sum() + 1e-30)
        return out, {"error_qubits": [], "correction": [], "logical_error": False}

    syndrome = code.measure_syndrome(error_qubits, "X")
    result = code.decode(syndrome, "X", max_weight=max_weight)
    out = np.asarray(distribution, dtype=np.float64).copy()
    for q, _typ in result.correction:
        if 0 <= q < out.size:
            out[q] = 0.0
    s = out.sum()
    if s > 0:
        out = out / s
    else:
        out = np.full_like(out, 1.0 / out.size)
    meta = {
        "error_qubits": error_qubits,
        "syndrome": syndrome,
        "correction": result.correction,
        "logical_error": result.logical_error,
    }
    return out, meta


class DistributionResidualCorrector:
    """Cambridge-style PINN residual smoother for a per-face distribution.

    Trains a small MLP to map face index → residual correction so that a
    noisy/partial field is driven toward a smooth target (here: a low-pass
    of the input). Pure numpy backprop; no external ML stack.
    """

    def __init__(self, n_faces: int, n_hidden: int = 32, seed: int = 0):
        self.n = n_faces
        self.net = TinyMLP(n_in=1, n_hidden=n_hidden, n_out=1, seed=seed)

    def fit(self, field: np.ndarray, epochs: int = 80, lr: float = 0.05) -> List[float]:
        x = np.linspace(0, 1, self.n).reshape(-1, 1)
        # Smooth target: 3-point moving average (circular)
        f = np.asarray(field, dtype=np.float64)
        target = (np.roll(f, 1) + f + np.roll(f, -1)) / 3.0
        target = target / (target.sum() + 1e-30)
        y = target.reshape(-1, 1)
        losses = []
        for _ in range(epochs):
            losses.append(self.net.train_step(x, y, lr=lr))
        return losses

    def correct(self, field: np.ndarray) -> np.ndarray:
        x = np.linspace(0, 1, self.n).reshape(-1, 1)
        pred, _ = self.net.forward(x)
        pred = np.clip(pred.reshape(-1), 0.0, None)
        # Blend: residual network proposes a smoothed field; mix with input
        f = np.asarray(field, dtype=np.float64)
        out = 0.5 * f + 0.5 * pred
        out = np.clip(out, 0.0, None)
        s = out.sum()
        return out / s if s > 0 else np.full(self.n, 1.0 / self.n)


@dataclass
class AcademicRenderOutput:
    """RenderOutput plus academic-elevation diagnostics."""
    base: RenderOutput
    qed_correction_applied: bool = False
    surface_code_meta: Optional[Dict[str, Any]] = None
    pinn_loss_final: Optional[float] = None
    nist_fidelity: Optional[float] = None
    squeezing_noise_factor: Optional[float] = None
    cavity_qed_ground_hz: Optional[float] = None
    anyon_fusion_sigma_sigma: Optional[List[str]] = None


class AcademicChronosEngine:
    """ChronosEngine elevated with academic mathematical enhancements."""

    def __init__(
        self,
        n_faces: int = 32,
        layers: int = 4,
        enable_emp: bool = True,
        enable_qed: bool = True,
        enable_surface_code: bool = True,
        enable_pinn_corrector: bool = True,
        squeezing_db: float = 10.0,
        emp_readout_fraction: float = 0.25,
    ):
        self.n = n_faces
        self.layers = layers
        self.enable_emp = enable_emp
        self.enable_qed = enable_qed
        self.enable_surface_code = enable_surface_code
        self.enable_pinn_corrector = enable_pinn_corrector
        self.squeezing_db = squeezing_db
        self.emp_readout_fraction = emp_readout_fraction
        metro = TokyoTech_Metrology()
        self._noise_factor = metro.squeezing_noise_reduction(squeezing_db)
        # Map squeezing into EMP epsilon (smaller epsilon = weaker measurement)
        self._emp_epsilon = 0.01 * self._noise_factor

    def render(self, scene: str = "default") -> AcademicRenderOutput:
        compiler = QSDLCompiler(ManifoldConfig(n_faces=self.n))
        qscene = compiler.compile(scene)

        lib = HamiltonianLibrary(n_faces=qscene.manifold.n_faces)
        h_terms = lib.build(qscene.objects, qscene.lights)
        total_h = h_terms.total_hamiltonian

        qed_applied = False
        if self.enable_qed:
            total_h = apply_qed_diagonal_corrections(total_h)
            # Rebuild cost list so evolution sees the corrected total as an extra term
            h_terms.cost_matrices = list(h_terms.cost_matrices) + [
                total_h - h_terms.total_hamiltonian
            ]
            h_terms.total_hamiltonian = total_h
            qed_applied = True

        evo = EvolutionEngine(
            n_faces=qscene.manifold.n_faces,
            layers=self.layers,
            enable_emp=self.enable_emp,
            emp_epsilon=self._emp_epsilon,
            emp_readout_fraction=self.emp_readout_fraction,
        )
        result = evo.evolve(
            hamiltonian_terms=h_terms.cost_matrices,
            resonance_weights=h_terms.resonance_weights,
            steps=qscene.quality.get("steps", 60),
            seed=qscene.quality.get("seed", 0),
        )
        distribution = result.distribution.copy()

        surface_meta = None
        if self.enable_surface_code:
            distribution, surface_meta = surface_code_correct_distribution(distribution)

        pinn_loss = None
        if self.enable_pinn_corrector:
            corr = DistributionResidualCorrector(n_faces=distribution.size, seed=qscene.quality.get("seed", 0))
            losses = corr.fit(distribution, epochs=60)
            distribution = corr.correct(distribution)
            pinn_loss = float(losses[-1]) if losses else None

        recon = ReconstructionEngine(
            resolution=qscene.camera["resolution"],
            face_positions=lib.face_positions,
        )
        if result.emp_report is not None:
            frame = recon.reconstruct_from_sparse_field(
                distribution, qscene.camera, scene_objects=qscene.objects
            )
        else:
            frame = recon.reconstruct(
                result.expectation_values, distribution, qscene.camera, scene_objects=qscene.objects
            )
        final_rgb = recon.tone_map(frame)
        h, w, _ = final_rgb.shape

        base = RenderOutput(
            energy=result.energy,
            scene=scene,
            frame_shape=final_rgb.shape,
            raster_compression_ratio=frame.metadata["raster_compression_ratio"],
            rendered_pixels_hit=frame.metadata["rendered_pixels_hit"],
            total_pixels=h * w,
            distribution=distribution,
            emp_enabled=self.enable_emp,
            fidelity_to_ground=result.fidelity_to_ground,
            time_dependent=result.time_dependent,
            scf_energy=h_terms.scf_energy,
            scf_converged=h_terms.scf_converged,
            corrections_applied=(
                int(result.emp_report.corrections_applied) if result.emp_report else 0
            ),
        )

        # NIST fidelity vs uniform reference on amplitude of distribution
        amp = np.sqrt(np.clip(distribution, 0, None)).astype(complex)
        amp = amp / (np.linalg.norm(amp) + 1e-30)
        nist_fid = NIST_Standards().validate_against_reference(amp, "uniform")

        # Lightweight JC diagnostic (small system — does not OOM)
        cavity = CERN_CavityQED(fock_dim=3, n_atoms=1)
        jc = cavity.solve()

        anyons = Caltech_Ising_Anyons()
        fusion = anyons.fuse("sigma", "sigma")

        return AcademicRenderOutput(
            base=base,
            qed_correction_applied=qed_applied,
            surface_code_meta=surface_meta,
            pinn_loss_final=pinn_loss,
            nist_fidelity=nist_fid,
            squeezing_noise_factor=self._noise_factor,
            cavity_qed_ground_hz=float(jc.eigenvalues[0]),
            anyon_fusion_sigma_sigma=fusion,
        )


def _self_test() -> str:
    src = (
        "scene academic_smoke { "
        "object sphere { geometry sphere(radius=1.0, center=(0,0,0)) "
        "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
        "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
        "camera { resolution=(64,36) fov=60.0 position=(0,0,5) } "
        "quality { layers=2 evolution_steps=12 seed=0 } "
        "}"
    )
    eng = AcademicChronosEngine(n_faces=32, layers=2, enable_emp=True)
    out = eng.render(src)
    assert out.qed_correction_applied is True
    assert out.base.rendered_pixels_hit > 0
    assert np.isclose(out.base.distribution.sum(), 1.0)
    assert out.nist_fidelity is not None and 0.0 <= out.nist_fidelity <= 1.0
    assert out.squeezing_noise_factor == 0.1  # 10 dB
    assert out.anyon_fusion_sigma_sigma == ["1", "psi"]
    assert out.cavity_qed_ground_hz is not None and np.isfinite(out.cavity_qed_ground_hz)

    # QED correction actually changes the Hamiltonian
    h0 = np.diag(np.linspace(-1, 1, 8))
    h1 = apply_qed_diagonal_corrections(h0)
    assert not np.allclose(h0, h1)

    return "academic.integration._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
