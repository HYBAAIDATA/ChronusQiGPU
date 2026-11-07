"""Chronus Quantum iGPU Security Layer — Post-Quantum Cryptography.

Production-ready post-quantum security with ML-DSA (FIPS 204), Ed25519,
zk-STARK FRI verification, and zero-auth verify endpoint.
"""

from chronus.security.ovid import OVIDReceipt, OVIDStorage, VerifyEndpoint
from chronus.security.signers import (
    Ed25519Signer,
    MLDSASigner,
    PostQuantumError,
    VerificationError,
)
from chronus.security.stark import ZKSTARKVerifier

__version__ = "36.0.0"
__all__ = [
    "MLDSASigner",
    "Ed25519Signer",
    "ZKSTARKVerifier",
    "VerifyEndpoint",
    "OVIDReceipt",
    "OVIDStorage",
    "SecurityContext",
    "PostQuantumError",
    "VerificationError",
]


class SecurityContext:
    """Security context for Chronus operations.

    Bundles all security components into a single context for
    convenient use across the platform.
    """

    def __init__(self) -> None:
        self.ml_dsa = MLDSASigner()
        self.ed25519 = Ed25519Signer()
        self.zk_stark = ZKSTARKVerifier()
        self.ovid = OVIDStorage()
        self.verify_endpoint = VerifyEndpoint(
            ml_dsa_signer=self.ml_dsa,
            ed25519_signer=self.ed25519,
            zk_stark_verifier=self.zk_stark,
            ovid_storage=self.ovid,
        )