"""Regression tests: the API has no built-in JWT signing key.

The service used to fall back to a signing key written in its source code when
CHRONUS_JWT_SECRET was unset, so anyone could mint a token for any tenant with any
role (system_admin included). These tests pin the fix: without CHRONUS_JWT_SECRET
each process signs with its own random key, a token signed with the former built-in
key is refused, and the token header cannot choose an unsupported algorithm.
"""

import base64
import json
import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from chronus.service.auth_middleware import (
    JWTValidator,
    Role,
    configured_jwt_secret,
    create_jwt_token,
    get_current_identity,
)

FORMER_BUILT_IN_KEY = "test-secret-key-for-hmac-32bytes-chronus!!"
CONFIGURED_KEY = "configured-signing-key-for-tests-0123456789abcdefghijklmnop"


def _claims(**overrides):
    now = int(time.time())
    claims = {
        "sub": "user-h",
        "tenant_id": "tenant-h",
        "roles": ["system_admin"],
        "aud": "chronus-api",
        "iss": "https://auth.chronus.io",
        "iat": now,
        "nbf": now - 10,
        "exp": now + 600,
    }
    claims.update(overrides)
    return claims


def _token_with_header(header):
    def encode(part):
        return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()

    return f"{encode(header)}.{encode(_claims())}.c2lnbmF0dXJl"


def test_token_signed_with_former_built_in_key_is_refused(monkeypatch):
    monkeypatch.delenv("CHRONUS_JWT_SECRET", raising=False)
    forged = jwt.encode(_claims(), FORMER_BUILT_IN_KEY, algorithm="HS256")
    with pytest.raises(HTTPException) as ctx:
        JWTValidator().validate_token(forged)
    assert ctx.value.status_code == 401


def test_forged_admin_token_cannot_authenticate_a_request(monkeypatch):
    monkeypatch.delenv("CHRONUS_JWT_SECRET", raising=False)
    forged = jwt.encode(_claims(), FORMER_BUILT_IN_KEY, algorithm="HS256")
    request = SimpleNamespace(state=SimpleNamespace())
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=forged)
    with pytest.raises(HTTPException) as ctx:
        get_current_identity(request, credentials)
    assert ctx.value.status_code == 401
    assert not hasattr(request.state, "identity")


def test_unconfigured_process_key_is_random_and_round_trips(monkeypatch):
    monkeypatch.delenv("CHRONUS_JWT_SECRET", raising=False)
    key = configured_jwt_secret()
    assert key != FORMER_BUILT_IN_KEY
    assert len(key) >= 32
    token = create_jwt_token("tenant-r", "user-r", Role.TENANT_ADMIN)
    identity = JWTValidator().validate_token(token)
    assert identity.tenant_id == "tenant-r"
    assert identity.has_role(Role.TENANT_ADMIN)


def test_configured_secret_signs_and_verifies(monkeypatch):
    monkeypatch.setenv("CHRONUS_JWT_SECRET", CONFIGURED_KEY)
    assert configured_jwt_secret() == CONFIGURED_KEY
    token = jwt.encode(_claims(), CONFIGURED_KEY, algorithm="HS256")
    assert JWTValidator().validate_token(token).tenant_id == "tenant-h"
    minted = create_jwt_token("tenant-c", "user-c", Role.DEVELOPER)
    assert jwt.decode(minted, CONFIGURED_KEY, algorithms=["HS256"], audience="chronus-api")[
        "tenant_id"
    ] == "tenant-c"
    other = jwt.encode(_claims(), FORMER_BUILT_IN_KEY, algorithm="HS256")
    with pytest.raises(HTTPException) as ctx:
        JWTValidator().validate_token(other)
    assert ctx.value.status_code == 401


@pytest.mark.parametrize("alg", ["none", "None", "HS1", "", ["HS256"]])
def test_unsupported_algorithms_are_refused(alg):
    validator = JWTValidator(secret=CONFIGURED_KEY)
    with pytest.raises(HTTPException) as ctx:
        validator.validate_token(_token_with_header({"alg": alg, "typ": "JWT"}))
    assert ctx.value.status_code == 401
    assert ctx.value.detail["error"] == "unsupported_algorithm"
