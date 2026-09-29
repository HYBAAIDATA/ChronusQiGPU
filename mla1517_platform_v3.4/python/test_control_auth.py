"""State-changing control requests need the operator key; without one, control is closed."""

from __future__ import annotations

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
    for name in (control_api.ADMIN_KEY_ENV, control_api.UNAUTHENTICATED_ENV):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    refusal = control_api.control_authorization(headers)
    assert (refusal[0] if refusal else None) == expected


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
