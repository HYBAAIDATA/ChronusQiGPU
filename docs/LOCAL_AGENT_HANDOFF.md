# Local execution handoff — complete production system on main

## Assignment and coordination

This is an executable assignment for the agent with the user's real local checkout, not a request to restate this document or wait for GitHub Actions. The outcome is a complete working production system. Do the work, repair reproduced defects, retain evidence and report exact blockers where access or owner decisions are genuinely necessary.

The remote assistant owns GitHub-source inspection, focused independent regression reproduction, role/contract review, and review of returned evidence. The local agent owns the full checkout, branch reconciliation, dependencies, native builds, Docker, composed services, browser journeys, load/recovery execution and collection of logs. Neither agent can claim the other's work ran without examining its evidence. The remote assistant cannot see or control the developer machine and cannot directly message its local agent; this tracked file is the shared handoff.

GitHub-hosted CI is unavailable because of billing. Do NOT wait for it, poll it, or report its absence as a reason not to execute local checks. Old device sign-in codes in previous notes are expired operational instructions, not certification steps. The local agent already has a checkout: do not ask the user to authenticate a different agent as a substitute for running local commands.

AI Studio is a separate version and must remain untouched. `main` is the canonical integration and certification branch. Do not start another long-lived branch or reorganize additional directories during qualification. Do not force-push, discard uncommitted work, fabricate results, loosen security/authority checks to pass tests, or bypass branch protection.

## 0. Reconcile the actual repository and source history FIRST

At handoff creation, GitHub MCP verified remote main as:

`fedf91ac7b327929a67bc0e5bc167de22080f1b7`

This includes PR144 (native exact execution qualification) merged at `6c8d71fc6f41f5b43514039bab3ee83bb55a14c1`, followed by the HttpOnly console login/lifecycle fixes. Those changes must survive the source-tree migration.

The user reports local commit `21543c95` with Docker consolidation/source reorganization. GitHub could not resolve that abbreviated commit in PhiEnterprise1/EuclidPhiEnterprise, and remote main did not contain certification_status.md at inspection. This is a reconciliation gate, not proof the local commit was lost. It could be unpushed or in another checkout/remote. Determine which before changing history.

1. In the real checkout record: `git rev-parse --show-toplevel`, `git branch --show-current`, `git status --short`, `git rev-parse HEAD`, and the origin URL with any embedded credentials redacted. Confirm origin is the intended PhiEnterprise1/EuclidPhiEnterprise repository. Do not silently change an unexpected remote.
2. Resolve `git show --no-patch --format=fuller 21543c95` and record its full SHA, or explicitly report why it is not present. Inspect its changed-file list and the intended moves/deletions. Do not trust the inconsistent reported Docker deletion totals; count tracked files.
3. Preserve and review any uncommitted work before switching branches. Do not use reset --hard, clean -fd, force checkout, blind git add -A, or a force push.
4. Fetch origin; reconcile the verified local work with the newest origin/main. If both histories advanced, perform a normal reviewed merge preserving both sets of changes. Resolve conflicts in imports, tests, package mappings and Docker/CI paths; do not choose one side wholesale. If work is on another local branch, integrate that verified work into main and finish on main.
5. Replace stale sign-in/CI text in certification_status.md with actual execution status. A code in a status file is not test evidence. Resolve any add/add conflict with the new factual status file rather than restoring expired instructions.
6. Push main normally, subject to repository protections. Fetch again and confirm local branch == main, clean worktree, and HEAD == origin/main. Record both SHAs. If protections prevent the push, report the actual refusal; do not bypass them.

The closeout must explicitly verify that main contains native-mode qualification in enterprise_contract.py / enterprise_api.py and the cookie-session access/lifecycle regressions in frontend. Paths may have moved; follow the actual committed tree, not old folder assumptions.

## 1. Establish a reproducible local qualification environment

Use an isolated Python 3.12 or 3.13 environment and the repository-declared Node version. Record OS, Python/Node/npm/compiler/Docker versions and exact commands. Use Git Bash/WSL or native equivalents appropriate to the machine; do not claim Linux container execution from a Windows host-only run.

Inspect tracked pyproject files, requirements, lockfiles, Makefiles, entrypoints, workflow commands and test roots using git's tracked-file inventory. Root pytest testpaths do not cover every nested package. Record all test roots, missing dependencies, collection errors and skipped tests. Do not hide problems with --noconftest, blanket ignores, xfail, -x-only runs, or fabricated fixtures. A focused isolated regression can be useful, but must be labeled separately from full-package/full-system execution.

Canonical installer currently in remote main:

`bash scripts/ci_install.sh "ml,dev,graph"`

It stages in-tree Kellogg and installs in-tree Chronus/TURING dependencies; they must not be replaced with guessed PyPI distributions. If the reorganization broke this installer, packaging or its paths, repair it first and rerun from a clean environment. Retain dependency resolution/install logs and `python -m pip check`.

Frontend: from frontend, execute `npm ci`, `npm run lint`, `npm run test:ts`, `npm run build`. Use the committed lockfile. Do not regenerate it merely to silence an install error without identifying and fixing the cause.

## 2. Execute the repository and installed-artifact gates

Run all tracked test roots, not just the earlier 113 native tests or the later 53 client tests. Initial commands to reconcile with the final committed paths:

- `python -m pytest tests/ --junitxml=<evidence>/root-tests.xml` (without stopping at the first failure).
- Tests under chronus/mla1517_platform/python and chronus/tests.
- TURING's own tests from turing_universal_quantum_computer; TOE, TENSOR/Kellogg, OVID, THESEUS, EUCLID, governance and other nested suites found in the tracked inventory.
- `python scripts/verify_unified_enterprise.py` and the Makefile's verify-unified/assurance-gates targets.
- `python scripts/import_audit.py`; import graph cycle/layer gates; canonical mining and PULVINI authority checks; source compilation over the tracked runtime Python packages.
- `python packaging/toe/build_and_verify.py` and `python packaging/euclid-engine/build_and_verify.py`; run canonical TURING/Kellogg/Chronus/root wheel and sdist qualification from their tracked build tooling/workflows.
- Test imports and the runtime regression suites in clean installed environments outside the source tree. A source-path import is not installed-wheel evidence.

Retain every command/exit code, collection/execution/pass/fail/skip counts, JUnit, raw logs, artifact hashes and unresolved defects. An unavailable package tool is a defect/gap to resolve, not a passing gate. After a fix, rerun affected gates and then the aggregate at the final main commit.

## 3. Verify Docker consolidation by execution

Inventory actual tracked Dockerfiles and every compose/script/workflow/deployment reference to removed variants. Reconcile the claimed 14 -> 4 with the real count; do not repeat the inconsistent reported deletion list.

Intended retained images: Dockerfile, Dockerfile.hybrid, Dockerfile.dev, deploy/azure/Dockerfile. Build all retained images with their real contexts. Verify copied source paths, installed package imports, non-root runtime where required, frontend assets, health/readiness routing, persistent data mounts and shutdown behavior. Test the development image's documented startup and the production/hybrid/Azure entrypoints. Removal is not complete while consumers still reference deleted Dockerfiles. Do not push images to a registry or deploy over production without the required approval.

## 4. Run the actual composed user journeys

Use docs/PRODUCTION_CLOSEOUT.md (J01-J08), frontend/JOURNEYS.md, frontend/WIRING.md and SYSTEM_CONTRACT.md as the acceptance register. Read their implementation scopes: the current mining console is not the complete enterprise workspace.

For each journey, record actor/tenant, prerequisites, real entrypoint and endpoint sequence, expected/observed states, refusal cases, persistent effects, receipts, evidence paths and verdict. Execute real backend functions and composed services; client transport mocks cannot prove service integration.

- J01 authentication: successful and refused login, Secure HttpOnly cookie, server role resolution, session expiry/revocation/logout, credential/secret redaction, cookie-only session changes, late-response rejection and cross-tenant/identity isolation. Exercise the rendered UI against the real Python server.
- J02 configuration/execution: server-owned allowlists/caps, authorized native start/stop, dual approval where required, target auto-stop, cancellation/retry, restart and receipts; forbidden roles/configurations must fail before dispatch.
- J03 integrated quantum/tensor/inference execution: full authorized TURING/TOE -> CHRONUS -> VQC/canonical TENSOR path, real results, arithmetic scope, independent correctness, routing/fallback and receipt binding; tenant and repeat/concurrency cases.
- J04 representation/custody: OVID roundtrip/addressability -> THESEUS durable commit/verification -> interruption/corruption -> quarantine -> authorized recovery/re-seal -> fresh-process restore, including data/model/audit consistency.
- J05 intelligence workflow: authenticated connector/tenant -> ingest -> TOE analysis -> lineage -> train/evaluate/promote -> export; denied roles, quarantined data, unsafe promotion, vendor faults and revocation.
- J06 operations/evidence: truthful status across UI/API, actual observability, alert investigation, tenant-safe audit/evidence export, digest validation, independent retention and redaction. A global evidence pack is not automatically a tenant-safe export.
- J07 customer/treasury: provisioning/authorization, backend-sourced ledger and economics, dual approval and custody-backed signing, rejection/replay handling, reconciliation and explicit offline state. Never move real funds for testing; use an explicitly labeled safe environment and record the untested live-settlement boundary.
- J08 deployment lifecycle: clean install/startup, reverse-proxy health/readiness, secret provisioning/rotation, backup and fresh-process restore, upgrade/rollback, graceful shutdown and restart.

Where a critical journey lacks an implementation, implement the real missing product path with the canonical owners and regression tests, not a hardcoded success adapter or a permission bypass. Identify material product/security decisions requiring the user's choice rather than inventing authority. Keep genuine external-access blockers explicit and continue independent work.

## 5. Preserve architecture and measure performance

TURING retains its full quantum/operator authority. TOE retains its full inference/certification scope, not merely an invariant checker. Canonical TENSOR/VQC execute; CHRONUS dispatches; OVID handles representation/addressability; THESEUS handles accountable custody. Honor the governing source documents without treating repository prose as permission to falsify measurements or override security.

Native mathematical execution is substrate-agnostic: no blanket GPU/QPU requirement and no emulation label solely because execution is software-defined. Explicit accelerator-bound modes must prove their actual target or refuse honestly. Pool ACK/share acceptance and financial settlement are external outcomes, separate from mathematical correctness. Never infer universal speedup, arbitrary dense-state capacity or production readiness from a sparse-state correctness result.

For representative end-to-end workloads retain correctness plus raw warm/cold latency, throughput, concurrency, peak memory, error/cancellation behavior, overload and recovery observations. Establish workload-specific acceptance budgets before final acceptance measurements, using existing product requirements or a clearly disclosed provisional budget requiring approval. Compare any claimed improvement with equivalent input/work/correctness and a named baseline. Run sustained soak/fault tests; record duration and environment. Test-suite duration is not a product performance benchmark.

## 6. Required evidence and handback

Use a fresh directory such as evidence/<execution-date>/production-closeout-local/<run-id>/. Prefer an evidence-only output directory outside the source tree during execution so clean-source checks are meaningful; copy reviewed evidence into the repository afterward. Do not rerun a source-clean gate against a knowingly dirty fix tree and label it exact-head.

Every run must identify source SHA, branch, source worktree state before execution, origin/main SHA, OS/environment, start/end time, commands, exit codes, executed/failed/skipped counts, deployment identity (where applicable), artifact/source SHA-256 and raw log/JUnit paths. Record missing/prerequisite-blocked gates distinctly. Generate DIGESTS.json over retained evidence excluding itself and report its own SHA-256 separately. Verify hashes independently after packaging/export.

After fixes are committed/pushed on main, rerun at that exact clean commit. Adding only retained evidence afterward must identify the tested parent/source SHA and manifest; do not pretend a self-referential commit tested itself. An implementation change invalidates affected results.

Return and push a concise handback containing:

1. Full local HEAD and origin/main SHAs; checked-out branch; clean/dirty state; repository identity; disposition of 21543c95.
2. J01-J08 table: PASS / FAIL / BLOCKED / NOT_RUN, named real entrypoints, evidence paths, and exact remaining blocker. PASS must identify the environment/scope; no fixture-to-deployment promotion.
3. All suite/build counts, collection errors/skips, clean-installed artifact and four Docker build/startup outcomes, and reproduced defects fixed.
4. Performance/fault/soak/backup/restore/rollback measurements with declared workload/budgets and raw data paths.
5. Evidence directory, DIGESTS.json SHA-256 and independent verification result.
6. Remaining release blockers and operational runbook. READY only when the complete agreed product scope has fresh passing acceptance evidence; otherwise NOT READY with precise blockers.

Do not finish by repeating expired authentication instructions or producing another plan. Execute the available tasks and return evidence. If blocked on one lane, continue the independent lanes rather than treating CI billing as a task-wide stop.
