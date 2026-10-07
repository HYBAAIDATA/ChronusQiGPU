from .engine import ChronosEngine, RenderOutput
from .manifold import M32Manifold, fibonacci_sphere
from .hamiltonian import HamiltonianLibrary, HamiltonianTerms
from .evolution_engine import EvolutionEngine, RenderResult
from .reconstruction import ReconstructionEngine, Frame8K
from .qsdl_compiler import QSDLCompiler, QScene, ManifoldConfig
from .weak_measurement import WeakMeasurementSession, apply_weak_measurement, uhlmann_fidelity
from .emp import ErrorMitigationProcessor, EMPReport
from .qx import (
    QXCommand,
    QXCommandBuffer,
    QXCommandType,
    QXExecutionReport,
    QXMemoryDomain,
    QXPipelineStage,
    QXReferenceExecutor,
    QXValidationError,
)
from .qx_bridge import QXSceneCompilation, compile_qsdl_to_qx, execute_qsdl_qx_reference
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
    "QXCommand",
    "QXCommandBuffer",
    "QXCommandType",
    "QXExecutionReport",
    "QXMemoryDomain",
    "QXPipelineStage",
    "QXReferenceExecutor",
    "QXValidationError",
    "QXSceneCompilation",
    "compile_qsdl_to_qx",
    "execute_qsdl_qx_reference",
    "ChronosTestHarness",
    "CapabilityAuditReport",
    "audit_capability_surface",
    "load_capability_manifest",
]
