"""Security regression tests for fail-closed JWT key resolution."""

import time

import jwt
import pytest
from fastapi import HTTPException

from chronus.service.auth_middleware import JWTValidator, jwks_cache

pytestmark = pytest.mark.simulated


def _signed_admin_token():
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "attacker",
            "tenant_id": "other-tenant",
            "roles": ["system_admin"],
            "aud": "chronus-api",
            "iss": "https://auth.chronus.io",
            "nbf": now - 10,
            "exp": now + 600,
        },
        "attacker-controlled-secret",
        algorithm="HS256",
    )


def test_development_permissive_flag_cannot_bypass_missing_hmac_key(monkeypatch):
    monkeypatch.setenv("CHRONUS_DEV_JWT_PERMISSIVE", "1")
    # Model the otherwise unavailable-key branch: no trusted HMAC key.
    monkeypatch.setattr(JWTValidator, "secret", property(lambda self: ""))
    validator = JWTValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate_token(_signed_admin_token())
    assert exc.value.status_code == 401
    assert exc.value.detail["error"] == "signing_key_not_found"


def test_asymmetric_algorithm_never_falls_back_to_hmac_secret(monkeypatch):
    monkeypatch.setenv("CHRONUS_DEV_JWT_PERMISSIVE", "1")
    monkeypatch.setattr(jwks_cache, "get_signing_key", lambda kid: None)
    header, payload, signature = _signed_admin_token().split(".")
    import base64
    import json

    fake_header = base64.urlsafe_b64encode(
        json.dumps({"typ": "JWT", "alg": "RS256"}).encode()
    ).rstrip(b"=").decode()
    forged = f"{fake_header}.{payload}.{signature}"
    validator = JWTValidator(secret="trusted-hmac-key")
    with pytest.raises(HTTPException) as exc:
        validator.validate_token(forged)
    assert exc.value.status_code == 401
    assert exc.value.detail["error"] == "signing_key_not_found"
