# PYTHIA production mining runbook

## Scope

PYTHIA is the mining product. Enterprise code is not part of this runtime.
The Python/C/OpenCL path under `mla1517_platform_v3.4` is canonical. The React
application is an operator UI and the Python control API is the only UI backend.

## Preflight

1. Install Python 3.12+ and the package dependencies from `pyproject.toml`.
2. Run `python scripts/assert_python_canonical.py` from the repository root.
3. Run `make test`.
4. Run `make release` only after all required native toolchains are available.
5. Treat every `NOT_RUN` result as an explicit deployment gap.
6. Do not set pool credentials in source, `.env.example`, manifests, or ZIPs.

## Hardware policy

- `MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl make test` requires a
  real OpenCL device and fails closed when none is present.
- A CPU reference run is labelled `measured_cpu_reference`, never GPU/iGPU.
- `measured_hardware` requires a discovered device, the actual hardware backend,
  observed hash count, and positive wall-clock elapsed time.
- `unavailable` and `rejected` are valid operational states; they are not
  silently converted to degraded success.

## Live Stratum policy

1. Configure a real pool endpoint and worker credentials outside the repository.
2. Start with submission disabled.
3. Confirm `mining.subscribe` returns and retain `extranonce1` and
   `extranonce2_size`.
4. Confirm a live nine-field `mining.notify` job is received.
5. Confirm `mining.set_difficulty` or `mining.set_target` is negotiated.
6. Candidates must be built from that live job, including coinbase, Merkle root,
   header, and nonce. The proof adapter independently recomputes SHA256d and
   compares the digest to the negotiated target.
7. Only then may the explicit submission gate be enabled. A true pool response
   is the only accepted-share signal.
8. Stale jobs, malformed fields, invalid targets, invalid Cassini seals, and
   target failures must stop submission rather than being retried as successes.

## Release artifacts

`make release` runs the existing regression release gate and then
`scripts/package_release.py`. The packager excludes `.git`, caches, virtual
Environments, build outputs, logs, results, and secret-looking files. It writes:

- `results/pythia-production-mining-<UTC>.zip`
- the matching `.sha256` checksum;
- `results/release_manifest.json`.

Packaging alone does not certify production readiness. The manifest keeps
`production_ready: false` until physical accelerator execution, live pool
acceptance, and production hashrate have actually been measured.

## Shutdown and incident handling

Stop the coordinator, preserve the release-gate JSON and telemetry records, and
quarantine malformed PRIME-DB or shared-memory records. Never repair a failed
proof record by editing its target, nonce, job id, or acceptance field.
