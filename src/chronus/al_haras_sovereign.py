"""
AL HARAS (HYBA Security) command-line demonstration.

Runs the AL HARAS inspection on a consistent and an inconsistent set of node
states and prints the computed decisions and signed receipts. It demonstrates
the implemented checks; it is not a certification or deployment test.
"""

import json

from chronus.security.al_haras.engine import (
    CyclotomicZ5,
    CellularSheafCohomology,
    DSW4DInstantonMonopoleHealer,
    RamanujanExpanderSpectralGapGuard,
    CyclotomicAnyonBraidEngine,
    HeckeModularChecksum,
    ALHarasSecurityFabric,
)
from chronus.security.al_haras.sovereign import (
    ExactQ5,
    GaloisField257Phi,
    SovereignGovernanceEngine,
    ALHarasSovereignProductSDK,
)

__all__ = [
    "CyclotomicZ5",
    "CellularSheafCohomology",
    "DSW4DInstantonMonopoleHealer",
    "RamanujanExpanderSpectralGapGuard",
    "CyclotomicAnyonBraidEngine",
    "HeckeModularChecksum",
    "ALHarasSecurityFabric",
    "ExactQ5",
    "GaloisField257Phi",
    "SovereignGovernanceEngine",
    "ALHarasSovereignProductSDK",
    "SheafCohomologyObstructionEngine",
    "DSW4DInstantonSelfHealer",
    "RamanujanSpectralMassGapGuard",
    "CyclotomicAnyonBraidCompilerZ5",
    "main",
]

# Compatibility aliases matching the standalone module names
SheafCohomologyObstructionEngine = CellularSheafCohomology
DSW4DInstantonSelfHealer = DSW4DInstantonMonopoleHealer
RamanujanSpectralMassGapGuard = RamanujanExpanderSpectralGapGuard
CyclotomicAnyonBraidCompilerZ5 = CyclotomicAnyonBraidEngine


def main() -> int:
    sdk = ALHarasSovereignProductSDK("demo_tenant")
    clean = sdk.inspect_and_admit_workload(b"EXAMPLE_PAYLOAD", state_vectors=[[1, 2, 3]] * 3)
    disagreeing = sdk.inspect_and_admit_workload(
        b"EXAMPLE_PAYLOAD", state_vectors=[[1, 2, 3], [50, -99, 120], [1, 2, 3]]
    )
    for label, result in (("consistent states", clean), ("disagreeing states", disagreeing)):
        print(f"--- {label}")
        print(json.dumps({
            "admitted": result["admitted_to_execution"],
            "state_check": result["sheaf_cohomology"]["status"],
            "worst_edge": result["sheaf_cohomology"].get("worst_edge"),
            "isolating_nodes": result["sheaf_cohomology"].get("isolating_nodes"),
            "receipt_key_id": result["receipt"]["signature"]["key_id"],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
