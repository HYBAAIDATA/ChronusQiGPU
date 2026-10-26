# Lucas Matrix System — Use Cases and Unlocks

## Executive summary

The Lucas Matrix System is the exact mathematical and provenance layer for
scaling the PYTHIA benchmark/control plane. It converts a declared domain
configuration into:

1. exact Lucas/Fibonacci recurrence values;
2. exact rational capacity transformations;
3. explicit cache/page-aligned capacities;
4. deterministic composite-domain identities;
5. a canonical matrix manifest;
6. a workload fingerprint and composite fingerprint;
7. independently verifiable benchmark evidence.

It is not a magic multiplier attached to a result. Every capacity, schedule,
state dimension, and reported measurement is derived from the selected domain
power and remains auditable.

## System contract

### Exact arithmetic

The primary path uses only arbitrary-precision integers and exact rational
multipliers:

```text
L0 = 2
L1 = 1
Ln = L(n-1) + L(n-2)

L(a+b) = (La·Lb + 5·Fa·Fb) / 2
L(a-b) = (-1)^b·(La·Lb - 5·Fa·Fb) / 2
```

Fast doubling computes `(Ln, Fn)` in `O(log n)` recurrence steps.

### Domain-specific matrix

The system intentionally does not force one power on every subsystem:

| Domain | Default power | Exact Lucas value | Transformation |
|---|---:|---:|---|
| Base pattern | 7 | 29 | baseline structural pattern |
| Memory | 7 | 29 | 64-byte aligned capacity |
| Network protocol | 11 | 199 | protocol budget |
| Search | 10 | 123 | search-space and budget |
| Database indexing | 13 | 521 | index capacity |
| Tensor | 12 | 322 | tensor width/depth budget |
| Virtual quantum | 15 | 1364 | exact mathematical state dimension |
| Coherence | 18 | 5778 | coherence budget |
| Verification | 20 | 15127 | verification budget |
| Hardware | 31 | 3010349 | mathematical hardware capacity metadata |
| Hardware extended | 50 | 28143753123 | extended capacity metadata |
| Pisot convergence | 76 | 7639424778862807 | convergence-domain scale |
| Schedule | 76 | 7639424778862807 | deterministic schedule capacity |
| I/O throughput | 21 | 24476 | 4096-byte aligned capacity |

The benchmark-facing matrix may select a different complete assignment through
`configs/lucas_scale_matrix.example.json`. The assignment is serialized into
the manifest and cannot be changed without changing the workload fingerprint.

### Capacity transformation

For domain `d`:

```text
raw_d       = floor(L_power(d) × multiplier_d)
capacity_d  = align_up(raw_d, alignment_bytes_d)
```

The implementation uses exact `Fraction` values for multipliers. Alignment is
explicit and upward, preventing cache-line, page, or buffer-boundary drift.

## What this unlocks

### 1. Reproducible benchmark scaling

Run the same workload at multiple matrix configurations and compare:

- wall-clock execution time;
- executed hash/oracle count;
- normalized cost per executed hash;
- memory and tensor dimensions;
- schedule coverage;
- verification status;
- matrix and composite fingerprints.

This unlocks a real scaling curve rather than a projection. Each point is
bound to a workload and matrix identity.

### 2. iGPU capacity planning

The `hardware`, `hardware_extended`, memory, and I/O domains provide exact
planning metadata for:

- lane and work-group budgets;
- memory allocation envelopes;
- aligned transfer buffers;
- queue and dispatch budgets;
- multi-rung benchmark plans.

The metadata is not a measured hashrate. A physical iGPU run must still supply
device identity, kernel execution, elapsed time, hashes, errors, and thermal
telemetry.

### 3. Tensor workload sizing

The tensor domain independently scales width and depth. This unlocks
repeatable allocation plans for:

- tensor-network contraction windows;
- matrix/tensor batch dimensions;
- storage and checkpoint sizing;
- deterministic comparison of tensor configurations.

The matrix does not claim that a larger tensor is automatically faster. It
makes the chosen tensor capacity explicit and reproducible.

### 4. Virtual quantum state planning

The virtual-quantum domain derives an exact integer qubit budget and
`2^q` mathematical state dimension. This unlocks:

- state-space capacity planning;
- exact circuit/state benchmark parameters;
- deterministic memory feasibility checks;
- separation of mathematical dimension from physical QPU evidence.

`quantum_model` results remain modeled unless a real quantum backend supplies
an execution trace. Classical simulation is not relabeled as quantum hardware.

### 5. Search and PQSC scheduling

The search and schedule domains independently control:

- search-space capacity;
- deterministic Lucas/Fibonacci nonce ordering;
- schedule stride selection;
- verification budget;
- complete and disjoint nonce coverage.

The PQSC path uses the same workload and consensus predicate as the classical
path. It changes the declared structural schedule, not the cryptographic
truth predicate.

### 6. Memory and I/O correctness

The memory and I/O domains make alignment a first-class invariant:

- cache-line alignment for memory allocations;
- page alignment for I/O buffers;
- deterministic upward rounding;
- manifest-visible boundary conditions;
- tamper detection if alignment changes after workload creation.

This closes the class of bugs where the recurrence value is correct but the
allocated buffer crosses an architectural boundary incorrectly.

### 7. Cryptographic sharding and verification

The matrix engine supports dedicated verification and sharding domains. This
unlocks:

- deterministic partition sizing;
- independently recomputable shard capacities;
- composite-domain composition such as `L_search+L_memory`;
- tamper-evident workload identity;
- independent result verification without trusting the benchmark runner.

### 8. Multi-host and multi-role deployment planning

Different hosts or services can receive different matrix profiles while
remaining comparable because each profile is fingerprinted. Example roles:

- Host A: hardware/iGPU-heavy profile;
- Host B: memory and verification-heavy profile;
- tensor worker: tensor/virtual-quantum-heavy profile;
- audit worker: verification/coherence-heavy profile.

The system can compare results only when the workload fingerprint, matrix
fingerprint, and composite fingerprint are explicitly recorded.

### 9. Provenance and client handover

Every artifact carries three independent evidence layers:

1. **Run evidence:** candidate/digest re-derived from the workload.
2. **Artifact evidence:** canonical JSON SHA-256 seal.
3. **System evidence:** workload + matrix + schema composite fingerprint.

This unlocks reproducible handover, offline verification, CI tamper tests, and
post-run audit without trusting the process that generated the artifact.

## Operating workflow

### Generate an artifact

```bash
python scripts/cli.py \
  --workload-id client-demo-001 \
  --seed-hex 1111111111111111111111111111111111111111111111111111111111111111 \
  --nonce-bits 12 \
  --target-bytes 1 \
  --scale-matrix-json configs/lucas_scale_matrix.example.json \
  --trials 3 \
  --output artifacts/client-demo-001.json
```

### Verify without rerunning the benchmark

```bash
python scripts/cli.py \
  --verify-only artifacts/client-demo-001.json
```

Expected result:

```text
artifact_verified = True
```

### Run the formal test battery

```bash
python -m pytest -q \
  tests/test_lucas_core.py \
  tests/test_lucas_scale_matrix.py \
  tests/test_benchmark_harness.py \
  tests/test_integration.py
```

## Evidence states

| State | Meaning |
|---|---|
| `verified_artifact` | Mathematical result, matrix, composite seal, and serialized runs verify |
| `quantum_model_unproven` | Mathematical model exists; no physical QPU evidence |
| `hardware_capacity_parameterized` | Hardware scale is present as exact metadata; no physical throughput claim |
| `kernel_benchmark_measured` | Physical kernel execution produced measured hashes and telemetry |
| `pool_share_accepted` | External pool confirmed a submitted share |

Only the last two require physical-host or external-system evidence. The
Lucas matrix alone never upgrades a claim to measured hardware performance or
accepted mining.

## Enterprise applications

- capacity planning for heterogeneous compute roles;
- deterministic benchmark and regression gates;
- aligned memory/I/O allocation;
- reproducible tensor and state-space experiments;
- cryptographic shard planning;
- multi-host workload partitioning;
- offline audit and client handover;
- CI enforcement against matrix drift and artifact tampering;
- research comparison across classical, structural, and modeled quantum paths.

## Boundary of the system

The system provides exact parameterization, structural composition, execution
measurement, and provenance. It does not by itself prove a new complexity
class, create physical energy, invert SHA-256, or establish a quantum hardware
speedup. Those claims require separate mathematical proofs or physical
measurements and must be attached to the relevant artifact.
