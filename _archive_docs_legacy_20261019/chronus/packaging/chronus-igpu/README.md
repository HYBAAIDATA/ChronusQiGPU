# hyba-chronus-igpu

The **Chronus execution plane** — the resident virtual iGPU, measurement
plane, seam contract and resident-Hendrix mining execution, together with the
Lucas ladder substrate those surfaces scale on.

## Declared direction (owner, 2026-10-11)

- The iGPU's potential is **exponential, limited by math only** — bounded by
  the mathematics it executes, not by a fixed hardware ceiling.
- **Lucas scales everything, and Lucas scales the iGPU** — `lucas_transform`
  and `pisot_transform` are iGPU workload kinds; the ladder is the scale
  contract of the machine, not a decorative constant.
- The iGPU is **independent of the host GPU** — `standalone_software` runs
  without one; `host_gpu_augmentation`/`preferred_accelerator` climbs into
  and scales a certified host when present (`required_adapter` /
  `required_device` pin explicit substrates and fail closed when absent).

Direction is declared in `UNIVERSAL_PRINCIPLE_MAP.md` §20; the
non-claims below record what is *not yet measured*.

## Boundary

This distribution ships the `chronus` execution surface **without** the
facade `chronus/__init__.py` and the `chronus/v33` mathematics plane (owned by
`hyba-chronos-mathematics`, declared as a dependency) and without
`chronus/mla1517` (the PYTHIA mining plane, owned by `hyba-pythia-mining`).

| Path | Owner |
| --- | --- |
| `chronus/__init__.py`, `chronus/v33/` | `hyba-chronos-mathematics` |
| `chronus/{virtual_igpu,measurement,seam,paradigm,spec,deploy,kernels}/`, `chronus/*.py` product modules | **this package** |
| `chronus/mla1517/`, `chronus/mla1517_platform/` | `hyba-pythia-mining` |
| `lucas/` | **this package** |
| `kellogg/` | `hyba-kellogg-tensor` |
| `chronos_one_igpu/` | `hyba-chronos-one-igpu` |

Modules that integrate the orchestrator (`chronus.fabric` → `hyba.inventory`,
`chronus.mining_bridge` → `quantum_compute_substrate`, `chronus.paradigm` →
`al_haras`, `chronus.delivery` → `chronus.mla1517.remote_gpu`) ship inside the
boundary and fail honestly with `ModuleNotFoundError` until
`hyba-pythia-mining` is installed beside this package. Nothing is silently
substituted.

## Claims this package does not make

- No physical-GPU evidence: device-bound execution requires the
  `hyba-chronos-one-igpu` contract and device-attested receipts.
- No pool acceptance: `mining.authorize` / share outcomes are literal pool
  responses, asserted only by the runtime evidence ledger.
- `publishable` stays false until CI produces a commit-bound verdict for the
  exact wheel and sdist digests.

## Build

```
python packaging/chronus-igpu/build_and_verify.py
```

Stages the boundary, builds wheel + sdist, scans for secrets and embedded
repo paths, installs into a clean venv via a local findlinks dir of the
declared dependencies, imports the required surface, asserts the excluded
surfaces are absent, runs the Lucas ladder + virtual-iGPU smoke, then
rebuilds the wheel from the sdist and repeats the installed check. Evidence
lands in `packaging/chronus-igpu/dist/artifact-verdict.json`.
