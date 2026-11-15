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

## Register a runner

On the Windows host (PowerShell as the service account that will run jobs):

```powershell
# From the repo Settings → Actions → Runners → New self-hosted runner
mkdir actions-runner; cd actions-runner
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-win-x64-2.321.0.zip -OutFile actions-runner-win-x64.zip
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory("$PWD/actions-runner-win-x64.zip", "$PWD")
./config.cmd --url https://github.com/HYBAAIDATA/ChronusQiGPU --token <REGISTRATION_TOKEN> --labels windows --name chronus-win-critical
./run.cmd
```

Use the registration token from the GitHub UI (short-lived). Prefer installing
the runner as a Windows service (`./svc.cmd install` / `start`) so it survives
logoff.

Required labels: `self-hosted` (added by default) and `windows`.

## Fork-PR caveat (public repos)

Workflows that run on `pull_request` from forks do **not** receive secrets and
are not scheduled onto organization self-hosted runners unless the repository
explicitly allows it. Prefer `pull_request_target` only with a locked-down
checkout of the merge ref, or require that critical-path checks run on
`push` to a branch in this repository after review.

Until a self-hosted runner with the `windows` label is online, those four jobs
will stay queued — that is expected, not a billing failure.

## Ops note

One self-hosted machine runs one job at a time by default. Keep the label
reserved for the critical path above so lint, gates, pytest, and offline smoke
stay responsive.
