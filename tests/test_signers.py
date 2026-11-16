"""Tests for the unified cryptographic signer API.

Ed25519 is covered by the RFC 8032 interoperability vector. ML-DSA-65 is
tested as an explicit provider: it either round-trips through the maintained
cryptography provider or fails closed as unavailable.
"""

import pytest
from cryptography.exceptions import InvalidSignature

from chronus.crypto.signers import (
    Ed25519Signer,
    MlDsa65Signer,
    SignerUnavailable,
    ml_dsa_available,
    verify,
)

SEED = bytes.fromhex(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
PUBLIC = bytes.fromhex(
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)
SIGNATURE = bytes.fromhex(
    "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555"
    "fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
)


def test_rfc8032_vector() -> None:
    signer = Ed25519Signer.from_private_bytes("rfc8032-test-1", SEED)
    assert signer.public_bytes() == PUBLIC
    assert signer.sign(b"") == SIGNATURE
    verify("Ed25519", PUBLIC, b"", SIGNATURE)


def test_tamper_is_rejected() -> None:
    signer = Ed25519Signer.from_private_bytes("tamper-test", SEED)
    signature = signer.sign(b"y")
    with pytest.raises(InvalidSignature):
        verify("Ed25519", signer.public_bytes(), b"x", signature)


def test_mldsa_provider_is_explicit() -> None:
    if not ml_dsa_available():
        with pytest.raises(SignerUnavailable):
            MlDsa65Signer.generate("mldsa-unavailable")
        return

    signer = MlDsa65Signer.generate("mldsa-test")
    signature = signer.sign(b"chronus")
    verify("ML-DSA-65", signer.public_bytes(), b"chronus", signature)
    with pytest.raises(InvalidSignature):
        verify("ML-DSA-65", signer.public_bytes(), b"tampered", signature)
