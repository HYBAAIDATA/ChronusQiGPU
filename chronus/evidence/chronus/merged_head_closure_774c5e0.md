# Merged-head software closure run — `774c5e0`

Local execution evidence. GitHub Actions minutes are exhausted, so CI proves nothing here (see *CI state*).
Supersedes `merged_head_closure_a05eb00.md`, which recorded 13 failures that are now closed.

| Field | Value |
|---|---|
| Tested commit | `774c5e0b678296fb620ad8c05676aa78ec4e695e` (branch `claude/dreamy-meitner-06b49k`, PR #113) |
| Base | `origin/main` @ `509fd24` (TURING production startup gate, 1.3.0), merged in `4a5242f`; diff vs base: 31 files, +1657/-111 |
| Host | 4 vCPU Intel Xeon @ 2.80 GHz, 15 GB, Linux 6.18, Python 3.13.16 |
| Method | `pytest` in 8 file-shards (`-q -rfEs`), plus the subdirectories, platform directory, platform unittest suite, TUQC (cwd inside the package), the drift / import / deploy sentries, the Intelligence self-test, flake8, black and the frontend gates; every stage log retained in the session scratchpad |
| Physical devices | none present (no OpenCL / CUDA / Metal runtime) |
| Environment notes | `fastapi` from the declared `ml` extra was installed (two millennium tests need it). The editable TURING install was refreshed to 1.3.0 after the merge: the first pass of shard 2 failed `test_version_single_source` against stale 1.2.0 install metadata; the shard was re-run in full after `pip install -e ./turing_universal_quantum_computer` and passed. Both outcomes are reported here. |

## Results

| Stage | Command | Result |
|---|---|---|
| Repo suite (`tests/test_*.py`, 8 shards) | `python -m pytest <files> -q -rfEs` | **4,036 passed, 0 failed, 16 skipped**, 671 subtests passed |
| `tests/test_chronus_v33`, `tests/euclid_dominance` | `python -m pytest …` | 51 passed |
| Platform directory (pyproject `testpaths`) | `python -m pytest chronus/mla1517_platform/python` | **830 passed, 0 failed, 9 skipped**, 9 subtests passed |
| Platform suite (AGENTS.md gauntlet) | `python -m unittest discover -s chronus/mla1517_platform/python` | 417 tests OK (6 skipped) |
| TUQC suite | `cd turing_universal_quantum_computer && python -m pytest tests -q` | **271 passed**, 46 subtests |
| Anti-drift | `python -m scripts.drift_sentry --verify` | PASS |
| Import audit | `python scripts/import_audit.py` | PASS — 0 findings, 0 swallowed |
| Deploy sentry | `python -m scripts.deploy_sentry` | 0 errors (3 pre-existing optional-dependency warnings) |
| Intelligence self-test | `python -X utf8 -m Intelligence.self_test` | PASS |
| Frontend | `npm ci`, `lint` (tsc), `test:ts` (vitest), `build` (vite) | all PASS; 47 tests in 7 files |
| flake8 | `python -m flake8 --count` | 15,709 (pristine `main` was 15,713) — not clean on either |
| black | `python -m black --check .` | 933 files would be reformatted (identical to pristine `main`) — not clean on either |

### Control-service smoke test (AGENTS.md §4.2)

`main.py --host 127.0.0.1 --port <p> --web-root dist/public` on this commit: `GET /api/v1/healthz` → 200 `status: ok`; `GET /` → 200 (built UI);
`GET /api/v1/readyz` → `ready: true` with honest components: `boot_audit` ready, `identity` ready, `worker_heartbeat_dir` ready, `stratum` disconnected,
`runtime_config` not_configured, `guardian` not_configured, `remote_opencl` not_configured, `custody` not_mounted, `m3_authorization` unavailable.

### Clean-wheel acceptance (P1-1 / P1-2)

Wheels built with `pip wheel --no-deps` from a `git archive` export of this commit, installed into a fresh venv holding only `numpy` plus these wheels, script run with `python -I` from outside the tree:

| Wheel | sha256 |
|---|---|
| `pythia_mla1517-0.1.0-py3-none-any.whl` | `26f9152bd53f9414cf7b6ea6d8a1c66cfeb7e295929682294064c3b118c74b5a` |
| `turing_universal_quantum_computer-1.3.0-py3-none-any.whl` | `6268ac0886d7e112bb550239b0139eef60d29b0f0aacc9a6992d3d89fa319451` |

`scripts/chronus_wheel_acceptance.py` result: `installed from: …/venv/lib/python3.13/site-packages/chronus/__init__.py`, then
`OK genesis nonce 2083236893 receipt ok True lane chronus` (exit 0): embedded `ChronusClient` submits the Bitcoin genesis `SHA256D_SCAN`, the hit nonce and digest match,
`validate_receipt(expect=…)` binds workload id / backend / policy / protocol, and `BackendRegistry().select("chronus")` returns a `ChronusVirtualIGPUHasher`.
Negative control: the same script exits 1 with an `AssertionError` when `chronus` resolves from the source tree.

## Closed since the previous artifact (13 failures → 0)

| Was failing | Class | Resolution |
|---|---|---|
| `test_fault_injection` proof-test register | lost tests | `ConstitutionWireTests` was dropped by merge `8893979` while the register still named it; restored. The other eight classes of that suite (which `docs/API_ELEVATION_GATE.md` reported as PASS) are restored in `tests/test_service_fabric_constitution.py`. |
| `test_folded_inference` | production defect | `tensor/verification.py` gated float reassociation with a dtype-blind absolute 1e-12, so a correct float32 matmul failed closed. Now the rigorous `2·γ_k·Σ\|terms\|` bound for the operand dtype, floored at 1e-12 (integer, vacuous and non-finite bounds keep the floor). 10 new tests, mutation-checked. |
| `test_operating_model` ×2 | production defect | `Intelligence/bitcoin_corpus.py` redeclared the Lucas ladder literal; now imports `lucas.ladder.SCALE_RUNGS` (identical values). |
| `test_pulvini_quantum_data_doctrine` | production defect | `frontend/scripts/_finish_hyba_migration.py` was corrupt Python since it was added; repaired. |
| `test_sequential_contracts` claims registry | docs drift | prohibited throughput/speed claims reworded in four docs. |
| `test_service_constitution` ×2 | registry drift | `'{cfg_path} absent'` registered in `ERROR_TAXONOMY.yaml`; `SERVICE_CONSTITUTION.yaml` regenerated by its renderer. |
| `test_millennium_package` ×2 | environment | need `fastapi` (declared `ml` extra); pass when installed. No repo change. |
| `test_hendrix_nonce_order`, `test_poincare_11d_nonce_order` | stale tests | rewritten for the plan-bound nonce order (`3b7d834`); the 11D test now uses a device-shaped hasher so inverting the 11D routing rule fails it. |
| `test_backend_failure_heals_and_reroutes` | stale test | the fixture device lacked `grind_target_batch`, which PYTHIA authority always dispatches through (`3381c8f`), so the injected fault never fired. The healer was not broken. |

## Defects found by this closure run itself

* An ambient-state leak: `tests/test_production_api_contract.py` persisted its config into the real `data/runtime_config.json`, and a leaked 3 H/s target throttled an unrelated mining voyage. Autouse fixtures in both test roots now isolate it.
* A regression I introduced and the gauntlet caught: the isolation fixture made `tests/conftest.py` import `pytest` unguarded, which the deploy sentry's DS02 gate rejected. Fixed in `008e879`.
* `RuntimeDaemon._select_adapter`: under `preferred_accelerator` an available physical adapter that could not run the workload blocked the declared software fallback; fixed.
* `OpenCLUhdAdapter` advertised `SHA256D_SCAN` while `execute()` always raises, so the Chronus lane would fail on an Intel OpenCL host; it now advertises nothing (device presence is still attested by `probe()`).
* `RuntimeDaemon.root` was a relative path on a process-global singleton; a later `chdir` made the lane probe fail with ENOENT. It is now resolved to an absolute path.

## Skips (25) — external gates, none counted as passes

`tests/` (16):

| Where | n | Reason |
|---|---|---|
| `tests/test_bitcoin_hasher_gpu.py:41` | 1 | could not import 'pyopencl': No module named 'pyopencl' |
| `tests/test_execution_router.py:525` | 1 | NOT_RUN: no OpenCL device (No module named 'pyopencl') |
| `tests/test_execution_router.py:541` | 1 | NOT_RUN: no OpenCL device (No module named 'pyopencl') |
| `tests/test_execution_router.py:552` | 1 | NOT_RUN: no OpenCL device (No module named 'pyopencl') |
| `tests/test_execution_router.py:563` | 1 | NOT_RUN: no OpenCL device (No module named 'pyopencl') |
| `tests/test_chronus_native_hash.py:109` | 1 | CUDA unavailable: CuPy/CUDA runtime unavailable: No module named 'cupy' |
| `tests/test_chronus_vigpu_acceptance.py:235` | 1 | physical accelerator evidence requires target host OpenCL device; run: python -m bench.chronus_igpu_evidence --size 512 --iterations 20 |
| `tests/test_chronus_vigpu_acceptance.py:244` | 1 | Azure/GCP execution pending credentials and deploy evidence; deployment packages may validate offline but cloud-run is an external gate |
| `tests/test_chronus_vigpu_acceptance.py:252` | 1 | pool acknowledgement requires live stratum; local_result ≠ accepted share |
| `tests/test_hash_pipeline.py:243` | 1 | OpenCL backend required |
| `tests/test_hash_pipeline.py:299` | 1 | OpenCL backend required for midstate cache test |
| `tests/test_golden_stride.py:150` | 1 | NOT_RUN: no OpenCL device on this host |
| `tests/test_hendrix_opencl.py:44` | 3 | could not import 'pyopencl': No module named 'pyopencl' |
| `tests/test_hendrix_opencl.py:73` | 1 | could not import 'pyopencl': No module named 'pyopencl' |

Platform directory (9):

| Where | n | Reason |
|---|---|---|
| `chronus/mla1517_platform/python/test_hardware_voyage.py:117` | 1 | NOT_RUN: no OpenCL device (gpu lane unavailable: OpenCL probe failed: No module named 'pyopencl') |
| `chronus/mla1517_platform/python/test_hardware_voyage.py:121` | 2 | NOT_RUN: no OpenCL device (gpu lane unavailable: OpenCL probe failed: No module named 'pyopencl') |
| `chronus/mla1517_platform/python/test_host_hardware.py:56` | 1 | build host/libmla1517_mmio.so first |
| `chronus/mla1517_platform/python/test_host_hardware.py:31` | 1 | build host/libmla1517_mmio.so first |
| `chronus/mla1517_platform/python/test_host_hardware.py:78` | 1 | build host/libmla1517_mmio.so first |
| `chronus/mla1517_platform/python/test_phase4_api.py:232` | 1 | AL HARAS guardian dependency is installed |
| `chronus/mla1517_platform/python/test_primedb_engine.py:28` | 1 | build host/libprimedb_storage.so first |
| `chronus/mla1517_platform/python/test_primedb_engine.py:13` | 1 | build host/libprimedb_storage.so first |

## CI state

Every check on every pushed head (`aea98a8`, `870b774`, `008e879`, `4a5242f`, `774c5e0`) fails in about 3 seconds with `runner_id: 0` and no runner assigned: the repository owner confirmed Actions minutes are exhausted.
No workflow step executed, so nothing about the code can be inferred from CI. State: **CI_BLOCKED**. Local execution above is the evidence.

## What this does and does not establish

* **Established (software, this host):** the PYTHIA → CHRONUS route executes from the process entry point (`mining_runtime._main_async` with `PYTHIA_EXECUTION_DEVICE=chronus`) to a scripted pool acknowledgement with `executed_route: chronus_batch` and `evidence_class: SOFTWARE_VERIFIED`; the genesis known-answer, lying- and reordering-adapter rejection, fail-closed policy, tenant isolation, receipt binding, ledger corruption rejection, THESEUS fresh-process recovery, TURING replay rejection and M3 custody paths all pass; the clean-wheel acceptance passes; no failing test remains in any suite listed above.
* **Not established:** any CI result; physical device execution or performance; live pool acknowledgement or an accepted share; cloud execution; fleet throughput or the governed 1e19 H/s hashrate ceiling; hardware-rooted attestation; AL HARAS admission wiring (a hook exists, no production caller passes it); repo-wide flake8 / black cleanliness (not clean on `main` either).
