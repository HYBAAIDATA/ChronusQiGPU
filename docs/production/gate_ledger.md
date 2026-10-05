# Gate Ledger — executed states @ QuantumPhi2/PhiMiner

**Executed:** 2026-10-01/02 · **Pin:** `main` @ `d1cb649` + working-tree changes in this PR · **Host:** Windows Server, Python 3.12.10 (`C:/Python312/python.exe`), Node 20.19.0, no OpenCL platform (`clGetPlatformIDs → PLATFORM_NOT_FOUND_KHR`), no C++17 toolchain, no `make`, no `gh`.

Convention per the repo's evidence culture: a row is **PASS** only with an artifact or executed output on disk; **GATED** means the gate exists and is correct but an external prerequisite (device, secret, runner, toolchain) is absent — the exact unblock requirement is named; **FAIL** means the gate ran and reported failure; **NOT_RUN** means not executed (reason recorded). Missing execution is missing evidence, not an observed zero.

## Assurance gates (`make/gates.mk` GATE_TARGETS → `results/*.json` via `scripts/gate_runner.py`)

On this host there is no `make` and no `python3` on PATH — every gate was run as `C:/Python312/python.exe scripts/<script>.py` from the repo root.

| Gate | Command | State | Evidence / reason |
|---|---|---|---|
| rule7-no-float | `scripts/rule7_no_float_gate.py` (new wrapper over `gate_impl` — see "Ledger defects fixed") | **PASS** — 17 exact paths scanned | `results/rule7-no-float.json` |
| abi-check | `scripts/abi_check.py` | **PASS** — schema v2 + 64-byte ABI | `results/abi-check.json` |
| refuted-claims | `scripts/refuted_claims_gate.py` | **PASS** — 0 unqualified refuted-claim matches | `results/refuted-claims.json`, `results/refuted-claims-violations.json` |
| import-audit | `scripts/import_audit.py` | **PASS** — 0 findings, 0 swallowed | `results/import-audit.json` |
| claim-register | `scripts/claim_register_gate.py` | **PASS** | `results/claim-register.json` |
| envelope-verify | `scripts/envelope_verify_gate.py` | **PASS** — valid accepted, tamper rejected | `results/envelope-verify.json` |
| conformance-vectors | `scripts/conformance_vectors.py` | **SKIP** — hard-coded honest skip: fewer than two independently available exact backends. Unblock: a built `emulator/build/chronus-emu` (needs C++17 toolchain, absent here) plus a second adapter per `cross_verification/` | `results/conformance-vectors.json` |
| resilience-suite | `scripts/resilience_suite.py` | **PASS** — suite retargeted at the real files (see "Ledger defects fixed") | `results/resilience-suite.json` |
| schema-freeze | `scripts/schema_freeze_gate.py` | **PASS** — schema v2 + 64-byte ABI | `results/schema-freeze.json` |
| promotion-manifest | `scripts/promotion_manifest.py` | **PASS** — conservative manifest evaluated | `results/promotion-manifest.json` |
| privileged-path-audit | `scripts/privileged_path_audit.py` | **FAIL → GATED** — 0 violations across 13 privileged routes; `MEDIATION_MANIFEST_KEY` absent → unsigned mediation evidence cannot promote. Unblock: provision `MEDIATION_MANIFEST_KEY` | `results/privileged-path-audit.json`, `results/mediation_manifest.json` |
| gate-rollup | `scripts/assert_gate_rollup.py` | **FAIL-CLOSED as designed** — 11 results aggregated; single failure is `privileged-path-audit` (above). Passes once the key is provisioned | `results/*.json` aggregate |

## Assurance manifest (`make test` / `assurance-gates`)

| Gate | Command | State | Evidence |
|---|---|---|---|
| al-haras manifest evaluation | `PYTHONPATH=.:chronus/mla1517_platform/python python -m al_haras.gate_cli config/al-haras-promotion-evidence.json` | **PASS** — all 7 subsystem targets evaluate `achieved == target` (guardian/identity/witness/schema/mediation: CONTRACTED; folded/pisot: RESEARCH), missing=[] everywhere | `results/assurance-gates.json` |

## Chronus script gates

| Gate | Command | State | Evidence / reason |
|---|---|---|---|
| chronus-1 ISA acceptance | `scripts/check_chronus_isa.py` | **PASS** — 20 instructions, exact barriers/divergence, matmul expressible | console PASS |
| chronus emulator build + checks 101–107 | `scripts/check_chronus_emulator.py` → chained `check_chronus101..107.py` | **GATED** — `C++17 compiler unavailable` (no g++/clang++/cl on this host). Unblock: install a C++17 toolchain so the emulator builds, which also feeds `cross_verification.ReferenceChronusAdapter` (unblocks conformance-vectors) | console AssertionError |
| UHD-620 physical evidence gate | `scripts/chronus_uhd620_evidence_gate.py` | **FAIL (environmental)** — `identity_negative`: on a zero-OpenCL-platform host the device resolver is never reached, so the gate cannot prove refusal of the unrequested identity (`reason='OpenCL enumeration failed'` rather than `identity not found`). Not weakened — refusal-by-absence is honest but is not the exercised resolver path. Unblock: any OpenCL platform; full evidence additionally requires a UHD 620 device | `artifacts/intel-uhd-620/` evidence set |
| Remote GPU agent — deviceless contract | `python -m chronus.mla1517.remote_gpu_agent` + live HTTP probes | **PASS** — `device_count:0` + non-empty `opencl_error`; valid POST → 503 fail-closed (never CPU fallback); malformed → 400; unknown path → 404 | `docs/evidence/remote_gpu_agent_deviceless.json` |
| remote GPU hardware acceptance | `scripts/remote_gpu_hardware_acceptance.py` | **GATED** — requires `MLA1517_REMOTE_GPU_TOKEN` + `MLA1517_REMOTE_GPU_ATTESTATION_KEY` + a reachable device-bearing agent endpoint | console: token required |
| production preflight | `scripts/production_preflight.py` | **PASS** (application profile) — python 3.12.10; `chronus.mla1517.mining.coordinator`, `control_api`, `system_fabric` importable; `data/` writable. Device/live-pool profiles remain unexercised (see GATED rows) | console JSON |
| paradigm gate | `scripts/paradigm_gate.py` | **PASS** — 5/5 legs: thesis_bounds, lemma_golden_stride, systems_vigpu_conformance, measurement_schedule_bakeoff, honesty_chaos (incl. `_LyingHardwareAdapter` negative) | `docs/evidence/paradigm_triad_latest.json` refreshed |
| deployment claims | `scripts/deployment_claims_gate.py` | **PASS** — external docs respect `claims.yaml` | console PASS |
| re-paper gate | `scripts/re_paper_gate.py` | **PASS** — M32 coverage, real sha256d proof boundary, measured chooser, behavioral claim gate. NOTE: hardware/OpenCL/pool/hashrate legs defer to the live deployment gate | console PASS |
| release gate | `scripts/release_gate.py` | **PASS** — rule7 console scan, MLA1517 reference runtime, 64-byte descriptor ABI | console PASS |
| drift sentry | `python -m scripts.drift_sentry --verify` | **PASS** | console |
| profile assembly | `scripts/profile_assembly_gate.py manifests/intent.example.yaml --intent-manifest` | **GATED** — `compile_assembly` requires `HYBA_ASSEMBLY_SIGNING_KEY` ≥32 bytes | console ValueError |
| strict hardware gate | `MLA1517_STRICT_HARDWARE_CI=1 → chronus/mla1517_platform/scripts/strict_hardware_gate.py` | **GATED** — flag unset + no OpenCL device; in CI it runs on the `[self-hosted, opencl, <device_id>]` runner | `make/gates.mk` |
| publish check runs | `scripts/publish_check_runs.py` | **NOT_RUN** — CI-only (`GITHUB_TOKEN`, checks API on a real push) | — |

## Test surfaces

| Surface | Command | State | Evidence |
|---|---|---|---|
| Root pytest | `pytest tests/ -q` | **PASS — 3497 passed, 20 skipped, 103 subtests, 0 failed** on the confirming full re-run (795s). Initial run: 3 failures — 2× missing `fastapi` env dep (`.[ml]` extra), 1× real `aethel/ovid.py` lineage collision — all fixed and re-verified | console run |
| Platform unittest | `unittest discover` in `chronus/mla1517_platform/python` | **PASS — 415 tests, 7 skipped** | console, 38s |
| TUQC pytest | `pytest tests -q` in `turing_universal_quantum_computer/` | **PASS — 197 passed, 39 subtests** | console, 392s |
| Frontend lint | `npm run lint` (`tsc --noEmit`) in `frontend/` | **PASS** | console |
| Frontend unit | `npm run test:ts` (vitest) | **PASS — 45 tests, 6 files** | console |
| Frontend build | `npm run build` | **PASS** — `dist/public` emitted | console |
| Intelligence self-test | `python -X utf8 -m Intelligence.self_test` | **PASS** — OVERALL | console |
| `Intelligence` collection deps | — | **PASS after `pip install -e ".[ml,dev]"`** — hypothesis/fastapi were missing on this host | pip log |

Node note: engine manifest wants Node ≥22 (`.nvmrc` 22.15.0); the box has 20.19.0 — all frontend gates pass on 20; the mismatch is recorded, not hidden (same convention as `validation.md`).

## Promotion pipeline legs (`promotion.yml` local equivalents)

| Step | Command | State | Reason |
|---|---|---|---|
| validate | `promotion_pipeline.py validate --subsystem guardian --target VERIFIED --commit <sha>` | **GATED** — transition legality + SHA binding reached, then `config/promotion-roles.json` absent. Unblock: a reviewed change copying `promotion-roles.example.json` with real GitHub identities (per `docs/al-haras/PROMOTION_RELEASE_AND_SERVICE_CATALOGUE.md` §20) | console |
| collect approvals | `collect_approvals.py --subsystem … --target … --commit … --authors …` | **GATED** — requires `GITHUB_TOKEN`/`GITHUB_REPOSITORY` (workflow env) + the roles file + human approvals on `promotion-*` GitHub environments | code inspection |
| advance | `advance_state.py --subsystem … --target … --commit …` | **GATED** — requires `PROMOTION_SIGNING_KEY` ≥32 bytes + `results/approvals/approvals.json`; produces signed `results/promotion_receipt.json` | console SystemExit |
| CI workflows | `ci.yml`, `pythia-ci.yml`, `pythia-push-gate.yml`, `mutation.yml`, `al-haras-evidence-gates.yml`, `euclid-*`, `mining-production-network.yml`, `hardware-acceptance.yml`, `promotion.yml`, `gitleaks`, `dependency-audit`, `azure-package`, `lucas15-operator-ablation` | **NOT_RUN locally** — CI provisions on push/PR; `hardware-acceptance` additionally needs the self-hosted OpenCL runner | — |

## Ledger defects fixed in this PR

1. **`rule7-no-float` produced no ledger artifact.** The make target ran `scripts/no_float_in_math_core.py` (console-only scanner over the 14 `chronus/mla1517/` exact-core modules) while every other gate writes `results/<gate>.json` via `gate_runner` — the rollup could not see it. Fix: extended `gate_impl.no_float` to cover the 3 canonical paths **plus** the 14-module exact core (17 paths), added `scripts/rule7_no_float_gate.py` matching the `gate_impl.main(name)` wrapper convention, repointed `make/gates.mk`. The standalone scanner is unchanged — it is still referenced by `release_gate.py`, `session_requirements_audit`, `audit_mla1517_local`, and `GAP_CLOSURE.md`.
2. **`al_haras/no_float_guard.py` Windows portability.** `read_text()` defaulted to cp1252 → `UnicodeDecodeError` (gate status ERROR) on a non-ASCII byte in the exact core. Both `scan_python` and `scan_native` now read explicit UTF-8.
3. **`resilience-suite` stale file list.** The gate hunted `test_crash_recovery.py`/`test_replay.py`/`test_policy_rotation.py`/`test_compound_failure.py` — none exist (0/4 SKIP). Retargeted to the repo's actual resilience suite with one leg per requirement: `test_b_salamander_recovery.py` (supervisor crash recovery), `test_theseus_recovery_replay.py` (replay), `test_chronus_attestation_policy.py` (policy), `test_chronus_hardware_rooted_adversarial.py` (compound/adversarial failure). Result: PASS.
4. **`aethel/ovid.py` lineage_id collision (real defect, failing test).** `lineage_id = sha256(transform_id|input_sha|output_digest|transform_ns|parents)` — `transform_ns` was the sole execution discriminator; Windows timer granularity let two folds of the same payload land in one tick → identical lineage ids (`test_lineage_ids_are_execution_unique` FAIL). A process-wide execution sequence is now mixed into the id material; `output_digest` stays content-deterministic.
5. **Missing `data/` runtime directory** (gitignored) blocked `production_preflight` → created locally; no repo change.

## Still open (not hidden)

- `privileged-path-audit` — needs `MEDIATION_MANIFEST_KEY`.
- `conformance-vectors` — needs a built chronus emulator (C++17 toolchain) + second backend.
- `check_chronus101–107` chain — needs C++17 toolchain.
- `chronus_uhd620_evidence_gate` — needs an OpenCL platform to exercise `identity_negative`; full evidence needs the physical UHD 620.
- `remote_gpu_hardware_acceptance`, `profile_assembly_gate`, `promotion_pipeline`/`collect_approvals`/`advance_state`, `hardware-acceptance.yml`, live stratum submission — need operator-held secrets, GitHub environment approvals, device runners.
- `config/promotion-roles.json` — absent by design; must be a reviewed change with real GitHub identities.
- `promotion.yml` has no `chronus` subsystem option; `chronus` has no `GateDefinition`/`promotion_gates` entry — extending the promotion model is a design decision for the issue owner.
- **PR CI is provisioning-dead, not gate-dead.** On PR #59 all 18 checks failed with zero retrievable logs (BlobNotFound on every job, including jobs this diff cannot touch — gitleaks, docker smoke, infrastructure). Same symptom class as `docs/production/validation.md` records for the sibling repo (check-runs API 403 / billing limits). No CI job ran far enough to evaluate this diff; the ledger rows above are the executed evidence.
