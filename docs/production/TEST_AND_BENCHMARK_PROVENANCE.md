# Test and Benchmark Provenance Register

Historical engineering evidence is retained because it identifies capabilities, tests and benchmark protocols that must not disappear during repository consolidation. Historical results remain historical until rerun or reconciled to the exact release commit.

The machine-readable authority is `evidence/migration/chronus_historical_evidence_register.json`.

## Migrated historical records

| Record | Original result | Current disposition |
| --- | --- | --- |
| Geodesic/Tensor extension — 24 Jul 2026 | 115/115 tests (68 original + 47 extension), 0.073 s; archive `GEODESIC_TENSOR_ENGINE_EXTENDED_20260724.zip`, SHA-256 `43d4d3a39fd13fb525bf3acf0b822af1ef55c6b801616aeb9bf326a76dcfa44b` | Capability mapped to current tensor runtime; current branch tests required |
| Geodesic/Tensor completion gate — 24 Jul 2026 | 61/61 integration operations; 110/110 property invariants; 12/12 operator checks; 122/122 unit/regression; 242/242 strict use-case assertions; 121/121 operator-gap checks | Preserved as historical evidence; exact-current rerun required |
| Enterprise Chronus–THESEUS–OVID custody work | 67 historical tests passed; historical record retained `production_ready: false` | Reimplemented under current authority boundaries; current triad tests added |
| Virtual iGPU software acceptance — Oct 2026 | 19 passed, 3 skipped; skips explicitly physical GPU/cloud/live pool | Fleet capability present; current release suite determines present qualification |
| Eleven-layer iGPU measurement | 30/30 measurement tests and 1,488/1,488 substrate tests; 16 stages available, 5 unavailable due absent sensors | Historical measurement record retained; rerun required for release claim |
| Intel UHD 620 physical history | 2026-09-21 record at commit `823cf39`: 22.13–23.44 MH/s kernel, 16.86–18.96 MH/s wall on `opencl:gpu` | Device/workload history only; post-migration artifact/device binding must be rerun or reconciled |
| UHD 630 | Historical record said pending | Remains unavailable until current target-host evidence exists |
| Enterprise native tensor hardening | Historical merged PR record described explicit CUDA C and MLX/Metal tensor routes with device-bound measurement semantics and no physical timing claim | Capability restored into maintained tensor package; device evidence still required |
| Storage suite — 15 Nov 2026 | Confidential deck records 16/16 storage checks at Chronusv2 revision `672f3d7` using `tests/test_storage.py` | Preserved as provenance; current close-out suite reruns storage/triad behavior |

## Current repository evidence retained

The repo already includes:
- `capabilities/acceleration_report.md`
- `evidence/acceleration/`
- `evidence/cyclotomic/`
- `artifacts/acceleration/`
- `tests/test_falsifiable_tensor.py`
- fleet and storage regression suites under `tests/`

Those records remain in place. The migration register supplements them with evidence that existed outside the maintained repository.

## Required current reruns

### Core triad

```bash
python -m pytest   tests/test_triad_production.py   tests/test_triad_capability_manifest.py   tests/test_geodesic_tensor_migration.py -q
```

### Full repository

The normal CI matrix remains authoritative for the exact close-out SHA. No historical count substitutes for it.

### Physical target evidence

For supported physical targets, retain:
- device and driver identity;
- exact source/kernel/input/output binding;
- correctness against the reference route;
- repeated timing and sustained-load behavior;
- available power/thermal sensors without filling unavailable values;
- artifact digest and validator result.

Historical UHD 620 numbers are not automatically promoted to the current tensor/OpenCL implementation.

## Promotion rule

A historical result is useful for three things: capability discovery, regression target definition and provenance. It becomes current release evidence only when the relevant implementation is present at the release SHA and the defined current gate reproduces or independently reconciles it.
