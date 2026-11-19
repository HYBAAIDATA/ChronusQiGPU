# Self-hosted Windows runner (critical path)

GitHub Actions billing on hosted runners is bypassed for the **critical path**
by routing those jobs to a machine labelled `[self-hosted, windows]`.

## Runner selection (hosted fallback)

The three critical-path jobs listed below read their `runs-on` labels from the repository variable
`CHRONUS_CRITICAL_RUNNER` (a JSON array):

```yaml
runs-on: ${{ fromJSON(vars.CHRONUS_CRITICAL_RUNNER || '["ubuntu-latest"]') }}
```

* Variable **unset** (default): jobs run on GitHub-hosted `ubuntu-latest`.
* Variable set to `["self-hosted","windows"]` (Settings → Secrets and
  variables → Actions → Variables): jobs route to the self-hosted machine
  described below.

Previously the label was hard-coded to `[self-hosted, windows]`. With no runner
registered every push and PR queued for 24 h and then failed, so `main` could
never go green. Only set the variable while a persistent runner is online —
if that machine sleeps, goes offline, or the service stops, the jobs queue and
the PR is **unmergeable** until it is back.

## Critical-path jobs only

In `.github/workflows/ci.yml` these jobs use the self-hosted label:

- `tests` (pytest)
- `quality-and-package` (lint / compile / package)
- `offline-stratum-smoke` (fake-pool accept round-trip)

`purity-gate` (mathematical purity + mechanism seal + attestation gates) runs on
hosted `ubuntu-latest` and is **not** moved by `CHRONUS_CRITICAL_RUNNER`.

All other workflow jobs remain on `ubuntu-latest`. Do **not** attach the
self-hosted label to the full 50+ check matrix — one machine serialises those
jobs and turns every PR into a long queue.

Each critical-path job also has:

```yaml
if: >-
  github.event_name != 'pull_request'
  || github.event.pull_request.head.repo.full_name == github.repository
```

so **fork PRs never run on the self-hosted machine**, while `push` and
`workflow_dispatch` still do (the left clause short-circuits before
`pull_request` is read). Jobs also set `timeout-minutes` and the workflow uses
`concurrency.cancel-in-progress` so a hung or stale run cannot occupy the only
slot forever.

## Prerequisites

| Requirement | Why |
|-------------|-----|
| **Python 3.13** on PATH (and via `actions/setup-python`) | Critical jobs pin 3.13; `runner_doctor` fails below that |
| **Git for Windows** on PATH | checkout and local evidence binding |
| **Work directory outside OneDrive** | Sync client file locks mid-build; import benchmarks become non-comparable |
| Runner registered as a **persistent** service | One `--ephemeral` run only covers the first of three jobs |

## Register a runner (persistent — required for three jobs)

Put `_work` on a local disk path, **not** under `OneDrive`:

```powershell
# From the repo Settings → Actions → Runners → New self-hosted runner
mkdir C:\actions-runner; cd C:\actions-runner
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-win-x64-2.321.0.zip -OutFile actions-runner-win-x64.zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD/actions-runner-win-x64.zip", "$PWD")
./config.cmd --url https://github.com/HYBAAIDATA/ChronusQiGPU --token <REGISTRATION_TOKEN> --labels windows --name chronus-win-critical --work C:\actions-runner\_work
./svc.cmd install
./svc.cmd start
```

Required labels: `self-hosted` (added by default) and `windows`. Treat the host
as high-trust: keep the same-repo `if:` guard, enable outside-collaborator
approval, and clean the work directory between jobs if you share the machine.

### Runner doctor (first CI step)

Critical-path jobs run `python scripts/ci/runner_doctor.py` before pip install.
It fails with an explicit message if Python is too old, `git` is missing, or the
work path sits under OneDrive — so a misconfigured machine does not become a
mystery timeout.

### Optional: ephemeral loop (advanced)

If you prefer ephemeral runners, you must **re-register after every job** —
one `--ephemeral` `./run.cmd` is not enough for three jobs:

```powershell
while ($true) {
  ./config.cmd --url https://github.com/HYBAAIDATA/ChronusQiGPU --token <TOKEN> --labels windows --name chronus-win-eph --work C:\actions-runner\_work --ephemeral --unattended --replace
  ./run.cmd
}
```

## Fork-PR caveat (public repos)

A **repository-level** self-hosted runner **does** accept `pull_request` jobs
from forks once the run is allowed (org runner-group policies do not apply).
That is why every critical-path job in this workflow is gated to same-repo
refs. Also enable “Require approval for all outside collaborators” under
Actions settings.

Do **not** use `pull_request_target` to check out and execute untrusted PR
code: that pattern runs with base-repo privileges and secrets (the “pwn
request” anti-pattern). Keep fork validation on `ubuntu-latest` hosted
runners, or require a push to a branch in this repository after review.

While `CHRONUS_CRITICAL_RUNNER` points at the self-hosted labels and no runner
with the `windows` label is online, those three jobs stay queued for same-repo
events. Unset the variable to fall back to hosted `ubuntu-latest`.

## Ops note

One self-hosted machine runs one job at a time by default. Keep the label
reserved for the critical path above so lint, gates, pytest, and offline smoke
stay responsive.
