"""Adversarial and edge-case tests for JWT validation, RBAC, and auth services.

Complements test_auth_kms.py with attack-oriented cases: algorithm confusion,
alg=none, claim spoofing, JWKS scheme abuse, rate limiting, and static token
registration abuse.
"""

import json
import time

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from chronus.service import auth as auth_alias_module
from chronus.service.auth_middleware import (
    AuthenticatedIdentity,
    JWKSCache,
    JWTValidator,
    Role,
    create_jwt_token,
    require_roles,
)
from chronus.service.dependencies import AuthService, RateLimiter, ServiceConfig

pytestmark = pytest.mark.simulated

SECRET = "test-secret-key-for-hmac-32bytes-chronus!!"
ISSUER = "https://auth.chronus.io"
AUDIENCE = "chronus-api"


def _validator():
    return JWTValidator(audience=AUDIENCE, issuer=ISSUER, secret=SECRET)


def _payload(**overrides):
    base = {
        "sub": "user-1",
        "tenant_id": "tenant-1",
        "roles": ["developer"],
        "aud": AUDIENCE,
        "iss": ISSUER,
        "iat": int(time.time()),
        "nbf": int(time.time()) - 10,
        "exp": int(time.time()) + 600,
    }
    base.update(overrides)
    return base


def _expect_401(validator, token):
    with pytest.raises(HTTPException) as ctx:
        validator.validate_token(token)
    assert ctx.value.status_code == 401
    return ctx.value


# ---------------------------------------------------------------------------
# Algorithm attacks
# ---------------------------------------------------------------------------


def test_alg_none_token_rejected():
    """alg=none downgrade attack must never authenticate."""
    token = jwt.encode(_payload(), key=None, algorithm="none")
    _expect_401(_validator(), token)


def test_rs256_header_with_hmac_secret_rejected():
    """Algorithm confusion: RS256 header must not validate against HMAC secret."""
    token = jwt.encode(_payload(), SECRET, algorithm="HS256")
    # Re-sign header declaring RS256 while body is HMAC-signed
    header, payload, _sig = token.split(".")
    import base64

    forged_header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    forged = f"{forged_header}.{payload}.forgedsignature"
    _expect_401(_validator(), forged)


def test_hs512_header_with_hs256_secret_still_verifies_signature():
    """HS-family algorithms use the configured secret; wrong key fails."""
    token = jwt.encode(_payload(), "different-secret", algorithm="HS512")
    _expect_401(_validator(), token)


# ---------------------------------------------------------------------------
# Malformed tokens
# ---------------------------------------------------------------------------


def test_malformed_header_rejected():
    validator = _validator()
    _expect_401(validator, "not-a-jwt")
    _expect_401(validator, "a.b")
    _expect_401(validator, "!!!.@@@.###")
    _expect_401(validator, "")


def test_token_with_tampered_payload_rejected():
    token = jwt.encode(_payload(), SECRET, algorithm="HS256")
    header, payload, sig = token.split(".")
    import base64

    evil = base64.urlsafe_b64encode(
        json.dumps(_payload(roles=["system_admin"])).encode()
    ).rstrip(b"=").decode()
    _expect_401(_validator(), f"{header}.{evil}.{sig}")


# ---------------------------------------------------------------------------
# Claim validation
# ---------------------------------------------------------------------------


def test_wrong_audience_rejected():
    token = jwt.encode(_payload(aud="other-api"), SECRET, algorithm="HS256")
    exc = _expect_401(_validator(), token)
    assert exc.detail["error"] == "invalid_token"


def test_wrong_issuer_rejected():
    token = jwt.encode(
        _payload(iss="https://evil.example.com"), SECRET, algorithm="HS256"
    )
    _expect_401(_validator(), token)


def test_future_nbf_rejected():
    token = jwt.encode(
        _payload(nbf=int(time.time()) + 3600), SECRET, algorithm="HS256"
    )
    _expect_401(_validator(), token)


def test_missing_tenant_claim_rejected():
    payload = _payload()
    del payload["tenant_id"]
    payload["sub"] = ""  # empty sub cannot stand in as tenant either
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    exc = _expect_401(_validator(), token)
    assert exc.detail["error"] == "missing_tenant_claim"


def test_tid_claim_accepted_as_tenant():
    payload = _payload()
    del payload["tenant_id"]
    payload["tid"] = "tenant-via-tid"
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    identity = _validator().validate_token(token)
    assert identity.tenant_id == "tenant-via-tid"


def test_roles_as_comma_string_parsed():
    token = jwt.encode(
        _payload(roles="developer, auditor"), SECRET, algorithm="HS256"
    )
    identity = _validator().validate_token(token)
    assert Role.DEVELOPER in identity.roles
    assert Role.AUDITOR in identity.roles


def test_unknown_roles_fall_back_to_tenant_user():
    token = jwt.encode(
        _payload(roles=["superuser", "root"]), SECRET, algorithm="HS256"
    )
    identity = _validator().validate_token(token)
    assert identity.roles == {Role.TENANT_USER}


def test_create_jwt_token_roundtrip():
    token = create_jwt_token("tenant-x", "user-x", Role.TENANT_ADMIN, secret=SECRET)
    identity = _validator().validate_token(token)
    assert identity.tenant_id == "tenant-x"
    assert identity.has_role(Role.TENANT_ADMIN)


# ---------------------------------------------------------------------------
# RBAC aliasing and privilege boundaries
# ---------------------------------------------------------------------------


def test_role_aliases_are_bidirectional():
    op = AuthenticatedIdentity("t", "u", {Role.OPERATOR}, {})
    assert op.has_role(Role.TENANT_ADMIN)
    ta = AuthenticatedIdentity("t", "u", {Role.TENANT_ADMIN}, {})
    assert ta.has_role(Role.OPERATOR)


def test_developer_cannot_escalate_to_admin():
    dev = AuthenticatedIdentity("t", "u", {Role.DEVELOPER}, {})
    assert not dev.has_role(Role.ADMIN)
    assert not dev.has_role(Role.SYSTEM_ADMIN)
    assert not dev.has_any_role({Role.ADMIN, Role.TENANT_ADMIN})


def test_external_auditor_has_no_privileges():
    auditor = AuthenticatedIdentity("t", "u", {Role.EXTERNAL_AUDITOR}, {})
    assert not auditor.has_role(Role.DEVELOPER)
    assert not auditor.has_role(Role.TENANT_ADMIN)
    assert auditor.has_role(Role.AUDITOR)


def test_require_roles_dependency_forbids():
    dep = require_roles(Role.SYSTEM_ADMIN)
    dev = AuthenticatedIdentity("t", "u", {Role.DEVELOPER}, {})
    with pytest.raises(HTTPException) as ctx:
        dep(identity=dev)
    assert ctx.value.status_code == 403


def test_require_roles_dependency_allows():
    dep = require_roles(Role.DEVELOPER)
    dev = AuthenticatedIdentity("t", "u", {Role.TENANT_USER}, {})
    assert dep(identity=dev) is dev  # TENANT_USER aliases DEVELOPER


def test_identity_to_dict_shape():
    identity = AuthenticatedIdentity("t", "u", {Role.DEVELOPER}, {}, is_jwt=False)
    data = identity.to_dict()
    assert data["roles"] == ["developer"]
    assert data["is_jwt"] is False


# ---------------------------------------------------------------------------
# JWKS cache hardening
# ---------------------------------------------------------------------------


def test_jwks_refuses_non_https_url(monkeypatch):
    monkeypatch.delenv("CHRONUS_STATIC_JWKS", raising=False)
    cache = JWKSCache(jwks_url="file:///etc/passwd", ttl_seconds=0)
    cache.refresh()
    assert cache.get_signing_key("any") is None
    cache = JWKSCache(jwks_url="http://insecure.example.com/jwks", ttl_seconds=0)
    cache.refresh()
    assert cache.get_signing_key("any") is None


def test_jwks_malformed_static_payload_ignored(monkeypatch):
    monkeypatch.setenv("CHRONUS_STATIC_JWKS", "{not json")
    cache = JWKSCache(ttl_seconds=0)
    cache.refresh()
    assert cache.get_signing_key("k") is None


def test_jwks_unknown_kid_returns_none(monkeypatch):
    monkeypatch.setenv(
        "CHRONUS_STATIC_JWKS",
        json.dumps({"keys": [{"kty": "oct", "kid": "known", "k": "v"}]}),
    )
    cache = JWKSCache(ttl_seconds=3600)
    assert cache.get_signing_key("unknown-kid") is None
    assert cache.get_signing_key("known") == "v"


# ---------------------------------------------------------------------------
# AuthService / RateLimiter unit and abuse cases
# ---------------------------------------------------------------------------


def test_auth_service_static_token_authentication(monkeypatch):
    monkeypatch.setenv(
        "CHRONUS_TENANT_TOKENS", json.dumps({"tenant-a": "secret-token-a"})
    )
    svc = AuthService()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret-token-a")
    assert svc.authenticate(creds) == "tenant-a"
    bad = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong")
    assert svc.authenticate(bad) is None
    assert svc.authenticate(None) is None


def test_auth_service_rejects_malformed_tenant_tokens_env(monkeypatch):
    monkeypatch.setenv("CHRONUS_TENANT_TOKENS", "{invalid json")
    with pytest.raises(ValueError, match="JSON object"):
        AuthService()
    monkeypatch.setenv("CHRONUS_TENANT_TOKENS", json.dumps(["not", "an", "object"]))
    with pytest.raises(ValueError, match="JSON object"):
        AuthService()


def test_auth_service_register_tenant_validation(monkeypatch):
    monkeypatch.setenv("CHRONUS_TENANT_TOKENS", "{}")
    svc = AuthService()
    with pytest.raises(ValueError):
        svc.register_tenant("", "token")
    with pytest.raises(ValueError):
        svc.register_tenant("tenant", "")
    svc.register_tenant("tenant-a", "shared-token")
    with pytest.raises(ValueError, match="another tenant"):
        svc.register_tenant("tenant-b", "shared-token")


def test_rate_limiter_exhaustion():
    limiter = RateLimiter(requests_per_minute=60, burst=3)
    assert limiter.check("t1") is True
    assert limiter.check("t1") is True
    assert limiter.check("t1") is True
    assert limiter.check("t1") is False
    # Other tenants unaffected
    assert limiter.check("t2") is True


def test_rate_limiter_refills_over_time(monkeypatch):
    limiter = RateLimiter(requests_per_minute=600, burst=1)
    assert limiter.check("t1") is True
    assert limiter.check("t1") is False
    bucket = limiter._buckets["t1"]
    bucket["last_refill"] -= 1.0  # simulate one second elapsed
    assert limiter.check("t1") is True


def test_service_config_defaults():
    cfg = ServiceConfig()
    assert cfg.max_workloads_per_tenant == 1000
    assert cfg.enable_zero_auth_verify is True


# ---------------------------------------------------------------------------
# auth alias module
# ---------------------------------------------------------------------------


def test_auth_alias_module_reexports():
    assert auth_alias_module.JWTValidator is JWTValidator
    assert auth_alias_module.Role is Role
    assert hasattr(auth_alias_module, "auth_service")
    assert set(auth_alias_module.__all__) >= {
        "AuthService",
        "Role",
        "create_jwt_token",
    }
