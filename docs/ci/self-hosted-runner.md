# Self-hosted Windows runner (critical path)

GitHub Actions billing on hosted runners is bypassed for the **critical path**
by routing those jobs to a machine labelled `[self-hosted, windows]`.

## Critical-path jobs only

In `.github/workflows/ci.yml` these jobs use the self-hosted label:

- `tests` (pytest)
- `quality-and-package` (lint / compile / package)
- `purity-gate` (mathematical purity + mechanism seal + attestation gates)
- `offline-stratum-smoke` (fake-pool accept round-trip)

All other workflow jobs remain on `ubuntu-latest`. Do **not** attach the
self-hosted label to the full 50+ check matrix — one machine serialises those
jobs and turns every PR into a long queue.

Each critical-path job also has:

```yaml
if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
```

so **fork PRs never run on the persistent self-hosted machine**. Same-repo PRs
and pushes still use it.

## Register a runner

On the Windows host (PowerShell as the service account that will run jobs):

```powershell
# From the repo Settings → Actions → Runners → New self-hosted runner
mkdir actions-runner; cd actions-runner
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-win-x64-2.321.0.zip -OutFile actions-runner-win-x64.zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD/actions-runner-win-x64.zip", "$PWD")
./config.cmd --url https://github.com/HYBAAIDATA/ChronusQiGPU --token <REGISTRATION_TOKEN> --labels windows --name chronus-win-critical --ephemeral
./run.cmd
```

Use the registration token from the GitHub UI (short-lived). Prefer
`--ephemeral` so each job gets a fresh runner process. If you must use a
long-lived service (`./svc.cmd install` / `start`), treat the host as
high-trust and keep the same-repo `if:` guard above.

Required labels: `self-hosted` (added by default) and `windows`.

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

Until a self-hosted runner with the `windows` label is online, those four jobs
will stay queued for same-repo events — that is expected, not a billing failure.

## Ops note

One self-hosted machine runs one job at a time by default. Keep the label
reserved for the critical path above so lint, gates, pytest, and offline smoke
stay responsive.
