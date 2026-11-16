# Recovered merge — provenance ledger

All files under `recovery_merge/` are byte-identical copies staged from
owner-disk ZIPs on 16 Nov 2026. Nothing here is imported by `src/` or
executed by tests; promotion into `src/` is explicit, per-file, below.

## Staged archives (SHA-256)

| Archive | SHA-256 (prefix) | Entries | Disposition |
|---|---|---|---|
| chronos-one-igpu-v3.4.zip | 406A6B49… | 133 | QSDL + Lucas + iGPU core + 8K BENCHMARKS.md/results.json |
| chronos-QiGPU-main_(1).zip | (staged) | 10,755 | Full snapshot; QSDL x6, tensor_train x1, v33 render results |
| pulvini_v3_enterprise_production_20260724.zip | 00B79A99… | 122 | enterprise TT tree + provenance/original_source |
| PULVINI_V3_HERMES_COMPLETION_20260724.zip | A307F93E… | 17 | geodesic_tensor_engine.py + completion logs |
| HYBA_1000_QUBIT_VQC_20260724.zip | 7B4EF036… | 10 | phi_quantum_machine + VQC integration |
| HYBA-recovery-evidence-20261029.zip | 93D6D6DA… | 7 | iGPU contract test + logs |
| HYBA_Library_Millennium_Recovery…(2).zip | 6DA5FEB0… | 37 | Yang-Mills + millennium math world |
| private-supplementary-qc-evidence.zip | 149D1D05… | 22 | contracts/math/production QC packs |

## Dedupe verdicts (executed)

- **qsdl_compiler.py (7 copies → 1):** v3.4 `src/` == v33 copy (`3AFC1CDC…`);
  `chronus/` copy is a distinct older version (`ECCFB1A2…`, x3 identical);
  backend copy is the real v3.0 grammar parser (`802AA6EA…`).
  **Promoted `backend/chronos/qsdl_compiler.py` → `src/chronus/qsdl/`** with
  v3.4 `qsdl_parser.py` and the compiler's sibling `manifold.py`
  (`389AB5AE…`, promotes with the pair). Others stay staged, not imported.
- **tensor_train.py (3 copies, all distinct):** mainline `75442338…`,
  enterprise `1FF3BD42…` (`astype(float)` in `_decompose`), provenance
  original `C2423737…` (`astype(float)` at compress line 140).
  **None promoted as engine code.** Live tree keeps
  `src/chronus/tensor/exact_rational_tt.py` (exact, no float cast).
  Recovered copies remain staged as defect provenance.
- **geodesic_tensor_engine.py (`E627CD69…`):** promoted to
  `src/chronus/pulvini/recovered/` as reference only — its claim lanes
  (EXTERNAL/BOUNDED/INTERNAL/RESTRICTED), embedded 2026 GPU baselines and
  hardcoded transistor specs are **not adopted** as repo claims.
- **Benchmark records:** `lucas_results.json` annotated in place
  (virtual-device design, OpenCL-as-escape-hatch, `us_per_record`,
  UNVERSIONED-WORKTREE provenance caveat); `results.json` staged untouched.

## Promotion rule

A staged file becomes production code only by explicit copy into `src/`
with a docstring noting its recovered origin, its hash, and what was
*not* adopted (baselines, prose claims, duplicate engines). No shim
imports, no `sys.path` insertions, no silent re-exports.
