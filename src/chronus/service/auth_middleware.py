"""OAuth2 / OIDC JWT Token Validation Middleware & Role-Based Access Control (RBAC).

Supports:
- Public key rotation via JSON Web Key Sets (JWKS)
- Tenant claims parsing (tenant_id / tid / sub)
- Role-Based Access Control (RBAC) with granular permission scopes
- Transparent fallback for development tokens
"""

import json
import logging
import os
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.request import Request as URLRequest, urlopen

import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class Role(str, Enum):
    """System-level RBAC roles (AL HARAS Authority)."""
    # Canonical 4 Role Tiers
    SYSTEM_ADMIN = "system_admin"
    TENANT_ADMIN = "tenant_admin"
    DEVELOPER = "developer"
    EXTERNAL_AUDITOR = "external_auditor"

    # Backward-compatible aliases
    ADMIN = "admin"
    OPERATOR = "operator"
    TENANT_USER = "tenant_user"
    AUDITOR = "auditor"


AL_HARAS_PRIVILEGES_MATRIX = {
    "system_admin": {
        "title": "System Admin",
        "persona": "Cloud Operator / Security Officer",
        "scope": "Full cluster topology control, node registration/fencing, KMS/HSM key rotation, global rate-limit policies.",
        "entitlements": "Configures 64-stream gRPC endpoints, assigns regional pods (alpha, beta, gamma, delta), manages physical vs virtual resource discovery.",
        "audit": "Accesses raw SRE metrics, OpenTelemetry traces, global audit logs, and hardware failover telemetry.",
        "allowed_endpoints": ["/v1/*", "/metrics", "/admin/*", "/v1/tenants/*", "/v1/fabric/pods"],
    },
    "tenant_admin": {
        "title": "Tenant Admin",
        "persona": "Enterprise FinOps / IT Lead",
        "scope": "Manages tenant API keys, OAuth2/OIDC SSO integration, tenant onboarding/offboarding, and secret lifecycle.",
        "entitlements": "Allocates Chronus Capacity Entitlements (CCE), configures compute/memory/storage quotas, authorizes burst capacity.",
        "audit": "Reviews tenant usage ledgers, four-part pricing breakdown (P_total), and Hermiten 25% value-share settlement reports.",
        "allowed_endpoints": ["/v1/tenants/{tenant_id}/*", "/v1/connectors/*", "/v1/workloads", "/v1/capacity", "/billing/*"],
    },
    "developer": {
        "title": "Developer / Engineer",
        "persona": "Data Scientist / ML Engineer",
        "scope": "Generates tenant-scoped API tokens (ptr_sdk_...), manages workload submission tags and task dependency graphs.",
        "entitlements": "Submits workloads across all 5 execution presets, binds ptr_ovid_ zero-copy connectors, inspects intermediate KV-caches, triggers cancellations or retries.",
        "audit": "Queries THESEUS journals, inspects OVID content-addressed blobs (o1_<hash>) and zero-copy pointers (ptr_ovid_<hash>), and retrieves execution receipts.",
        "allowed_endpoints": ["/v1/workloads", "/v1/connectors/*", "/v1/storage", "/v1/capabilities"],
    },
    "external_auditor": {
        "title": "External Auditor",
        "persona": "Zero-Auth Verifier",
        "scope": "Zero administrative access; no payload, secret, or tenant-metadata exposure.",
        "entitlements": "None (Read-only verification endpoint /verify/{receipt_hash}).",
        "audit": "Evaluates FIPS 204 ML-DSA signatures and FRI zk-STARK polynomial quotient proofs.",
        "allowed_endpoints": ["/v1/verify/*", "/verify/*"],
    },
}


class JWKSCache:
    """Thread-safe JWKS cache with automatic TTL expiration and rotation on demand."""

    def __init__(self, jwks_url: Optional[str] = None, ttl_seconds: int = 3600) -> None:
        self.jwks_url = jwks_url or os.getenv("CHRONUS_JWKS_URL")
        self.ttl_seconds = ttl_seconds
        self._keys: Dict[str, Any] = {}
        self._last_fetch = 0.0

    def get_signing_key(self, kid: Optional[str]) -> Optional[Any]:
        """Retrieve public signing key for the given kid, refreshing cache if missing."""
        now = time.monotonic()
        if not self._keys or (now - self._last_fetch > self.ttl_seconds):
            self.refresh()

        if kid and kid in self._keys:
            return self._keys[kid]

        # Key rotation scenario: kid not found in cache, attempt single immediate refresh
        if kid and self.jwks_url:
            logger.info("Key ID %s not found in JWKS cache; triggering immediate refresh for rotation", kid)
            self.refresh()
            return self._keys.get(kid)

        # Fallback to single key if only one key exists and no kid was provided
        if not kid and len(self._keys) == 1:
            return next(iter(self._keys.values()))

        return None

    def refresh(self) -> None:
        """Fetch and parse JWKS from the remote endpoint or local JSON definition."""
        raw_jwks = os.getenv("CHRONUS_STATIC_JWKS")
        if not raw_jwks and self.jwks_url:
            try:
                req = URLRequest(self.jwks_url, headers={"User-Agent": "Chronus-JWKS-Resolver/1.0"})
                with urlopen(req, timeout=10.0) as resp:
                    raw_jwks = resp.read().decode("utf-8")
            except Exception as exc:
                logger.warning("Failed to fetch JWKS from %s: %s", self.jwks_url, exc)
                return

        if not raw_jwks:
            return

        try:
            jwks_data = json.loads(raw_jwks)
            keys = jwks_data.get("keys", [])
            new_keys = {}
            for key_dict in keys:
                kid = key_dict.get("kid")
                kty = key_dict.get("kty")
                if kty == "RSA":
                    public_key = RSAAlgorithm.from_jwk(json.dumps(key_dict))
                    if kid:
                        new_keys[kid] = public_key
                elif kty == "oct":
                    # Symmetric fallback / shared secret
                    k = key_dict.get("k")
                    if kid and k:
                        new_keys[kid] = k
            self._keys = new_keys
            self._last_fetch = time.monotonic()
            logger.info("Successfully loaded %d public key(s) from JWKS", len(self._keys))
        except Exception as exc:
            logger.error("Failed to parse JWKS payload: %s", exc)


jwks_cache = JWKSCache()


class AuthenticatedIdentity:
    """Represents an authenticated principal, tenant context, and roles."""

    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        roles: Set[Role],
        claims: Dict[str, Any],
        is_jwt: bool = True,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.roles = roles
        self.claims = claims
        self.is_jwt = is_jwt

    ROLE_ALIASES = {
        Role.SYSTEM_ADMIN: {Role.ADMIN, Role.SYSTEM_ADMIN},
        Role.ADMIN: {Role.ADMIN, Role.SYSTEM_ADMIN},
        Role.TENANT_ADMIN: {Role.OPERATOR, Role.TENANT_ADMIN},
        Role.OPERATOR: {Role.OPERATOR, Role.TENANT_ADMIN},
        Role.DEVELOPER: {Role.TENANT_USER, Role.DEVELOPER},
        Role.TENANT_USER: {Role.TENANT_USER, Role.DEVELOPER},
        Role.EXTERNAL_AUDITOR: {Role.AUDITOR, Role.EXTERNAL_AUDITOR},
        Role.AUDITOR: {Role.AUDITOR, Role.EXTERNAL_AUDITOR},
    }

    def has_role(self, role: Role) -> bool:
        if Role.ADMIN in self.roles or Role.SYSTEM_ADMIN in self.roles:
            return True
        target_roles = self.ROLE_ALIASES.get(role, {role})
        return bool(self.roles.intersection(target_roles))

    def has_any_role(self, roles: Set[Role]) -> bool:
        if Role.ADMIN in self.roles or Role.SYSTEM_ADMIN in self.roles:
            return True
        expanded = set()
        for r in roles:
            expanded.update(self.ROLE_ALIASES.get(r, {r}))
        return bool(self.roles.intersection(expanded))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "roles": [r.value for r in self.roles],
            "is_jwt": self.is_jwt,
        }


class JWTValidator:
    """Validates OIDC / OAuth2 JWT bearer tokens and resolves tenant identity."""

    def __init__(
        self,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> None:
        self.audience = audience or os.getenv("CHRONUS_JWT_AUDIENCE", "chronus-api")
        self.issuer = issuer or os.getenv("CHRONUS_JWT_ISSUER")
        self.secret = secret or os.getenv("CHRONUS_JWT_SECRET", "test-secret-key-for-hmac-32bytes-chronus!!")

    def validate_token(self, token: str) -> AuthenticatedIdentity:
        """Decode and validate JWT token claims."""
        # Inspect unverified header for key rotation kid
        try:
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg", "RS256")
            kid = unverified_header.get("kid")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_token_header", "message": f"Malformed JWT header: {exc}"},
            )

        # Resolve verification key (JWKS or secret)
        verification_key = None
        if alg.startswith("HS") and self.secret:
            verification_key = self.secret
        else:
            verification_key = jwks_cache.get_signing_key(kid)

        if not verification_key and self.secret:
            verification_key = self.secret

        if not verification_key:
            # If no key was configured, allow development verification if bypass allowed
            dev_mode = os.getenv("CHRONUS_DEV_JWT_PERMISSIVE", "0") == "1"
            if dev_mode:
                claims = jwt.decode(token, options={"verify_signature": False})
                return self._build_identity(claims)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "signing_key_not_found", "message": f"No public key available for kid={kid}"},
            )

        options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_aud": bool(self.audience),
            "verify_iss": bool(self.issuer),
        }

        try:
            claims = jwt.decode(
                token,
                verification_key,
                algorithms=[alg],
                audience=self.audience if self.audience else None,
                issuer=self.issuer if self.issuer else None,
                options=options,
            )
            return self._build_identity(claims)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "token_expired", "message": "The provided access token has expired."},
            )
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_token", "message": f"Token validation failed: {exc}"},
            )

    def _build_identity(self, claims: Dict[str, Any]) -> AuthenticatedIdentity:
        # Resolve tenant_id from claims
        tenant_id = (
            claims.get("tenant_id")
            or claims.get("tid")
            or claims.get("tenant")
            or claims.get("sub")
        )
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "missing_tenant_claim", "message": "JWT does not contain a tenant identity claim."},
            )

        user_id = str(claims.get("sub", tenant_id))

        # Parse roles
        raw_roles = claims.get("roles") or claims.get("role") or claims.get("permissions") or []
        if isinstance(raw_roles, str):
            raw_roles = [r.strip() for r in raw_roles.split(",") if r.strip()]

        roles_set: Set[Role] = set()
        for r in raw_roles:
            try:
                roles_set.add(Role(r.lower()))
            except ValueError:
                # Custom scope/role
                pass

        if not roles_set:
            roles_set.add(Role.TENANT_USER)

        return AuthenticatedIdentity(
            tenant_id=str(tenant_id),
            user_id=user_id,
            roles=roles_set,
            claims=claims,
            is_jwt=True,
        )


jwt_validator = JWTValidator()


def get_current_identity(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthenticatedIdentity:
    """Dependency extracting and validating authenticated identity.
    
    Supports both modern OIDC/OAuth2 JWT tokens and legacy static tenant tokens.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_required", "message": "Authorization Bearer token required."},
        )

    token = credentials.credentials

    # Check if token is a standard JWT (3 segments separated by dots)
    if token.count(".") == 2:
        try:
            identity = jwt_validator.validate_token(token)
            request.state.identity = identity
            return identity
        except HTTPException:
            # If JWT validation fails, check if token was also registered statically
            pass

    # Check static fallback via AuthService
    from chronus.service.dependencies import auth_service
    tenant_id = auth_service.authenticate(credentials)
    if tenant_id:
        identity = AuthenticatedIdentity(
            tenant_id=tenant_id,
            user_id=f"user_{tenant_id}",
            roles={Role.TENANT_USER},
            claims={"sub": tenant_id, "tenant_id": tenant_id},
            is_jwt=False,
        )
        request.state.identity = identity
        return identity

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "invalid_credentials", "message": "Invalid token or signature."},
    )


def require_roles(*allowed_roles: Role) -> Callable:
    """FastAPI dependency enforcing Role-Based Access Control."""
    allowed_set = set(allowed_roles)

    def dependency(identity: AuthenticatedIdentity = Depends(get_current_identity)) -> AuthenticatedIdentity:
        if not identity.has_any_role(allowed_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_permissions",
                    "message": f"Requires one of roles: {[r.value for r in allowed_set]}",
                    "current_roles": [r.value for r in identity.roles],
                },
            )
        return identity

    return dependency


def create_jwt_token(
    tenant_id: str,
    user_id: str,
    role: Role | str = Role.DEVELOPER,
    secret: Optional[str] = None,
    expires_in_seconds: int = 86400,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Mint an authenticated JWT token with role claims for testing or tenant access."""
    key = secret or os.getenv("CHRONUS_JWT_SECRET", "test-secret-key-for-hmac-32bytes-chronus!!")
    now = int(time.time())
    role_str = role.value if isinstance(role, Role) else str(role)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": [role_str],
        "aud": os.getenv("CHRONUS_JWT_AUDIENCE", "chronus-api"),
        "iss": os.getenv("CHRONUS_JWT_ISSUER", "https://auth.chronus.io"),
        "iat": now,
        "nbf": now - 10,
        "exp": now + expires_in_seconds,
    }
    if additional_claims:
        payload.update(additional_claims)
    return jwt.encode(payload, key, algorithm="HS256")
