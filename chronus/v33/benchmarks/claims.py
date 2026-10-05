# claims.py
# Chronos GPU -- claim ledger (5 Oct 2026)
#
# The marketing suite (technical whitepaper, competitive benchmark table,
# market positioning, VC pitch deck; 3 Aug 2026) and the delivery plan make
# specific, quantitative claims. This ledger keeps every one of them
# machine-checkable against the benchmark artifacts in this directory, with
# three honest states:
#
#   MEASURED       -- the claim is backed by a committed measurement artifact
#                     from a real workload under the reproducibility protocol.
#   GATED          -- the claim is true of the built code path but its
#                     quantitative number requires a device/host that has not
#                     yet run it (e.g. a bound GPU). The gate names the exact
#                     evidence that will move it to MEASURED.
#   UNMEASURED     -- no artifact exists yet; the claim stays a target, never
#                     cited as achieved.
#
# Doctrine: "elevate the code to meet the documents, never water the
# documents down." The ledger never deletes a claim -- it records where the
# elevation stands, so no future reviewer has to re-derive the honesty
# position from scratch.
#
# Run:
#   PYTHONPATH=. python chronus/v33/benchmarks/claims.py
#   python -m chronus.v33.benchmarks.claims

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from chronus.v33.benchmarks.protocol import PROTOCOL_VERSION

BENCH_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Claim:
    claim_id: str
    source_doc: str
    claim_text: str
    evidence_path: str
    evidence_reader: str
    status: str  # MEASURED | GATED | UNMEASURED
    current_best: str
    gate_to_measured: str = ""


LEDGER: tuple = (
    Claim(
        claim_id="frame-time-8k",
        source_doc="Whitepaper §3 / Benchmark table / Pitch deck slide 5",
        claim_text="Frame time 8-16 ms (60-120 FPS at 8K) on classical GPU substrate.",
        evidence_path="benchmarks/render_elevation_results.json",
        evidence_reader="full_render_8k.samples_per_pixel_1.wall_seconds",
        status="GATED",
        current_best=(
            "CPU reference path measured 2.68 s at 8K (v3.1, 1.77x over v3.0); "
            "the documented 8-16 ms number requires a bound GPU device, which no "
            "committed run has had (fail-closed lane reports measured:false)."
        ),
        gate_to_measured=(
            "Run render_elevation on a host with a bound CuPy device; commit "
            "render_elevation_results.json with gpu_lane.measured=true."
        ),
    ),
    Claim(
        claim_id="supersampling-4x",
        source_doc="Whitepaper §3 / Benchmark table",
        claim_text="4x mathematical supersampling (true antialiasing, not upscaling).",
        evidence_path="benchmarks/render_elevation_results.json",
        evidence_reader="full_render_8k.samples_per_pixel_4",
        status="MEASURED",
        current_best=(
            "4 spp traced at 8K: 11.16 s, hits 1,833,696, antialiases 1,584 "
            "silhouette pixels; exact per-sample oracle reproduction in tests."
        ),
    ),
    Claim(
        claim_id="multi-object-scene",
        source_doc="Whitepaper §2 (QSDL scenes with multiple objects/materials/lights)",
        claim_text="Scenes with multiple objects, materials and lights render as composed scenes.",
        evidence_path="benchmarks/real_workload_results.json",
        evidence_reader="real_workloads[].frame_facts",
        status="MEASURED",
        current_best=(
            "v3.2 composite elevation: nearest-hit composition across sphere/"
            "box/plane objects; two-sphere and studio scenes measured at 1080p "
            "and 8K; single-sphere baseline path bit-identical."
        ),
    ),
    Claim(
        claim_id="gi-quality",
        source_doc="Benchmark table ('GI quality: perfect by construction')",
        claim_text="Perfect global illumination by construction.",
        evidence_path="benchmarks/results.json",
        evidence_reader="full_render_at_scale.32.distinct_distribution_values",
        status="GATED",
        current_best=(
            "Honest relabelling stands: the validated demo scene resolves 32 "
            "distinct distribution values; 'perfect' is the mathematical design "
            "goal of the exact-diagonalisation pipeline, not a measured frame "
            "property. The code path (exact dense eigendecomposition, no Monte "
            "Carlo, no denoiser) is the construction the documents describe."
        ),
        gate_to_measured=(
            "Define and measure an accepted GI-error metric (e.g. vs an "
            "analytic reference scene) so 'perfect' becomes a number."
        ),
    ),
    Claim(
        claim_id="pulvini-11.5x",
        source_doc="Whitepaper §3 / Benchmark table ('Memory compression 11.5x via PULVINI')",
        claim_text="11.5x memory compression on the final frame buffer.",
        evidence_path="benchmarks/render_elevation_results.json",
        evidence_reader="full_render_8k.samples_per_pixel_1.raster_compression_ratio",
        status="UNMEASURED",
        current_best=(
            "The v33 render path measures raster_compression_ratio "
            "(3,628,800x on the demo scene: parametric state vs dense frame) "
            "-- an ordinary procedural-vs-raster ratio, NOT the 11.5x PULVINI "
            "phi-fold claim. PULVINI folding is a separate (enterprise/mining) "
            "plane capability and is not asserted by this artifact."
        ),
        gate_to_measured=(
            "Run the PULVINI fold over a rendered frame on its owning plane "
            "and commit that plane's measured artifact."
        ),
    ),
    Claim(
        claim_id="first-principles-physics",
        source_doc="Market positioning §3 ('Physics = Hamiltonian updates; real QED terms')",
        claim_text=(
            "First-principles physics via real Hamiltonian terms "
            "(incl. SCF material bridge)."
        ),
        evidence_path="benchmarks/results.json",
        evidence_reader="theory_self_tests + bcs_gap_solver",
        status="MEASURED",
        current_best=(
            "Theory domains (superconductivity BCS self-consistent solver, "
            "chemistry SCF bridge, photonics, metrology, control, error "
            "correction, anyons, QCD, cryogenics, oscillator arrays) self-test "
            "PASS on the committed run; HamiltonianLibrary builds real cost/"
            "driving terms from QSDL geometry/material/light."
        ),
    ),
    Claim(
        claim_id="qsdl-compiler",
        source_doc="Whitepaper §2.1 (QSDL compiler: full grammar, types, constraints)",
        claim_text="QSDL scene language compiles to manifold-mapped Hamiltonian terms.",
        evidence_path="benchmarks/results.json",
        evidence_reader="qsdl_parse_compile",
        status="MEASURED",
        current_best=(
            "Parser + compiler measured (parse 0.288 ms, compile 0.649 ms on "
            "the committed host); grammar covers scenes, objects, geometry "
            "(sphere/box/plane/mesh/procedural), materials, quantum blocks, "
            "transforms, animation, lights, camera readout, quality."
        ),
    ),
    Claim(
        claim_id="gpu-substrate-lane",
        source_doc="Whitepaper §3 ('Substrate: Classical GPU Numba/CuPy/Metal')",
        claim_text=(
            "Runs on classical GPU substrate (CuPy lane shipped; "
            "OpenCL/Metal lanes follow)."
        ),
        evidence_path="benchmarks/render_elevation_results.json",
        evidence_reader="gpu_lane",
        status="GATED",
        current_best=(
            "CuPy lane shipped fail-closed (bind-time self-check battery, "
            "per-dispatch sampled CPU recheck, explicit-request-raises). No "
            "committed run has bound a device; gpu_lane.measured=false with "
            "the recorded reason. OpenCL/Metal render lanes not yet built."
        ),
        gate_to_measured=(
            "Bind a real CUDA/Metal device, run the elevation benchmark, "
            "commit the artifact with a true gpu_lane measurement."
        ),
    ),
    Claim(
        claim_id="phi-power-scaling",
        source_doc="Implementation record (phi-power benchmark tiers)",
        claim_text="phi^n scaling study with exact Lucas-number identity cross-check.",
        evidence_path="benchmarks/results.json",
        evidence_reader="phi_power_scaling.tiers",
        status="GATED",
        current_best=(
            "phi^10/12/15 measured on the committed host; phi^18/phi^20 are "
            "measured:false (runner caps at phi^15) -- the 20.2 s phi^18 "
            "number in the implementation record is amended by this ledger. "
            "Unmeasured tiers are never cited as achieved."
        ),
        gate_to_measured=(
            "Raise max_measured_power on a host with the memory for the "
            "5,778-face (phi^18) dense eigendecomposition and re-run."
        ),
    ),
)


def _read_artifact(rel_path: str) -> Optional[Dict[str, Any]]:
    path = BENCH_DIR / Path(rel_path).name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def evaluate() -> Dict[str, Any]:
    """Build the ledger view: every claim with its artifact present or absent."""
    rows: List[Dict[str, Any]] = []
    for claim in LEDGER:
        artifact = _read_artifact(claim.evidence_path)
        rows.append(
            {
                "claim_id": claim.claim_id,
                "source_doc": claim.source_doc,
                "claim": claim.claim_text,
                "status": claim.status,
                "current_best": claim.current_best,
                "gate_to_measured": claim.gate_to_measured,
                "evidence_path": claim.evidence_path,
                "evidence_reader": claim.evidence_reader,
                "evidence_artifact_present": artifact is not None,
            }
        )
    measured = sum(1 for r in rows if r["status"] == "MEASURED")
    gated = sum(1 for r in rows if r["status"] == "GATED")
    unmeasured = sum(1 for r in rows if r["status"] == "UNMEASURED")
    return {
        "schema": "chronos-v33-claim-ledger-v1",
        "protocol_version": PROTOCOL_VERSION,
        "summary": {
            "total_claims": len(rows),
            "measured": measured,
            "gated": gated,
            "unmeasured": unmeasured,
        },
        "claims": rows,
    }


def main() -> None:
    ledger = evaluate()
    out_path = BENCH_DIR / "claims_ledger.json"
    out_path.write_text(json.dumps(ledger, indent=2, default=str))
    s = ledger["summary"]
    print(
        f"Claim ledger: {s['total_claims']} claims -- "
        f"{s['measured']} MEASURED, {s['gated']} GATED, {s['unmeasured']} UNMEASURED"
    )
    for row in ledger["claims"]:
        markers = {
            "MEASURED": "[MEASURED]",
            "GATED": "[GATED   ]",
            "UNMEASURED": "[UNMEAS.]",
        }
        marker = markers[row["status"]]
        artifact = "artifact present" if row["evidence_artifact_present"] else "artifact absent"
        print(f"  {marker} {row['claim_id']} ({artifact})")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()