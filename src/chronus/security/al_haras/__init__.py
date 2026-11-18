"""
AL HARAS — HYBA Security.

Motto from the product notes: "Speak friend and enter or you shall not pass."
"We are not building a bigger lock. We are removing the door, changing the topology."

What the package computes (see docs/security/AL_HARAS_NOTES_RECONCILIATION.md):
exact cellular-sheaf consistency checks with residual location and repair,
Reed-Solomon trace repair over GF(257), an exactly certified Paley expander,
exact Fibonacci braid relations over Z[zeta_5], an elliptic-curve payload
fingerprint, and decision receipts signed with both Ed25519 and ML-DSA-87
(FIPS 204). Older module names that use
gauge-theory or "Millennium" vocabulary are kept for compatibility; their
docstrings state the mechanism actually implemented. Nothing in this package
establishes certification, deployment, or hardware behaviour.
"""

from chronus.security.al_haras import (
    braids,
    expander,
    fingerprint,
    golden,
    reed_solomon,
)
from chronus.security.al_haras.receipts import ReceiptSigner, signed_receipt
from chronus.security.al_haras.sheaf import GraphSheaf, SheafError, analyse_states
from chronus.security.al_haras.engine import (
    CyclotomicZ5,
    CellularSheafCohomology,
    DSW4DInstantonMonopoleHealer,
    RamanujanExpanderSpectralGapGuard,
    CyclotomicAnyonBraidEngine,
    HeckeModularChecksum,
    ALHarasSecurityFabric,
)
from chronus.security.al_haras.sovereign import (
    ExactQ5,
    GaloisField257Phi,
    SovereignGovernanceEngine,
    ALHarasSovereignProductSDK,
)
from chronus.security.al_haras.topological_os import (
    ALHarasTopologicalKernel,
    ALHarasSovereignOSProduct,
)
from chronus.security.al_haras.defense_frontiers import (
    TacticalSwarmMeshEngine,
    PostQuantumSubstrateEngine,
    HyperscaleDefenseSimulationEngine,
    CNISelfHealingEngine,
    StrategicDefenseCoordinator,
)
from chronus.security.al_haras.agentic_immune import (
    AgentNode,
    AgentNodeType,
    AgenticSheafTopology,
    AgenticSheafGuard,
    ThreatClassification,
    AgentDAG,
    DAGEdge,
    AgentState,
    ExecutionResult,
    AgenticSheafImmuneSystem,
    StiefelRestrictionMap,
    norm_sq,
)
from chronus.security.al_haras.hardware_t_isa import (
    TISAOpcode,
    TISAInstruction,
    TopologicalRegisterFile,
    RISCVTopologicalCoprocessor,
    TopologicalSheafFault,
    RicciCurvatureNeckFault,
    encode_t_isa_instruction,
    decode_t_isa_instruction,
    RoCCInstruction,
    CoprocessorRegisters,
    MemoryBus,
    cyclo5_poly_mul_mod_phi5,
    dsw_instanton_repair_alu,
    execute_t_isa_instruction,
    STATUS_HARMONIC_CONSENSUS,
    STATUS_FAULT,
)
from chronus.security.al_haras.orbital_mesh import (
    SatelliteNode,
    SatelliteOrbitClass,
    OrbitalConstellationMesh,
    OrbitalSatelliteDefenseMesh,
    CyclotomicBraidKnot,
    encode_cyclotomic_braid,
    verify_mac_lane_coherence,
    construct_lps_cayley_graph,
    LPSCayleyGraph,
    LPSCayleyHop,
    Status as OrbitalMeshStatus,
)
from chronus.security.al_haras.zk_neural import (
    VerifiableNeuralComputeEngine,
    NeuralLayerTrace,
    LineRateVerifiableNeuralCompute,
    forward_pass_with_trace,
    interpolate_trace_polynomial,
    compute_vanishing_polynomial_on_trace_domain,
    polynomial_divide_exact,
    generate_fri_stark_proof,
    verify_stark_quotient,
)
from chronus.security.al_haras.formal_invariants import (
    FormalTopologicalProofVerifier,
    FormalProofVerdict,
)
from chronus.security.al_haras.threshold_mpc import (
    AnyonBraidShare,
    BunkerLocation,
    TopologicalThresholdMPC,
)
from chronus.security.al_haras.sovereign_settlement import (
    SovereignCentralBank,
    SovereignTransferSimplex,
    HomologicalSettlementEngine,
    SovereignCBDCSettlementEngine,
    Ledger1Chain,
    create_ledger_transition_chain,
    evaluate_boundary_operator_1,
    verify_hecke_eigenform_invariant,
    commit_settlement_ledger,
    SovereignSettlementRejection,
    SettlementReceipt,
)
from chronus.security.al_haras.holographic_qec import (
    HolographicNode,
    HappyTensorNetwork,
    HolographicQECEngine,
)
from chronus.security.al_haras.tempest_scrambler import (
    Matrix2x2,
    TempestEmissionScrambler,
)
from chronus.security.al_haras.autonomous_roe import (
    ROECriterion,
    EngagementSimplex,
    AutonomousROEValidator,
)
from chronus.security.al_haras.authorizer import LocalALHarasAuthorizer
from chronus.security.al_haras.millennium_security import (
    NetworkGraphEdge,
    RicciCurvatureDeCloaker,
    HodgeCovertChannelFilter,
    UltrametricMemorySandbox,
    AnosovColdBootScrambler,
    PicardLefschetzAntiJammingFilter,
)
from chronus.security.al_haras.millennium_unification import (
    SpectralDualityBridge,
    HarmonicCohomologyBridge,
    ParabolicFlowSingularityBridge,
    GrandMillenniumUnificationNexus,
)

__all__ = [
    "braids",
    "expander",
    "fingerprint",
    "golden",
    "reed_solomon",
    "ReceiptSigner",
    "signed_receipt",
    "GraphSheaf",
    "SheafError",
    "analyse_states",
    "CyclotomicZ5",
    "CellularSheafCohomology",
    "DSW4DInstantonMonopoleHealer",
    "RamanujanExpanderSpectralGapGuard",
    "CyclotomicAnyonBraidEngine",
    "HeckeModularChecksum",
    "ALHarasSecurityFabric",
    "ExactQ5",
    "GaloisField257Phi",
    "SovereignGovernanceEngine",
    "ALHarasSovereignProductSDK",
    "ALHarasTopologicalKernel",
    "ALHarasSovereignOSProduct",
    "TacticalSwarmMeshEngine",
    "PostQuantumSubstrateEngine",
    "HyperscaleDefenseSimulationEngine",
    "CNISelfHealingEngine",
    "StrategicDefenseCoordinator",
    "AgentNode",
    "AgentNodeType",
    "AgenticSheafTopology",
    "AgenticSheafGuard",
    "ThreatClassification",
    "AgentDAG",
    "DAGEdge",
    "AgentState",
    "ExecutionResult",
    "AgenticSheafImmuneSystem",
    "StiefelRestrictionMap",
    "norm_sq",
    "TISAOpcode",
    "TISAInstruction",
    "TopologicalRegisterFile",
    "RISCVTopologicalCoprocessor",
    "TopologicalSheafFault",
    "RicciCurvatureNeckFault",
    "encode_t_isa_instruction",
    "decode_t_isa_instruction",
    "RoCCInstruction",
    "CoprocessorRegisters",
    "MemoryBus",
    "cyclo5_poly_mul_mod_phi5",
    "dsw_instanton_repair_alu",
    "execute_t_isa_instruction",
    "STATUS_HARMONIC_CONSENSUS",
    "STATUS_FAULT",
    "SatelliteNode",
    "SatelliteOrbitClass",
    "OrbitalConstellationMesh",
    "OrbitalSatelliteDefenseMesh",
    "CyclotomicBraidKnot",
    "encode_cyclotomic_braid",
    "verify_mac_lane_coherence",
    "construct_lps_cayley_graph",
    "LPSCayleyGraph",
    "LPSCayleyHop",
    "OrbitalMeshStatus",
    "VerifiableNeuralComputeEngine",
    "NeuralLayerTrace",
    "LineRateVerifiableNeuralCompute",
    "forward_pass_with_trace",
    "interpolate_trace_polynomial",
    "compute_vanishing_polynomial_on_trace_domain",
    "polynomial_divide_exact",
    "generate_fri_stark_proof",
    "verify_stark_quotient",
    "FormalTopologicalProofVerifier",
    "FormalProofVerdict",
    "AnyonBraidShare",
    "BunkerLocation",
    "TopologicalThresholdMPC",
    "SovereignCentralBank",
    "SovereignTransferSimplex",
    "HomologicalSettlementEngine",
    "SovereignCBDCSettlementEngine",
    "Ledger1Chain",
    "create_ledger_transition_chain",
    "evaluate_boundary_operator_1",
    "verify_hecke_eigenform_invariant",
    "commit_settlement_ledger",
    "SovereignSettlementRejection",
    "SettlementReceipt",
    "HolographicNode",
    "HappyTensorNetwork",
    "HolographicQECEngine",
    "Matrix2x2",
    "TempestEmissionScrambler",
    "ROECriterion",
    "EngagementSimplex",
    "AutonomousROEValidator",
    "LocalALHarasAuthorizer",
    "NetworkGraphEdge",
    "RicciCurvatureDeCloaker",
    "HodgeCovertChannelFilter",
    "UltrametricMemorySandbox",
    "AnosovColdBootScrambler",
    "PicardLefschetzAntiJammingFilter",
    "SpectralDualityBridge",
    "HarmonicCohomologyBridge",
    "ParabolicFlowSingularityBridge",
    "GrandMillenniumUnificationNexus",
]
