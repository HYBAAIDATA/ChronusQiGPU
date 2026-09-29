"""State-changing control requests need the operator key; without one, control is closed."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

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
    monkeypatch.setenv(control_api.ADMIN_KEY_ENV, KEY)
    monkeypatch.setenv("PYTHIA_BOOT_AUDIT", str(tmp_path / "audit.log"))
    monkeypatch.setattr(control_api, "_AUDIT", None)
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

    def post(headers):
        request = Request(
            url, data=b"{}", method="POST", headers={"Content-Type": "application/json", **headers}
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    try:
        status, body = post({})
        assert status == 401 and body["error"] == "operator key required" and calls == []
        status, body = post({"Authorization": f"Bearer {KEY}"})
        assert status == 200 and body == {"ok": True} and calls == [{}]
    finally:
        server.shutdown()
        server.server_close()
