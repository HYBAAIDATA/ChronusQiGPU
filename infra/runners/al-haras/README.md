# AL HARAS Ephemeral Sovereign Runner

Self-hosted, single-job GitHub Actions runner with a hardware/kernel root of
trust. Each runner boots, pins the AL HARAS eBPF/LSM programs, registers
ephemerally, attests its kernel state before accepting job code, executes
exactly one job, scrubs, and re-registers. Nothing persists between jobs.

Recommended host: dedicated bare metal or an Azure Confidential VM with
AMD SEV-SNP / Intel TDX so job memory is hardware-encrypted against the
hypervisor.

## Layout

| Path | Installed to | Purpose |
| --- | --- | --- |
| `chronus-sovereign-runner.service` | `/etc/systemd/system/` | Ephemeral runner unit (systemd-hardened) |
| `al-haras-bootstrap.sh` | `/usr/local/sbin/` | Root pre-start: lock unprivileged BPF, pin LSM programs |
| `al-haras-teardown.sh` | `/usr/local/sbin/` | Root post-stop: scrub workspace, deregister runner |
| `register-ephemeral.sh` | `/opt/actions-runner/bin/` | `--ephemeral` registration with sovereign labels |
| `hooks/pre-job-attest.sh` | `/opt/actions-runner/hooks/` | `ACTIONS_RUNNER_HOOK_JOB_STARTED`: kernel/LSM attestation + receipt |
| `hooks/post-job-scrub.sh` | `/opt/actions-runner/hooks/` | `ACTIONS_RUNNER_HOOK_JOB_COMPLETED`: workspace/temp scrub |

## Install

```bash
sudo install -m 0644 chronus-sovereign-runner.service /etc/systemd/system/
sudo install -m 0755 al-haras-bootstrap.sh al-haras-teardown.sh /usr/local/sbin/
sudo install -m 0755 register-ephemeral.sh /opt/actions-runner/bin/
sudo install -m 0755 hooks/pre-job-attest.sh hooks/post-job-scrub.sh /opt/actions-runner/hooks/
sudo systemctl daemon-reload
sudo systemctl enable --now chronus-sovereign-runner.service
```

Prerequisites: runner image ships pre-compiled AL HARAS LSM objects under
`/opt/al-haras/lsm/*.o` (never compile on the runner), `bpftool`, and a
short-lived registration token in `RUNNER_CFG_TOKEN`.

## Using the sovereign pool from a workflow

Do **not** enable this as a standing workflow until at least one runner with
these labels is online — jobs would queue forever. Template:

```yaml
jobs:
  qualify-v36:
    runs-on: [self-hosted, sovereign, al-haras-enforced]
    steps:
      - name: Verify AL HARAS Pre-Flight Receipt Exists
        run: |
          RECEIPT="/tmp/al_haras_pre_flight_receipt_${GITHUB_RUN_ID}.json"
          test -f "$RECEIPT" || (echo "Missing AL HARAS receipt!" && exit 1)
          cat "$RECEIPT"

      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      # ... Chronusv2 test and qualification steps ...

      - name: Attest AL HARAS Pre-Flight Receipt
        uses: actions/attest-build-provenance@96b4a1ef7235a096b17240c259729fdd70c83d45 # v2
        with:
          subject-path: /tmp/al_haras_pre_flight_receipt_${{ github.run_id }}.json
```

See `docs/sovereign-hardening.md` §3 for the runner-group and routing policy.
