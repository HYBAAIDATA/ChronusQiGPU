import pytest

from mining.braiins_sv2 import (
    BRAIINS_AUTHORITY_KEY,
    BRAIINS_SV2_URL,
    BraiinsSv2Config,
    client_for_channel,
    normalize_identity,
)
from mining.stratum_v2 import Sv2TransportError
from tests.test_stratum_v2 import FakeSecureChannel


def test_official_url_parses_authority_key():
    cfg = BraiinsSv2Config.from_url(BRAIINS_SV2_URL, "PYTHAGORAS.PYTHIA")
    assert cfg.host == "stratum.braiins.com"
    assert cfg.port == 3333
    assert cfg.authority_key == BRAIINS_AUTHORITY_KEY
    assert cfg.user_identity == "pythagoras.PYTHIA"


def test_sv1_url_is_rejected():
    with pytest.raises(Sv2TransportError):
        BraiinsSv2Config.from_url("stratum+tcp://stratum.braiins.com:3333")


def test_missing_authority_key_rejected():
    with pytest.raises(Sv2TransportError):
        BraiinsSv2Config.from_url("stratum2+tcp://stratum.braiins.com:3333")


def test_identity_case_matches_live_authorize():
    assert normalize_identity("PYTHAGORAS.PYTHIA") == "pythagoras.PYTHIA"
    assert normalize_identity("pythagoras.PYTHIA") == "pythagoras.PYTHIA"


def test_plaintext_channel_rejected():
    ch = FakeSecureChannel()
    ch.secure = False
    with pytest.raises(Sv2TransportError, match="plaintext"):
        client_for_channel(ch)


def test_secure_channel_builds_setup_for_braiins():
    ch = FakeSecureChannel()
    client = client_for_channel(ch, BraiinsSv2Config())
    cfg = BraiinsSv2Config()
    frame = cfg.setup()
    assert frame.endpoint_host == "stratum.braiins.com"
    assert frame.endpoint_port == 3333
    assert frame.device_id == "pythagoras.PYTHIA"
    assert frame.flags == 1
    assert client is not None
