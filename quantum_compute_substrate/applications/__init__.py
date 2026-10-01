"""
Large-scale scientific application kernels built on the φ-resonance
algebraic substrate.

Each kernel is a *reference implementation* using the substrate’s
quantum-mathematical primitives. Kernels are numerically verified against
textbook baselines, not claims of state-of-the-art domain performance.

Domains:
    - particle_physics: LHC-style event classification
    - quantum_chemistry: VQE for the H₂ molecule (Nature 549:242, 2017)
    - climate:          quantum-mathematical advection kernel
    - genomics:         quantum-mathematical Smith–Waterman alignment
"""

from .particle_physics import LHCEventClassifier
from .quantum_chemistry import H2VQE
from .climate import AdvectionKernel
from .genomics import QuantumSequenceAligner
