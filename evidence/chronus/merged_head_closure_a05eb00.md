# Merged-head software closure run — `a05eb00`

Local execution evidence (GitHub Actions minutes are exhausted, so CI proves nothing here).

| Field | Value |
|---|---|
| Tested commit | `a05eb007e3dfdf1522f6a36e5aa306f8efd9c2fe` (branch `claude/dreamy-meitner-06b49k`, PR #113) |
| Base | `origin/main` @ `518f392` (includes #92, #99, #100, #102, #103, #104, #105–#109); diff vs base = the 8 files fixed in PR #113 |
| Host | 4 vCPU Intel Xeon @ 2.10 GHz, 15.7 GB, Linux 6.18, Python 3.13.16 |
| Method | `pytest` in 8 file-shards (`-q -rs`), failing shards re-run with `-rfEs`; extra stages for subdirectories; every stage log retained in the session scratchpad |
| Physical devices | none present (no OpenCL / CUDA / Metal / GPU runtime) |

## Results

| Stage | Command | Result |
|---|---|---|
| Repo suite (top-level `tests/test_*.py`, 8 shards) | `python -m pytest <files> -q -rs` | **3,958 passed, 10 failed, 16 skipped**, 669 subtests passed |
| `tests/test_chronus_v33`, `tests/euclid_dominance` | `python -m pytest …` | 51 passed |
| Platform directory (pyproject `testpaths`) | `python -m pytest chronus/mla1517_platform/python` | 826 passed, **3 failed**, 9 skipped, 9 subtests |
| Platform suite (AGENTS.md gauntlet) | `python -m unittest discover -s chronus/mla1517_platform/python` | PASS (rc 0) |
| TUQC suite | `cd turing_universal_quantum_computer && python -m pytest tests -q` | **271 passed**, 46 subtests |
| Anti-drift | `python -m scripts.drift_sentry --verify` | PASS |
| Import audit | `python scripts/import_audit.py` | PASS — 0 findings, 0 swallowed |
| Deploy sentry | `python -m scripts.deploy_sentry` | 0 errors (3 pre-existing optional-dependency warnings) |
| Intelligence self-test | `python -X utf8 -m Intelligence.self_test` | PASS (rc 0) |
| flake8 | `python -m flake8 --count` | 15,710 (pristine `main`: 15,713) — not clean on either |
| black | `python -m black --check .` | 933 files would be reformatted (identical on pristine `main`) — not clean on either |

## Failures (13) — none are new

Every failed test was reproduced on a pristine base (`1d1f272`, `54bfdfd` or `518f392`); the one failing subtest also appears in the earlier full run on `3b456aa`. None involve the files changed by PR #113.

`tests/` (10 + 1 subtest):

| Test | Area |
|---|---|
| `test_fault_injection::ScenarioRegisterTests::test_proof_tests_exist_in_this_module_or_companion` | fault-injection scenario register |
| `test_folded_inference::test_folded_linear_pilot_matches_dense_numpy_path` | folded inference |
| `test_millennium_package::MillenniumNoMockTests::test_reasoning_service_imports_real_backends` | millennium |
| `test_millennium_package::MillenniumNoMockTests::test_reasoning_service_runs_real_probe` | millennium |
| `test_operating_model::test_deployed_paths_have_no_bypass_or_ladder_drift` | operating model |
| `test_operating_model::test_goal_stack_starvation` | operating model |
| `test_pulvini_quantum_data_doctrine::test_repository_pulvini_data_boundary_gate_passes` | PULVINI boundary |
| `test_sequential_contracts::test_claims_registry_loads_and_evaluates_clean` | claims registry (prohibited claims in docs) |
| `test_service_constitution::TestRenderedDocsSync::test_constitution_doc_is_in_sync` | rendered docs |
| subtest: `test_service_constitution::TestErrorTaxonomy::test_emitted_dynamic_details_are_registered` (`'{cfg_path} absent'`) | error taxonomy |

Platform directory (3):

| Test | Note |
|---|---|
| `test_hendrix_nonce_order::test_hendrix_is_the_coordinators_default_order` | Stale since `3b7d834`: the nonce order is now plan-bound, so mutating `PYTHIA_NONCE_ORDER` after the plan is built no longer changes it. Needs a test redesign, not a production fix. |
| `test_poincare_11d_nonce_order::test_production_coordinator_routes_11d_through_cpu_reference` | Same cause. |
| `test_production_loop_e2e::test_backend_failure_heals_and_reroutes` | `timed out waiting for RESTART_LANE dispatched` — self-healing reroute; **not yet diagnosed**. |

## Fixed by this branch (were failing on `main` before PR #113)

TURING shared-custody boundary refused every genuine run (4 tests); `VQCPipeline._replay` `NameError` (1 test + 2 replay-attack tests that never ran); M3 proof-receipt overwrite and stale-job coordinator (2 tests); `BackendSelection.as_dict` crashed for hashers holding locks, making the `remote` and `chronus` lanes unselectable with an evidence path (1 test); hardware-rooted corroboration test (1); fleet partial-coverage test that hung >150 s (1).

## Skips (25) — external gates, none counted as passes

* No OpenCL runtime (`pyopencl` absent): `test_hardware_voyage` (3), `test_execution_router` (4), `test_golden_stride`, `test_hash_pipeline` (2), `test_hendrix_opencl` (4), `test_bitcoin_hasher_gpu`.
* No CUDA runtime (`cupy` absent): `test_chronus_native_hash`.
* Native libraries not built: `test_host_hardware` (3, `libmla1517_mmio.so`), `test_primedb_engine` (2, `libprimedb_storage.so`).
* Physical accelerator evidence needs a target-host OpenCL device; cloud execution needs credentials; pool acknowledgement needs a live Stratum pool (`test_chronus_vigpu_acceptance`, 3).
* `test_phase4_api:232` — skipped because the AL HARAS guardian dependency is installed.

## What this does and does not establish

* **Established (software, this host):** PYTHIA → CHRONUS ordered-batch execution, explicit-nonce verification, lying/reordered adapter rejection, M3 lease/submit and custody paths, TURING certificate and result-substitution replay rejection, and the import/drift/deploy gates all pass on the merged head with PR #113 applied. No new failure relative to the pre-existing set.
* **Not established:** a clean repo-wide suite (13 pre-existing failures remain), any CI result, physical device execution, live pool acknowledgement or accepted share, fleet/10 EH/s measurement, hardware-rooted attestation.
