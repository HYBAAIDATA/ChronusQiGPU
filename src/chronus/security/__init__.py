"""Security primitives in the Chronus reference implementation.

Includes Ed25519 signing, an experimental ML-DSA module that is NOT a conformant
FIPS 204 implementation, proof-shaped STARK checks whose soundness is not
established (see docs/claim-audit.md), KMS provider abstractions, OVID
content-addressed storage, and the AL HARAS (HYBA Security) engines. AL HARAS
results are computed exactly; see docs/security/AL_HARAS_NOTES_RECONCILIATION.md.
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
    MlDsaSigner,
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

__version__ = "36.0.1"
__all__ = [
    "MLDSASigner",
    "MlDsaSigner",
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
        self.al_haras_sovereign = ALHarasSovereignProductSDK(
            sovereign_state_id=sovereign_state_id
        )
        self.defense_coordinator = StrategicDefenseCoordinator()
        self.verify_endpoint = VerifyEndpoint(
            ml_dsa_signer=self.ml_dsa,
            ed25519_signer=self.ed25519,
            zk_stark_verifier=self.zk_stark,
            ovid_storage=self.ovid,
        )
