# Geodesic Tensor historical archive — local regression replay (16 November 2026)

**Evidence class:** LOCAL HISTORICAL ARCHIVE REPLAY. **Not a current-repository test result, release certification, device test or live mining evidence.**

## Inputs and provenance

- ChatGPT Library `GEODESIC_TENSOR_ENGINE_EXTENDED_20260724.zip` (SHA-256 `43d4d3a39fd13fb525bf3acf0b822af1ef55c6b801616aeb9bf326a76dcfa44b`).
- ChatGPT Library `HYBA_PULVINI_V3_OWNER_RESEARCH_HANDOFF_20261115.zip` (SHA-256 `561d0b9cec7aa4ae80117f9267f44abc53328ecfe46445c51123261e846032cc`).
- July `geodesic_tensor_engine.py` (83,339 bytes, SHA-256 `e627cd693452904bd1ba1145058a0504955e58d10ce88f0001ed8fdbb4b87525`).
- November handoff `integration_seam/src/chronus/pulvini/formal.py` (7,149 bytes, SHA-256 `8d14a821b3dd8e8ad66ff380f6a5a40745a64b72eee2dbfa191c1550f9ee8586`).
- Original archive tests `test_geodesic_tensor_engine.py` and `test_geodesic_tensor_engine_extensions.py`. The tests import the historical `euclid.pythagoras.quantum.pulvini_enterprise` package; the temporary sandbox arranged those historical files at that import path. **No tracked current Chronus module was replaced.**
- Python 3.13.5, pytest 9.0.2, NumPy 2.3.5. Local execution timestamp: `2026-11-16T06:41:00Z`.

## Exact command and result

From the sandbox directory holding the temporary import package:

```bash
python -m pytest -q test_geodesic_tensor_engine.py test_geodesic_tensor_engine_extensions.py \
  --disable-warnings --junitxml=/mnt/data/archive_geodesic_replay_20261116.xml
```

```text
........................................................................ [ 62%]
...........................................                              [100%]
115 passed in 0.17s
```

Exit code: **0**. Locally captured stdout/log SHA-256 `2d17774f6990c3559277b9ed913217cc5c4f1dcfc5752b7191d0e308ded3e412`. JUnit XML SHA-256 `0eea293feccb03a63c26d4e2ef9bf194a317c04791d00127bd10de502823524b`. The raw artifacts were generated in the session workspace, not in GitHub Actions.

## Limits

1. This **mixed-archive** test uses July Geodesic implementation and tests with a November PULVINI formal dependency. It does not prove the exact original July full dependency stack.
2. It does not import or test `src/chronus/tensor/geodesic.py` from current `main`, compare every interface, or exercise Chronus deployment, device drivers, native GPU, mining/pool execution, or durable storage.
3. No performance claim can be promoted from the `0.17s` test duration; that is pytest wall time, not application throughput.
4. Current PR #130 regression tests and all current-head CI checks remain separately UNVERIFIED until real runner steps execute and succeed.
5. Historical source archives remain in the private Library; do not copy their outdated monolithic runtime into the active authority tree merely to match a legacy symbol.

## Trace

Source reconciliation: [2026-11-16 source archive report](../../docs/audits/2026-11-16-source-archive-reconciliation.md). Source code: `src/chronus/tensor/geodesic.py`. Regression surface: `tests/test_geodesic_tensor_migration.py`.
