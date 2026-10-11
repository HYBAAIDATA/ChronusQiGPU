# CHRONUS audit-closure report — `774c5e0`

Companion to `merged_head_closure_774c5e0.md` (the retained test run). Claim states used: `VERIFIED`, `SOURCE_WIRED`,
`IMPLEMENTED_NOT_EXECUTED`, `HONEST_UNAVAILABLE`, `DEVICE_OBSERVED`, `CI_BLOCKED`, `EXTERNAL_EVIDENCE_REQUIRED`, `UNMEASURED`.
"VERIFIED" here means an executed local software test is named; it never means physical hardware, CI or a live pool.

## A. Final revision

| | |
|---|---|
| Repository | `QuantumPhi2/PhiMiner` |
| Branch | `claude/dreamy-meitner-06b49k` (PR #113, draft) |
| SHA | `774c5e0b678296fb620ad8c05676aa78ec4e695e` |
| Base | `origin/main` @ `509fd24`, merged in `4a5242f` |
| Audited HEAD (original audit) | `1fde89e`, an ancestor |

## B. Starting audit gaps

| Gate | Status | Patch (file::symbol) | Verified by | State |
|---|---|---|---|---|
| P0-1 production caller | CLOSED | `mining_runtime.py::_main_async` → `PythiaProductionMiningCoordinator` → `mining_hasher.py::ChronusVirtualIGPUHasher.grind_target_batch` → `ChronusClient`; opt-in lane `PYTHIA_EXECUTION_DEVICE=chronus` (not in the `auto` order) | `test_production_loop_e2e.py::test_share_submits_through_the_chronus_lane_from_the_production_entry` (entry point to scripted-pool ack); `test_chronus_vigpu_production_route.py::test_production_coordinator_executes_through_chronus_virtual_igpu`; `tests/test_chronus_production_route.py::test_plan_executes_through_chronus_and_returns_a_host_verified_candidate` | VERIFIED (scripted pool) |
| P0-2 SHA256d | CLOSED | `adapters.py::CPUEmulatorAdapter._sha256d_scan` (header76 + LE nonce, bounds-checked, explicit ordered `nonces`) | `test_chronus_vigpu_sha256d_contract.py::test_known_vector_matches_published_genesis_hash`, `test_nonce_bounds_fail_closed`, `test_explicit_nonce_batch_preserves_submitted_order` | VERIFIED |
| P0-3 host re-verification | CLOSED | `host_verify.py::verify_candidate/verify_hits`; `execution_router.py::_independent_recheck`; `verifier.py::_verify_sha256d_scan` | `test_host_verifier_rejects_forged_candidates`; `test_chronus_production_route.py::test_lying_adapter_is_a_device_error_and_never_a_candidate`; `test_chronus_vigpu_production_route.py::test_lying_adapter_never_reaches_pythia_as_a_candidate` | VERIFIED |
| P0-4 unknown workload | CLOSED (plain `ValueError`, no dedicated class) | `abi.py::Workload.__post_init__/from_dict` | `test_unknown_workload_kind_is_rejected_not_custom`, `test_malformed_serialized_workload_is_rejected` | VERIFIED |
| P0-5 unknown policy | CLOSED (plain `ValueError`) | `abi.py::Workload`, `runtime.py::RuntimeDaemon._policy` | `test_invalid_policy_strings_rejected`, `test_valid_policies_execute` | VERIFIED |
| P0-6 `allow_software_fallback` | CLOSED | `runtime.py::RuntimeDaemon._select_adapter` (now also falls back when an available physical adapter cannot run the kind) | `test_fallback_disabled_fails_closed_and_enabled_records_provenance`, `test_physical_adapter_that_cannot_run_the_kind_does_not_block_software_fallback` | VERIFIED. Receipt carries `requested_policy`, `actual_backend`, `route_reason`; there is no dedicated requested-backend or `fallback_reason` field. |
| P0-7 authority wording | CLOSED | `chronus/device.py` (`CLAIM_BOUNDARY`), `chronus/__init__.py`; `compute_substrate: "chronus_execution_plane"` across device/fabric/seam | `tests/test_chronus_scale_paradigm.py` asserts the substrate value; wording otherwise by review | VERIFIED (partly pinned by tests) |
| P0-8 tenant isolation | CLOSED | `memory.py::VirtualMemoryPlane.store/retrieve` (handle = sha256 of tenant + object id; `PermissionError` on mismatch) | `test_cross_tenant_handles_are_isolated`, `test_daemon_denies_cross_tenant_retrieve_and_isolates_identical_bytes` (daemon level, no reservation leak) | VERIFIED. No shared-blob dedup (the prompt said "if useful"). |
| P1-1 packaging | CLOSED | `pyproject.toml` `packages` includes `chronus.virtual_igpu`, `chronus.measurement.*`, `chronus.paradigm` | clean-wheel run (below) | VERIFIED |
| P1-2 clean-wheel workload | CLOSED | `scripts/chronus_wheel_acceptance.py` (now takes the source tree as an argument) | recorded run in `merged_head_closure_774c5e0.md`: genesis nonce `2083236893`, receipt ok, lane `chronus`; negative control exits 1 | VERIFIED (local, not CI) |
| P1-3 receipt binding | CLOSED, opt-in | `evidence.py::validate_receipt(expect=…)` over `BINDABLE_RECEIPT_FIELDS` | `test_receipt_binds_every_identity_field`, `test_receipt_expectations_bind_kernel_and_package` | VERIFIED. Only fields the caller passes are checked; no production path calls the validator (the wheel script and conformance do). |
| P1-4 ledger corruption | CLOSED with gaps | `evidence.py::EvidenceLedger._load` raises on bad JSON / chain / hash / HMAC | `test_ledger_rejects_every_corruption_class`, `test_ledger_reload_rejects_tampering` | VERIFIED. Tail truncation and edit-plus-rehash without the optional HMAC key are not detected (documented by `test_adversarial_rehash_warning_or_mismatch`). |
| P1-5 custody where required | CLOSED where required | `runtime.py::_commit_custody` for `constraints={"custody":"required"}`; M3 strict path `storage_recorder.py` / `m3_coordinator.py::submit_candidate` | `test_chronus_theseus_restart_contract.py::*`; `test_m3_runtime_closure.py::test_strict_verified_proof_is_custodied_before_submission_record` | VERIFIED. The PYTHIA mining workload does not request Chronus-level custody (mining does not require it). |
| P1-6 fresh-process restore | CLOSED | `TheseusFileCustody` reopened by a subprocess | `test_verified_result_is_committed_then_recovered_by_a_new_process` | VERIFIED |
| P1-7 remote production security | CLOSED for production mode | `wire.py::serve(production=True, tls_terminated_externally=…, authorizer=…)`: token required, TLS-termination acknowledged, generic error bodies; `client.py` enforces HTTPS + token off-loopback | fail-closed contract suite | VERIFIED. `production` defaults off unless `CHRONUS_VIGPU_PRODUCTION` is set; AL HARAS is not wired to the `authorizer` hook. |
| P1-8 reservation lifecycle | CLOSED | `runtime.py::_execute_with_deadline` (`_draining`, `TIMED_OUT_BUT_EXECUTION_DRAINING`) | `test_reservation_is_held_until_timed_out_worker_terminates` | VERIFIED |
| P1-9 delivery mode | CLOSED | `chronus/delivery.py` uses the ABI `DeliveryMode`; `client.py` rejects endpoint+embedded, missing endpoint, `cloud_instance` | `test_chronus_delivery.py`, `test_remote_unavailable_never_falls_back_to_local` | VERIFIED |
| P1-10 identity truthfully bound | CLOSED for software | receipt `actual_backend`/`actual_device`, `evidence_class: SOFTWARE_VERIFIED`, `physical_device_executed` false for `cpu-emulator` | route and e2e tests assert the software label | VERIFIED. Device and kernel identity are adapter-supplied; physical identity is `EXTERNAL_EVIDENCE_REQUIRED`. |
| §20 backend ladder | HONEST_UNAVAILABLE | vigpu CUDA / Metal adapters are `UnavailableAdapter`; `OpenCLUhdAdapter.execute()` always raises and, since this closure, advertises no operation | `test_uhd_adapter_never_advertises_what_it_cannot_execute` | HONEST_UNAVAILABLE |
| §22 Salamander | P2 (no authorised CHRONUS contract) | none | — | not wired, stated |
| §23 AL HARAS | hook only | `RuntimeDaemon(admission_policy=…)` | `test_admission_policy_hook_denies_before_execution` (uses a lambda) | SOURCE_WIRED; the real policy authority is not reached |
| §24 TURING→CHRONUS | GATED / NOT YET WIRED | none (allowed by the prompt) | `test_turing_production_pipeline.py::test_chronus_lane_is_honest_on_cpu_host`; replay rejection: `test_pipeline_replay_rejects_cross_run_certificate_bundle`, `test_pipeline_replay_rejects_result_payload_substitution` | gated |

## C. Files changed

The route, verifier, custody, packaging and hardening work landed on `main` through earlier merged PRs (#95, #103, #108 and the CHRONUS verifier from #90).
PR #113 relative to `main` @ `509fd24`: 31 files, +1657 / -111.

* **Production:** `tensor/verification.py` (dtype-aware reassociation bound), `Intelligence/bitcoin_corpus.py` (single ladder source),
  `chronus/virtual_igpu/runtime.py` (`_select_adapter`, absolute `RuntimeDaemon.root`), `chronus/virtual_igpu/adapters.py` (`OpenCLUhdAdapter`),
  `chronus/mla1517/mining/{backend_registry,storage_recorder,m3_coordinator}.py` (`BackendSelection.as_dict`, strict-M3 receipt preservation, `_m3_required`),
  `aethel/enterprise/system_relations.py` and `turing_universal_quantum_computer/.../pipeline.py::_replay` (TURING custody boundary and replay),
  `frontend/scripts/_finish_hyba_migration.py` (repaired).
* **Docs / registries:** `docs/ERROR_TAXONOMY.yaml`, `docs/SERVICE_CONSTITUTION.yaml` (regenerated), `docs/kellogg/README.md`, and four claims-gate rewordings (`docs/CHRONUS.md`, `docs/PYTHIA_MINING_AUTHORITY.md`, `docs/DETERMINISTIC_10_EH_MATHEMATICAL_CAPACITY.md`, `docs/papers/FAIL_CLOSED_VIRTUAL_ACCELERATORS.md`). The Chronus capability documentation (`chronus/README.md` §19–20) landed earlier and is not in this diff.
* **Tests:** new `tests/test_service_fabric_constitution.py` (49 restored tests), `tests/test_chronus_vigpu_fail_closed_contract.py` (selection, UHD, tenant, chdir tests), `chronus/mla1517_platform/python/test_production_loop_e2e.py` (Chronus entry-point test), rewritten nonce-order tests, `tests/test_tensor_verification.py`, two hermetic-config `conftest.py` files, and the earlier merge-integration test fixes (`tests/test_turing_production_pipeline.py`, `tests/test_chronus_hardware_rooted_adversarial.py`, `tests/test_remote_hasher.py`).
* **Scripts / evidence:** `scripts/chronus_wheel_acceptance.py`; `evidence/chronus/merged_head_closure_a05eb00.md` (earlier run), `merged_head_closure_774c5e0.md` and this report.

Exact list: `git diff --stat 509fd24..774c5e0`.

## D. Canonical PYTHIA → CHRONUS production route

```text
PYTHIA PRODUCTION CALLER
  chronus/mla1517_platform/python/mining_runtime.py::_main_async  (select_execution_backend; M3PythiaProductionMiningCoordinator(execution_hasher=selection.hasher); run_execution_loop)
    ↓ [A]
PYTHIA COORDINATOR / PLAN
  chronus/mla1517/mining/coordinator.py::run_execution_loop → m3_coordinator.py::M3PythiaProductionMiningCoordinator.search_current_job → coordinator.py::search_current_job
  plan: geodesic_support.py::PythiaProductionMiningCoordinator._apply_pythia_authority (executor_route = _pythia_batch_route() = "chronus_batch")
    ↓ [B]
ROUTER → CHRONUS CLIENT
  geodesic_support.py::PythiaProductionMiningCoordinator._router_for → ProductionExecutionRouter.execute_plan → execution_router.py::ExecutionRouter.execute_plan
  → geodesic_support.py::ProductionExecutionRouter._run_chunk → chronus/virtual_igpu/mining_hasher.py::ChronusVirtualIGPUHasher.grind_target_batch → _submit
  → chronus/virtual_igpu/client.py::ChronusClient.submit
    ↓ [C]
WORKLOAD VALIDATION
  chronus/virtual_igpu/abi.py::Workload.__post_init__
    ↓ [D]
POLICY / ADMISSION
  chronus/virtual_igpu/runtime.py::RuntimeDaemon.submit (tenant cap, quota, deadline, admission_policy hook, custody-required check)
    ↓ [E]
BACKEND SELECTION
  runtime.py::RuntimeDaemon._select_adapter
    ↓ [F]
EXECUTION
  runtime.py::RuntimeDaemon._execute_with_deadline → chronus/virtual_igpu/adapters.py::CPUEmulatorAdapter.execute → _sha256d_scan
    ↓ [G]
INDEPENDENT VERIFICATION
  (1) verifier.py::verify_workload_result → _verify_sha256d_scan   (2) host_verify.py::verify_hits/verify_candidate (from mining_hasher)   (3) execution_router.py::_independent_recheck
    ↓ [H]
RECEIPT
  runtime.py::RuntimeDaemon.submit builds the ExecutionReceipt and appends to evidence.py::EvidenceLedger; retained as ChronusVirtualIGPUHasher.last_result
    ↓ [I]
THESEUS CUSTODY [if required]
  runtime.py::_commit_custody (only when constraints custody=required); M3 strict mode: m3_coordinator.py::submit_candidate → authorize_and_custody
    ↓ [J]
PYTHIA RESULT
  execution_router.py candidate dict → coordinator.py::search_current_job → submit_candidate
```

| Arrow | Class | Evidence |
|---|---|---|
| A entry point → coordinator | VERIFIED | `test_production_loop_e2e.py::test_share_submits_through_the_chronus_lane_from_the_production_entry` launches `mining_runtime._main_async` with `PYTHIA_EXECUTION_DEVICE=chronus`; the causal log shows `executed_route: chronus_batch`, `evidence_class: SOFTWARE_VERIFIED` |
| B coordinator → router → client | VERIFIED | the same test; `test_chronus_vigpu_production_route.py::test_production_coordinator_executes_through_chronus_virtual_igpu`; `tests/test_chronus_production_route.py` |
| C workload validation | VERIFIED | `test_unknown_workload_kind_is_rejected_not_custom`, `test_malformed_serialized_workload_is_rejected` |
| D policy / admission | VERIFIED for core checks; `EXTERNAL_EVIDENCE_REQUIRED` for AL HARAS | `test_admission_policy_hook_denies_before_execution` uses a lambda; the real authority is not reached |
| E backend selection | VERIFIED | `test_valid_policies_execute`, `test_required_adapter_and_device_unavailable_fail_closed`, `test_physical_adapter_that_cannot_run_the_kind_does_not_block_software_fallback` |
| F execution | VERIFIED (software emulator); physical adapters `HONEST_UNAVAILABLE` | `test_chronus_vigpu_sha256d_contract.py` |
| G independent verification | VERIFIED | `test_lying_adapter_is_a_device_error_and_never_a_candidate`, `test_runtime_verifier_rejects_wrong_probe_order` |
| H receipt | VERIFIED for creation, retention and (opt-in) validation | route tests assert `last_result["receipt"]`; `test_receipt_binds_every_identity_field` |
| I custody | VERIFIED standalone; not requested by the mining workload; M3 strict path `SOURCE_WIRED` plus recorder-level tests | `test_chronus_theseus_restart_contract.py`; `test_m3_runtime_closure.py` |
| J result | VERIFIED against a scripted local pool; live pool `EXTERNAL_EVIDENCE_REQUIRED` | the e2e test asserts the pool received and acknowledged one submit |

No hop is `UNREACHABLE`.

## E. SHA256d correctness evidence

`tests/test_chronus_vigpu_sha256d_contract.py`: `test_known_vector_matches_published_genesis_hash` (genesis header → published hash, byte-reversed);
`test_scan_assembles_header76_plus_little_endian_nonce` (adapter reproduces the genesis hit at nonce 2083236893);
`test_scan_ignores_nonce_bytes_embedded_in_header80`; `test_range_scan_work_count_stops_at_first_hit` (`checked == 3`); `test_no_hit_counts_every_nonce` (`checked == 7`);
`test_explicit_nonce_batch_preserves_submitted_order`; `test_nonce_bounds_fail_closed` (9 cases); `test_header_must_be_80_bytes_and_target_in_range`;
`test_host_verifier_rejects_forged_candidates` (wrong nonce, wrong hash, above target, outside range, outside batch).
Negative candidates through the production path: `test_lying_adapter_is_a_device_error_and_never_a_candidate`, `test_lying_adapter_never_reaches_pythia_as_a_candidate`, `test_runtime_verifier_rejects_wrong_probe_order`.

## F. Fail-closed policy evidence

`tests/test_chronus_vigpu_fail_closed_contract.py`: unknown workload (5 bad kinds), `CUSTOM` still allowed when explicit, malformed serialized workload, tampered content hash,
invalid policy strings (empty, wrong case), required adapter / device unavailable → `AdapterUnavailable` with in-flight back to 0, fallback disabled → fail closed, fallback enabled → provenance recorded;
`tests/test_chronus_production_route.py::test_missing_chronus_lane_fails_closed`.

## G. Tenant isolation evidence

`test_cross_tenant_handles_are_isolated` (memory plane: same bytes, different handles; A cannot read B's and vice versa; a shared content id grants nothing);
`test_daemon_denies_cross_tenant_retrieve_and_isolates_identical_bytes` (daemon level: cross-tenant `RETRIEVE` raises `PermissionError`, no reservation leak, identical bytes get distinct object ids).
Not found: a cross-tenant test of the evidence ledger or the artifact plane. The legacy `migrate()` does no caller check.

## H. Packaging evidence

Clean-wheel run recorded in `merged_head_closure_774c5e0.md`: both wheels built from a `git archive` export of this commit (sha256 recorded), installed into a fresh venv with only `numpy`,
`python -I` from outside the tree: genesis `SHA256D_SCAN` through an embedded `ChronusClient` finds nonce `2083236893`, `validate_receipt(expect=…)` passes, `BackendRegistry().select("chronus")` returns the Chronus hasher.
The same script exits 1 when `chronus` resolves from the source tree.

## I. Receipt / evidence integrity

`test_receipt_binds_every_identity_field` (14 fields mutated and stripped); `test_receipt_expectations_bind_kernel_and_package`; `test_ledger_rejects_every_corruption_class` (truncated line, malformed JSON, missing middle entry, reordered entries, altered chain digest);
`test_validate_receipt_rejects_cpu_as_hardware_rooted`; `tests/test_chronus_hardware_rooted_adversarial.py::test_uncorroborated_hardware_rooted_claims_fail_closed` (6 forged-attestation shapes downgraded to `runtime_signed`) and
`test_clean_self_derived_chain_is_not_hardware_rooted_without_an_external_verifier`. `test_corroborated_attestation_survives` uses a stand-in verifier that replays the adapter's own record: it proves the mechanism, not a real trust root.

## J. THESEUS custody evidence

`test_verified_result_is_committed_then_recovered_by_a_new_process`: a `RuntimeDaemon` with `TheseusFileCustody` commits the evidence for a custody-required scan; the parent drops all handles; a `subprocess` reopens custody with the same key, verifies the record
(producer `chronus`, kind `vigpu_execution_evidence`, payload digest equals the evidence digest) and reads `status ok`. Also `test_required_custody_without_custody_fails_closed`, `test_custody_failure_is_not_swallowed_and_withholds_the_result`, `test_unverifiable_commit_fails_closed`.
The same HMAC key is shared with the child; the custody backend is `TheseusFileCustody` in `hyba_db/`.

## K. Tests actually executed

Commands, counts and durations are in `merged_head_closure_774c5e0.md`: 4,036 passed / 0 failed / 16 skipped in `tests/`; 51 in the `v33` / `euclid_dominance` directories; 830 passed / 0 failed / 9 skipped in the platform directory;
417 platform unittest tests OK; 271 TUQC; drift, import-audit, deploy sentries and the Intelligence self-test PASS; frontend lint, vitest (47) and build PASS; control-service smoke test PASS; clean-wheel acceptance PASS.
All 25 skips are external gates and none is counted as a pass. flake8 (15,709) and black (933 files) are not clean on this branch or on `main`.

## L. CI state

`CI_BLOCKED`. Every check on every pushed head fails in about 3 seconds with `runner_id: 0` and no runner assigned; the repository owner confirmed GitHub Actions minutes are exhausted.
No workflow step executed, so there is no source-test signal from CI either way. Local execution above is the evidence.

## M. Physical backend evidence

No committed evidence file records a device observation. `evidence/chronus/capability_probe_3b456aa.json` records `physical_device_observed: false`; `artifacts/chronus107-evidence.json` records `physical_execution: false`. The host has no `pyopencl`, `cupy`, `mlx` or `torch`.

| Backend | Software implemented | Physical device observed | Workload executed | Correctness verified | Performance measured |
|---|---|---|---|---|---|
| cpu-emulator virtual iGPU adapter | YES | NO | YES (software) | YES (software) | YES on a non-physical host: ~433–452k verified H/s through the submit path (`capability_probe_3b456aa.json`); raw single-core hashlib 1.15 MH/s |
| OpenCL UHD adapter (vigpu) | probe only; `execute()` raises, advertises no operation | NO | NO | NO | NO |
| OpenCL mining lane (`BitcoinHasher`, registry `gpu`) | YES (separate from the vigpu adapter) | NO | NO (tests skip) | NO | NO |
| CUDA | `ChronusCudaSha256dHasher` in source; vigpu adapter is `UnavailableAdapter` | NO | NO | NO | NO |
| Metal | `ChronusMetalSha256dHasher` in source; vigpu adapter is `UnavailableAdapter` | NO | NO | NO | NO |
| Remote service | `remote_gpu.py` + `ChronusClient` remote mode | NO | stub only (`tests/test_remote_hasher.py`) | stub level | NO |
| Native `libmla1517` | source only; no `.so` built | NO | NO | NO | NO |
| `cpu_reference` | YES | n/a | YES | YES (hashlib oracle) | UNMEASURED as a distinct lane |

The governed 1e19 H/s hashrate ceiling is a constant in code (`target_measured: False`); no measurement supports it.

## N. Remaining P2 / P3 gates

Allowed by the prompt to remain evidence gates: ROCm / oneAPI, TURING→CHRONUS VQC offload, cloud deployment, hardware-rooted attestation, fleet qualification, live pool acknowledgement, accepted share, the hashrate ceiling, thermal / power qualification, production SLA.
Also open and bounded: Salamander has no authorised CHRONUS contract; AL HARAS is a hook with no production caller; physical adapters (OpenCL / CUDA / Metal) need target-host evidence.

Weaker than it sounds, so nobody overreads this report:

* `submit_via_virtual_igpu` (the symbol the audit named) still has no non-test caller; the route closes through `ChronusVirtualIGPUHasher` → `ChronusClient`.
* The PYTHIA mining workload carries no `constraints`, so it does not request Chronus-level custody; custody on the mining path is the separate M3 strict mode, and no test combines the M3 coordinator with the Chronus lane.
* "Typed rejection" is a plain `ValueError` / `AdapterUnavailable`, not dedicated exception classes.
* `validate_receipt` is opt-in and not called by any production path; device and kernel identity come from the adapter.
* Ledger integrity is chain plus hash; the HMAC key is optional, tail truncation is undetectable and an edit with a recomputed unkeyed hash passes (documented by a test).
* The float reassociation bound grows linearly with the term count: for float32 with a large contraction length it can admit corruption smaller than the rounding envelope. It is the rigorous envelope, reported as the verdict's `tolerance`.
  Some shapes (constant arrays, size-1 segments, integer matmul) return `unverified` from the folded recompute; none returns a false pass.
* `control_api._readiness_components` emits an `m3_authorization` component that the registry's `pythia.ready` response-schema string does not list (documentation drift, not a test failure).

## O. Claims still unavailable

```text
physical GPU performance
hardware-rooted attestation
cloud production execution
fleet throughput
pool ACK (live)
accepted share
the governed 1e19 H/s hashrate ceiling as a measured rate
production SLA
CI-green on any head
```

## P. Final verdict

```text
CANONICAL_EXECUTION_READY_WITH_EXTERNAL_HARDWARE_GATES
```

Why not `NOT_READY` or `UNDETERMINED`: the canonical production software route is reachable end to end and exercised from the process entry point; all eight P0 gates pass; every P1 gate is closed or explicitly bounded above; every suite listed in `merged_head_closure_774c5e0.md` passes with no failing test.

Why not the bare software verdict: what remains is not software work. It is physical-device evidence, a live pool, cloud execution, hardware-rooted attestation and a working CI runner, plus the AL HARAS admission wiring, which is a hook today.
Software execution is VERIFIED on the software emulator only; no physical-device result is claimed anywhere.
