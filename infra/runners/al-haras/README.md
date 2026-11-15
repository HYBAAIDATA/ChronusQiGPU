# AL HARAS ephemeral sovereign runner

Deployment files for a self-hosted GitHub Actions runner that takes one job
per registration on a dedicated Linux host. Before the runner registers, a
root bootstrap checks the AL HARAS BPF LSM objects against a SHA-256 manifest,
loads and attaches them, disables unprivileged BPF and writes an attestation
for that systemd invocation. Before the job's first step, a job-started hook
checks that attestation and writes a receipt containing SHA-256 digests. After
the job the unit stops, a root teardown cleans up, and systemd starts the next
cycle with a fresh copy of the runner.

**Status.** CI checks these files with `bash -n` and with stub-based tests
(`tests/test_al_haras_runner_scripts.py`). They have not been run on a real
host from this repository. This directory contains neither the LSM program
sources nor compiled objects, and nothing here evaluates which policy those
programs enforce. No hardware attestation (TPM, AMD SEV-SNP, Intel TDX report)
is collected. A confidential VM or dedicated bare metal is a recommendation
for the host, not something these scripts check.

## One runner cycle

| Step | Unit line / trigger | Runs as | What happens |
| --- | --- | --- | --- |
| 1 | `ExecStartPre=+…/al-haras-bootstrap.sh` | root, outside the sandbox | Requires `bpf` in the active LSM list; sets `kernel.unprivileged_bpf_disabled=1`; mounts bpffs (mode 0700) if needed; checks each object against the manifest; runs `bpftool prog loadall <copy> <pin dir> autoattach`; requires every pinned entry to be an `lsm_mac` link to an `lsm` program; replaces `/opt/actions-runner` with a copy of `/opt/actions-runner-dist`; removes earlier invocations' pins; writes `/run/al-haras/attestation`. Any failure stops the unit before registration, removes the new links and leaves the previous ones attached. |
| 2 | `ExecStartPre=+…/register-ephemeral.sh` | root, then `config.sh` as `github-runner` | Reads `/etc/al-haras/runner.env`; runs `config.sh --ephemeral --disableupdate --unattended --replace` through `setpriv`, passing the token in `ACTIONS_RUNNER_INPUT_TOKEN`. |
| 3 | `ExecStart=/opt/actions-runner/run.sh` | `github-runner`, sandboxed | Waits for one job. |
| 4 | job-started hook `pre-job-attest.sh` | `github-runner`, sandboxed | Checks the attestation (see below). On failure it exits non-zero and GitHub marks the job failed without running its steps. Otherwise it writes the receipt. |
| 5 | job steps | `github-runner`, sandboxed | |
| 6 | job-completed hook `post-job-scrub.sh` | `github-runner`, sandboxed | Deletes the receipt, the checkout and this user's files in `/tmp`, `/var/tmp`, `/dev/shm`. |
| 7 | runner exits | | GitHub has de-registered the ephemeral runner and the runner deletes its local registration files; systemd stops what is left in the unit's cgroup (`KillMode=control-group`). |
| 8 | `ExecStopPost=+…/al-haras-teardown.sh` | root, outside the sandbox | Compares the recorded links with the kernel's current links and logs the result; archives runner diagnostic logs; deletes `_work` and the registration files; deletes the attestation. |
| 9 | `Restart=always`, `RestartSec=3` | | Back to step 1. A failing bootstrap or registration is retried every 3 s and never registers a runner. |

"Sandboxed" means the unit's `NoNewPrivileges=`, `PrivateTmp=`, `RemoveIPC=`,
`ProtectSystem=strict`, `ProtectKernelModules=` and `ProtectKernelTunables=`
apply. The `+` prefix exempts a command from all of them. The bootstrap needs
that exemption: under `ProtectKernelTunables=` and `ProtectSystem=`,
`/proc/sys` and `/sys/fs/bpf` are read-only, and a bpffs mount would stay in
a private mount namespace. The previous unit used `PermissionsStartOnly=true`,
which is deprecated since systemd 240. It gave every `ExecStartPre=` and
`ExecStopPost=` command the same exemption, including `register-ephemeral.sh`,
so `config.sh` ran as root and refused to configure ("Must not run with
sudo").

## Files and install locations

| File | Installed to | Purpose |
| --- | --- | --- |
| `chronus-sovereign-runner.service` | `/etc/systemd/system/` | Unit: lifecycle above, sandbox for the runner and jobs. |
| `al-haras-bootstrap.sh` | `/usr/local/sbin/` | Root pre-start: LSM checks, load and attach, runner refresh, attestation. |
| `al-haras-teardown.sh` | `/usr/local/sbin/` | Root post-stop: link comparison, log archive, cleanup. |
| `register-ephemeral.sh` | `/usr/local/libexec/al-haras/` | Ephemeral registration without exposing the token to jobs. |
| `hooks/pre-job-attest.sh` | `/usr/local/libexec/al-haras/hooks/` | `ACTIONS_RUNNER_HOOK_JOB_STARTED`: attestation check and receipt. |
| `hooks/post-job-scrub.sh` | `/usr/local/libexec/al-haras/hooks/` | `ACTIONS_RUNNER_HOOK_JOB_COMPLETED`: post-job deletion. |

The scripts and hooks live outside `/opt/actions-runner` because a job can
write there (GitHub's documentation also says hook scripts should not be
stored in the runner application directory). For the same reason the
bootstrap rebuilds `/opt/actions-runner` from the root-owned
`/opt/actions-runner-dist` on every cycle. Otherwise a job could replace
`run.sh`, the runner binaries or the runner's `.env` file, and with them the
hook settings for the next job.

Paths the scripts use: `/opt/al-haras/lsm/` (objects and
`manifest.sha256`), `/sys/fs/bpf/al_haras/<INVOCATION_ID>/` (pinned links),
`/run/al-haras/attestation`, `/run/al-haras/stage` (private object copies
during the bootstrap), `/opt/actions-runner-dist`, `/opt/actions-runner`,
`/opt/actions-runner/_work/_al_haras/pre-flight-receipt.json`,
`/etc/al-haras/runner.env` and `/var/log/al-haras/runner-diag/`.

## Host requirements

- systemd 232 or later (`+` prefix, `ProtectSystem=strict`, `RemoveIPC=`).
- A kernel built with `CONFIG_BPF_LSM=y` and booted with `bpf` in the `lsm=`
  list, with securityfs mounted at `/sys/kernel/security`.
- A `bpftool` whose `bpftool prog help` lists `autoattach`; the bootstrap
  checks this.
- coreutils, findutils, and util-linux (`setpriv`, `mountpoint`).
- Every program in every LSM object must be an LSM program that libbpf can
  attach automatically (`SEC("lsm/<hook>")` or `SEC("lsm.s/<hook>")`). Any other
  program type makes the bootstrap fail.
- Do not enable lingering (`loginctl enable-linger`) for `github-runner`, and
  do not add it to the `docker` group or to sudoers. Each would let job code
  outlive the unit or act as root, and nothing here would detect it.
- Registration tokens expire one hour after they are created, and every cycle
  registers again. Something outside these files must write a fresh
  `RUNNER_CFG_TOKEN` into `/etc/al-haras/runner.env` before the old one
  expires. Until then each start fails at step 2.

## Install

```bash
# Runner user and directories. The bootstrap copies /opt/actions-runner-dist
# into /opt/actions-runner on every cycle.
sudo useradd --system --home-dir /opt/actions-runner --no-create-home --shell /usr/sbin/nologin github-runner
sudo install -d -o github-runner -g github-runner -m 0750 /opt/actions-runner
sudo install -d -o root -g root -m 0755 /opt/actions-runner-dist
sudo tar -xzf actions-runner-linux-x64-<version>.tar.gz -C /opt/actions-runner-dist
sudo chown -R root:root /opt/actions-runner-dist
sudo chmod -R go-w /opt/actions-runner-dist

# LSM objects from your image build (not in this repository) and their manifest:
# run `sha256sum *.o > manifest.sha256` in the build output directory.
sudo install -d -o root -g root -m 0755 /opt/al-haras/lsm
sudo install -o root -g root -m 0644 build/*.o build/manifest.sha256 /opt/al-haras/lsm/

# Registration settings (root-only, holds the token; see Configuration).
sudo install -d -o root -g root -m 0700 /etc/al-haras
sudo install -o root -g root -m 0600 runner.env /etc/al-haras/runner.env

# Scripts, hooks and unit.
sudo install -o root -g root -m 0755 al-haras-bootstrap.sh al-haras-teardown.sh /usr/local/sbin/
sudo install -d -o root -g root -m 0755 /usr/local/libexec/al-haras/hooks
sudo install -o root -g root -m 0755 register-ephemeral.sh /usr/local/libexec/al-haras/
sudo install -o root -g root -m 0755 hooks/pre-job-attest.sh hooks/post-job-scrub.sh /usr/local/libexec/al-haras/hooks/
sudo install -o root -g root -m 0644 chronus-sovereign-runner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chronus-sovereign-runner.service
```

## Configuration

`/etc/al-haras/runner.env` holds `KEY=VALUE` lines. `#` comments and blank
lines are allowed, as is one pair of quotes around a value. Any key not
listed below is rejected. The file must be owned by root with mode 0600. Only
`register-ephemeral.sh` reads it. It is deliberately not an
`EnvironmentFile=`: the runner passes its whole environment to every job
step.

| Variable | Set in | Used by | Default | Meaning |
| --- | --- | --- | --- | --- |
| `RUNNER_CFG_TOKEN` | `runner.env` | `register-ephemeral.sh` | required | Registration token. It reaches `config.sh` only as `ACTIONS_RUNNER_INPUT_TOKEN`, which the runner reads and then deletes from its environment. It never appears on a command line or in the unit environment. Expires one hour after creation. |
| `REPO_URL` | `runner.env` | `register-ephemeral.sh` | `https://github.com/hybadatadevops1/Chronusv2` | Repository URL, or the organization URL when `RUNNER_GROUP` is used. |
| `RUNNER_LABELS` | `runner.env` | `register-ephemeral.sh` | `sovereign,al-haras-enforced` | Custom labels. The runner adds `self-hosted`, `Linux` and the architecture itself. |
| `RUNNER_GROUP` | `runner.env` | `register-ephemeral.sh` | unset | Runner group. Groups exist only for organizations and enterprises, and `config.sh` fails if the group does not exist, so `--runnergroup` is passed only when this is set. |
| `RUNNER_NAME` | `runner.env` | `register-ephemeral.sh` | `sovereign-<short hostname>-<epoch seconds>` | Runner name. In the hooks, `RUNNER_NAME` is GitHub's default variable with the registered name. |
| `ACTIONS_RUNNER_HOOK_JOB_STARTED` | unit `Environment=` | actions runner | `/usr/local/libexec/al-haras/hooks/pre-job-attest.sh` | Job-started hook. |
| `ACTIONS_RUNNER_HOOK_JOB_COMPLETED` | unit `Environment=` | actions runner | `/usr/local/libexec/al-haras/hooks/post-job-scrub.sh` | Job-completed hook. |
| `ACTIONS_RUNNER_REQUIRE_JOB_CONTAINER` | unit `Environment=` | actions runner | `false` | Jobs do not have to declare a job container. |
| `HOME` | unit `Environment=` | runner, jobs | `/opt/actions-runner` | A writable home inside the sandbox (`ProtectSystem=strict` makes the rest read-only). |
| `AL_HARAS_DIAG_RETENTION_DAYS` | unit `Environment=` | `al-haras-teardown.sh` | `14` | Days to keep archived runner diagnostic logs. |
| `INVOCATION_ID` | systemd | bootstrap, pre-job hook, teardown | set by systemd | Identifies one unit invocation, which is one runner cycle. The attestation is bound to it. |
| `GITHUB_REPOSITORY`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, `GITHUB_JOB`, `GITHUB_SHA`, `GITHUB_WORKFLOW_REF`, `RUNNER_NAME` | runner (default variables) | `pre-job-attest.sh` | | Copied into the receipt. |
| `GITHUB_WORKSPACE` | runner (default variable) | `post-job-scrub.sh` | | Checkout to delete. It must lie under `/opt/actions-runner/_work`. |

The scripts do not read `RUNNER_CFG_PAT`, which an earlier comment
mentioned, or `RUNNER_REMOVE_TOKEN`, which the earlier teardown used (see
Deregistration). JIT configuration (`run.sh --jitconfig`) is not implemented.

## Attestation (`/run/al-haras/attestation`)

The file is written by the bootstrap and owned by root (0644, in a root 0755
directory). It contains one `key=value` per line: `format`
(`al-haras-attestation/1`), `invocation_id`, `boot_id`, `kernel_release`,
`generated_at`, `lsm` (the active LSM list), `unprivileged_bpf_disabled`,
`bpftool` (version line), `manifest`, `manifest_sha256`, `pin_dir`, one
`object=<name>.o <sha256>` per manifest entry, and one
`link=<object> <program> <link_id> <prog_id> <prog_tag> lsm_mac` per attached
program. The bootstrap also prints the file to the journal.

The manifest (`/opt/al-haras/lsm/manifest.sha256`) uses `sha256sum` format
with lowercase hex. Object names may contain only `[A-Za-z0-9_-]` plus `.o`,
because bpffs rejects pin names that contain dots. Every `*.o` in the
directory must be listed. Objects must be root-owned and not group- or
world-writable.

**What the job-started hook checks.** It runs as `github-runner`, which
cannot read bpffs (mode 0700, root). With unprivileged BPF disabled, it also
cannot query the kernel for programs. It therefore checks:

- live: `bpf` is in `/sys/kernel/security/lsm` and
  `kernel.unprivileged_bpf_disabled` is `1`;
- the attestation and its directory, and the manifest and its directory, are
  owned by root and not group- or world-writable, and are not symlinks;
- the attestation's `invocation_id` equals this unit's `INVOCATION_ID`, its
  `boot_id` equals this boot's, and its `kernel_release` equals `uname -r`;
- `manifest_sha256` equals the SHA-256 of the manifest on disk; the
  attestation lists exactly the manifest's objects with the same SHA-256
  values, and records at least one `lsm_mac` link for every object.

**What this does not establish.** The hook trusts the root-written record.
It does not see the kernel's live program state, so root could change that
state after the bootstrap. The teardown compares the recorded links with the
kernel after the job and logs any difference. That is detection after the
fact, not prevention. Program tags and ids are recorded but not compared with
expected values, because tags depend on the kernel; the object hashes are
what is pinned. Nothing here evaluates what the programs enforce.

## Pre-flight receipt

The receipt is written by the job-started hook to
`/opt/actions-runner/_work/_al_haras/pre-flight-receipt.json`. It exists only
if every check above passed. It is JSON with: `schema`
(`al-haras-pre-flight-receipt/1`), `generated_at`, `attestation_path`,
`attestation_sha256` (SHA-256 of the attestation file),
`attestation_owner_uid`, `attestation_mode`, `attestation` (every attestation
field), `objects` (name and SHA-256 per object), `lsm_links` (object,
program, link id, program id, program tag, attach type),
`observed_at_job_start` (the live values the hook compared) and `github`
(repository, run id, run attempt, job, commit SHA, workflow ref, runner
name).

The receipt is **not signed**. It is owned by the job user, so later steps of
the same job could change it. The attestation itself is root-owned and
cannot be changed by the job. A workflow that needs evidence should do two
things: check the receipt's `attestation_sha256` against
`/run/al-haras/attestation`, and sign or attest both files, as in the
template below.

## Retention

| Artifact | Location | Removed by | To keep it |
| --- | --- | --- | --- |
| Attestation | `/run/al-haras/attestation` | teardown at the end of each cycle; `/run` is cleared at reboot | The bootstrap prints it to the journal. Attest it in the job. |
| Pinned LSM links | `/sys/fs/bpf/al_haras/<INVOCATION_ID>/` | the next bootstrap, after the new links are attached; reboot | |
| Private object copies | `/run/al-haras/stage` | the bootstrap, before it exits | |
| Pre-flight receipt | `/opt/actions-runner/_work/_al_haras/` | post-job hook at the end of the job, then teardown, then the next bootstrap | Upload or attest it in a job step. |
| Job checkout | `$GITHUB_WORKSPACE` | post-job hook | |
| Rest of `_work` (actions, tool cache) | `/opt/actions-runner/_work` | teardown | |
| Job temp files | `/tmp`, `/var/tmp` (private per invocation) | post-job hook (this user's entries); systemd when the unit stops | |
| Shared memory, SysV IPC | `/dev/shm`, IPC namespace | post-job hook (`/dev/shm` entries); `RemoveIPC=true` when the unit stops | |
| Registration files | `.runner`, `.credentials`, `.credentials_rsaparams` | the runner after its ephemeral job; teardown; next bootstrap | |
| Runner diagnostic logs | `/opt/actions-runner/_diag` → `/var/log/al-haras/runner-diag/<INVOCATION_ID>/` (root-only, `*.log` under 64 MiB) | teardown deletes copies older than `AL_HARAS_DIAG_RETENTION_DAYS` (14); the next bootstrap deletes `_diag` | Forward them to external storage; GitHub asks for this for ephemeral runners. |
| Journal (all script output) | journald | journald's own retention settings | Ship it to append-only storage (`docs/sovereign-hardening.md` §5). |

Deletion unlinks files; it does not overwrite disk blocks. If residual data
on disk matters, use encrypted ephemeral storage or reimage the host.

## Deregistration

- **Normal path.** A runner registered with `--ephemeral` is de-registered by
  GitHub after it has processed one job, and the runner deletes its local
  registration files when it exits.
- **Stopped before a job was assigned.** The registration stays in GitHub as
  offline. The teardown and the next bootstrap delete the local files, so the
  stale registration cannot be used from this host. GitHub automatically
  removes an ephemeral runner that has not connected for more than one day.
  To remove it sooner, use Settings → Actions → Runners or the REST API.
- The teardown does not run `config.sh remove`. That needs a separate removal
  token (also valid for one hour), and it would mean root running code from
  the job-writable runner directory outside the sandbox.

## Using the sovereign pool from a workflow

Do **not** turn this into a standing workflow until at least one runner with
these labels is online: GitHub keeps such jobs queued and fails them after 24
hours. Template:

```yaml
jobs:
  qualify:
    runs-on: [self-hosted, sovereign, al-haras-enforced]
    permissions:
      contents: read
      id-token: write       # Sigstore OIDC certificate for the attestation step
      attestations: write
    steps:
      # The job-started hook has already failed the job if any check failed.
      # This ties the job-writable receipt to the root-owned attestation.
      - name: Check AL HARAS receipt against the host attestation
        shell: bash
        run: |
          set -euo pipefail
          receipt=/opt/actions-runner/_work/_al_haras/pre-flight-receipt.json
          digest=$(sha256sum /run/al-haras/attestation | cut -d' ' -f1)
          grep -q "\"attestation_sha256\": \"${digest}\"" "$receipt"
          cat "$receipt"

      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      # ... Chronusv2 test and qualification steps ...

      # Signs the SHA-256 digests of both files (Sigstore). Artifact attestations
      # are rejected on user-owned private repositories (docs/sovereign-hardening.md
      # §1); there, sign both files with `cosign sign-blob` instead.
      - name: Attest AL HARAS attestation and receipt
        continue-on-error: true
        uses: actions/attest-build-provenance@96b4a1ef7235a096b17240c259729fdd70c83d45 # v2
        with:
          subject-path: |
            /run/al-haras/attestation
            /opt/actions-runner/_work/_al_haras/pre-flight-receipt.json
```

See `docs/sovereign-hardening.md` §3 for routing: labels on a user-owned
repository, or runner groups in an organization.
