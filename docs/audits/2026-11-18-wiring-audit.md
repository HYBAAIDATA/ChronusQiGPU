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
   if a key is not read under `src/`. `docker-compose.yml` now passes
   `CHRONUS_JWT_SECRET` from `.env` to the `api` container, which previously
   always fell back to a random per-process key.
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
