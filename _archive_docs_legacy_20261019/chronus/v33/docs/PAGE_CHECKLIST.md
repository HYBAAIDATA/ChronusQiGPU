# PAGE ↔ TREE checklist — Chronos GPU maths + Chronus elevation

**BLUF:** HYBA page claims for the Chronos GPU **maths engine** map to `chronus/v33/` (v3.3.0). Chronus **elevation / device** planes map to sibling trees under `chronus/` and `bench/`. This file is the in-tree verification map. It does **not** declare production closure or UHD 630 PASS.

**Evidence class:** layout + imports verified in-tree; historical bench numbers are sandbox Linux (4 Aug 2026); wall times host-specific.

---

## Maths engine

**Page path:** `src/chronos/`  
**Here:** `chronus/v33/`

| Verified-implementation bullet | Path under `chronus/v33/` | Status |
|---|---|---|
| M32 manifold | `manifold.py` (`M32Manifold`, `fibonacci_sphere`) | **IN** |
| QSDL parser | `qsdl_parser.py` | **IN** |
| QSDL compiler | `qsdl_compiler.py` | **IN** |
| Eigendecomposition / Hamiltonian path | `hamiltonian.py`, `evolution_engine.py` | **IN** |
| Ray trace / raster path | `graphics/`, `reconstruction.py` | **IN** |
| Compression metadata / fold / MPS / TEBD | `compression/` | **IN** |
| BCS / superconductivity maths | `theory/superconductivity.py` | **IN** |
| 1000-qubit TT / large Hilbert helpers | `academic/tensor_compression.py`, `compression/large_space.py` | **IN** |
| Test harness | `test_harness.py` | **IN** |
| φ scaling | `phi_scaling.py` | **IN** |
| Engine orchestrator | `engine.py` (`ChronosEngine`) | **IN** |
| Memory integration (v3.3+) | `memory/` | **IN** (beyond page v3.0 zip) |
| EMP | `emp.py` | **IN** |
| Weak measurement | `weak_measurement.py` | **IN** |
| Research registry | `registry.py` / research registry surface | **IN** |

Package version export: `chronus.v33.__version__` → **3.3.0**.

---

## Package layout (page table → paths)

| Page module | Path | Notes |
|---|---|---|
| academic | `chronus/v33/academic/` | CERN, MIT, Caltech, Cambridge, Tokyo Tech, NIST, JC, tensor compression, integration |
| theory (10+ domains) | `chronus/v33/theory/` | See domain list below |
| compression | `chronus/v33/compression/` | phi_fold, mps_tools, tebd, large_space |
| control | `chronus/v33/control/` | controller + feedback |
| environment | `chronus/v33/environment/` | decoherence, thermal |
| fields | `chronus/v33/fields/` | laser, microwave |
| graphics | `chronus/v33/graphics/` | render pipeline |
| memory (v3.3+) | `chronus/v33/memory/` | MPS / QRAM / block-encode / hierarchy |
| emp | `chronus/v33/emp.py` | EMP report path |
| weak_measurement | `chronus/v33/weak_measurement.py` | weak measurement session |

### Theory domains

| # | Domain | File |
|---|---|---|
| 1 | anyons | `theory/anyons.py` |
| 2 | chemistry | `theory/chemistry.py` |
| 3 | control | `theory/control.py` |
| 4 | cryogenics | `theory/cryogenics.py` |
| 5 | error_correction | `theory/error_correction.py` |
| 6 | euclid | `theory/euclid.py` |
| 7 | metrology | `theory/metrology.py` |
| 8 | oscillator_array | `theory/oscillator_array.py` |
| 9 | photonics | `theory/photonics.py` |
| 10 | qcd | `theory/qcd.py` |

Plus: `theory/superconductivity.py`, `theory/report.py` (maths / research pages — **not** physical 15 mK hardware).

---

## Benchmarks

| Artifact | Path | Note |
|---|---|---|
| Raw results | `chronus/v33/benchmarks/results.json` | Sandbox Linux, 4 Aug 2026 |
| Runner | `chronus/v33/benchmarks/run_benchmarks.py` | Re-run for local wall times |
| Narrative | `chronus/v33/docs/BENCHMARKS.md` | Tables + interpretation (archive host) |
| Bench README | `chronus/v33/benchmarks/README.md` | BLUF + how to run |

### Energy / geometry anchor (honest)

| Check | Archived v3.0 sandbox (`results.json`) | Live `chronus.v33` smoke (this monorepo) |
|---|---|---|
| 8K frame shape | 7680×4320 | **(4320, 7680, 3)** — same pixel grid |
| Rendered / total pixels | 1,832,112 / 33,177,600 | **1,832,112 / 33,177,600** — bit-identical hit count |
| Ground energy (default path) | **−7.337994** | **≈ −7.388** on current v3.3 default render (deterministic per build; **not** bit-identical to the Aug-4 archive) |

**Do not** silently equate live energy to the archived −7.337994 without a controlled re-bench. Pixel geometry is the stable cross-check; energy can shift when mixer/adjacency/default scene/memory path evolved from v3.0 → v3.3. Re-run `benchmarks/run_benchmarks.py` and replace `results.json` only with Rule-7 labelled host evidence.

**Wall times are not re-measured on every host.**

---

## Chronus elevation planes

| Plane | Path | Status |
|---|---|---|
| device | `chronus/` (device, fabric, engine entrypoints) | **IN** (product tree) |
| virtual_igpu | `chronus/virtual_igpu/` | **IN — MVP** |
| measurement | `chronus/measurement/` | **IN** |
| evidence CLI | `bench/chronus_igpu_evidence.py` | **IN** |
| mla1517 | `chronus/mla1517/` | **IN** |
| igpu (retired sole root) | — | **absent** as top-level product root |
| Enterprise / UnifiedEnterprise | external | **external** |
| Maths engine home | `chronus/v33/` | **IN** (active) |

### PENDING gates (still PENDING — do not mark PASS)

| Gate | Status |
|---|---|
| UHD 630 evidence / PASS | **PENDING** |
| Full backend ladder | **PENDING** |
| Production closure | **PENDING** |
| Windows RAPL | **PENDING** |

### Live smoke snapshot (monorepo continuation)

| Probe | Result |
|---|---|
| `chronus.v33.__version__` | `3.3.0` |
| `ChronosEngine().render("default")` frame | `(4320, 7680, 3)` |
| hits / total | `1832112 / 33177600` |
| energy (live) | finite, negative, deterministic re-render; ≈ −7.388 — **≠** archived −7.337994 |
| facade + memory + gap-close tests | green on continuation pass |

---

## Not included as zip

| Item | Status |
|---|---|
| `chronos-gpu-v3-maths.zip` / id `08a7226b-…` | **Not in tree** as a zip blob |
| Substance of the maths engine | **Present** as `chronus/v33/` |
| Full historical snapshot | `chronus_local_backup_20261001/` (backup; not the active import root) |
| Operator older root drop (v2) | `legacy/chronos_gpu_v2_drop/` (provenance only) |

---

## Claim boundaries (honest, short)

1. **Quantum-from-maths** on a **classical silicon** substrate — not a physical QPU product claim.
2. **No quantum speedup** claim from benchmarks or demos.
3. **No cryo hardware** performance claim from this tree.
4. Recorded bench **wall times** are **one Linux sandbox host** (4 Aug 2026); re-run locally.
5. Archived energy **−7.337994** is **historical sandbox** evidence. Live v3.3 energy is deterministic per build but may differ (≈ −7.388 on current default smoke). Neither figure is a hardware efficiency rating.
6. **UHD 630**, full backend ladder, **production closure**, and **Windows RAPL** remain **PENDING**.
7. Root `chronos/` is a **deprecated facade** to v3.3 — prefer `chronus.v33`.
8. Chronus product iGPU offering ≠ Chronos GPU maths package naming — see `chronus/README.md`.
9. SHA-256d remains the sole mining validity oracle; tensor/iGPU advice cannot mutate coverage or targets.

---

## Import map

```python
from chronus.v33 import ChronosEngine, M32Manifold   # preferred
from chronos import ChronosEngine                    # deprecated facade
```

```bash
pytest tests/test_chronus_v33 tests/test_chronos_facade.py -q
python -m chronus.v33.benchmarks.run_benchmarks
python chronus/v33/examples/demo.py
```

Related docs:

- Package README: `chronus/v33/README.md`
- Drop integration record: `docs/CHRONOS_DROP_INTEGRATION.md`
- Backup snapshot (full): `chronus_local_backup_20261001/`
