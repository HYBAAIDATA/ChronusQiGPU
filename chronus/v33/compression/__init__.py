"""Large Hilbert spaces via MPS / tensor networks (no dense 2^n vectors)."""
from ..academic.tensor_compression import MatrixProductState, CompressionAudit
from .large_space import LargeHilbertSpace

__all__ = [
    "MatrixProductState",
    "CompressionAudit",
    "LargeHilbertSpace",
    "mps_tools",
    "structure_report",
    "local_expectation_contracted",
    "build_ghz_mps",
    "tebd",
    "run_tebd",
    "convergence_study_dt",
    "TEBDRunReport",
    "adaptive_dt_tebd",
    "adaptive_chi_tebd",
    "imaginary_tebd",
    "tebd_solver",
    "phi_fold",
    "fold_compress",
    "unfold_decompress",
    "fold_compress_mps_product",
    "FoldReport",
]

from . import mps_tools
from .mps_tools import structure_report, local_expectation_contracted, build_ghz_mps

from . import tebd
from .tebd import (
    run_tebd, convergence_study_dt, TEBDRunReport,
    adaptive_dt_tebd, adaptive_chi_tebd, imaginary_tebd, tebd_solver,
)

from . import phi_fold
from .phi_fold import fold_compress, unfold_decompress, fold_compress_mps_product, FoldReport
