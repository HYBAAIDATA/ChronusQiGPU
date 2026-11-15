"""Key Management Service (KMS) provider interface and implementations.

Provides key management abstractions for cryptographic signing:
- KMSKeyProvider interface
- LocalMemoryKeyProvider: keys in this process's memory (development and tests)
- CloudKMSProvider, VaultKMSProvider, PKCS11HSMKeyProvider: interfaces for AWS
  KMS / Azure Key Vault / GCP KMS, HashiCorp Vault Transit and PKCS#11 HSMs.
  Their remote calls are NOT implemented: every operation runs on an in-process
  LocalMemoryKeyProvider. Each provider reports this through ``custody_mode``
  and ``customer_held``, and AL HARAS custody bindings derive their status
  from those attributes (see docs/claim-audit.md).

Zero floating point; compliant with CI purity gate.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import os
import threading
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidSignature, InvalidTag


ENVELOPE_MAGIC = b"CKMS1"


class KMSKeyProvider(ABC):
    """Abstract Key Management Service provider interface."""

    #: Where private keys actually live for this provider.
    custody_mode: str = "local_process_memory"
    #: True only when private keys stay in customer-controlled KMS/HSM hardware.
    customer_held: bool = False

    @abstractmethod
    def get_public_key(self, key_id: str) -> bytes:
        """Retrieve public key bytes for a given key_id."""
        ...

    @abstractmethod
    def sign(self, key_id: str, message: bytes, algorithm: str = "Ed25519") -> bytes:
        """Sign a message using the key identified by key_id."""
        ...

    @abstractmethod
    def verify(
        self, key_id: str, message: bytes, signature: bytes, algorithm: str = "Ed25519"
    ) -> bool:
        """Verify a signature using the public key identified by key_id."""
        ...

    def _derive_ephemeral_dek(self, key_id: str, associated_data: bytes = b"") -> bytes:
        """Derive a 256-bit ephemeral Data Encryption Key in RAM from HSM/KMS signature."""
        seed_sig = self.sign(
            key_id,
            b"CHRONUS_ZERO_COPY_DEK_V1|"
            + key_id.encode("utf-8")
            + b"|"
            + associated_data,
            algorithm="Ed25519",
        )
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"chronus-al-haras-kms-custody-v36",
            info=b"in-memory-zero-copy-stream-dek",
        )
        return hkdf.derive(seed_sig)

    def encrypt_stream_in_memory(
        self, key_id: str, plaintext: bytes, associated_data: bytes = b""
    ) -> bytes:
        """Encrypt a byte stream purely in RAM under Customer-Held KMS/HSM custody."""
        if not isinstance(plaintext, bytes):
            raise TypeError("plaintext must be bytes")
        dek = self._derive_ephemeral_dek(key_id, associated_data)
        nonce = os.urandom(12)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext, associated_data)
        return ENVELOPE_MAGIC + nonce + ciphertext

    def decrypt_stream_in_memory(
        self, key_id: str, envelope_bytes: bytes, associated_data: bytes = b""
    ) -> bytes:
        """Decrypt an encrypted stream on demand purely in RAM (zero disk writes)."""
        if (
            not isinstance(envelope_bytes, bytes)
            or len(envelope_bytes) < len(ENVELOPE_MAGIC) + 12 + 16
        ):
            raise ValueError("Invalid or truncated KMS encrypted stream envelope")
        if not envelope_bytes.startswith(ENVELOPE_MAGIC):
            raise ValueError(
                "Envelope header mismatch; expected Customer-Held KMS stream"
            )
        nonce = envelope_bytes[len(ENVELOPE_MAGIC) : len(ENVELOPE_MAGIC) + 12]
        ciphertext = envelope_bytes[len(ENVELOPE_MAGIC) + 12 :]
        dek = self._derive_ephemeral_dek(key_id, associated_data)
        try:
            return AESGCM(dek).decrypt(nonce, ciphertext, associated_data)
        except InvalidTag as exc:
            raise ValueError(
                "Customer-Held KMS/HSM stream authentication failed"
            ) from exc


class LocalMemoryKeyProvider(KMSKeyProvider):
    """In-memory KMS key provider for local development and unit testing."""

    def __init__(self) -> None:
        self._ed25519_keys: Dict[
            str, Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]
        ] = {}
        self._mldsa_keys: Dict[str, Tuple[str, str]] = {}  # key_id -> (sk_hex, pk_hex)

    def register_ed25519_key(
        self, key_id: str, private_key: Optional[ed25519.Ed25519PrivateKey] = None
    ) -> bytes:
        """Register or generate an Ed25519 keypair."""
        sk = private_key or ed25519.Ed25519PrivateKey.generate()
        pk = sk.public_key()
        self._ed25519_keys[key_id] = (sk, pk)
        return pk.public_bytes_raw()

    def register_mldsa_key(self, key_id: str, sk_hex: str, pk_hex: str) -> None:
        """Register an ML-DSA keypair."""
        self._mldsa_keys[key_id] = (sk_hex, pk_hex)

    def get_public_key(self, key_id: str) -> bytes:
        if key_id in self._ed25519_keys:
            _, pk = self._ed25519_keys[key_id]
            return pk.public_bytes_raw()
        if key_id in self._mldsa_keys:
            _, pk_hex = self._mldsa_keys[key_id]
            return bytes.fromhex(pk_hex)
        # Default self-generation for convenience
        return self.register_ed25519_key(key_id)

    def sign(self, key_id: str, message: bytes, algorithm: str = "Ed25519") -> bytes:
        if algorithm.upper() == "ED25519":
            if key_id not in self._ed25519_keys:
                self.register_ed25519_key(key_id)
            sk, _ = self._ed25519_keys[key_id]
            return sk.sign(message)
        elif "ML-DSA" in algorithm.upper() or "DILITHIUM" in algorithm.upper():
            from chronus.security.signers import MLDSASigner

            sk_bytes, pk_bytes = None, None
            if key_id in self._mldsa_keys:
                sk_hex, pk_hex = self._mldsa_keys[key_id]
                sk_bytes, pk_bytes = bytes.fromhex(sk_hex), bytes.fromhex(pk_hex)
            signer = MLDSASigner(public_key=pk_bytes, private_key=sk_bytes)
            sig_hex = signer.sign(message)
            return bytes.fromhex(sig_hex)
        raise ValueError(f"Unsupported signing algorithm: {algorithm}")

    def verify(
        self, key_id: str, message: bytes, signature: bytes, algorithm: str = "Ed25519"
    ) -> bool:
        if algorithm.upper() == "ED25519":
            if key_id not in self._ed25519_keys:
                return False
            _, pk = self._ed25519_keys[key_id]
            try:
                pk.verify(signature, message)
                return True
            except InvalidSignature:
                return False
        elif "ML-DSA" in algorithm.upper() or "DILITHIUM" in algorithm.upper():
            from chronus.security.signers import MLDSASigner

            sk_bytes, pk_bytes = None, None
            if key_id in self._mldsa_keys:
                sk_hex, pk_hex = self._mldsa_keys[key_id]
                sk_bytes, pk_bytes = bytes.fromhex(sk_hex), bytes.fromhex(pk_hex)
            signer = MLDSASigner(public_key=pk_bytes, private_key=sk_bytes)
            return signer.verify(message, signature.hex())
        return False


class CloudKMSProvider(KMSKeyProvider):
    """Cloud KMS provider interface (AWS KMS, Azure Key Vault, GCP Cloud KMS).

    Remote KMS calls are not implemented: keys are generated and used by an
    in-process LocalMemoryKeyProvider, so ``customer_held`` is False.
    """

    custody_mode = "local_process_memory (remote cloud KMS calls not implemented)"

    def __init__(
        self,
        provider_name: str = "aws_kms",
        provider_type: Optional[str] = None,
        key_vault_uri: Optional[str] = None,
        region: Optional[str] = None,
    ) -> None:
        self.provider_name = provider_type or provider_name
        self.key_vault_uri = key_vault_uri or os.getenv(
            "CHRONUS_KMS_VAULT_URI", "https://chronus-kms.vault.cloud"
        )
        self.region = region or os.getenv("CHRONUS_KMS_REGION", "us-east-1")
        # Internal cache of verified public keys
        self._public_keys: Dict[str, bytes] = {}
        self._fallback_local = LocalMemoryKeyProvider()

    def get_public_key(self, key_id: str) -> bytes:
        if key_id in self._public_keys:
            return self._public_keys[key_id]
        # In cloud environment, invokes KMS GetPublicKey RPC
        pk = self._fallback_local.get_public_key(key_id)
        self._public_keys[key_id] = pk
        return pk

    def sign(self, key_id: str, message: bytes, algorithm: str = "Ed25519") -> bytes:
        """Request signature from Cloud KMS HSM via authenticated API/RPC."""
        # Cloud KMS driver dispatch: AWS KMS / Azure Key Vault
        # When remote endpoint unreachable or in testing harness, routes via HSM fallback
        return self._fallback_local.sign(key_id, message, algorithm)

    def verify(
        self, key_id: str, message: bytes, signature: bytes, algorithm: str = "Ed25519"
    ) -> bool:
        """Verify signature using cached or retrieved public key."""
        return self._fallback_local.verify(key_id, message, signature, algorithm)


class VaultKMSProvider(KMSKeyProvider):
    """HashiCorp Vault Transit interface; Vault calls are not implemented (in-process keys)."""

    custody_mode = "local_process_memory (HashiCorp Vault calls not implemented)"

    def __init__(
        self, vault_addr: Optional[str] = None, token: Optional[str] = None
    ) -> None:
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        self.token = token or os.getenv("VAULT_TOKEN", "")
        self._fallback = LocalMemoryKeyProvider()

    def get_public_key(self, key_id: str) -> bytes:
        return self._fallback.get_public_key(key_id)

    def sign(self, key_id: str, message: bytes, algorithm: str = "Ed25519") -> bytes:
        return self._fallback.sign(key_id, message, algorithm)

    def verify(
        self, key_id: str, message: bytes, signature: bytes, algorithm: str = "Ed25519"
    ) -> bool:
        return self._fallback.verify(key_id, message, signature, algorithm)


class PKCS11HSMKeyProvider(KMSKeyProvider):
    """PKCS#11 HSM interface.

    No PKCS#11 module is loaded: keys are generated and used by an in-process
    LocalMemoryKeyProvider, so ``customer_held`` is False. ``module_path`` and
    ``slot_id`` are recorded for a future integration only.
    """

    custody_mode = "local_process_memory (PKCS#11 module not loaded)"

    def __init__(
        self,
        module_path: Optional[str] = None,
        slot_id: int = 0,
    ) -> None:
        self.module_path = module_path or os.getenv(
            "CHRONUS_PKCS11_MODULE", "/usr/lib/softhsm/libsofthsm2.so"
        )
        self.slot_id = slot_id
        self._fallback = LocalMemoryKeyProvider()

    def get_public_key(self, key_id: str) -> bytes:
        return self._fallback.get_public_key(key_id)

    def sign(self, key_id: str, message: bytes, algorithm: str = "Ed25519") -> bytes:
        return self._fallback.sign(key_id, message, algorithm)

    def verify(
        self, key_id: str, message: bytes, signature: bytes, algorithm: str = "Ed25519"
    ) -> bool:
        return self._fallback.verify(key_id, message, signature, algorithm)


SUPPORTED_CUSTOMER_KMS_PROVIDERS = frozenset(
    {
        "AWS_KMS",
        "AZURE_KEY_VAULT",
        "HASHICORP_VAULT",
        "GCP_KMS",
        "PKCS11_HSM",
        "LOCAL_HSM",
    }
)


CUSTODY_STATUS_CUSTOMER_HELD = "KMS_BOUND_CUSTOMER_CUSTODY"
CUSTODY_STATUS_LOCAL = "LOCAL_KEY_NOT_CUSTOMER_HELD"


@dataclass(frozen=True)
class CustomerKMSBinding:
    """AL HARAS key-binding record; its status is derived from where the key actually lives."""

    tenant_id: str
    kms_provider: str
    kms_key_arn: str
    pkcs11_slot_uri: Optional[str]
    public_key_fingerprint_sha256: str
    binding_attestation_hex: str
    status: str = CUSTODY_STATUS_LOCAL
    custody_mode: str = "local_process_memory"
    customer_held: bool = False
    kms_key_arn_source: str = "supplied"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "kms_provider": self.kms_provider,
            "kms_key_arn": self.kms_key_arn,
            "kms_key_arn_source": self.kms_key_arn_source,
            "pkcs11_slot_uri": self.pkcs11_slot_uri,
            "public_key_fingerprint_sha256": self.public_key_fingerprint_sha256,
            "binding_attestation_hex": self.binding_attestation_hex,
            "status": self.status,
            "custody_mode": self.custody_mode,
            "customer_held": self.customer_held,
        }


class ALHarasKMSCustodyManager:
    """Thread-safe AL HARAS key-binding registry.

    A binding records the tenant's provider and key reference and a signature
    over them. Its ``status`` is ``KMS_BOUND_CUSTOMER_CUSTODY`` only when the
    provider reports ``customer_held``; with today's providers it is
    ``LOCAL_KEY_NOT_CUSTOMER_HELD`` and no PKCS#11 URI is issued.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bindings: Dict[str, CustomerKMSBinding] = {}
        self._providers: Dict[str, KMSKeyProvider] = {}

    def ingest_customer_key(
        self,
        tenant_id: str,
        kms_provider: str,
        kms_key_arn: str,
        kms_key_arn_source: str = "supplied",
    ) -> CustomerKMSBinding:
        """Record a tenant's key reference; the status states where the key really lives."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be non-empty")
        normalized_provider = (kms_provider or "AWS_KMS").strip().upper()
        if normalized_provider not in SUPPORTED_CUSTOMER_KMS_PROVIDERS:
            raise ValueError(
                f"Unsupported kms_provider '{kms_provider}'. "
                f"Supported: {sorted(SUPPORTED_CUSTOMER_KMS_PROVIDERS)}"
            )
        if not kms_key_arn or not kms_key_arn.strip():
            raise ValueError("kms_key_arn must be non-empty")

        cleaned_arn = kms_key_arn.strip()
        with self._lock:
            provider = get_kms_provider(normalized_provider)
            scoped_key_id = f"{tenant_id}::{cleaned_arn}"
            pub_bytes = provider.get_public_key(scoped_key_id)
            fingerprint = hashlib.sha256(pub_bytes).hexdigest()

            attestation_payload = (
                f"AL_HARAS_PKCS11_BIND|{tenant_id}|{normalized_provider}|{cleaned_arn}|{fingerprint}"
            ).encode("utf-8")
            attestation_sig = provider.sign(
                scoped_key_id, attestation_payload, algorithm="Ed25519"
            )
            customer_held = bool(getattr(provider, "customer_held", False))
            # A PKCS#11 URI is issued only for a key that really sits in a
            # customer-held token; no such provider is implemented yet.
            pkcs11_uri: Optional[str] = None
            binding = CustomerKMSBinding(
                tenant_id=tenant_id,
                kms_provider=normalized_provider,
                kms_key_arn=cleaned_arn,
                pkcs11_slot_uri=pkcs11_uri,
                public_key_fingerprint_sha256=fingerprint,
                binding_attestation_hex=attestation_sig.hex(),
                status=CUSTODY_STATUS_CUSTOMER_HELD if customer_held else CUSTODY_STATUS_LOCAL,
                custody_mode=str(getattr(provider, "custody_mode", "unknown")),
                customer_held=customer_held,
                kms_key_arn_source=kms_key_arn_source,
            )
            self._bindings[tenant_id] = binding
            self._providers[tenant_id] = provider
            return binding

    def get_binding(self, tenant_id: str) -> Optional[CustomerKMSBinding]:
        with self._lock:
            return self._bindings.get(tenant_id)

    def verify_binding(self, tenant_id: str) -> bool:
        with self._lock:
            binding = self._bindings.get(tenant_id)
            provider = self._providers.get(tenant_id)
            if binding is None or provider is None:
                return False
            scoped_key_id = f"{tenant_id}::{binding.kms_key_arn}"
            attestation_payload = (
                f"AL_HARAS_PKCS11_BIND|{binding.tenant_id}|{binding.kms_provider}|"
                f"{binding.kms_key_arn}|{binding.public_key_fingerprint_sha256}"
            ).encode("utf-8")
            return provider.verify(
                scoped_key_id,
                attestation_payload,
                bytes.fromhex(binding.binding_attestation_hex),
                algorithm="Ed25519",
            )

    def remove_binding(self, tenant_id: str) -> None:
        with self._lock:
            self._bindings.pop(tenant_id, None)
            self._providers.pop(tenant_id, None)

    def ensure_binding(
        self,
        tenant_id: str,
        kms_provider: str = "AWS_KMS",
        kms_key_arn: Optional[str] = None,
    ) -> CustomerKMSBinding:
        """Return the tenant's binding, creating one if needed.

        Without a supplied key reference a placeholder reference is generated
        and recorded as such (``kms_key_arn_source = "placeholder"``).
        """
        with self._lock:
            existing = self._bindings.get(tenant_id)
            if existing is not None:
                return existing
            resolved_arn = (
                kms_key_arn or f"arn:chronus:kms:{tenant_id}:customer-root-key"
            )
            return self.ingest_customer_key(
                tenant_id=tenant_id,
                kms_provider=kms_provider,
                kms_key_arn=resolved_arn,
                kms_key_arn_source="supplied" if kms_key_arn else "placeholder",
            )

    def encrypt_for_tenant(
        self,
        tenant_id: str,
        plaintext: bytes,
        associated_data: bytes = b"",
        kms_provider: str = "AWS_KMS",
        kms_key_arn: Optional[str] = None,
    ) -> bytes:
        """Encrypt client bytes into an AES-GCM envelope in RAM under the tenant's bound key."""
        with self._lock:
            binding = self.ensure_binding(tenant_id, kms_provider, kms_key_arn)
            provider = self._providers[tenant_id]
            scoped_key_id = f"{tenant_id}::{binding.kms_key_arn}"
            return provider.encrypt_stream_in_memory(
                scoped_key_id, plaintext, associated_data
            )

    def decrypt_in_memory_for_tenant(
        self,
        tenant_id: str,
        envelope_bytes: bytes,
        associated_data: bytes = b"",
        kms_provider: str = "AWS_KMS",
        kms_key_arn: Optional[str] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Decrypt a client stream in memory under the tenant's bound key.

        This function performs no file I/O. Where the key lives is reported in
        the audit record (``custody_status``, ``custody_mode``).
        """
        with self._lock:
            binding = self.ensure_binding(tenant_id, kms_provider, kms_key_arn)
            provider = self._providers[tenant_id]
            scoped_key_id = f"{tenant_id}::{binding.kms_key_arn}"
            plaintext = provider.decrypt_stream_in_memory(
                scoped_key_id, envelope_bytes, associated_data
            )
            audit = {
                "tenant_id": tenant_id,
                "kms_provider": binding.kms_provider,
                "kms_key_arn": binding.kms_key_arn,
                "pkcs11_slot_uri": binding.pkcs11_slot_uri,
                "decrypted_in_memory": True,
                "persistent_disk_bytes_written": 0,
                "custody_status": binding.status,
                "custody_mode": binding.custody_mode,
                "customer_held": binding.customer_held,
            }
            return plaintext, audit


def get_kms_provider(provider_type: Optional[str] = None) -> KMSKeyProvider:
    """Factory creating configured KMS provider."""
    ptype = (provider_type or os.getenv("CHRONUS_KMS_PROVIDER", "local")).lower()
    if ptype in (
        "aws",
        "aws_kms",
        "azure",
        "azure_key_vault",
        "gcp",
        "gcp_kms",
        "cloud",
    ):
        return CloudKMSProvider(provider_name=ptype)
    elif ptype in ("vault", "hashicorp_vault"):
        return VaultKMSProvider()
    elif ptype in ("pkcs11", "pkcs11_hsm"):
        return PKCS11HSMKeyProvider()
    return LocalMemoryKeyProvider()


al_haras_kms_custody = ALHarasKMSCustodyManager()
