#!/usr/bin/env python3
"""AL HARAS (HYBA Security) security module: command-line demonstration.

This root script is kept for people who ran the original prototype. It now
uses the implemented package (src/chronus/security/al_haras): an exact
cellular-sheaf consistency check, Reed-Solomon trace repair and an Ed25519
signed decision receipt. See docs/security/AL_HARAS_NOTES_RECONCILIATION.md.
"""

import json
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from chronus.security.al_haras.engine import (  # noqa: E402
    ALHarasSecurityFabric,
    CellularSheafCohomology,
    CyclotomicAnyonBraidEngine,
    DSW4DInstantonMonopoleHealer,
    HeckeModularChecksum,
    RamanujanExpanderSpectralGapGuard,
)

__all__ = [
    "ALHarasSecurityFabric",
    "CellularSheafCohomology",
    "CyclotomicAnyonBraidEngine",
    "DSW4DInstantonMonopoleHealer",
    "HeckeModularChecksum",
    "RamanujanExpanderSpectralGapGuard",
]


def main() -> int:
    agree = ALHarasSecurityFabric.evaluate_ingress(b"EXAMPLE", [[1, 2, 3]] * 3)
    disagree = ALHarasSecurityFabric.evaluate_ingress(b"EXAMPLE", [[1, 2, 3], [9, 2, 3], [1, 2, 3]])
    drill = DSW4DInstantonMonopoleHealer.inspect_and_heal(b"EXAMPLE TRACE", is_perturbed=True, fault_count=2)
    print(json.dumps({
        "consistent_states_admitted": agree["admitted"],
        "disagreeing_states_admitted": disagree["admitted"],
        "located_nodes": disagree["sheaf_cohomology"]["isolating_nodes"],
        "trace_repair_verified": drill["integrity_verified"],
        "expander_certified": RamanujanExpanderSpectralGapGuard.verify_mass_gap()["satisfies_bound"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
