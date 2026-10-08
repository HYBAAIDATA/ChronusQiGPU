"""State-changing controls require a server-bound operator identity or legacy key."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims

import control_api

KEY = "a" * 64
CEO_TOKEN = "ceo-session-token"


@pytest.mark.parametrize(
    "env, headers, expected",
    [
        ({}, {}, HTTPStatus.FORBIDDEN),  # no key configured: closed
        ({control_api.UNAUTHENTICATED_ENV: "1"}, {}, None),  # declared dev box
        ({control_api.ADMIN_KEY_ENV: KEY}, {}, HTTPStatus.UNAUTHORIZED),
        (
            {control_api.ADMIN_KEY_ENV: KEY},
            {"Authorization": "Bearer wrong"},
            HTTPStatus.UNAUTHORIZED,
        ),
        ({control_api.ADMIN_KEY_ENV: KEY}, {"Authorization": KEY}, HTTPStatus.UNAUTHORIZED),
        ({control_api.ADMIN_KEY_ENV: KEY}, {"Authorization": f"Bearer {KEY}"}, None),
        ({control_api.ADMIN_KEY_ENV: KEY}, {"Authorization": f"bearer {KEY}"}, None),
        # A configured key wins over the dev flag.
        (
            {control_api.ADMIN_KEY_ENV: KEY, control_api.UNAUTHENTICATED_ENV: "1"},
            {},
            HTTPStatus.UNAUTHORIZED,
        ),
    ],
)
def test_the_authorization_rule(monkeypatch, env, headers, expected):
    for name in (
        control_api.ADMIN_KEY_ENV,
        control_api.UNAUTHENTICATED_ENV,
        control_api.OPERATOR_PRINCIPALS_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    refusal = control_api.control_authorization(headers)
    assert (refusal[0] if refusal else None) == expected


def _principal_map(role="ceo", digest=None):
    return json.dumps(
        {
            "andre": {
                "role": role,
                "token_sha256": digest or hashlib.sha256(CEO_TOKEN.encode()).hexdigest(),
            }
        }
    )


def test_server_principal_map_precedes_shared_key(monkeypatch):
    monkeypatch.setenv(control_api.ADMIN_KEY_ENV, KEY)
    monkeypatch.setenv(control_api.OPERATOR_PRINCIPALS_ENV, _principal_map())
    assert control_api.control_authorization({"Authorization": f"Bearer {KEY}"}) == (
        HTTPStatus.UNAUTHORIZED,
        "operator principal required",
    )
    assert control_api.control_authorization(
        {
            "Authorization": f"Bearer {KEY}",
            control_api.OPERATOR_PRINCIPAL_HEADER: "andre",
        }
    ) == (HTTPStatus.UNAUTHORIZED, "operator credential required")


def test_server_mapped_ceo_identity_is_returned(monkeypatch):
    monkeypatch.setenv(control_api.OPERATOR_PRINCIPALS_ENV, _principal_map())
    principal, refusal = control_api.authenticate_control_principal(
        {
            "Authorization": f"Bearer {CEO_TOKEN}",
            control_api.OPERATOR_PRINCIPAL_HEADER: "andre",
        }
    )
    assert refusal is None
    assert principal == control_api.ControlPrincipal(
        principal_id="andre",
        role="ceo",
        source="server_principal_map",
    )


@pytest.mark.parametrize(
    "mapping",
    [
        "{",
        "{}",
        _principal_map(role="viewer"),
        _principal_map(digest="not-a-sha256"),
    ],
)
def test_invalid_principal_mapping_fails_closed(monkeypatch, mapping):
    monkeypatch.setenv(control_api.OPERATOR_PRINCIPALS_ENV, mapping)
    refusal = control_api.control_authorization({})
    assert refusal == (
        HTTPStatus.SERVICE_UNAVAILABLE,
        "operator principal mapping is invalid",
    )


def test_a_refused_request_never_reaches_its_handler(monkeypatch, tmp_path):
    """Privileged POSTs are mediated by the guardian: the operator key alone is
    not a subscription, so only a full boundary request reaches the handler."""
    monkeypatch.setenv(control_api.ADMIN_KEY_ENV, KEY)
    monkeypatch.setenv("PYTHIA_BOOT_AUDIT", str(tmp_path / "audit.log"))
    monkeypatch.setenv("AL_HARAS_SUBSCRIPTION_KEYS", json.dumps({"test": "k" * 32}))
    monkeypatch.setenv("AL_HARAS_DATA_DIR", str(tmp_path / "al-haras"))
    monkeypatch.setattr(control_api, "_AUDIT", None)
    control_api.pythia_guardian_api.cache_clear()
    token = SubscriptionAuthority({"test": b"k" * 32}, "hyba-subscriptions").issue(
        SubscriptionClaims(
            subscription_id="sub-test",
            tenant_id="tenant-1",
            issuer="hyba-subscriptions",
            key_id="test",
            capabilities=("hyba.security",),
            actors=("operator-1",),
            not_before=0,
            expires_at=int(time.time()) + 3600,
        )
    )
    calls = []

    def stop(body):
        calls.append(body)
        return HTTPStatus.OK, {"ok": True}

    table = dict(control_api._Handler._POST_TABLE)
    table["/api/v1/mining/stop"] = stop
    monkeypatch.setattr(control_api._Handler, "_POST_TABLE", table)
    server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/api/v1/mining/stop"

    def post(headers, data=b"{}"):
        request = Request(
            url, data=data, method="POST", headers={"Content-Type": "application/json", **headers}
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    try:
        status, _ = post({})
        assert status == 400 and calls == []
        status, _ = post({"Authorization": f"Bearer {KEY}"})
        assert status == 400 and calls == []
        observation = {"observation": {"value": 1}}
        status, body = post(
            {
                "Authorization": f"Bearer {token}",
                "X-HYBA-Tenant": "tenant-1",
                "X-HYBA-Actor": "operator-1",
            },
            data=json.dumps(observation).encode("utf-8"),
        )
        assert status == 200 and body["ok"] is True and calls == [observation]
    finally:
        server.shutdown()
        server.server_close()
        control_api.pythia_guardian_api.cache_clear()


class _ControlServer:
    """Boot the real handler once; the principal map is re-read per request."""

    def __enter__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def session(self, headers):
        url = f"http://127.0.0.1:{self.server.server_address[1]}/api/v1/control/session"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read()
                return response.status, json.loads(raw), raw
        except HTTPError as exc:
            raw = exc.read()
            return exc.code, json.loads(raw), raw


def _clear_control_auth_env(monkeypatch):
    for name in (
        control_api.ADMIN_KEY_ENV,
        control_api.UNAUTHENTICATED_ENV,
        control_api.OPERATOR_PRINCIPALS_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def test_control_session_refusals(monkeypatch):
    """The session endpoint returns the auth contract's own 401/403/503."""
    _clear_control_auth_env(monkeypatch)
    with _ControlServer() as server:
        # Nothing configured anywhere: control is closed.
        status, body, _ = server.session({})
        assert status == HTTPStatus.FORBIDDEN and body["ok"] is False

        monkeypatch.setenv(control_api.OPERATOR_PRINCIPALS_ENV, _principal_map())
        # Missing credential material entirely.
        status, body, _ = server.session({})
        assert status == HTTPStatus.UNAUTHORIZED
        assert body["error"] == "operator principal required"
        # Unknown principal id.
        status, body, _ = server.session(
            {
                "Authorization": f"Bearer {CEO_TOKEN}",
                control_api.OPERATOR_PRINCIPAL_HEADER: "mallory",
            }
        )
        assert status == HTTPStatus.FORBIDDEN
        assert body["error"] == "operator principal is not authorized"
        # Known principal, wrong bearer token.
        status, body, _ = server.session(
            {
                "Authorization": "Bearer wrong-token",
                control_api.OPERATOR_PRINCIPAL_HEADER: "andre",
            }
        )
        assert status == HTTPStatus.UNAUTHORIZED
        assert body["error"] == "operator credential required"

        # An invalid server-side mapping refuses closed, not open.
        monkeypatch.setenv(control_api.OPERATOR_PRINCIPALS_ENV, "{")
        status, body, _ = server.session(
            {
                "Authorization": f"Bearer {CEO_TOKEN}",
                control_api.OPERATOR_PRINCIPAL_HEADER: "andre",
            }
        )
        assert status == HTTPStatus.SERVICE_UNAVAILABLE
        assert body["error"] == "operator principal mapping is invalid"


def test_control_session_returns_only_server_mapped_identity(monkeypatch):
    _clear_control_auth_env(monkeypatch)
    monkeypatch.setenv(control_api.ADMIN_KEY_ENV, KEY)
    with _ControlServer() as server:
        # The legacy shared key stays its mapped role — never elevated.
        status, body, raw = server.session({"Authorization": f"Bearer {KEY}"})
        assert status == HTTPStatus.OK
        assert body["principal_id"] == "legacy-admin"
        assert body["role"] == "operator"
        assert body["source"] == "legacy_admin_key"
        assert KEY.encode() not in raw

        # A server-mapped non-CEO principal reports operator, not ceo.
        monkeypatch.setenv(control_api.OPERATOR_PRINCIPALS_ENV, _principal_map(role="operator"))
        status, body, raw = server.session(
            {
                "Authorization": f"Bearer {CEO_TOKEN}",
                control_api.OPERATOR_PRINCIPAL_HEADER: "andre",
            }
        )
        assert status == HTTPStatus.OK
        assert body["principal_id"] == "andre"
        assert body["role"] == "operator"
        assert body["source"] == "server_principal_map"
        assert CEO_TOKEN.encode() not in raw

        # A server-mapped CEO is the only way role == "ceo" is reported.
        monkeypatch.setenv(control_api.OPERATOR_PRINCIPALS_ENV, _principal_map())
        status, body, raw = server.session(
            {
                "Authorization": f"Bearer {CEO_TOKEN}",
                control_api.OPERATOR_PRINCIPAL_HEADER: "andre",
            }
        )
        assert status == HTTPStatus.OK
        assert body == {
            "schema_version": body["schema_version"],
            "ok": True,
            "principal_id": "andre",
            "role": "ceo",
            "source": "server_principal_map",
            "generated_at": body["generated_at"],
        }
        assert CEO_TOKEN.encode() not in raw
