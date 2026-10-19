# Chronos drop — review & integration record

**BLUF:** The root `chronos/` drop was **older Chronos GPU v2**. This repo already had **v3.3** under `chronus/v33/`. Integration = archive v2 + thin deprecated facade — **not** a second engine and **not** a downgrade.

**Date:** integration pass against operator drop at repo root  
**Evidence class:** implemented in-tree (layout + facade); runtime verified by smoke import + existing `tests/test_chronus_v33/`

---

## 1. What landed

| Artifact | Generation | Header signal |
| --- | --- | --- |
| Operator drop `chronos/engine.py` | **v2.0** audit fix | “ChronosEngine orchestrator v2.0 (audit fix, 3 Aug 2026)” |
| In-repo `chronus/v33/engine.py` | **v3.3** | “v3.3 (memory integration, 4 Aug 2026)” |
| Backup `chronus_local_backup_20261001/src/chronos/` | v3-aligned | Full tree + tests + pyproject `chronos-gpu` 3.0.0 |

v3.3 already includes everything the v2 drop had, plus:

- `memory/` (MPS / QRAM / block-encode / hierarchy)
- `emp.py`, `fields/`, `graphics/`, `control/`, `environment/`
- `theory/` (cryogenics, photonics, anyons, … — maths posture, not physical 15 mK claim)
- `phi_scaling.py`, `weak_measurement.py`, `registry.py`
- richer `academic/` (`integration.py`, `jaynes_cummings.py`)
- `CAPABILITY_MANIFEST.json`

---

## 2. Decision (pyramid)

**Governing thought:** One Chronos maths engine — `chronus.v33`.

| Option | Outcome |
| --- | --- |
| A. Run v2 drop beside v3.3 | **Rejected** — dual packages, import ambiguity, silent downgrade risk |
| B. Overwrite v3.3 with v2 | **Rejected** — destroys memory/EMP/theory gap-close work |
| C. Archive v2 + facade → v3.3 | **Chosen** — preserves drop, keeps product forward |

---

## 3. What we did

1. Moved operator sources → `legacy/chronos_gpu_v2_drop/` (provenance README included).
2. Replaced top-level `chronos/` with a **deprecated re-export** of `chronus.v33` (+ `chronos.academic` → `chronus.v33.academic`).
3. Documented the map here and in `chronos/README.md` / legacy README.
4. Left product Chronus (`chronus/` iGPU, virtual_igpu, scale) unchanged as the hardware-facing offering.
5. Did **not** claim physical cryogenic hardware, hashrate, or “perfect GI” from either generation.

---

## 4. Import map

```text
import chronos                 →  chronus.v33   (DeprecationWarning)
import chronos.academic        →  chronus.v33.academic
from chronus.v33 import …      →  preferred
from chronus import …          →  iGPU product API (not the Chronos maths engine)
```

Canonical tests already target `chronus.v33`:

- `tests/test_chronus_v33/test_memory.py`
- `tests/test_chronus_v33/test_gap_close.py`
- (siblings under the same package)

---

## 5. Honest non-claims

| Claim | Status |
| --- | --- |
| v2 drop merged as product engine | **No** — archived |
| Facade preserves `import chronos` | **Yes** — implemented |
| Chronus iGPU home moved | **No** — still `chronus/` |
| Physical 15 mK / cavity hardware from theory modules | **No** — maths / research pages only |
| SHA-256d replaced by Chronos render | **No** — mining validity oracle unchanged |

---

## 6. Follow-ups (planned, not done in this pass)

- Optional: add `chronos` to setuptools package discovery if wheel installs need the facade (editable/conftest path already resolves repo root).
- Optional: port any unique backup-only benchmarks from `chronus_local_backup_20261001/benchmarks/` under `chronus/v33` with Rule-7 labels.
- Do **not** wire QAOA/Fisher deep-variational into Chronos exact path (existing audit posture).

---

*Style: McKinsey form — BLUF, pyramid, evidence trail. Brand tokens: `docs/HYBA_STYLE_GUIDE_FRONTEND_PRODUCT.md`.*


## Continuation pass — v3 page promotion

**Date context:** follow-on to the archive-v2 + facade pass.

**What landed**

- Benchmarks, docs, and examples from `chronus_local_backup_20261001/` are promoted **beside** the active maths engine at `chronus/v33/`:
  - `chronus/v33/benchmarks/` — `results.json`, `run_benchmarks.py`, package `__init__.py`, README
  - `chronus/v33/docs/` — BENCHMARKS, AUDIT_NOTES, ACADEMIC_AUDIT, HISTORICAL_ANALOGIES, RELEASE_NOTES, **PAGE_CHECKLIST**
  - `chronus/v33/examples/` — `demo.py`, `memory_integration.py` (imports → `chronus.v33`)
- Package README: `chronus/v33/README.md`
- Page ↔ tree checklist: `chronus/v33/docs/PAGE_CHECKLIST.md` (maths bullets, layout table, elevation planes, PENDING gates, claim boundaries, import map)

**What did not change**

- **No** overwrite of active engine sources under `chronus/v33/**/*.py` (only new package files under benchmarks/examples plus docs/README).
- **`chronus_local_backup_20261001/`** remains the full historical snapshot; not deleted; not the active import root.
- **`chronos-gpu-v3-maths.zip` / `08a7226b…`** still **absent** from the tree; substance is `chronus/v33/`.
- Frontend untouched.
- **Not** declared: production closure, UHD 630 PASS, full backend ladder, Windows RAPL.

**Imports in promoted scripts**

- `from chronos…` → `from chronus.v33…` in `run_benchmarks.py` and examples.
- Preferred: `from chronus.v33 import ChronosEngine`.

**Live smoke (continuation)**

- `chronus.v33.__version__` → `3.3.0`
- 8K contract: shape `(4320, 7680, 3)`, hits `1832112 / 33177600` — **matches archive**
- Energy: live default render ≈ **−7.388** vs archived **−7.337994** — documented as historical vs live; not silently equated
- Facade + memory + gap-close tests: green
- PENDING gates (UHD 630, backend ladder, production closure, Windows RAPL): **still PENDING**
