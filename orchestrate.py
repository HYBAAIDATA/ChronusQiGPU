"""Collapse the gap: run every artifact, emit one certificate."""

from __future__ import annotations

import json
import os
import sys


def collapse_the_gap(repo: str = "QuantumPhiRedux/PhiMiner") -> dict:
    from thermo.model import all_constants_sourced, falsification_tests
    from chronus.seam.bennett import pebble_bounds
    from standard.certificate import generate_certificate

    assert all_constants_sourced(), "constants must be sourced"
    space, _ = pebble_bounds(4, 2)
    assert space == 7
    assert "adiabatic_energy" in falsification_tests()

    cert = generate_certificate(repo=repo)
    os.makedirs("bench/results", exist_ok=True)
    with open("bench/results/certificate.json", "w", encoding="utf-8") as fh:
        json.dump(cert.as_dict(), fh, indent=2)
    return cert.as_dict()


if __name__ == "__main__":
    cert = collapse_the_gap()
    print(json.dumps({
        "claimed_level": cert["claimed_level"],
        "proved_level": cert["proved_level"],
        "gaps": list(cert["gaps"]),
        "signature": cert["signature"][:16],
    }, indent=2))
    sys.exit(0)
