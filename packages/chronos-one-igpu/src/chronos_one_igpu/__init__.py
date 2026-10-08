from .engine import ChronosEngine, RenderOutput
from .manifold import M32Manifold, fibonacci_sphere
from .hamiltonian import HamiltonianLibrary, HamiltonianTerms
from .evolution_engine import EvolutionEngine, RenderResult
from .reconstruction import ReconstructionEngine, Frame8K
from .qsdl_compiler import QSDLCompiler, QScene, ManifoldConfig
from .test_harness import ChronosTestHarness
from . import academic
from . import theory
from . import phi_scaling
from . import igpu
from .igpu import OneIGPU, OneIGPUResult, MLAObject, PrimeDB, HostGPUPlan
from .lucas_runtime import BackendCapabilities, LucasRuntime, ReferenceLucasBackend
from .lucas_scaling import LucasTier, plan as lucas_scale_plan, tier as lucas_scale_tier
from .evidence import EvidencePack
from .adapters import AdapterRegistry, CpuAdapter, OpenCLAdapter, PipelineSpec, default_pipeline_spec
from .sparse import lucas_sparse, lucas_batch_sparse, sparse_dispatch, stream_rungs
from .certificate import ExtendedCertificate, bind_record, sign_certificate, verify_signature
from .pool import StratumJob, StratumSubmission, ShareResponse, lucas_to_stratum, bind_response
from .lucas_datapath import (DatapathConfig, DatapathFailure, JsonShareAdapter, LucasShare, MiningTarget, NonceWindow, SpatialLucasPipeline, disjoint_segments, nonce_window)
from .lucas_engine import (InvariantViolation, LucasRecord, PrimeIndexedStore, binet_exact, binet_fold, binet_unfold, fibonacci_pair, lucas, make_record, process_batch, zeckendorf_decode, zeckendorf_encode)

__version__ = "3.11.2rc3"
__all__ = [
    "academic", "igpu", "OneIGPU", "OneIGPUResult", "MLAObject", "PrimeDB", "HostGPUPlan",
    "theory",
    "phi_scaling",
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
    "ChronosTestHarness", "BackendCapabilities", "LucasRuntime", "ReferenceLucasBackend",
    "LucasTier", "lucas_scale_plan", "lucas_scale_tier",
    "EvidencePack", "AdapterRegistry", "CpuAdapter", "OpenCLAdapter", "PipelineSpec", "default_pipeline_spec",
    "lucas_sparse", "lucas_batch_sparse", "sparse_dispatch", "stream_rungs",
    "ExtendedCertificate", "bind_record", "sign_certificate", "verify_signature",
    "StratumJob", "StratumSubmission", "ShareResponse", "lucas_to_stratum", "bind_response",
    "DatapathConfig", "DatapathFailure", "JsonShareAdapter", "LucasShare",
    "MiningTarget", "NonceWindow", "SpatialLucasPipeline", "disjoint_segments", "nonce_window",
    "InvariantViolation", "LucasRecord", "PrimeIndexedStore",
    "binet_exact", "binet_fold", "binet_unfold", "fibonacci_pair",
    "lucas", "make_record", "process_batch", "zeckendorf_decode",
    "zeckendorf_encode",
]

from . import golden_quantum
from .golden_quantum import NonceLease

__all__ += ["golden_quantum", "NonceLease"]

from .family_algebra import PhiElement, FibonacciOrbit, FamilyCertificate, triple_identity
__all__ += ['PhiElement', 'FibonacciOrbit', 'FamilyCertificate', 'triple_identity']

from .igpu.structured_solver import StructuredHamiltonian, GroundState
from .pythi_native import NativePolicy, compute_receipt as compute_native_receipt, verify_receipt as verify_native_receipt
__all__ += ['StructuredHamiltonian','GroundState','NativePolicy','compute_native_receipt','verify_native_receipt']

from .igpu.resident import ResidentConfig, ResidentRuntime
from .projection_analysis import projection_contract, preimage_at, preimage_ordinal
__all__ += ["ResidentConfig","ResidentRuntime","projection_contract","preimage_at","preimage_ordinal"]
