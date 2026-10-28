# Live pool smoke — self-hosted runner setup

One-time setup so the `Live Pool Smoke` workflow (`.github/workflows/live-pool-smoke.yml`)
can execute the bounded one-share Stratum acceptance run on the owner's
WSL2 / iGPU host. The pool password lives only in a GitHub Environment
secret — write-only, never readable back, never in chat, files or logs.

## 1. Register the self-hosted runner (one time, on the host)

The runner needs labels `self-hosted` and `chronus`:

```bash
# On the WSL2 host
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o runner.tar.gz -L https://github.com/actions/runner/releases/download/v2.329.0/actions-runner-linux-x64-2.329.0.tar.gz
tar xzf runner.tar.gz
# Get a registration token (repo admin), then:
./config.sh --url https://github.com/HYBAAIENTERPRISE/HYBAEnterprise \
            --token <REGISTRATION_TOKEN> \
            --labels self-hosted,linux,x64,chronus \
            --name chronus-wsl2 --unattended
./run.sh   # or: sudo ./svc.sh install && sudo ./svc.sh start
```

For the opencl lane the host also needs the Intel OpenCL runtime visible to WSL2:

```bash
sudo apt install -y ocl-icd-opencl-dev opencl-headers clinfo
clinfo | grep -i intel   # must list an Intel device; otherwise the workflow halts by design
```

## 2. Create the environment and secret (one time)

```bash
gh secret set PYTHIA_POOL_PASSWORD --repo HYBAAIENTERPRISE/HYBAEnterprise --env pool-live-smoke
# prompts for the value; it is write-only from this point on
```

The `pool-live-smoke` environment may also carry a required-reviewers
protection rule; dispatch stays limited to collaborators with write access.

## 3. Run

```bash
gh workflow run live-pool-smoke.yml --repo HYBAAIENTERPRISE/HYBAEnterprise \
  -f pool=viabtc -f worker='ACCOUNT.001' -f backend=opencl
gh run watch
```

or Actions → Live Pool Smoke → Run workflow. Failover pool: `-f pool=braiins`
with the Braiins worker identity.

## 4. Outcomes (run card)

| Condition | Result |
| --- | --- |
| No Intel device on opencl lane | Job halts before any traffic — connected but no shares; no CPU fallback |
| Pool rejects auth | Shares rejected — job fails, redacted log uploaded |
| `result = true` on a submit | Shares accepted — `accepted_share.log.redacted` artifact (password scrubbed), 90-day retention |
| No accept inside 600s | Bounded exit, redacted log uploaded, verdict noted in the run summary |

The worker name and pool choice are not secrets and appear in logs; the
password never does.

## Capacity note

The workflow runs directly on the host (no container). The host's Docker
capacity (~100 GB) is untouched and remains available for the heavier lanes
— native stack smoke, quantum/folding workloads — which can join as
additional self-hosted jobs once this lane is green.
