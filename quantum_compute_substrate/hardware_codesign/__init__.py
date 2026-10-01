"""
Hardware co-design specifications for the φ-resonance substrate.

Contains architecture-exploration models for four target backends:
    - fpga_spec.py:        FPGA kernel specs (Xilinx / Intel Agilex)
    - asic_design.py:      φ-scaled tensor core ASIC exploration
    - photonic.py:          Silicon-photonic φ-fold model
    - neuromorphic.py:      Neuromorphic hybrid (Loihi 2 / SpiNNaker) model

All modules are *specifications and simulators*, not tape-outs. Claim lane
MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC).
"""

from .fpga_spec import FPGAKernelSpec
from .asic_design import PhiScaledTensorCoreASIC
from .photonic import PhotonicPhiFold
from .neuromorphic import NeuromorphicHybrid
