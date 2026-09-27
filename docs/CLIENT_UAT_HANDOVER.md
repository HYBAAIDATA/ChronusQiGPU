# PYTHIA Client UAT and Handover Pack

**Client:** PHIDATA2/PYTHIA  
**Release candidate:** `production/stratum-mining-hardening`  
**System:** AETHEL → Tensor → TURING → iGPU/OpenCL → Stratum V1  
**Handover posture:** implementation UAT is separate from live-pool acceptance.

## 1. Executive decision

The release candidate is **implementation-ready for controlled client UAT**.
It is not yet permissible to label the system **mining successfully** until a
real pool returns `mining.submit.result == true` and the redacted evidence is
captured.

The hosted CI environment must not pretend to provide the client's UHD 620.
CI proves software contracts on CPU; the client host proves OpenCL visibility,
kernel execution, and pool acceptance.

## 2. Scope of acceptance

This UAT covers:

1. Repository integrity and secret boundaries.
2. Import, syntax, and production call-graph integrity.
3. Bitcoin consensus vectors, target conversion, and exact 80-byte headers.
4. Stratum subscribe, authorize, difficulty/target, notify, extranonce, and
   stale-job handling.
5. AETHEL storage, Tensor fold round-trip, TURING nonce scheduling, and the
   iGPU/OpenCL hash adapter.
6. Docker Compose deployment contracts.
7. Client-host OpenCL benchmark.
8. Controlled dry-run against the configured pool.
9. Live submission with an explicit approval gate.
10. Capture of a real accepted-share response.

It does not claim physical quantum hardware. The TURING layer is deterministic
software/symbolic state preparation. The iGPU is the actual OpenCL execution
substrate attached by the host deployment.

## 3. Entry criteria

Before beginning UAT, the client operator must confirm:

- The candidate commit is identified and reviewable.
- The host is the intended Windows/WSL2 machine with Docker Desktop.
- `/dev/dxg` and `/usr/lib/wsl` are available to the iGPU overlay.
- `clinfo` can see the intended Intel GPU.
- Pool credentials are stored in an ignored `.env` or secret manager.
- No credential is pasted into GitHub, a commit, an issue, or an evidence log.
- `HYBA_REQUIRE_HYBA=1` remains enabled.
- `PYTHIA_DEVICE_VENDOR=Intel`, `PYTHIA_DEVICE_PCI_IDS=0x5917`, and the
  expected device name are configured for the UHD 620 gate.

## 4. Test matrix

| ID | Test | Expected evidence | Status rule |
|---|---|---|---|
| UAT-01 | Repository guard | `IRONCLAD REPOSITORY GUARD: GREEN` | Must pass |
| UAT-02 | Production contract audit | JSON `status=green` | Must pass |
| UAT-03 | Import/syntax/compile | No syntax or import failures | Must pass |
| UAT-04 | Consensus vector | Genesis hash matches known vector | Must pass |
| UAT-05 | Mock Stratum workflow | Subscribe → authorize → job → search → submit → accepted | Must pass |
| UAT-06 | Compose contract | `docker compose config --quiet` succeeds | Must pass |
| UAT-07 | Hardware identity | Exact Intel UHD 620 `0x5917` accepted; wrong device rejected | Must pass on client host |
| UAT-08 | OpenCL kernel run | `kernel_executed=true`, non-zero hashes, zero errors | Must pass on client host |
| UAT-09 | Pool dry run | Authorized, job received, device work measured, no submit | Must pass before live |
| UAT-10 | Live share | Pool returns `result=true` | Required for final acceptance |
| UAT-11 | Failover | Disconnect causes bounded retry and next configured pool | Required for handover |
| UAT-12 | Stale-job safety | New generation prevents stale submission | Required for handover |

## 5. Offline UAT walkthrough

Run from the repository root:

```bash
python scripts/client_uat.py --json
```

This performs no pool connection and no share submission. A normal first result
is `conditional` because the physical OpenCL gate is deliberately not run in a
hosted or CPU-only environment.

For the client machine, run:

```bash
python scripts/client_uat.py --json --hardware
```

The OpenCL result must identify the intended device and report zero execution
errors. A rate alone is insufficient; the consensus self-check and kernel
execution fields must also pass.

## 6. Deployment walkthrough

Use the WSL2 overlay; do not use the device-less default override for hardware
UAT:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docker-compose.igpu-wsl2.yml \
  config --quiet

docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docker-compose.igpu-wsl2.yml \
  up -d

docker compose ps
curl -fsS http://localhost:8377/api/v1/readyz
```

Then prove visibility independently:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  -f docker-compose.igpu-wsl2.yml \
  --profile probe run --rm igpu-probe
```

Expected Gate A evidence:

- Intel OpenCL platform visible.
- UHD 620 device `0x5917` visible.
- OpenCL context creation succeeds.
- No CPU substitution when the exact identity gate is enabled.

## 7. Pool walkthrough

Configure credentials only through the ignored environment file or secret
manager. Do not place them in this document.

Set:

```bash
export PYTHIA_EXECUTION_PATH=aethel
export PYTHIA_HASH_BACKEND=opencl
export HYBA_REQUIRE_HYBA=1
export HYBA_DEVICE_VENDOR=Intel
export HYBA_DEVICE_PCI_IDS=0x5917
```

Dry run first:

```bash
python -m mining.production_miner --dry-run --max-runtime 120
```

The operator must capture redacted logs containing:

```text
Execution path=AETHEL->Tensor->TURING->iGPU
Stratum authorized
Job received
Hasher backend=opencl
```

Dry run must not contain a `mining.submit` request.

Only after UAT-08 and UAT-09 pass may the approved operator enable the existing
live-submit gates and run:

```bash
python -m mining.production_miner --submit --max-runtime 3600 --max-shares 1
```

Final acceptance requires:

```text
Share result accepted=True
```

The accepted response must be retained in a redacted evidence file with the
commit SHA, timestamp, pool label, job ID redacted or pseudonymized, device,
backend, accepted/rejected counters, and exit reason.

## 8. Rollback and stop conditions

Stop immediately if any of the following occurs:

- Device identity is not exact or the gate falls back to CPU.
- Kernel self-check fails.
- A header is not exactly 80 bytes.
- Independent SHA-256d recheck fails.
- A stale job is about to be submitted.
- The client cannot bound socket reads/writes.
- Credentials appear in logs, artifacts, or Git.
- Pool authorization is ambiguous or rejected.
- A share is submitted without the explicit approval environment gate.

Rollback is the previous known-good commit plus the device-less default compose
configuration. No rollback should reuse a live credential from an evidence
bundle.

## 9. Handover evidence pack

The handover folder should contain only redacted artifacts:

```text
commit.txt
client_uat.json
compose_config.txt
opencl_benchmark.json
pool_dry_run.log.redacted
accepted_share.log.redacted
failover_test.log.redacted
operator_signoff.md
```

Never include `.env`, pool passwords, private keys, full worker credentials,
extranonce secrets, or unredacted connection strings.

## 10. Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| Engineering owner |  |  |  |
| Client technical owner |  |  |  |
| Operations owner |  |  |  |
| Security reviewer |  |  |  |

**Final status options:**

- `implementation green — live evidence pending`
- `hardware benchmark green — pool dry run pending`
- `connected but no shares`
- `shares rejected`
- `shares accepted`

No other status wording should be used in client reporting.
