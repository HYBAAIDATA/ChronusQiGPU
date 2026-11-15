"""Canonical signed receipt chain; in-memory until THESEUS persistence is integrated."""
from __future__ import annotations
import hashlib
from dataclasses import asdict, dataclass, replace
from typing import Any
from chronus.security.canonical import canonical_bytes
from cryptography.exceptions import InvalidSignature

from chronus.crypto.signers import Ed25519Signer, verify as verify_signature

@dataclass(frozen=True)
class Receipt:
    workload_id: str
    tenant_id: str
    result_digest: str
    node_id: str
    sequence: int
    issued_at: str
    key_id: str
    version: int = 1
    prev_digest: str | None = None
    backend: str = "unknown"

    def unsigned(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        return hashlib.sha256(canonical_bytes(self.unsigned())).hexdigest()

@dataclass(frozen=True)
class SignedReceipt:
    receipt: Receipt
    digest: str
    signature: bytes

    def to_dict(self) -> dict[str, Any]:
        return {**self.receipt.unsigned(), "digest": self.digest, "signature": self.signature.hex()}

class ReceiptLog:
    def __init__(self):
        self._entries: list[SignedReceipt] = []

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def head_digest(self) -> str | None:
        return self._entries[-1].digest if self._entries else None

    def append(self, receipt: Receipt, key: Ed25519Signer) -> SignedReceipt:
        if receipt.sequence != len(self._entries):
            raise ValueError("sequence gap")
        if receipt.prev_digest != self.head_digest:
            raise ValueError("predecessor digest mismatch")
        if receipt.key_id != key.key_id:
            raise ValueError("signer key mismatch")
        digest = receipt.digest()
        signed = SignedReceipt(receipt, digest, key.sign(bytes.fromhex(digest)))
        self._entries.append(signed)
        return signed

    @staticmethod
    def verify(signed: SignedReceipt, public_key: bytes, tamper: dict[str, Any] | None = None) -> bool:
        try:
            receipt = replace(signed.receipt, **tamper) if tamper else signed.receipt
            if receipt.digest() != signed.digest:
                return False
            verify_signature("Ed25519", public_key, bytes.fromhex(signed.digest), signed.signature)
            return True
        except (ValueError, TypeError, KeyError, InvalidSignature):
            return False

    def verify_chain(self, public_key: bytes) -> tuple[bool, str]:
        previous = None
        for i, signed in enumerate(self._entries):
            if signed.receipt.sequence != i or signed.receipt.prev_digest != previous:
                return False, f"chain broken at {i}"
            if not self.verify(signed, public_key):
                return False, f"invalid signature at {i}"
            previous = signed.digest
        return True, f"{len(self._entries)} receipts verified"
