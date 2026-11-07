"""In-process content-addressed object and receipt primitives.

The implementation is process-local; it is not a durable or distributed
storage service.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class OVIDReceipt:
    """Receipt binding an object digest to optional signature records."""

    def __init__(
        self,
        receipt_id: str,
        hash_value: str,
        ml_dsa_signature: Optional[str] = None,
        ed25519_signature: Optional[str] = None,
        timestamp: Optional[str] = None,
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.receipt_id = receipt_id
        self.hash_value = hash_value
        self.ml_dsa_signature = ml_dsa_signature
        self.ed25519_signature = ed25519_signature
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.latency_ms = latency_ms
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "hash_value": self.hash_value,
            "ml_dsa_signature": self.ml_dsa_signature,
            "ed25519_signature": self.ed25519_signature,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OVIDReceipt":
        return cls(
            receipt_id=data["receipt_id"],
            hash_value=data["hash_value"],
            ml_dsa_signature=data.get("ml_dsa_signature"),
            ed25519_signature=data.get("ed25519_signature"),
            timestamp=data.get("timestamp"),
            latency_ms=data.get("latency_ms", 0.0),
            metadata=data.get("metadata"),
        )


class OVIDStorage:
    """In-memory content-addressed byte store and receipt registry."""

    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}
        self._receipts: Dict[str, OVIDReceipt] = {}
        self._store_count = 0
        self._retrieve_count = 0

    def store(self, payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        object_id = hashlib.sha256(payload).hexdigest()
        self._store.setdefault(object_id, payload)
        self._store_count += 1
        return object_id

    def retrieve(self, ovid_id: str) -> Optional[bytes]:
        self._retrieve_count += 1
        return self._store.get(ovid_id)

    def create_receipt(
        self,
        ovid_id: str,
        ml_dsa_signature: Optional[str] = None,
        ed25519_signature: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> OVIDReceipt:
        payload = self._store.get(ovid_id)
        if payload is None or hashlib.sha256(payload).hexdigest() != ovid_id:
            raise ValueError(f"OVID ID {ovid_id} not found or invalid")
        receipt = OVIDReceipt(
            receipt_id=ovid_id,
            hash_value=ovid_id,
            ml_dsa_signature=ml_dsa_signature,
            ed25519_signature=ed25519_signature,
            latency_ms=latency_ms,
        )
        self._receipts[ovid_id] = receipt
        return receipt

    def get_receipt(self, ovid_id: str) -> Optional[OVIDReceipt]:
        return self._receipts.get(ovid_id)

    def verify_receipt(self, receipt: OVIDReceipt) -> bool:
        payload = self._store.get(receipt.receipt_id)
        return bool(
            payload is not None
            and receipt.receipt_id == receipt.hash_value
            and hashlib.sha256(payload).hexdigest() == receipt.receipt_id
            and (
                receipt.ml_dsa_signature
                or receipt.ed25519_signature
            )
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "store_count": self._store_count,
            "retrieve_count": self._retrieve_count,
            "stored_objects": len(self._store),
            "receipts": len(self._receipts),
            "content_addressable": True,
            "durable": False,
        }


class VerifyEndpoint:
    """Receipt verifier operating against a supplied object store."""

    def __init__(
        self,
        ml_dsa_signer: Any,
        ed25519_signer: Any,
        zk_stark_verifier: Any,
        ovid_storage: Optional[OVIDStorage] = None,
    ) -> None:
        self.ml_dsa_signer = ml_dsa_signer
        self.ed25519_signer = ed25519_signer
        self.zk_stark_verifier = zk_stark_verifier
        self.ovid_storage = ovid_storage or OVIDStorage()
        self._verification_count = 0
        self._zero_auth_count = 0

    def verify_receipt(self, receipt: OVIDReceipt) -> bool:
        self._verification_count += 1
        if not self.ovid_storage.verify_receipt(receipt):
            return False
        if receipt.ml_dsa_signature:
            if self.ml_dsa_signer is None or not self.ml_dsa_signer.verify(
                receipt.hash_value.encode("ascii"), receipt.ml_dsa_signature
            ):
                return False
        if receipt.ed25519_signature:
            if self.ed25519_signer is None or not self.ed25519_signer.verify(
                receipt.hash_value.encode("ascii"), receipt.ed25519_signature
            ):
                return False
        return bool(receipt.ml_dsa_signature or receipt.ed25519_signature)

    def verify_hash_zero_auth(self, hash_value: str) -> Dict[str, Any]:
        self._zero_auth_count += 1
        receipt = self.ovid_storage.get_receipt(hash_value)
        valid = receipt is not None and self.verify_receipt(receipt)
        return {
            "valid": valid,
            "hash": hash_value,
            "receipt_id": receipt.receipt_id if receipt and valid else None,
            "auth_required": False,
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_verifications": self._verification_count,
            "zero_auth_verifications": self._zero_auth_count,
        }
