> **v3.11 installation:** the standalone distribution now installs as
> `chronos_one_igpu`, not `chronos`, to avoid shadowing PhiMiner's canonical
> package. Import `OneIGPU` from `chronos_one_igpu`. Earlier `chronos` examples
> below describe the preserved historical source API. See CHANGELOG-v3.11.md.

# Chronos ONE iGPU v3.10 — resident execution and exact projection closure

Additive standalone package over the original completed core. Native residency
works without GPU hardware. Resident sessions auto-bind an available OpenCL or
Apple MLX/Metal executor, otherwise stay native and report the absence reason.
Explicit physical binding fails closed; no cross-cloud placement happens.

Virtual-unit scaling (80, 800, 8000 or Lucas-derived) is implemented as bounded
logical scheduling, not extra silicon or an unmeasured throughput multiplier.
Exact family intrinsics and tiled workloads execute beneath the same owner.

Read `docs/RESIDENT_ELEVATION.md`, `docs/FEEDBACK_AUDIT-v3.10.json`, and
`docs/PYTHI_NATIVE_OBLIGATIONS.json`. Compiled modular proofs and projection
checks are in `validation/v3.10.0-*`. All historical documentation below is
preserved; use versioned current release evidence for current status.

```bash
chronos-igpu doctor
chronos-igpu resident-info --virtual-units 8000
chronos-igpu resident-info --virtual-units 8000 --bind metal
chronos-igpu projection-analysis --rung-bits 8
chronos-igpu native-security-gate
```

Full production qualification is not asserted: physical targets, registry
upload, complete T1–T10 formalization, native-chain security and unfinished
interfaces remain recorded. Building an installable package does not close
those gates. No new speed, GPU/ASIC, energy or competitor claim is made.

---

# v3.9 — Structured execution and PYTHI-native computation

Additive standalone release, preserving the original Lucas and Chronos engines. Structured S6 is measured on CPU; OpenCL structured operator awaits hardware execution. Separate PYTHI-native local computation/verification has no Bitcoin compatibility or consensus deployment claim. See docs/STRUCTURED_PYTHI_ELEVATION.md and docs/PYTHI_NATIVE_OBLIGATIONS.json. All supplied inventory items and prior unfinished architecture are retained.

# v3.8.1 — Deterministic solver reuse

Additive release above the preserved core. See docs/DETERMINISTIC_ELEVATION.md for the exact-input cache, CPU benchmark, evidence binding and carried-forward backlog. Native and universal distributions remain distinct; warm reuse is not a sparse solver or physical ASIC claim.

# Chronos ONE iGPU — additive v3.8 ASIC-like mining

Preserves the supplied completed exact core and adds prepared SHA256d, fused ordered target scans, bounded mining lanes, stale-job cancellation, durable progress and retry-safe execution.

```python
from chronos import OneIGPU
from chronos.golden_quantum import NonceLease
with OneIGPU() as gpu:
    gpu.configure_asic_like() # native when installed; explicit hashlib-copy identity otherwise
    result = gpu.mine(prefix_76_bytes, exact_target, NonceLease(start, stop, job_id, epoch),
                      max_evaluations=4096, current_epoch=epoch)
```

See `docs/ASIC_MINING.md` for equations, native builds, service usage, measured adjacency and exact scope. The new native CPU path is ASIC-like in structure, not physical ASIC silicon.

# Retained v3.7 capability surface

An additive elevation of the supplied completed core: independent logical iGPU, exact Lucas/Fibonacci family algebra, default-enabled Golden Quantum solve-first execution, optional physical host composition and authenticated execution evidence.

## Install and run

```bash
python -m pip install .
chronos-igpu doctor
chronos-igpu family 10 12 15 > family.json
chronos-igpu verify-family family.json
```

```python
from chronos import OneIGPU, FamilyCertificate
with OneIGPU() as gpu:
    original = gpu.dispatch([10, 12, 15, 18, 20]); original.verify()
    certificate = gpu.family_certificate([10, 12, 15])
    assert FamilyCertificate.verify(certificate)
    assert certificate['combined_index'] == 37
    folded = gpu.fold_exact([1, 2, 3, 4])
    assert folded.unfold_partial([0, 3]) == (1, 4)
```

## Preserve, compose, validate

All 52 original source files remain; 48 are byte-identical. Four facade/export/topology files are extended for integration. The original exact sequence engine remains the authority. `validation/CORE_PRESERVATION.json` lists hashes, and the original regression suites are retained.

- Exact quadratic-field algebra composes pair and three-way orbits and certifies Lucas/Binet, norm/Pell-Cassini and Zeckendorf views together.
- S1–S6 solve-first and F1–F3 fallback execute through one owner with exact target and bounded work.
- OpenCL source implements Lucas256 and SHA256d; adapters enforce device limits and host candidate verification.
- Apple public-framework extras add explicit-materialisation MLX tensor execution and Core ML model inference; native dense/ReLU ranking is executable without Apple hardware.
- Authenticated service, tenant/workload receipts, packed witness cache, replay, concurrent evidence locking, CLI and publication tooling are included.

## Documentation

- `docs/GOLDEN_IGPU_INTEGRATION.md`: consolidated architecture, pseudocode and completion map.
- `docs/FAMILY_COMPOSITION.md`: equations, pair/triple composition and engineering insight.
- `docs/APPLE_NEURAL_INTEGRATION.md`: public-framework integration and usage.
- `docs/PUBLICATION.md`: installation, registry-ready distributions and release procedure.
- `docs/IMPLEMENTATION_STATUS.json`: exact implemented/unbound/not-implemented status.
- `docs/source_notes/`: unedited supplied notes and integrity manifest.
- `validation/RELEASE_REPORT.json`: executed results, build checks and target status.

```bash
python -m pip install .[dev]
python -m pytest -q
python -m build
python -m twine check dist/*
```

The wheel and sdist are publishable artifacts, not a claim that every optional platform is already production-qualified. Apple/OpenCL target hardware, Docker deployment and external pool transport were not run here. Missing binary ISA/600-cell/TT-MPO/pool implementations remain recorded. See the status map rather than inferring scope from test count.

Copyright (c) 2026 Andre Taylor-Morris. MIT licensed. No institutional affiliation or participation is claimed.
