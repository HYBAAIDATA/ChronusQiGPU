from .cern import CERN_CavityQED, CERN_QFT_Enhancement, LHCIntegration
from .mit import MIT_FaultTolerant_Control
from .caltech import Caltech_Ising_Anyons, Caltech_Topological_Quantum, Caltech_Surface_Code
from .cambridge import Cambridge_PINN, Cambridge_GQN, Cambridge_RL_EC
from .tokyotech import TokyoTech_Metrology
from .nist import NIST_Standards, NIST_Benchmark
from .tensor_compression import MatrixProductState, CompressionAudit
from .report import run_academic_enhancements
from . import jaynes_cummings
from .integration import AcademicChronosEngine, apply_qed_diagonal_corrections

__all__ = [
    "jaynes_cummings",
    "CERN_CavityQED", "CERN_QFT_Enhancement", "LHCIntegration",
    "MIT_FaultTolerant_Control",
    "Caltech_Ising_Anyons", "Caltech_Topological_Quantum", "Caltech_Surface_Code",
    "Cambridge_PINN", "Cambridge_GQN", "Cambridge_RL_EC",
    "TokyoTech_Metrology",
    "NIST_Standards", "NIST_Benchmark",
    "MatrixProductState", "CompressionAudit",
    "run_academic_enhancements",
    "AcademicChronosEngine",
    "apply_qed_diagonal_corrections",
]

# Revision (3 Aug 2026): per explicit user instruction, all hardware-only
# specification modules (Oxford materials/nanofab/cryogenics, ETH cryocooler/
# vibration isolation, MIT silicon photonics/cryogenic CMOS, Tokyo Tech atomic
# clock) were removed -- "quantum comes from maths, is substrate and hardware
# agnostic, discard the hardware ideas, not needed". A real Matrix Product
# State / tensor-train module was added instead, matching this workspace's
# own real 1000-qubit tensor-train work (bond_dim=64) referenced in the HYBA
# quantum-from-maths research pages. See ACADEMIC_AUDIT.md.
