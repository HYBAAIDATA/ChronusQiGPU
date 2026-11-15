import pytest
from cryptography.exceptions import InvalidSignature
from chronus.crypto.signers import Ed25519Signer, MlDsa65Signer, SignerUnavailable, ml_dsa_available, verify, ML_DSA_65_PK_SIZE, ML_DSA_65_SIG_SIZE
SEED=bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PUB=bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
SIG=bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
def test_rfc8032():
    signer=Ed25519Signer.from_private_bytes("vec", SEED)
    assert signer.public_bytes()==PUB
    assert signer.sign(b"")==SIG
    verify("Ed25519", PUB, b"", SIG)
def test_tamper():
    with pytest.raises(InvalidSignature):
        verify("Ed25519", PUB, b"tamper", SIG)
def test_ml_dsa():
    if not ml_dsa_available():
        with pytest.raises(SignerUnavailable):
            MlDsa65Signer.generate("test")
        return
    signer=MlDsa65Signer.generate("test")
    assert len(signer.public_bytes())==ML_DSA_65_PK_SIZE
    sig=signer.sign(b"receipt")
    assert len(sig)==ML_DSA_65_SIG_SIZE
    verify("ML-DSA-65", signer.public_bytes(), b"receipt", sig)
    with pytest.raises(InvalidSignature):
        verify("ML-DSA-65", signer.public_bytes(), b"altered", sig)
