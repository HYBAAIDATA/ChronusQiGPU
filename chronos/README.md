# Chronos GPU v2 drop (archived)

**Status:** Provenance only — do not import from here in product code.

This tree is the older Chronos GPU package the operator dropped at repo root
(`chronos/`). It is the **v2.0 audit-fix** generation (engine headers say
"v2.0 (audit fix, 3 Aug 2026)").

## Why archived

| Layer | Location | Generation |
| --- | --- | --- |
| This drop | `legacy/chronos_gpu_v2_drop/` | Chronos GPU **v2** |
| Active Chronos maths engine | `chronus/v33/` | Chronos GPU **v3.3** (memory, EMP, theory, control, …) |
| Product iGPU offering | `chronus/` | Chronus (device, virtual_igpu, scale, MLA1517) |
| Fuller upstream snapshot | `chronus_local_backup_20261001/src/chronos/` | v3-aligned backup + tests |

Integrating this drop as a second live package would **downgrade** the tree
(v2 over v3.3). Integration policy: keep v3.3 as source of truth; expose a
deprecated top-level `chronos` facade that re-exports `chronus.v33`.

## Do not

- Do not add this path to `sys.path` ahead of `chronus.v33`
- Do not claim v2 gate counts / energies as current product metrics
- Do not merge v2 `engine.py` over `chronus/v33/engine.py`
