"""Certificate: no third state. Every invariant has a status."""

from __future__ import annotations

from conformance.tests.conformance import certify, check_conformance
from standard.certificate import INVARIANT_IDS, generate_certificate
from standard.check_invariants import check_all
from thermo.model import all_constants_sourced, falsification_tests, landauer_bound


def test_constants_sourced():
    assert all_constants_sourced()
    assert "adiabatic_energy" in falsification_tests()
    assert landauer_bound(1) > 0


def test_every_invariant_has_status():
    ev = check_all()
    assert set(ev) == set(INVARIANT_IDS)
    allowed = {"proved", "tested", "modeled", "benchmarked", "assumed", "gap"}
    for inv, e in ev.items():
        assert e.status in allowed, inv


def test_closed_paths_have_status():
    ev = check_all()
    assert ev["K5"].status == "modeled"
    assert ev["Q3"].status == "tested"
    assert ev["T6"].status == "tested"
    assert ev["F7"].status == "tested"


def test_closed_algebra_is_proved():
    ev = check_all()
    for inv in ("T3", "R1", "R2", "K6", "K8", "AC2", "R4"):
        assert ev[inv].status == "proved", inv


def test_certificate_levels():
    cert = generate_certificate()
    assert cert.reproducible is True
    assert cert.signature
    assert "K5_SNARK" in cert.gaps
    assert "ASIC1" in cert.gaps
    assert cert.claimed_level in {"minimal", "core", "extended", "full"}
    assert cert.proved_level in {"minimal", "core", "extended", "full"}


def test_core_conformance():
    results = check_conformance("core")
    assert results
    assert certify("minimal") is True
    assert certify("core") is True
