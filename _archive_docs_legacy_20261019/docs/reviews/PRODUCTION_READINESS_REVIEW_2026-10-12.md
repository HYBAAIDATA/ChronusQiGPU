# Production Readiness Review — PhiEnterprise / PYTHIA

| Item | Value |
|---|---|
| Date | 2026-10-12 |
| Scope | Whole repository on `main` @ `790804f5`; fixes on branch `production-readiness` (PR #1) |
| Method | Reproduce every CI workflow locally and on GitHub; bisect against the pre-consolidation tree (`a99be461`); fix only defects with a proven cause; record everything else with evidence |
| Verdict | **Not production-ready yet.** The build, packaging, gates and deploy wiring are repaired. The remaining blockers are owner policy decisions and older functional defects, listed below. |

## Summary

`main` was red across almost every workflow. The cause was commit `99cf7daa` ("elevation"), which moved 778 files into `chronus/` as pure renames without updating any references. The umbrella wheel could not build, CI installs failed at step one, and the mining coordinator could no longer load its production manifest. That first failure also hid a second layer of older defects (gate wiring, stale anchors, broken fixtures) that had not been visible for some time.

This branch repairs the move and every older defect with a clear owner-free fix. It does this in 14 self-contained commits, each pushed as it was finished. On the latest commit, GitHub reports **57 checks passing, 20 failing, 20 skipped**, up from a near-total failure. Every one of the 20 failures is either a policy decision for the owners or a functional defect that was already failing on the pre-move tree (section 4).

## 1. Root cause and repair of the `chronus/` consolidation

| Defect | Effect | Fix |
|---|---|---|
| `pyproject.toml` package-dir still pointed at pre-move paths | Umbrella wheel could not build, so every CI job failed at install | `lucas/chronos/compiler/format/tools/isa` → `chronus/<name>` |
| `manifests/chronus10{5,6,7}` moved | `ProductionMiningIntegration.from_repository` and wheel package-data lost the #107 production manifest | Moved back to `manifests/` |
| `kernels/*.chronus.s` moved | Installed `compiler` silently lost its kernel templates | Moved back; `lowering.py` resolves both layouts |
| `conformance/` package shadowed by `chronus/conformance.py` | Conformance replay imported the wrong module | Restored top-level `conformance/`; `build.py` byte-identical (pinned generator hash still matches) |
| Plugin backends moved (`gpu/backends/chronus.py`, `tensor/backends/chronus_*`) | Backend registry broke | Restored |
| Repo-root depth (`parents[k]`) in moved scripts and tests | Scripts resolved paths outside the repo | Corrected across `chronus/scripts`, `chronus/tests` and packaging |
| Emulator `-I`/`-S` paths and `emulator`/`cross_verification` imports | Whole #101–#107 evidence chain failed at step one | Fixed; #101–#104 pass |
| `hyba/operating_model/verifiers.py` exempted `lucas/ladder.py` by path | Ladder-drift check would flag the canonical module itself | `chronus/lucas/ladder.py` |
| Publication catalog, inventory baseline, July capability manifest, research registry, conformance targets | Gates pointed at missing files | Paths updated (identity hashes unchanged) |
| Source-tree CI jobs (`PYTHONPATH`) | `No module named 'lucas'` | `chronus/` appended after the root (root names keep precedence) |
| Mutation sandboxes | Every mutation job refused to run | `chronus` added to the sandbox path |

The import audit (0 findings), import cycles (0 new) and import layers (0 new) were verified after every step.

## 2. Older defects fixed (not caused by the move)

- **Claim register never evaluated `claims.yaml`.** A stale artifact hash and a prohibited exahash-throughput claim (register entry `p-throughput-eh`) had gone undetected. The gate now enforces the register.
- **Gate roll-up could never pass.** Two gates write list-valued detail files to `results/`, and the roll-up rejected them as malformed. Auxiliary files are now ignored, but a file named for a required gate is still checked strictly. The AL HARAS job also lacked pytest, so `resilience-suite` reported "no test report".
- **Critical mutation sentinels were stale.** One anchor matched twice after the CUDA/Metal lane duplicated the recheck block, and another matched nothing after a refactor. All 7 sentinels now kill their planted defect.
- **Docker images.** In-tree dependencies that are not on PyPI are now installed through `scripts/ci_install.sh`. The container no longer crashes at boot (it needed a writable heartbeat directory owned by the non-root user). Compose now requires the Stratum identity, and `.dockerignore` excludes the dev signing key.
- **Clean-wheel smoke** now builds and installs every in-tree core dependency (`chronos-one-igpu`, `kellogg-tensor`, `turing-vqc`) and resolves third-party dependencies normally. Verified locally: the remote GPU agent's `/v1/health` returns `remote_opencl_v2`.
- **EUCLID v17 release** always emitted `RELEASE_BLOCKED`. It required `reports/euclid_v17/run.log`, which nothing produces and `.gitignore` excludes, and `tee` hid the failure. The stale path is removed and the steps now run under `bash -eo pipefail`. A merge had also dropped a test fixture while keeping its use. The release builds locally with its manifest and zip.
- **Deploy sentry** now understands `package-dir` mappings and the import names of in-tree HYBA distributions. This removed 6 false findings, 3 of them introduced by the move.
- **Dependency hygiene.** Nothing imports `nltk`, yet it carried the only pip-audit advisory (PYSEC-2026-3740, no upstream fix). It is removed from the `[ml]` extra and its stale CI download step is gone. The unused `KELLOGG_VERSION` workflow variable is also removed.
- **Vendored `lucas/ladder.py`** in TURING drifted from the canonical copy. The canonical file only adds helpers, so the vendored copy is synced.
- **CI lint scope.** Exact renames (`-M100%`) are no longer re-linted, because restoring pre-move files must not force a style rewrite of hash-pinned code. Every file this branch edits passes flake8 and ruff.

## 3. What was verified

| Area | Result |
|---|---|
| `make gates` | 10 PASS, conformance-vectors SKIP (by design), privileged-path-audit PASS in CI (FAIL locally only because `MEDIATION_MANIFEST_KEY` is a CI secret) |
| Gate roll-up (CI) | 0 failed, 0 malformed, 0 missing; blocked only by the conformance-vectors SKIP (see 4.1) |
| Import audit / cycles / layers / ownership / constitution / publication catalog | All pass |
| Claims (`evaluate_release(..., reproduce=True)`) | Pass |
| Chronus evidence chain #101–#104 | Pass (#105–#107: see 4.3) |
| Critical mutation sentinels | 7/7 killed |
| Frontend | Plugin validation, `tsc`, vitest 51/51, vite build; `npm audit` 0 vulnerabilities |
| Control API security | Fail-closed auth with `hmac.compare_digest`; verified live (401 with no or wrong key, 200/202 with the right key); the dev bypass is not set in any deploy config |
| Service boot | `pythia` serves `/api/health`, cognition status and the operator UI |
| Secret scan, dependency audit and SBOM, gate-evidence integrity, publication identity, portfolio audit | Pass on GitHub |

## 4. Remaining blockers (owner decisions)

### 4.1 Policy decisions

1. **Strict M3 custody versus fixtures.** Commit `335e4004` refuses live submission unless `PYTHIA_M3_REQUIRED=1`. The Docker live smoke, `test_production_loop_e2e` and installed-boundaries were never updated to provision an M3 tenant, so the agentic-mining worker never starts. The smoke has failed on `main` since at least 2026-10-09. Decide whether fixtures provision M3 (`scripts/provision_m3_tenant.py`) or get a test-only allowance.
2. **Reference implementations in production context.** `chronos_one_igpu.reference_contract` raises `ReferenceUnavailable` for `pythia_search.fp64` and `structured_matvec.float_projection` in production context. This breaks `test_native_production_routing` and the resident-route structured-solver suite. Either approve these references or route the tests through an approved context.
3. **Conformance-vectors SKIP.** The gate skips until two independent exact backends exist, and the roll-up treats any skip as a failure. This is correct fail-closed behaviour, so release is blocked until a second exact backend lands.
4. **Publication-catalog fingerprint.** The `pyproject.toml` interface fingerprint was re-recorded because the package-dir source locations changed. Import names and console scripts are unchanged. This needs an owner acknowledgement.
5. **Deploy-sentry boundary findings (2).** The TURING workflows install `.` without the test extra, and `mining/search.py` imports `chronos_one_igpu`, which the TURING distribution does not declare. This is a distribution-boundary decision.

### 4.2 Pre-existing functional defects (failing on the pre-move tree)

These 132 test failures already failed on `a99be461`, before the move, and were confirmed by running the same files on both trees. Main clusters:
- `BoundBackend` has no attribute `failed` (22 errors, chain-verification suites)
- 11D Poincaré nonce-order and coordinator alias suites
- TOE chooser throttle wiring, Stratum state and Stratum V2 adapters (including `extranonce must not contain NUL`)
- L-HRAS and organism-integration suites (`KeyError: 'lhras.respond'`, reachability-stage expectations)
- `tests/test_gate_rollup_integrity.py` targets the pre-tamper-evident roll-up API (`REQUIRED_GATES`)
- Windows `\\?\` long-path normalisation in `tests/test_m3_adversarial.py`
- `test_agi_unified_intelligence::test_factory_roles_use_distinct_substrates`
- TOE runtime solve (503), oracle T7 holographic-entropy rung, `toe` packaging metadata

### 4.3 Other open items

- The Chronus #105–#107 checks fail with an identical `corpus_sha256` assertion on the pre-move tree, meaning the conformance corpus changed after the hash was pinned.
- The Lean jobs fail with "No lake-manifest.json found"; one needs to be generated and committed.
- The EUCLID governed-runtime production-gates suite and the "Compose EUCLID release verdict" PyPI-name check also fail; the second depends on registry state.
- `requirements-lock.txt` is stale: `anthropic==0.40.0` is below the declared `>=0.45`, `numpy` is on 1.x, and CI does not use the lock. Regenerate it or delete it.
- `manifests/dev-signing.key` is a committed development HMAC key. Only an audit script falls back to it, but the only signed manifest uses it. Production must re-sign with `DEPLOYMENT_MANIFEST_KEY`.
- Gitleaks allowlists the whole `tests/` and `legacy/` directories; narrow this to specific fixtures.
- Without `PYTHONHASHSEED=0`, pytest-xdist collection is non-deterministic across workers. Pin the seed in CI.
- GitHub warns that Node 20 actions are deprecated and that `ubuntu-latest` moves to Ubuntu 26 on 2026-10-19. Pin the runners.

## 5. Recommended path to production

1. Merge PR #1. It is safe to review commit by commit, and nothing touches consensus logic.
2. Owners decide items 4.1.1–4.1.5. Items 1 and 2 alone should turn the Docker smoke, installed-boundaries, resident-route and the behavioural gates green.
3. Triage the 132 older failures by cluster, starting with `BoundBackend.failed` (one root cause, 22 errors).
4. Fix the corpus hash for #105–#107, commit the Lean manifest and regenerate the lock file.
5. Re-sign deployment manifests with the production key, then run `production-closure.yml` (`--require-no-skip`) as the release gate.
