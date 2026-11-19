# End-to-end wiring audit (2026-11-18)

Scope: declared entry points -> code, config and env they depend on. Every
finding below was verified by running code on Python 3.13 (Linux), not taken
from docs. Release posture is unchanged: **NOT QUALIFIED**.

## Entry points verified wired

| Entry point | Target | Evidence |
| --- | --- | --- |
| Dockerfile `api-runtime` / compose `api` | `uvicorn chronus.service.app:app` | imports; `/health/ready` and `/health/live` return 200 (`tests/test_wiring_entrypoints.py`) |
| Dockerfile `miner-runtime` / compose `miner` | `chronus_live_miner.py` -> `chronus.execution.mining_entrypoint` | module and all forwarded names exist (test) |
| `chronus-fleet` console script | `chronus.fleet.cli:main` | resolves (test) |
| `ga-api` console script / `make run` | `ga.cli:main` | resolves (test) |
| `make import`, `make claims` | `scripts/ci/check_ga_import.py`, `ga.claims` | run: import-ok; 7 claims verified, 0 failed |
| compose `web` | `frontend/app/api/chronus/[...path]/route.ts` reads `CHRONUS_BACKEND_URL` | present |
| alembic | `migrations/env.py` -> `chronus.service.postgres_store.metadata` | offline `alembic upgrade head --sql` runs; schema replay test |

## Fixed in this change

1. **Missing migration.** `postgres_store.metadata` declares `ciaas_tenants` and
   `ciaas_capacity_ledger`, but `0001_initial_schema` never created them, so an
   `alembic upgrade head` database lacked tables the CIaaS paths use. Added
   `0002_ciaas_tenancy_tables`; a test replays all revisions on SQLite and
   asserts table/column parity with the metadata (fails on `main`). The
   revision uses `CREATE TABLE/INDEX IF NOT EXISTS` (online and in offline
   `--sql` output), because
   `PostgresWorkloadStore.init_db()` runs `metadata.create_all` and may have
   created them on databases stamped at 0001; a second test covers that path
   and checks existing rows survive.
2. **Stale `.env.example`.** None of its keys (`TENANT_ID`, `ACCESS_TOKEN`,
   `REGION`, `LOG_LEVEL`, `LOG_FILE`, `SKIP_HEAVY_BENCHMARKS`,
   `ENABLE_MUTATION_TESTING`) are read from the environment by any code, while
   the variables the API and miner actually require (`CHRONUS_JWT_SECRET`,
   `CHRONUS_TENANT_TOKENS`, mining admission, `MINING_<POOL>_*`) were absent.
   Rewritten from the real `os.getenv` reads (optional keys commented out so an
   empty value never overrides a code default; tenant tokens documented as
   `{"<tenant_id>": "<bearer-token>"}`, matching `AuthService`); a test fails
   if a key is not read under `src/`. `docker-compose.yml` now loads `.env`
   (optional) into the `api` container, so the JWT secret/issuer,
   `CHRONUS_ENV`, CIaaS custody path and mining-admission settings reach it;
   previously none did and the API always fell back to a random per-process
   key. Miner settings (pool credentials, pool allowlist, miner custody
   identity) moved to `.env.miner.example`, which compose loads into the
   `miner` container only, so pool passwords never reach the API container.
3. **Import-time side effect in the wheel.** `src/chronus/consortium/fix_refs.py`
   opened and rewrote a hard-coded `c:/Users/leonn/...` path at import time and
   was imported by nothing. Moved to `scripts/dev/consortium_fix_refs.py`; a
   test rejects module-level developer-machine paths under `src/chronus`.
4. `alembic` added to the `dev` extra so CI runs the migration test;
   `install-dev` added to Makefile `.PHONY`.

## Broken / unwired, reported only (not changed here)

- **Main CI test job never runs.** `ci.yml` `tests`, `quality-and-package` and
  `stratum-smoke` require `[self-hosted, windows]`; on the last `main` push they
  sat queued 24h and were cancelled, so the pytest suite is not exercised by CI.
  (CI-green stream.)
- **5 failing tests on `main`** (reproduced locally, unrelated to this change):
  `test_enhanced_tensor_representation_v2::...test_search_endpoint`,
  `test_falsifiable_tensor::{test_build_network_enforces_hard_cap,
  test_experiment_e3_honest_1000_node_claim, test_api_run_experiments}`,
  `test_qualification_register_parses::...fail_closed`.
  `POST /v1/tensor/network/build` reaches `NotImplementedError: charge-aware
  DMRG environments are not implemented` and returns HTTP 500 - an API route
  wired to a stub.
- **`src/chronus/access_control.py`** fails to import (`NameError: Role`); already
  tracked as non-authoritative in issue #91. Do not activate.
- **`src/chronus/chronus_gpiu-v36.py`** (8k lines) is not an importable module
  name but ships in the wheel; its path is pinned in `manifests/*.json`, so it
  is allow-listed rather than renamed.
- **Import fails without extras:** `chronus.execution.mining_entrypoint`,
  `mining_scheduler`, `mining_selftest` need `turing` (`packages/turing`, the
  `[mining]` extra; tests get it via pytest `pythonpath`).
  `chronus.pulvini.recovered.geodesic_tensor_engine` imports a non-existent
  top-level `euclid` module.
- **Orphaned modules (imported by nothing in src/tests/scripts):**
  `acceleration.chronos_gpu`, `core.types_part1`, `core.types_part2`,
  `crypto.verify_bundle`, `durable` (top-level; the maintained one is
  `storage.durable`), `execution.main`, `hermes`, `integration`,
  `padovan_folded`, `pulvini.recovered.{geodesic_tensor_engine,
  quantum_formalism, quantum_optimizer}`, `service.production_hr_api`,
  `stratum.stratum_v2`, `verification`, `verify_cli`.
- **Version drift:** `pyproject` 37.0.0.dev0, `/health/ready` reports 36.0.0,
  `/health` reports 36.0.1.
- `make test-cover` uses `--cov=src/chronus` and `make lint` checks all of
  `src/`, unlike CI's scoped ruff run; local and CI lint disagree.
- `scripts/dev/fix_mining.py` and `scripts/dev/check_braces.py` are not valid
  Python.

## Root-level leftovers (suggest cleanup, not deleted)

`_add_constants.py`, `_add_mask64.py`, `_find_multiline_defs.py`, `_fix3.py`,
`_fix6.py`, `_fix7.py`, `_fix_claims.py`, `_test_ga_import.py`,
`apply_ovid_patch.py` (empty), `BLOCKER_MILLENIEIEUM_1.patch`,
`BLOCKER_MILLENIEIEUM_2.patch`, `BLOCKER_TOE_1.patch`,
`al_haras_scenarios_output.txt`, `al_haras_test_output.txt`,
`temp_pytest_output.txt`, `chronus_dirs.txt` (empty), `chronus_files.txt`,
`docs_readme.txt` (1.9 MB), `hendrix.mhtml` (7.5 MB),
`.pytest_temp_ga_handover/`. `theory_of_everything.py` and
`BLOCKER_TOE_1.patch` were intentionally left untouched.

## Closeout (2026-11-19)

Wiring PR #173 merged as `c11af3e6` (main). The follow-up closeout PR carries:

### Orphaned modules (17) — disposition

| Module | Finding | Disposition |
|---|---|---|
| `durable` (`DurableChain`) | Documented in `docs/EVALUATOR_T2.md`; no tests | **Kept, wired**: signed-replay resume and foreign-key refusal tested |
| `verify_cli` | Independent evaluator CLI for receipt chains | **Kept, wired**: console script `chronus-verify-chain`; exit codes 0/2 tested |
| `crypto.verify_bundle` | Public-key-only dual-signature verifier | **Kept, wired**: console script `chronus-verify-bundle`; valid/tampered tested |
| `padovan_folded` | Exact F_257 Padovan transform, unique | **Moved** to `chronus.math.padovan_folded`; mathematical contract tested |
| `service.production_hr_api` (v1) | Maintained module (archive README); attrition endpoint crashed (500) | **Kept, wired**: endpoints tested; attrition-risk refuses with 501 when the tensor layer refuses its objective |
| `hermes` | Canonical namespace, already tested by `test_repository_layout` | Kept (not actually orphaned) |
| `pulvini.recovered.{geodesic_tensor_engine, quantum_formalism, quantum_optimizer}` | Quarantined provenance; `test_recovered_merge` asserts the engine never imports them; `geodesic_tensor_engine` needs a missing `euclid` package | Kept as research provenance; not wired by design |
| `core.types_part1`, `core.types_part2` | Definition-for-definition duplicates of `core.enums`, `core.constants`, `core.dataclasses` (AST-compared) | Removed |
| `execution.main` | Five-line print-only skeleton | Removed |
| `verification` | Empty package | Removed |
| `acceleration.chronos_gpu` | NumPy wrappers plus identity "placeholder" kernels; the fleet/iGPU packages are the maintained path | Removed |
| `integration` | Written against a non-existent `AdapterRegistry` API (`functionals`/`discover`), broken `__all__`, placeholder mining shard | Removed |
| `stratum.stratum_v2` | Stub with a simulated Noise handshake; never imported. Stratum V2 is **not implemented** | Removed |

### Version single source

Handled in PR #183 (`chronus.__version__` as the only declaration, read by
`pyproject.toml`; value `37.0.0.dev0`, tag `v37.0.0.dev0-internal`, last stable
tag `v36.0.1`), not duplicated here.

### Root cleanup

Removed one-off edit scripts (`_fix*.py`, `_add_*.py`, `_find_multiline_defs.py`,
`_test_ga_import.py`, `apply_ovid_patch.py`), captured outputs
(`al_haras_*_output.txt`, `temp_pytest_output.txt`, `chronus_dirs.txt`,
`chronus_files.txt`), the committed `.pytest_temp_ga_handover/` and
`hendrix.mhtml` (a saved internal page with personal data; the repository is
public). `hendrix.mhtml` **remains in git history**; purging it needs a history
rewrite and force-push. The owner decided (2026-11-19) to leave history intact, so
there will be no rewrite and no force-push. `BLOCKER_TOE_1.patch` is kept on
instruction.

### Legacy root files retired (2026-11-19)

Before deleting them, each file was compared with the current tree and with git
history (4,380 commits). They are not lost: each file stays in history at the
commit before its removal, with blobs `f785714a` (`BLOCKER_MILLENIEIEUM_1.patch`),
`db9405ad` (`BLOCKER_MILLENIEIEUM_2.patch`) and `8cab95aa` (`docs_readme.txt`).

- **`BLOCKER_MILLENIEIEUM_2.patch`** (commit `e410c72f`, "max_seconds blocker")
  passes `MINING_MAX_SECONDS` into `engine.run(max_seconds=...)`. That change is
  already on main in `src/chronus/execution/mining_entrypoint.py` (`async_main`
  reads `MINING_MAX_SECONDS`, and `run()` validates a positive integer). The patch
  only adds a comment to `chronus_live_miner.py`, so nothing in it is unique.
- **`BLOCKER_MILLENIEIEUM_1.patch`** rewrites `scripts/ci/manifest.py`. Both sides
  of the patch belong to the withdrawn "fabricated manifest" generator. The patch
  adds a hard-coded HMAC key (`SECRET_BUILD_KEY`), `shell=True` command strings,
  an unconditional `PRODUCTION_QUALIFIED` status and constant metrics
  (`mypy_strict: PASS`, `submit_rate_achieved_sec: 15`). The maintained
  `scripts/ci/manifest.py` replaced that design: it runs literal argv without a
  shell, writes unsigned diagnostics and stays `NOT_QUALIFIED` without an external
  release-evidence packet. Applying the patch would be a security and honesty
  regression. It holds no implementation or evidence to keep.
- **`docs_readme.txt`** is not random corruption. It is a 968,227-character UTF-16
  concatenation of 170 Markdown documents that had already been mojibaked
  (UTF-8 read as cp1252). After decoding and repairing it, 7,115 substantive lines
  (≥ 40 characters) were checked against every tracked text file. 6,978 are in the
  current tree verbatim, and 76 of the 137 others are in git history. After
  matching on alphanumeric content only, 14 lines remain unmatched. They are
  (a) two rows of a "claim audit" table whose withdrawals are already stated in
  `STATUS.md` ("historical qualification manifests and benchmark claims remain
  provenance only") and in `docs/executive/executive-architecture-and-project-summary.md`;
  (b) the header block of a "v36.0 Irrefutable CI System Audit" certificate. That
  block claims `PRODUCTION_QUALIFIED`, "370 passed" and a verified zk-STARK at
  commit `21f69805`, which are the fabricated-manifest claims withdrawn by
  `e410c72f`; and (c) one ASCII-art line showing a configured "10.0 EH/s" cap.
  None of these is research, implementation or reproducible evidence, so the file
  holds nothing unique to preserve.

All three files are deleted in this PR.

### CI execution evidence

`scripts/ci/test_execution_gate.py` reads pytest JUnit and fails on failures,
passed counts below the suite floor, skips outside the hardware/platform/pinned
dependency allowlist, and xfails missing from `tests/known-failures.txt`. The main
tests, OpenCL reference and new pinned scikit-learn 1.8.0 dataset jobs run it, and
`ci-required` fails unless every required job concluded `success` (skipped,
cancelled or never-started jobs are not passing evidence). On 2026-11-19
`ci-required` (context `CI required (every job executed and succeeded)`, GitHub
Actions app 15368) was added to the required status checks of the `main-production`
ruleset (id 27423249). The strict up-to-date policy is kept and there are no bypass
actors.
cancelled or never-started jobs are not passing evidence). Making `ci-required` the
required status check is a repository-settings change left to the owner.

### Production execution paths of the five wired modules (2026-11-19)

Importability is not reachability. `tests_installed/test_production_paths.py`
installs the wheel built by the CI "Lint, compile and package" job into a clean
venv. That venv has no `PYTHONPATH`, no user site-packages and no source tree;
the test asserts that `chronus.__file__` is under `site-packages`. Each module is
then exercised the way it runs in production. The CI job is "Installed wheel
production paths (clean venv)": its JUnit is gated as suite `installed` (at least
5 passed, no skips), and `ci-required` depends on it.

| Module | Intended production path | Exercised by |
|---|---|---|
| `chronus.durable.DurableChain` | An evaluator process appends signed receipts durably (fsynced journal); after a restart it resumes only through signed replay | Two separate evaluator processes: append 2 receipts, exit, restart, resume and append 1. The exported bundle is accepted by the installed `chronus-verify-chain` (exit 0, 3 receipts), and a tampered receipt is rejected (exit 2) |
| `chronus.verify_cli` | Installed console script `chronus-verify-chain` | As above, the binary from the venv's `bin/` |
| `chronus.crypto.verify_bundle` | Installed console script `chronus-verify-bundle` | A valid dual-signed bundle exits 0 with `VALID`; a tampered one exits 1 with `INVALID_OR_UNAVAILABLE` |
| `chronus.service.production_hr_api` | New console script `chronus-hr-api` (start-up `main()` runs uvicorn; loopback by default, `--host`/`--port` or `CHRONUS_HR_API_HOST`/`PORT`) | A real server process on a free TCP port; `/health`, tensor init, optimize-query, causal analyze/counterfactual return 200, and attrition-risk returns an explicit 501 |
| `chronus.math.padovan_folded` | Library API of the installed package | Fold/unfold of a 16-byte record and the exact period in the installed package. **It has no runtime caller**: no service, CLI or job uses it yet, so it is a shipped library capability, not a runtime path |

The HR API is a separate application. It is **not** mounted in the main Chronus
API (`chronus.service.app`), and no deployment manifest (compose, Bicep)
starts it. That gives it a production start-up path, but no deployment is
established.

### Why the four other modules stay

- **`chronus.hermes`** is the documented canonical import path for the bounded
  acceleration modules (`chronus.hermes.fourier`, `chronus.hermes.state` are the
  same module objects as `chronus.acceleration.*`). `chronus.fleet.scheduler`
  refers to it, and `tests/test_repository_layout.py::test_hermes_exports_the_acceleration_modules`
  pins it. Removing it would break the published namespace. It was never truly
  orphaned.
- **`chronus.pulvini.recovered.{geodesic_tensor_engine, quantum_formalism, quantum_optimizer}`**
  are the byte-recovered PULVINI V3 sources (`PULVINI_V3_HERMES_COMPLETION_20260724.zip`).
  They are the provenance for the `benchmarks/recovered/*.json` results, which
  `tests/test_recovered_merge.py` pins as `RECOVERED_MEASURED` with the source
  archive SHA-256 and `re_measured_on_head: false`. Deleting them would leave
  those recorded results without their source. They are quarantined by design:
  the package docstring states that nothing in production imports them, and
  `test_recovered_reference_modules_not_imported_by_engine` enforces that.
  `geodesic_tensor_engine` also needs an `euclid` package that is not a
  dependency, so it cannot run as engine code. **Finding:** all three are still
  packaged in the wheel. Excluding `chronus/pulvini/recovered` from the
  distribution, while keeping it in the repository, would reduce the shipped
  surface. This is recommended but not done here.
