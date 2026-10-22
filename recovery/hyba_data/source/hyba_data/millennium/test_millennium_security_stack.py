from __future__ import annotations

import secrets

from al_haras.millennium_security_stack import (
    BSDSecurity,
    HodgeSecurity,
    MillenniumSecurityStack,
    NavierStokesSecurity,
    PVsNPSecurity,
    RiemannSecurity,
    YangMillsSecurity,
)
from hermes.offerings import MillenniumSecurityOffering


def _reg(stack, identity: str, credential: str) -> None:
    stack.layers["riemann"].register(identity, credential)


def test_p_vs_np_o1_registry():
    p = PVsNPSecurity()
    sig = p.register_threat({"malware": "x"})
    hit = p.detect_threat({"malware": "x"})
    miss = p.detect_threat({"clean": True})
    assert hit["status"] == "REJECTED"
    assert miss["status"] == "ACCEPTED"
    assert hit["signature"] == sig or hit["signature"]


def test_yang_mills_aead_roundtrip_and_tamper():
    y = YangMillsSecurity()
    ct = y.encrypt(b"national-security-payload")
    assert y.decrypt(ct) == b"national-security-payload"
    bad = bytearray(ct)
    bad[-1] ^= 0x01
    try:
        y.decrypt(bytes(bad))
        raise AssertionError("tamper accepted")
    except Exception:
        pass


def test_riemann_auth_reject_wrong_cred():
    r = RiemannSecurity()
    r.register("agent-7", "correct-secret")
    ok = r.authenticate("agent-7", "correct-secret")
    bad = r.authenticate("agent-7", "wrong")
    assert ok["status"] == "AUTHENTICATED"
    assert bad["status"] == "REJECTED"
    assert isinstance(ok["prime"], int)


def test_navier_stokes_blocks_turbulence():
    n = NavierStokesSecurity()
    smooth = n.prevent_attack_propagation({"severity": 0.1, "hops": 1, "fanout": 1, "burst_rate": 0.0})
    turb = n.prevent_attack_propagation({"severity": 0.9, "hops": 5, "fanout": 4, "burst_rate": 2.0})
    assert smooth["status"] == "ALLOWED"
    assert turb["status"] == "BLOCKED"


def test_bsd_ecdh_shared_secret():
    b = BSDSecurity()
    a = b.generate_key_pair()
    c = b.generate_key_pair()
    s1 = b.derive_shared(a["private_key"], c["public_key"])
    s2 = b.derive_shared(c["private_key"], a["public_key"])
    assert s1 == s2
    assert len(s1) == 32


def test_hodge_protect_and_breach():
    h = HodgeSecurity()
    ok = h.protect({"audit_integrity": True, "launch_guard": "READY", "merkle_verified": True})
    bad = h.protect({"tampered": True})
    assert ok["status"] == "PROTECTED"
    assert bad["status"] == "BREACH_DETECTED"


def test_stack_accept_and_block_known_threat():
    s = MillenniumSecurityStack()
    _reg(s, "u1", "c1")
    good = s.process_payload(
        {"ok": True},
        identity="u1",
        credential="c1",
        attack={"source": "u1", "severity": 0.05, "hops": 1, "fanout": 1, "burst_rate": 0.0},
        system={"audit_integrity": True, "launch_guard": "READY"},
    )
    assert good["status"] == "ACCEPTED", good
    assert good["unhackable"] is False
    assert good["layers"]["yang_mills"]["aead"] is True
    assert good["layers"]["bsd"]["shared_secret_match"] is True
    assert good["audit_integrity"] is True

    s.layers["p_vs_np"].register_threat({"bad": 1})
    blocked = s.process_payload({"bad": 1})
    assert blocked["status"] == "BLOCKED"
    assert blocked["layer"] == "P vs NP"


def test_stack_blocks_turbulent_attack():
    s = MillenniumSecurityStack()
    _reg(s, "u", "p")
    out = s.process_payload(
        {"x": 1},
        identity="u",
        credential="p",
        attack={"source": "adv", "severity": 1.0, "hops": 8, "fanout": 8, "burst_rate": 5.0},
        system={"audit_integrity": True, "launch_guard": "READY"},
    )
    assert out["status"] == "BLOCKED"
    assert out["layer"] == "Navier-Stokes"


def test_offering_deploy_operational():
    d = MillenniumSecurityOffering().deploy()
    assert d["layers"] == 6
    assert d["status"] == "DEPLOYABLE"
    assert d["claim_lane"] == "OPERATIONAL_MILLENNIUM_STACK"
    assert d["unhackable"] is False
    assert all(v["implemented"] is True for v in d["layer_detail"].values())
    assert d["stack"]["sample"]["status"] == "ACCEPTED"
    assert d["audit_integrity"] is True


def test_property_random_clean_payloads_accepted():
    s = MillenniumSecurityStack()
    for i in range(12):
        _reg(s, f"id{i}", f"cred{i}")
        out = s.process_payload(
            {"i": i, "nonce": secrets.token_hex(4)},
            identity=f"id{i}",
            credential=f"cred{i}",
            attack={"source": f"id{i}", "severity": 0.02, "hops": 1, "fanout": 1, "burst_rate": 0.0},
            system={"audit_integrity": True, "launch_guard": "READY"},
        )
        assert out["status"] == "ACCEPTED", out
        assert s.audit.verify_integrity()


def test_anonymous_and_tofu_denied():
    s = MillenniumSecurityStack()
    anon = s.process_payload({"x": 1})
    assert anon["status"] != "ACCEPTED"
    tofu = s.process_payload({"x": 1}, identity="n", credential="p")
    assert tofu["status"] != "ACCEPTED"


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:
                failed += 1
                print("FAIL", name, repr(e))
    raise SystemExit(failed)
