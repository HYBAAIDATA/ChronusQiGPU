# Runbook — install, configure, operate, recover, release

Verified at `e09afab` on Windows + Linux-docker paths. Commands marked
[verified] ran in this session; others are repo-documented.

## Install (development)

```bash
python -m venv .venv                     # or: uv venv .venv
pip install -e ".[ml,dev]" -e ./turing_universal_quantum_computer   # [verified via uv]
npm ci --prefix frontend                 # Node >= 20 works; repo requests >=22 (.nvmrc 22.15.0)
```

Windows note: `.venv` made by `uv` has no pip → `uv pip install --python .venv/Scripts/python.exe ...` [verified].
`npm` not on bash PATH → use `npm.cmd` inside `frontend/` or `node <npm-cli> --prefix frontend` [verified].

## Install (delivered artifact)

```bash
python -m build                     # or uv build → dist/ wheels for pythia-mla1517 + TUQC [verified]
pip install dist/pythia_mla1517-0.1.0-py3-none-any.whl \
            dist/turing_universal_quantum_computer-1.0.0-py3-none-any.whl   # [verified clean-env]
```

## Configure

Environment (all fail-closed when missing): `MLA1517_STRATUM_USER`,
`MLA1517_STRATUM_PASSWORD`, `MLA1517_BRAIINS_ENDPOINT` (or per-pool `*_ENDPOINT`),
`MLA1517_MMIO_DEVICE` (hardware), `PYTHIA_RUNTIME_CONFIG` (optional path —
defaults to `data/runtime_config.json`), `PYTHIA_WORKER_HEARTBEAT_DIR`,
`PYTHIA_IDENTITY_HMAC_SECRET` (64-hex), live-submit triple gate:
`HYBA_ENABLE_LIVE_SHARE_SUBMIT` + `HYBA_LIVE_SHARE_APPROVAL_ID` +
`HYBA_AUTONOMOUS_EXTERNAL_ACTIONS`.

`.env` at repo root is auto-loaded; process env wins. `.env.<pool>` merges only
via `live_mine.py`/`live_handshake.py`.

## Start / stop / restart

```bash
python main.py --host 127.0.0.1 --port 3000 --web-root dist/public   # control API + UI [help verified]
python -u chronus/mla1517_platform/python/main.py ...                   # same entry, direct path
```

Boot writes `BOOT_AUDIT.log` + `pythia-main.lock` to the boot-work dir
(`C:\tmp\pythia\` on this Windows box — verified path; `data/` holds only
runtime_config). Second instance needs `PYTHIA_BOOT_LOCK`/`PYTHIA_BOOT_AUDIT`
overrides.
Stop: SIGTERM/SIGINT — runner-stop semantics under Owner B verification (RUN-01).
Restart: runtime_config + heartbeat sidecars reload — persistence verification pending (B).

## Diagnose

- `GET /api/v1/mla1517/status` — device/workers/stratum/canonicalEngine honesty fields
- `GET /readyz` `/api/health` `/healthz` — liveness/readiness (healthchecks used by both Dockerfiles)
- `GET /api/v1/ready-to-mine` — 503 + JSON body when not ready (by design)
- `GET /api/v1/system/map` + `/api/v1/system/verify` — fabric map + verification
- `GET /metrics` — worker sidecar metrics (hashrate only from executed work)
- `scripts/re_paper_gate.py`, `python -m scripts.drift_sentry --verify`,
  `python -X utf8 -m Intelligence.self_test` — offline verdicts [all verified PASS]

## Backup / restore

- `data/runtime_config.json` — operator-facing config (bounded writes; pool passwords merged server-side)
- `C:\tmp\pythia\BOOT_AUDIT.log`, heartbeat dir sidecars (`*.bin` HMAC + `*.metrics.json`)
- Restore = reinstall + same env + existing `data/` dir; recovery verification pending (B).

## Release gates (before calling a build releasable)

1. `pytest tests/ -x -q` green [baseline: 1221/8skip]
2. `unittest discover -s chronus/mla1517_platform/python` green [baseline: 203/6skip]
3. `cd turing_universal_quantum_computer && pytest tests -q` green [baseline: 44/1FAIL — `test_vqc_execution_certifies_window` open → Owner A]
4. `flake8`/`black` on the 9 gated platform files clean [verified]
5. Frontend: `npm run test:ts` (25/25), `lint`, `build` [verified]
6. Wheel builds + clean-env install + `pythia-api --help`/`pythia-mine --help` [verified]
7. `re_paper_gate` + `drift_sentry --verify` + `self_test` [verified]
8. Hardware gate on an OpenCL host: `MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl make test` — **must be run on a device host before release** [NOT_RUN here]
9. Live pool evidence: bounded run on a configured pool — requires explicit authorization [NOT_RUN]

## Docker

`docker build -f Dockerfile -t pythia .` (multi-stage node22+py3.12, OpenCL ICDs vendored) /
`deploy/azure/Dockerfile` (hardened, non-root, healthcheck `/healthz`). Docker build NOT_RUN here.
