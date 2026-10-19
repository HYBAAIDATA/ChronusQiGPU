# Apple M5 transfer and intelligence acceptance — 9 October 2026

Status: **M5 HANDOVER CANDIDATE — NOT YET EXECUTED OR CERTIFIED ON THE M5**.
This document supersedes the outdated 7 October pickup procedure, not the 5 October owner-controlled authority register.

## Lessons from 8 October M5 attempt

Retained logs: repository files m5, m5evidence, M5run.
- A zombie main.py launched from a checkout moved to Trash held a live lock; subprocesses then imported from a deleted path. Inspect effective PID, cwd and executable; stop only verified stale processes. Never kill all python processes or blindly delete locks.
- The Linux default heartbeat directory /run/pythia/hb was unwritable on macOS. Use a private persistent path on the Mac, not /tmp for production state.
- Two mining coordinator signature regressions involved asynchronous_submission/submission_queue_size and defer_pool_outcome. Both corrections are now visibly present in inspected main; execute regression tests on the exact deployment revision.
- Python 3.13.16 .venv was usable in source, but some package imports came from the checkout rather than installed artifacts. A wheel/sdist and isolated-import test remains mandatory.
- Build tooling was initially absent; artifact verification required arguments and installed packages. The frontend could not be served because Node/npm and dist/public were absent.
- Connected Stratum shadow mining ran CPU hashing, not physical Apple GPU/ASIC acceleration, and no live submission acceptance was shown.

## A. Stop, snapshot, anchor

Run on the M5 from the active checkout:

    ps -axo pid,ppid,command | grep -E '[m]ain.py|[m]ining_runtime.py|[d]iscovery_runtime.py'
    git fetch origin
    git rev-parse HEAD
    git rev-parse origin/main
    git status --porcelain
    uname -s && uname -m
    xcode-select -p

Only continue with an exact approved source commit and clean tree, after deliberately shutting down the old supervisor and workers. Snapshot data/, the SQLite file, CAS root, THESEUS custody/replica/journal root, key references and configuration before first restart. Backups must not go into Git.

## B. Rebuild Mac venv from verified dependencies

Do not copy the Windows or previous Mac venv; create a distinct clean environment:

    cd ~/Desktop/PhiMiner
    python3.12 -m venv .venv-m5
    .venv-m5/bin/python -m pip install --upgrade pip build wheel twine pytest
    .venv-m5/bin/python -m pip --version

Python 3.12 initially aligns with previously used Windows 3.12.10. Python 3.13 is allowed only after compatible ARM64 dependency/artifact verification. The checked-in requirements-lock.txt is NOT a verified Python 3.13/macOS ARM64 lock; resolve and pin an exact tested Mac dependency set before deployment. Build and install actual HYBA package wheels from their declared dedicated build roots rather than relying on PYTHONPATH or source imports. Run pip check and isolated imports with python -I from outside checkout. Do not pass a stub or missing distribution as installed.

## C. macOS state + secure custody

    mkdir -p "$HOME/Library/Application Support/HYBA/PhiMiner/heartbeats"
    export PYTHIA_WORKER_HEARTBEAT_DIR="$HOME/Library/Application Support/HYBA/PhiMiner/heartbeats"

Where overridden, PYTHIA_BOOT_LOCK and PYTHIA_BOOT_AUDIT must point to accessible canonical state. Keep durable DB, CAS and THESEUS custody outside temporary directories. Do not print secret values.

Strict M3 requires PYTHIA_M3_REQUIRED=1, PYTHIA_STORAGE_DB, PYTHIA_STORAGE_ROOT, PYTHIA_STORAGE_CUSTODY_ROOT, PYTHIA_STORAGE_TENANT, PYTHIA_STORAGE_INTEGRITY_KEY_HEX and PYTHIA_STORAGE_CUSTODY_KEY_HEX, with a tenant *already provisioned under authorised admission*. AL HARAS gate configuration is independently mandatory. PYTHIA_STORAGE_OVID_EXACT=1 explicitly enables exact OVID representation transform and checked materialisation; do not silently change owner-gated transform policy.

During migration, HYBA_ENABLE_LIVE_SHARE_SUBMIT and HYBA_AUTONOMOUS_EXTERNAL_ACTIONS remain OFF. A nonempty approval ID is not implied by having pool credentials. External pool acceptance and hardware acceleration are separate gates.

## D. One-command local integration preflight

    .venv-m5/bin/python scripts/m5_transfer_preflight.py --execute --output artifacts/m5-transfer-preflight.json
    .venv-m5/bin/python scripts/euclid_v17_integration_gate.py --output artifacts/euclid-v17-m5.json
    .venv-m5/bin/python scripts/m3_evidence_pack.py --out evidence/m3_storage_gate
    .venv-m5/bin/python scripts/production_preflight.py --profile application --strict --output artifacts/m5-app.json

Require real tests of the following, not import-only or health flags:
- EUCLID v17 F1–F6 dispatch rights, specialist component evidence, fresh-process replay, stable organ identity, OVID/THESEUS adaptive custody and negative-transfer controls.
- PYTHIA mining cognition supplied through the canonical EUCLID composition root and TOE; PYTHIA remains final SearchPlan/Bitcoin truth authority.
- TURING exact VQC and CHRONUS execution with separate CPU/software vs hardware/device provenance, independent SHA256d/target verification and Hendrix complete traversal.
- SALAMANDER observe/diagnose/authorised act/measure/rollback closed loop; AL HARAS denial and custody evidence.
- OVID exact transform/source lineage, THESEUS SQLite/CAS/HMAC custody and fresh-process replay, Geodesic rebuildable projections with tenant isolation.
- Verifying loopback pool with strict provenance and no duplicate mining records after interrupted writes.
- Tests against the installed wheels from outside the repo; clean wheel-from-sdist, frontend/Node >=22 tests and build, and full relevant CI matrix.

If any test path or package is missing, fail rather than skip or substitute a fixture. Use real fresh operating-system subprocesses for claimed restart verification.

## E. Controlled first startup

Build the frontend with npm ci and the repo-declared node version, then start exactly one API process using the M5 venv. Confirm healthz, authenticated readyz, mining/cognition status, process tree, heartbeat freshness, OVID/THESEUS reconciliation and AL HARAS policy. A 401/403 from security-protected readiness/metrics must not be worked around by opening those routes. Do not confuse one healthy endpoint with an integrated intelligence or accelerated hashing result.

## Release boundary

GO requires exact source identity, clean installed wheels, full applicable integrated checks passing, custody restart, measured genuine backend receipts and owner release approval.
NO-GO for stale/duplicate process, altered authority/ontology, unverified dependencies, incomplete custody, failed tests, absent device receipts or unsupported pool claims.
The M5/Metal/ASIC-like acceleration and real external-pool acceptance remain UNAVAILABLE until verified there. Publishing and ontology changes remain owner-gated.
