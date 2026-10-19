"""NEGATIVE CONTROL - deliberately defective code. Never import this.

Each function reproduces a real finding from the AL HARAS audits so that the
CI claim scanner can be proven non-vacuous. A scanner that never fires is
indistinguishable from a scanner that is switched off.

Expected detections:
  encrypt_at_rest      CRYPTO-1 (no primitive) + CRYPTO-2 (XOR)   [S5]
  _sign_attestation    CRYPTO-1 (no primitive)                    [Round 3]
  generate_keypair_pqc CRYPTO-3 (fake keypair)                    [Round 3]
  ENCRYPTION_CLAIM     CLAIM-1  (unearned AES-256-GCM string)     [S5]
"""

import hashlib
import secrets

ENCRYPTION_CLAIM = "encryption_at_rest: AES-256-GCM"


def encrypt_at_rest(data: bytes, key: bytes) -> bytes:
    """S5: claims AES-256-GCM, actually a repeating-key XOR."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _sign_attestation(payload: bytes) -> str:
    """Round 3: a 'signature' that is not a signature."""
    return f"signed::{len(payload)}"


def verify_attestation(payload: bytes, signature: str) -> bool:
    """Round 3: verification that cannot fail meaningfully."""
    return signature.startswith("signed::")


def generate_keypair_pqc() -> tuple[bytes, bytes]:
    """Round 3: public key is a hash of the private key. Not a keypair."""
    private_key = secrets.token_bytes(96)
    public_key = hashlib.sha256(private_key).digest()
    return private_key, public_key
