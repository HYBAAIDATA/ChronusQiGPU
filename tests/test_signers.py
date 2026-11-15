from chronus.security.signers import Ed25519Signer, MlDsaSigner
import pytest
SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PUBLIC = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
SIGNATURE = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
def test_rfc8032_vector():
    signer = Ed25519Signer(SEED)
    assert signer.public_key == PUBLIC
    assert signer.sign(b"") == SIGNATURE
    assert Ed25519Signer.verify(b"", SIGNATURE, PUBLIC)
def test_tamper():
    signer = Ed25519Signer()
    assert not signer.verify(b"x", signer.sign(b"y"), signer.public_key)
def test_mldsa_unavailable():
    assert not MlDsaSigner.conformant
    with pytest.raises(NotImplementedError):
        MlDsaSigner().sign(b"x")
