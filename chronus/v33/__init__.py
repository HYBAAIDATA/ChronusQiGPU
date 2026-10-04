"""July ``src.chronos`` v3.3 surface — the classical graphics/research engine.

This package is the graphics Chronos: M32 manifold, QSDL, dense ground-state
solve, ray trace, and the memory/compression custody tables. It is not the
mining iGPU — the mining runtime is the ``chronus`` hardware package above it
(``chronus/opencl_host.py``, ``chronus/mla1517_platform/``). The two share only
a name; see ``docs/CHRONUS_V33_FULL_CONVERGENCE.md``.
"""

from .engine import ChronosEngine, RenderOutput
from .manifold import M32Manifold, fibonacci_sphere
from .hamiltonian import HamiltonianLibrary, HamiltonianTerms
from .evolution_engine import EvolutionEngine, RenderResult
from .reconstruction import ReconstructionEngine, Frame8K
from .qsdl_compiler import QSDLCompiler, QScene, ManifoldConfig
from .weak_measurement import WeakMeasurementSession, apply_weak_measurement, uhlmann_fidelity
from .emp import ErrorMitigationProcessor, EMPReport
from .test_harness import ChronosTestHarness
from .capability_audit import CapabilityAuditReport, audit_capability_surface, load_capability_manifest
from . import academic
from . import theory
from . import phi_scaling
from . import weak_measurement
from . import emp
from . import control
from . import environment
from . import fields
from . import graphics
from . import compression
from . import memory

__version__ = "3.3.0"
__all__ = [
    "academic",
    "theory",
    "phi_scaling",
    "emp",
    "compression",
    "memory",
    "graphics",
    "fields",
    "environment",
    "control",
    "weak_measurement",
    "ChronosEngine",
    "RenderOutput",
    "M32Manifold",
    "fibonacci_sphere",
    "HamiltonianLibrary",
    "HamiltonianTerms",
    "EvolutionEngine",
    "RenderResult",
    "ReconstructionEngine",
    "Frame8K",
    "QSDLCompiler",
    "QScene",
    "ManifoldConfig",
    "WeakMeasurementSession",
    "apply_weak_measurement",
    "uhlmann_fidelity",
    "ErrorMitigationProcessor",
    "EMPReport",
    "ChronosTestHarness",
    "CapabilityAuditReport",
    "audit_capability_surface",
    "load_capability_manifest",
]
