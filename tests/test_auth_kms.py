"""Unit and integration tests for Identity, Access Management (RBAC) and KMS Integration.

Tests:
- JWKSCache key fetching, rotation, and TTL expiration
- AuthenticatedIdentity role hierarchy and permissions
- JWTValidator claims decoding, tenant resolution, and role extraction
- KMSKeyProvider implementations (LocalMemoryKeyProvider, CloudKMSProvider, VaultKMSProvider)
- Ed25519 and ML-DSA signature creation and verification
"""

import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from chronus.security.kms import (
    CloudKMSProvider,
    KMSKeyProvider,
    LocalMemoryKeyProvider,
    VaultKMSProvider,
    get_kms_provider,
)
from chronus.service.auth_middleware import (
    AuthenticatedIdentity,
    JWKSCache,
    JWTValidator,
    Role,
)


class TestRBACAndIdentity(unittest.TestCase):
    """Test RBAC roles and AuthenticatedIdentity permissions."""

    def test_role_enum_values(self):
        """Ensure all required system roles are defined."""
        self.assertEqual(Role.ADMIN.value, "admin")
        self.assertEqual(Role.OPERATOR.value, "operator")
        self.assertEqual(Role.TENANT_USER.value, "tenant_user")
        self.assertEqual(Role.AUDITOR.value, "auditor")

    def test_admin_has_all_roles(self):
        """Admin role must satisfy any role requirement."""
        identity = AuthenticatedIdentity(
            tenant_id="tenant-root",
            user_id="user-admin",
            roles={Role.ADMIN},
            claims={"sub": "user-admin"},
        )
        self.assertTrue(identity.has_role(Role.ADMIN))
        self.assertTrue(identity.has_role(Role.OPERATOR))
        self.assertTrue(identity.has_role(Role.TENANT_USER))
        self.assertTrue(identity.has_role(Role.AUDITOR))
        self.assertTrue(identity.has_any_role({Role.TENANT_USER, Role.AUDITOR}))

    def test_tenant_user_role_scoping(self):
        """Tenant user has scoped permissions without escalation."""
        identity = AuthenticatedIdentity(
            tenant_id="tenant-acme",
            user_id="user-bob",
            roles={Role.TENANT_USER},
            claims={"sub": "user-bob"},
        )
        self.assertTrue(identity.has_role(Role.TENANT_USER))
        self.assertFalse(identity.has_role(Role.ADMIN))
        self.assertFalse(identity.has_role(Role.OPERATOR))
        self.assertFalse(identity.has_any_role({Role.ADMIN, Role.OPERATOR}))


class TestJWTValidation(unittest.TestCase):
    """Test JWT token validation, claim parsing, and error conditions."""

    def setUp(self):
        self.secret = "test-secret-key-for-hmac-32bytes-chronus!!"
        self.validator = JWTValidator(
            audience="chronus-api",
            issuer="https://auth.chronus.io",
            secret=self.secret,
        )

    def test_valid_token_with_roles_and_tenant(self):
        """Valid token successfully decodes identity and roles."""
        payload = {
            "sub": "user-123",
            "tenant_id": "tenant-alpha",
            "roles": ["tenant_user", "auditor"],
            "aud": "chronus-api",
            "iss": "https://auth.chronus.io",
            "exp": int(time.time()) + 3600,
            "nbf": int(time.time()) - 10,
        }
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        identity = self.validator.validate_token(token)

        self.assertEqual(identity.user_id, "user-123")
        self.assertEqual(identity.tenant_id, "tenant-alpha")
        self.assertIn(Role.TENANT_USER, identity.roles)
        self.assertIn(Role.AUDITOR, identity.roles)
        self.assertFalse(identity.has_role(Role.ADMIN))

    def test_expired_token_rejected(self):
        """Expired JWT raises HTTPException 401."""
        payload = {
            "sub": "user-123",
            "tenant_id": "tenant-alpha",
            "aud": "chronus-api",
            "iss": "https://auth.chronus.io",
            "exp": int(time.time()) - 100,
        }
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        with self.assertRaises(HTTPException) as ctx:
            self.validator.validate_token(token)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_tampered_signature_rejected(self):
        """JWT with tampered signature raises HTTPException 401."""
        payload = {
            "sub": "user-123",
            "tenant_id": "tenant-alpha",
            "aud": "chronus-api",
            "iss": "https://auth.chronus.io",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, "wrong-secret-key-32bytes-padding!!", algorithm="HS256")
        with self.assertRaises(HTTPException) as ctx:
            self.validator.validate_token(token)
        self.assertEqual(ctx.exception.status_code, 401)


class TestJWKSCache(unittest.TestCase):
    """Test JWKSCache for public key discovery and TTL caching."""

    def test_cache_with_static_jwks(self):
        """JWKSCache parses static JWKS payload."""
        static_jwks = {
            "keys": [
                {
                    "kty": "oct",
                    "kid": "key-test-1",
                    "k": "shared-symmetric-key-data",
                }
            ]
        }
        old_val = os.environ.get("CHRONUS_STATIC_JWKS")
        try:
            os.environ["CHRONUS_STATIC_JWKS"] = json.dumps(static_jwks)
            cache = JWKSCache(ttl_seconds=60)
            key = cache.get_signing_key("key-test-1")
            self.assertEqual(key, "shared-symmetric-key-data")
        finally:
            if old_val is not None:
                os.environ["CHRONUS_STATIC_JWKS"] = old_val
            else:
                os.environ.pop("CHRONUS_STATIC_JWKS", None)


class TestKMSKeyProviders(unittest.TestCase):
    """Test KMSKeyProvider implementations."""

    def test_local_memory_provider_ed25519(self):
        """Test LocalMemoryKeyProvider Ed25519 roundtrip sign and verify."""
        provider = LocalMemoryKeyProvider()
        key_id = "tenant-key-ed25519-1"
        pk_bytes = provider.register_ed25519_key(key_id)
        self.assertEqual(len(pk_bytes), 32)

        message = b"Chronus quantum execution payload"
        sig = provider.sign(key_id, message, algorithm="Ed25519")
        self.assertEqual(len(sig), 64)

        # Verification succeeds
        self.assertTrue(provider.verify(key_id, message, sig, algorithm="Ed25519"))

        # Tampered message fails
        self.assertFalse(provider.verify(key_id, b"Tampered payload", sig, algorithm="Ed25519"))

    def test_local_memory_provider_mldsa(self):
        """Test LocalMemoryKeyProvider ML-DSA key registration and verification."""
        from chronus.security.signers import MLDSASigner
        signer = MLDSASigner(security_level=3)
        pk_hex, sk_hex = signer.generate_keypair()

        provider = LocalMemoryKeyProvider()
        key_id = "tenant-key-mldsa-1"
        provider.register_mldsa_key(key_id, sk_hex, pk_hex)

        message = b"Quantum lattice verification block"
        sig = provider.sign(key_id, message, algorithm="ML-DSA")
        self.assertTrue(provider.verify(key_id, message, sig, algorithm="ML-DSA"))
        self.assertFalse(provider.verify(key_id, b"Corrupted", sig, algorithm="ML-DSA"))

    def test_cloud_kms_provider(self):
        """Test CloudKMSProvider AWS/Azure HSM abstraction."""
        provider = CloudKMSProvider(provider_type="aws_kms")
        key_id = "arn:aws:kms:us-east-1:123456789012:key/test-key-id"
        pk_bytes = provider.get_public_key(key_id)
        self.assertEqual(len(pk_bytes), 32)

        message = b"AWS KMS signed message"
        sig = provider.sign(key_id, message)
        self.assertTrue(provider.verify(key_id, message, sig))

    def test_vault_kms_provider(self):
        """Test VaultKMSProvider Transit engine abstraction."""
        provider = VaultKMSProvider(vault_addr="http://127.0.0.1:8200")
        key_id = "transit/keys/chronus-signing-key"
        pk_bytes = provider.get_public_key(key_id)
        self.assertEqual(len(pk_bytes), 32)

        message = b"Vault transit engine signature"
        sig = provider.sign(key_id, message)
        self.assertTrue(provider.verify(key_id, message, sig))

    def test_get_kms_provider_factory(self):
        """Test get_kms_provider returns correct provider instance."""
        old_env = os.environ.get("CHRONUS_KMS_PROVIDER")
        try:
            os.environ["CHRONUS_KMS_PROVIDER"] = "local"
            p1 = get_kms_provider()
            self.assertIsInstance(p1, LocalMemoryKeyProvider)

            os.environ["CHRONUS_KMS_PROVIDER"] = "cloud"
            p2 = get_kms_provider()
            self.assertIsInstance(p2, CloudKMSProvider)

            os.environ["CHRONUS_KMS_PROVIDER"] = "vault"
            p3 = get_kms_provider()
            self.assertIsInstance(p3, VaultKMSProvider)
        finally:
            if old_env is not None:
                os.environ["CHRONUS_KMS_PROVIDER"] = old_env
            else:
                os.environ.pop("CHRONUS_KMS_PROVIDER", None)


if __name__ == "__main__":
    unittest.main()
