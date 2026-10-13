# theory/ -- real, computable mathematics for the "unbuilt" physical
# sections (cavity arrays, cryogenics, superconductivity, photonics, anyonic
# braiding, metrology, QCD, control theory, error correction, quantum
# chemistry), per explicit instruction: "quantum comes from maths, is
# substrate and hardware agnostic" -- nothing here specifies or simulates
# physical apparatus; every function is pure, tested, hardware-agnostic math.
from . import (
    oscillator_array,
    cryogenics,
    superconductivity,
    photonics,
    anyons,
    metrology,
    qcd,
    control,
    error_correction,
    chemistry,
)
from .report import run_unbuilt_maths, self_test_all

__all__ = [
    "oscillator_array",
    "cryogenics",
    "superconductivity",
    "photonics",
    "anyons",
    "metrology",
    "qcd",
    "control",
    "error_correction",
    "chemistry",
    "run_unbuilt_maths",
    "self_test_all",
]
