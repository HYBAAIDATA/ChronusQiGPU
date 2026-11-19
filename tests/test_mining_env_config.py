"""Pool configuration must preserve hostnames before any network activity."""
import json

import pytest

from chronus.execution import mining_entrypoint as entry
from chronus.stratum.endpoint import parse_endpoint

pytestmark = pytest.mark.simulated


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    monkeypatch.setattr(entry, "_load_dotenv", lambda: None)
    monkeypatch.delenv("PYTHIA_POOL_SPECS", raising=False)
    monkeypatch.setenv("MINING_ACTIVE_POOL", "BRAIINS")
    monkeypatch.setenv("MINING_BRAIINS_USER", "example.worker")
    monkeypatch.setenv("MINING_BRAIINS_PASSWORD", "x")
    monkeypatch.delenv("MINING_BRAIINS_PORT", raising=False)


@pytest.mark.parametrize(
    "host,port,expected_host,expected_port",
    [
        ("stratum.braiins.com", "3333", "stratum.braiins.com", 3333),
        ("stratum.braiins.com\n", "443", "stratum.braiins.com", 443),
        ("stratum.braiins.com", None, "stratum.braiins.com", 3333),
        ("stratum.braiins.com:443", "3333", "stratum.braiins.com", 443),
        (
            "stratum+tcp://stratum.braiins.com",
            "3333",
            "stratum.braiins.com",
            3333,
        ),
        (
            "stratum+tcp://stratum.braiins.com:443",
            "3333",
            "stratum.braiins.com",
            443,
        ),
        ("[::1]", "3333", "::1", 3333),
        ("[::1]:443", "3333", "::1", 443),
    ],
)
def test_braiins_hostname_and_port(
    monkeypatch, host, port, expected_host, expected_port
):
    monkeypatch.setenv("MINING_BRAIINS_HOST", host)
    if port is not None:
        monkeypatch.setenv("MINING_BRAIINS_PORT", port)
    label, endpoint, user, password = entry.load_env_config()
    assert (label, endpoint.host, endpoint.port, endpoint.tls, user, password) == (
        "BRAIINS",
        expected_host,
        expected_port,
        False,
        "example.worker",
        "x",
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        ":443",
        "stratum+tcp://:443",
        "http://stratum.braiins.com:3333",
        "[::1",
        "::1",
        "stratum.braiins.com:",
        "stratum.braiins.com:not-a-port",
        "stratum.braiins.com:0",
        "stratum.braiins.com:65536",
        "user@stratum.braiins.com:3333",
        "stratum.braiins.com:3333/path",
    ],
)
def test_pool_endpoint_rejects_malformed_or_unsafe_values(endpoint):
    with pytest.raises(ValueError):
        parse_endpoint(endpoint)


def test_ipv6_endpoint_renders_with_required_brackets():
    assert str(parse_endpoint("[::1]:443")) == "stratum+tcp://[::1]:443"


def test_explicit_pool_specs_remain_highest_priority(monkeypatch):
    monkeypatch.setenv("MINING_BRAIINS_HOST", "unused.invalid")
    monkeypatch.setenv(
        "PYTHIA_POOL_SPECS",
        json.dumps(
            [
                {
                    "endpoint": "stratum+tcp://stratum.braiins.com:443",
                    "user": "spec.worker",
                }
            ]
        ),
    )
    label, endpoint, user, _ = entry.load_env_config()
    assert (label, endpoint.host, endpoint.port, user) == (
        "SPECS",
        "stratum.braiins.com",
        443,
        "spec.worker",
    )
