"""In-process content-addressed object and receipt primitives.

The implementation is process-local; it is not a durable or distributed
storage service.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


POINTER_PREFIX = "ptr_ovid_"


@dataclass(frozen=True)
class OVIDZeroCopyPointer:
    """Lightweight content-addressed zero-copy reference pointer (ptr_ovid_<hash>).

    Maps directly to an external data block at rest inside the client's storage
    tier and encryption boundary without staging bulk file copies.
    """

    pointer_id: str
    content_hash: str
    source_uri: str
    connector_id: str
    tenant_id: str
    byte_offset: int = 0
    byte_length: int = 0
    access_class: str = "REMOTE_REFERENCE"
    encryption_boundary: str = "CUSTOMER_KMS_ENVELOPE"
    data_stays_at_rest: bool = True
    detected_format: str = "RAW_BINARY"
    algebraic_descriptor: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if not self.pointer_id.startswith(POINTER_PREFIX):
            raise ValueError(f"pointer_id must start with '{POINTER_PREFIX}'")
        if (
            not isinstance(self.content_hash, str)
            or len(self.content_hash) != 64
            or any(c not in "0123456789abcdef" for c in self.content_hash)
        ):
            raise ValueError("content_hash must be a lowercase 64-char SHA-256 hex digest")
        if self.pointer_id != f"{POINTER_PREFIX}{self.content_hash}":
            raise ValueError("pointer_id must equal ptr_ovid_<content_hash>")
        if not isinstance(self.byte_offset, int) or isinstance(self.byte_offset, bool) or self.byte_offset < 0:
            raise ValueError("byte_offset must be a non-negative integer")
        if not isinstance(self.byte_length, int) or isinstance(self.byte_length, bool) or self.byte_length < 0:
            raise ValueError("byte_length must be a non-negative integer")
        if self.data_stays_at_rest is not True:
            raise ValueError("Zero-copy pointer invariant violated: data_stays_at_rest must be True")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pointer_id": self.pointer_id,
            "content_hash": self.content_hash,
            "source_uri": self.source_uri,
            "connector_id": self.connector_id,
            "tenant_id": self.tenant_id,
            "byte_offset": self.byte_offset,
            "byte_length": self.byte_length,
            "access_class": self.access_class,
            "encryption_boundary": self.encryption_boundary,
            "data_stays_at_rest": self.data_stays_at_rest,
            "bulk_staging_bytes": 0,
            "detected_format": self.detected_format,
            "algebraic_descriptor": self.algebraic_descriptor,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OVIDZeroCopyPointer":
        return cls(
            pointer_id=data["pointer_id"],
            content_hash=data["content_hash"],
            source_uri=data["source_uri"],
            connector_id=data["connector_id"],
            tenant_id=data["tenant_id"],
            byte_offset=data.get("byte_offset", 0),
            byte_length=data.get("byte_length", 0),
            access_class=data.get("access_class", "REMOTE_REFERENCE"),
            encryption_boundary=data.get("encryption_boundary", "CUSTOMER_KMS_ENVELOPE"),
            data_stays_at_rest=data.get("data_stays_at_rest", True),
            detected_format=data.get("detected_format", "RAW_BINARY"),
            algebraic_descriptor=data.get("algebraic_descriptor") or {},
            created_at=data.get("created_at") or datetime.now(timezone.utc).isoformat(),
        )


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
    """In-memory content-addressed byte store, zero-copy pointer map, and receipt registry."""

    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}
        self._pointers: Dict[str, OVIDZeroCopyPointer] = {}
        self._receipts: Dict[str, OVIDReceipt] = {}
        self._store_count = 0
        self._retrieve_count = 0
        self._pointer_eval_count = 0

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

    def register_zero_copy_pointer(
        self,
        *,
        content_hash: str,
        source_uri: str,
        connector_id: str,
        tenant_id: str,
        byte_offset: int = 0,
        byte_length: int = 0,
        access_class: str = "REMOTE_REFERENCE",
        encryption_boundary: str = "CUSTOMER_KMS_ENVELOPE",
        detected_format: str = "RAW_BINARY",
        algebraic_descriptor: Optional[Dict[str, Any]] = None,
    ) -> OVIDZeroCopyPointer:
        """Create and register an in-place zero-copy pointer (ptr_ovid_<hash>).

        Does not copy or stage raw payload bytes into ``self._store``.
        """
        normalized_hash = content_hash.strip().lower()
        pointer_id = f"{POINTER_PREFIX}{normalized_hash}"
        pointer = OVIDZeroCopyPointer(
            pointer_id=pointer_id,
            content_hash=normalized_hash,
            source_uri=source_uri,
            connector_id=connector_id,
            tenant_id=tenant_id,
            byte_offset=byte_offset,
            byte_length=byte_length,
            access_class=access_class,
            encryption_boundary=encryption_boundary,
            data_stays_at_rest=True,
            detected_format=detected_format,
            algebraic_descriptor=algebraic_descriptor or {},
        )
        self._pointers[pointer_id] = pointer
        return pointer

    def resolve_pointer(self, pointer_id: str) -> Optional[OVIDZeroCopyPointer]:
        """Resolve a ptr_ovid_<hash> zero-copy reference pointer."""
        self._pointer_eval_count += 1
        return self._pointers.get(pointer_id)

    def list_pointers(self, tenant_id: Optional[str] = None) -> List[OVIDZeroCopyPointer]:
        """List registered zero-copy pointers, optionally scoped by tenant."""
        if tenant_id is None:
            return list(self._pointers.values())
        return [p for p in self._pointers.values() if p.tenant_id == tenant_id]

    def create_pointer_receipt(
        self,
        pointer_id: str,
        ml_dsa_signature: Optional[str] = None,
        ed25519_signature: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> OVIDReceipt:
        """Issue an OVIDReceipt bound to an in-place zero-copy pointer."""
        pointer = self._pointers.get(pointer_id)
        if pointer is None:
            raise ValueError(f"Zero-copy pointer {pointer_id} not found")
        receipt = OVIDReceipt(
            receipt_id=pointer.pointer_id,
            hash_value=pointer.content_hash,
            ml_dsa_signature=ml_dsa_signature,
            ed25519_signature=ed25519_signature,
            latency_ms=latency_ms,
            metadata={
                "zero_copy": True,
                "source_uri": pointer.source_uri,
                "access_class": pointer.access_class,
                "data_stays_at_rest": True,
            },
        )
        self._receipts[pointer.pointer_id] = receipt
        self._receipts[pointer.content_hash] = receipt
        return receipt

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
        if receipt.receipt_id.startswith(POINTER_PREFIX):
            pointer = self._pointers.get(receipt.receipt_id)
            return bool(
                pointer is not None
                and pointer.content_hash == receipt.hash_value
                and pointer.data_stays_at_rest is True
                and (receipt.ml_dsa_signature or receipt.ed25519_signature)
            )
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
            "zero_copy_pointers": len(self._pointers),
            "pointer_evaluations": self._pointer_eval_count,
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
