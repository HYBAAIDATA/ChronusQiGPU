"""Security primitives in the Chronus reference implementation.

Integrates NIST FIPS 204 ML-DSA, Ed25519, FRI ZK-STARK verifier,
the AL HARAS Sovereign Topological Quantum Immunity Swarm Fabric,
and the Pentagon, GCHQ, and NATO 4-Frontier Strategic Defense Substrates.
"""

from chronus.security.ovid import (
    OVIDReceipt,
    OVIDStorage,
    OVIDZeroCopyPointer,
    POINTER_PREFIX,
    VerifyEndpoint,
)
from chronus.security.kms import (
    CloudKMSProvider,
    KMSKeyProvider,
    LocalMemoryKeyProvider,
    PKCS11HSMKeyProvider,
    VaultKMSProvider,
    al_haras_kms_custody,
    get_kms_provider,
)
from chronus.security.signers import (
    Ed25519Signer,
    MLDSASigner,
    PostQuantumError,
    VerificationError,
)
from chronus.security.stark import ZKSTARKVerifier
from chronus.security.al_haras import (
    ALHarasSecurityFabric,
    ALHarasSovereignProductSDK,
    CellularSheafCohomology,
    CyclotomicAnyonBraidEngine,
    CyclotomicZ5,
    DSW4DInstantonMonopoleHealer,
    ExactQ5,
    GaloisField257Phi,
    HeckeModularChecksum,
    RamanujanExpanderSpectralGapGuard,
    SovereignGovernanceEngine,
    ALHarasTopologicalKernel,
    ALHarasSovereignOSProduct,
    TacticalSwarmMeshEngine,
    PostQuantumSubstrateEngine,
    HyperscaleDefenseSimulationEngine,
    CNISelfHealingEngine,
    StrategicDefenseCoordinator,
)

__version__ = "36.0.0"
__all__ = [
    "MLDSASigner",
    "Ed25519Signer",
    "ZKSTARKVerifier",
    "VerifyEndpoint",
    "OVIDReceipt",
    "OVIDStorage",
    "OVIDZeroCopyPointer",
    "POINTER_PREFIX",
    "SecurityContext",
    "PostQuantumError",
    "VerificationError",
    "CloudKMSProvider",
    "KMSKeyProvider",
    "LocalMemoryKeyProvider",
    "PKCS11HSMKeyProvider",
    "VaultKMSProvider",
    "al_haras_kms_custody",
    "get_kms_provider",
    "ALHarasSecurityFabric",
    "ALHarasSovereignProductSDK",
    "CellularSheafCohomology",
    "CyclotomicAnyonBraidEngine",
    "CyclotomicZ5",
    "DSW4DInstantonMonopoleHealer",
    "ExactQ5",
    "GaloisField257Phi",
    "HeckeModularChecksum",
    "RamanujanExpanderSpectralGapGuard",
    "SovereignGovernanceEngine",
    "ALHarasTopologicalKernel",
    "ALHarasSovereignOSProduct",
    "TacticalSwarmMeshEngine",
    "PostQuantumSubstrateEngine",
    "HyperscaleDefenseSimulationEngine",
    "CNISelfHealingEngine",
    "StrategicDefenseCoordinator",
]


class SecurityContext:
    """Security context for Chronus operations.

    Bundles all security components into a single context for
    convenient use across the platform.
    """

    def __init__(self, sovereign_state_id: str = "sovereign_default") -> None:
        self.ml_dsa = MLDSASigner()
        self.ed25519 = Ed25519Signer()
        self.zk_stark = ZKSTARKVerifier()
        self.ovid = OVIDStorage()
        self.al_haras_fabric = ALHarasSecurityFabric()
        self.al_haras_sovereign = ALHarasSovereignProductSDK(sovereign_state_id=sovereign_state_id)
        self.defense_coordinator = StrategicDefenseCoordinator()
        self.verify_endpoint = VerifyEndpoint(
            ml_dsa_signer=self.ml_dsa,
            ed25519_signer=self.ed25519,
            zk_stark_verifier=self.zk_stark,
            ovid_storage=self.ovid,
        )
