# Chronos GPU v3.3 — benchmarks

**BLUF:** `results.json` records numbers from a **Linux sandbox run on 4 Aug 2026**. Wall times are **host-specific** (CPU, numpy build, load). Re-measure locally before citing latency.

## Stable vs historical

| Check | Role |
|---|---|
| 8K hits **1,832,112 / 33,177,600** | **Stable live contract** (still holds on monorepo v3.3 smoke) |
| Energy **−7.337994** | **Historical** sandbox archive only — live default render ≈ **−7.388** on current v3.3; deterministic per build, not bit-identical to the archive |
| Wall times (≈4.0–4.2 s 8K, etc.) | Informative for that Linux host only |

## What is claimed

| Artifact | Meaning |
|---|---|
| `results.json` | Historical sandbox evidence (Linux host). Not re-measured on every developer machine. |
| Pixel hit counts | Geometry / ray-hit contract shared with the page |
| Wall times | Host-bound; re-run for local numbers |

## What is not claimed

- No quantum speedup
- No cryogenic / physical QPU / cryo-hardware performance
- No production-closure or UHD 630 PASS from these numbers alone
- Live energy is **not** silently asserted equal to −7.337994

## How to run

From the **repo root** (so `chronus` is importable):

```bash
# Preferred: package module
python -m chronus.v33.benchmarks.run_benchmarks

# Or path execution with PYTHONPATH=repo root
PYTHONPATH=. python chronus/v33/benchmarks/run_benchmarks.py
```

Writes/updates `chronus/v33/benchmarks/results.json` beside this README. Label any new capture with host OS, Python, NumPy (Rule-7).

## Narrative

Human-readable tables and interpretation: [`../docs/BENCHMARKS.md`](../docs/BENCHMARKS.md).

Page ↔ tree map: [`../docs/PAGE_CHECKLIST.md`](../docs/PAGE_CHECKLIST.md).
