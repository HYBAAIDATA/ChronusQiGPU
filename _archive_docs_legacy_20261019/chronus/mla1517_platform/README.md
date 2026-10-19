# PYTHIA production mining — Phase 1

Python is the canonical mining control plane. The frontend is an operator UI and does not hash, construct Stratum jobs, validate targets, or submit shares. The exact runtime path is documented in `PYTHIA_API_CONTRACT.md` and `RUNBOOK.md`.

## Phase 1 status

This project includes the complete source-tree scaffold, Python 3.11+ project metadata, release manifest, packaging gate, and explicit physical-deployment boundaries. No GPU, FPGA, iGPU, pool acceptance, or production hashrate is claimed until physically measured.

The scaffold helper is `build_pythia_env.sh`; it never overwrites existing files.

---

# MLA1517 polyglot build — v0.1

This is the first bridge build, using only tested mathematical primitives.

- `python/` — golden reference and hypothesis suite
- `cpp/` — CPU backend/conformance kernel; ready for CUDA/HIP kernel replacement
- `rust/` — production runtime/PRIME-DB scaffold; requires Rust toolchain
- `contracts/` — stable C ABI boundary
- `results/` — conformance outputs

The C++ backend implements Fibonacci, Lucas, Cassini, and Zeckendorf conformance. The Rust crate mirrors the promoted exact primitives. No Lucas/Pisot quantum speedup or prime-capacity claim is implemented.

## Extended algebra families

`python/extended_algebra.py` adds the Plastic, Supergolden, and Tribonacci roots and their recurrence families. The exact polynomial identities and recurrence definitions pass. Domain claims are evidence-gated:

- the supplied Plastic identity `rho^5 = rho^2 + 1` is refuted; the correct identity is `rho^5 = rho^2 + rho + 1`;
- spectral gap is reported as a graph connectivity/stability metric, not drug-binding energy;
- metallic ratios do not prove zero grid harmonic overlap;
- the packing, forecasting, docking, and turbine claims remain experiments, not production capabilities.

## Docker-native mathematical engine

`Dockerfile.native` builds the C++ execution transport for an independent mathematical container.

- `/dev/shm`/POSIX shared memory carries the M32 transport region.
- A sequence-numbered lock-free ring passes fixed 64-byte hot descriptors.
- The descriptor carries D1-D11 plus a route/control slot.
- The 32-way nonce/work partition is deterministic and non-overlapping.
- D1 supports deterministic ghost payloads for idle geometry benchmarks.
- Aethel retains exact/cold state, lineage, checkpoints, and proofs.
- Python remains the reference/control plane; C++ owns the high-throughput transport path.
- `MLA1517_WORKLOAD=structured_mining` selects the progressive 12-node execution / 20-node vault profile.
- `MLA1517_WORKLOAD=simt_warp` selects the 32-lane warp-vote and UMA routing contract.

Build and run the local conformance engine:

```text
make shm-test
```

The cross-process test moves 100,003 descriptors through the shared ring and verifies all 32 partition assignments.

Run the progressive mining profile locally:

```text
make progressive-mining-test
```

The mining profile generates nonces with `partition_id + 32 * step`, applies the cheap D2/D6 structured sieve, computes D3-D5 only for survivors, verifies D10 Cassini, and writes complete 11D states only to the sparse vault.

The SIMT conformance profile tests 32-lane ballot voting, branch-free lane compaction, 12 execution-node / 20 memory-node mapping, and UMA winner routing.

## Host-to-silicon bridge and Stratum coordinator

The host integration is implemented in three layers:

```text
PCIe/UIO MMIO + Aethel UMA
        ↓
host/libmla1517_mmio.so
        ↓ ctypes
chronus/mla1517/hardware.py
        ↓
python/manifold_pool_coordinator.py
```

Build and run the driver/coordinator tests:

```sh
make host-driver-test
```

The C ABI writes the difficulty mask and base step, starts/stops the engine,
and polls the 20 Aethel vault-node sequence slots. It returns a torn-read-safe
64-byte state only after the producer sequence is stable. `MLA1517_MMIO_DEVICE`
must be supplied explicitly; the driver never opens `/dev/mem` implicitly.
A regular file is supported for deterministic integration tests.

Set `MLA1517_PRIME_DB_RING` to enable the native dual-output path. The single
MMIO owner then publishes each stable state to both Path A (Python/Stratum)
and Path B (the C11 `/dev/shm` SPSC ring). `Dockerfile.primedb` runs the
consumer that commits states into `vertex_00.db` through `vertex_19.db`.

The deployment is orchestrated by `docker-compose.yml`:

```sh
export MLA1517_STRATUM_USER='account.worker'
export MLA1517_PRIME_DB_HOST_DIR=/mnt/nvme0n1/primedb_data
docker compose up --build
```

The compose file shares the coordinator IPC namespace with PRIME-DB. It does
not treat mmap visibility as instant NVMe durability: `MLA1517_PRIME_DB_SYNC_EVERY`
controls explicit `msync` and `fsync` barriers. Provision the host data
directory with suitable capacity and permissions before deployment.

The optional `telemetry` compose service maps the dedicated
`/dev/shm/mla1517_telemetry` block and exposes `/ws/topology`. It is
observational only, uses a read-only PRIME-DB bind mount, and is not on the
compute or commit path.

`Dockerfile.salamander` provides the gated supervisory plane. Salamander
defaults to observe-only; `MLA1517_SALAMANDER_ENABLE=1` is required before it
can quarantine a lane or update the polyhedral-mask CSR. The sidecar has no
Docker socket and does not rewrite container CPU affinity at runtime. Any
automatic action is therefore limited to the declared MMIO ABI and remains
auditable.

When `MLA1517_EUCLIDCORE_ENABLE=1` is also set, Salamander may use the
deterministic EuclidCore measured policy over the four declared choices. It
selects only from observed empirical rewards; it performs no random sampling
and fabricates no outcome. The default remains disabled.

The coordinator defaults to Braiins with ViaBTC failover:

```sh
docker build -f Dockerfile.headless_miner -t chronus/mla1517/headless-miner .
docker run --rm \
  --device=/dev/uio0 \
  -e MLA1517_MMIO_DEVICE=/dev/uio0 \
  -e MLA1517_STRATUM_USER='worker' \
  -e MLA1517_STRATUM_PASSWORD='x' \
  chronus/mla1517/headless-miner
```

Pool submission is disabled unless `--submit` is explicitly supplied. The
`format_mla1517_to_stratum_share(...)` implements the requested legacy
12-field candidate serializer, while `format_mla1517_hot_state_candidate(...)`
decodes the actual packed `<Q14I` MLA1517 v1 descriptor. Both produce only the
standard JSON shape. They do not prove the pool's own PoW target. The
production coordinator therefore refuses arbitrary raw states and requires a
negotiated MLA1517 pool adapter to provide exact `stratum_params` before
public-pool submission is enabled.

### Corrected Salamander control contract

The production reference now includes a 20 Hz Salamander control loop with a
versioned seqlock telemetry snapshot, leaky-bucket fault decay and hysteresis,
ACK-gated staged CSR commits, a 24-lane minimum floor, nonce watermark/orphan
accounting, 60-second lane probation with three readmission passes, and
20-second Michie accept/revert mask trials. Failover is dampened with a
30-second cooldown and 10-second secondary dwell. EuclidCore remains an
explicit optional policy (`MLA1517_SALAMANDER_POLICY=euclid`); the default
supervisor mode is observe-only and no controller runs without the explicit
`MLA1517_SALAMANDER_ENABLE=1` flag.

### Agentic mining workflow

`python/agentic_mining.py` implements the five-intelligence cortex from
measured data only: deterministic geometry, exact M32 topology, measured
forward transitions, commissioned causal effects, and observed-support
counterfactual evaluation. It performs no generated rollouts, no probabilistic
policy selection, and no implicit MMIO write. Unsupported actions are rejected
and Salamander retains veto authority before any optional ACK-gated actuator.

### Session requirements audit

`REQUIREMENTS_AUDIT.md` and `scripts/session_requirements_audit.py` map the
expressed and implied session requirements to concrete math, RTL, C11, C++,
Python, Docker, telemetry, storage, and control artifacts. The audit separates
captured requirements from physical boundaries that cannot be invented: FPGA/
ASIC bring-up, external pool validity, 10 EH/s or 20,000-GPU equivalence, and
unlimited capacity remain measured deployment claims.

## Canonical exact quantum execution

All exact quantum workloads enter through `chronus/mla1517/accelerator.py` and
`chronus/mla1517/quantum.py`. Amplitudes are elements of
`Q(sqrt(2)) + i Q(sqrt(2))`, represented by rational coordinates; Hadamard,
Pauli, S/T, tensor-product, CNOT, and exact normalization operations therefore
perform no floating-point arithmetic. State-vector allocation is bounded by an
explicit amplitude limit and raises `MemoryError` rather than degrading.

The canonical hardware selector does not fall back from a requested
`mla1517_chronus` quantum backend. It raises `AcceleratorUnavailable` until an
exact-arithmetic device kernel is installed. Arbitrary Hamiltonian matrix
exponentials are likewise rejected; the current exact evolution contract is
limited to declared Pauli-Z quarter-turns. The existing CPU reference backend
is retained only for the non-quantum MLA1517 conformance/runtime path.

## Strict Lucas-Pisot GPU ladder

The declared ladder is fixed and exact: `10, 12, 15, 18, 20, 31, 50, 76`.
`chronus/mla1517/scaling.py` defines the ladder and exact Fibonacci, Lucas, and
Padovan/Pisot results. `kernels/mla1517_lucas_pisot_scale.cl` is the OpenCL
kernel that receives the scale vector and returns exact uint64 recurrence
results for these bounded rungs. `OpenCLLadderExecutor` verifies the device
output against the exact reference and never falls back to CPU execution.

Run sovereign hardware CI with:

```sh
MLA1517_STRICT_HARDWARE_CI=1 MLA1517_GPU_BACKEND=opencl make test
```

That mode fails immediately without a real OpenCL device, exact ladder output,
and a PRIME-DB invariant round trip. The ordinary reference suite remains
separate and does not claim GPU activity.

## Live Lucas-Pisot scaling measurement

`docker-compose.gpu.yml` and `Dockerfile.lucas-scaling` define the explicit GPU deployment path for the v3.4 live measurement harness. The service requests `capabilities: [gpu]`, maps `/dev/dri`, and requires the host OpenCL ICD vendor directory. There is no CPU fallback.

Run only with an approved pool adapter and explicit live authorization:

```sh
export MLA1517_ENABLE_LIVE_SUBMIT=1
export MLA1517_LIVE_APPROVAL_ID='approved-run-id'
export MLA1517_STRATUM_USER='account.worker'
export MLA1517_STRATUM_PASSWORD='pool-password'
export MLA1517_STRATUM_ADAPTER='adapter_module:factory'
export MLA1517_ADAPTER_DIR=/opt/mla1517/adapters
export MLA1517_OPENCL_VENDOR_DIR=/etc/OpenCL/vendors

docker compose -f docker-compose.gpu.yml up --build --abort-on-container-exit
```

`scripts/measure_lucas_scaling.py` dispatches each declared rung on a real OpenCL device and submits only candidates constructed by the negotiated adapter from the current Stratum job. It refuses to invent a nonce, job, timestamp, target, or acceptance response. Effective hashrate is calculated only from pool-accepted shares and the pool-announced share difficulty/target. If any rung produces zero accepted shares, the run stops and fails closed. The Lucas/Pisot result is not itself a Bitcoin proof; the adapter must construct a consensus-valid pool submission.
