# Chronos ONE iGPU — standalone v3.8

## Additive v3.7 enhancement

The completed original core is preserved: 52 original source files remain, 48 byte-identical; four facade/export/topology files are extended. Exact sequence authority still comes from the supplied lucas_engine. No source module is replaced with a new sequence engine.

New additions: exact Q(phi) paired and three-way family composition; jointly checked Binet/Lucas/norm/Pell-Cassini/Zeckendorf certificates; Apple MLX tensor and Core ML model bindings; native dense/ReLU ranking that preserves candidate ownership; concurrency-safe evidence appends; operator CLI, wheel/sdist metadata and publication checks. The separately named optional Apple binding requires its real macOS target. Publication files are ready; registry upload is not performed.

See FAMILY_COMPOSITION.md, APPLE_NEURAL_INTEGRATION.md and PUBLICATION.md for equations, execution boundaries and usage. The status map includes the new components and retains every previous incomplete interface explicitly.

## Architecture and ownership

ONE logical `chronos_igpu` exists independently of any physical GPU. `OneIGPU` owns the exact core, Golden Quantum runtime, storage, planner, fabric and receipts. `SuperGPU` and `InfinityGPU` are compatibility aliases over this same owner, not additional GPUs.

Native execution uses host CPU/NumPy/hashlib. Physical host-GPU execution is composed through an OpenCL adapter; the adapter executes multi-limb Lucas and SHA256d kernels and reports the bound device. Authenticated remote host agents can bind to that same fabric. Native independence and physical-overlay capability are distinct, both represented in the contract.

## Core pseudocode

```text
igpu := OneIGPU(mode=standalone, solve_first=true)
executor_inventory := igpu.compose()
plan := stream(base_items * exact_Lucas(scale_index), address_limit)
route := igpu.route(operation, scale_index)
admit(workload_id, tenant, budget, epoch, deadline, trust_class)

S1 := exact_pair_fold(candidates) + lossless_byte_fold + phi_phase_transform
S2 := job_epoch_bound_prime_gap_checkpoint(S1)
S3 := normalize_and_check_coherence(S1)
S4 := finite_Mandelbrot_boundary_rank(S3)
S5 := bounded_infinity_fold_interleave(S4)
S6 := Chronos_Hermitian_eigensolve(S5)
for candidate in S6:
    execute_exact_SHA256d_and_check_target(candidate)
if no verified result:
    F1 := GoldenQuantum_phi_feedback(actual_hash_oracle, remaining_budget)
    F2 := golden_stride_bijection(remaining_owned_nonces)
    F3 := remaining_owned_nonce_coverage
execute only admitted, disjoint owned work on the selected executor
host_recheck every device-reported successful candidate
receipt := bind(workload, logical_device, executor, capability, rung,
                partition, completed_work, elapsed_time, output_digest, trust)
seal_chain(receipt); optionally_HMAC_sign; retain_trusted_head
```

The Golden Quantum runtime is enabled by default. An explicitly disabled solve-first path exists only for a classical baseline. Quotas, epoch checks, deadlines, normalization, exact target checks and resource admission apply to both paths.

## Mathematical contracts

- Exact pair node stores `(sum=left+right, left)`; right is `sum-left`. Rationals preserve exact reconstruction. Selective restoration reads requested leaf pairs only; `scale()` operates directly on every folded pair.
- Exact Lucas, Fibonacci, Cassini, Zeckendorf and prime-address records retain integer authority. Binet/Pisot decimal projection carries an explicit residual and is not used as integer authority.
- `N_eff = min(base_items * L_n, address_limit - start)`. Declared ladder: 10, 12, 15, 18, 20, 31, 50, 76, 110. Scaling expands logical work windows and lane-aligned dispatch. Executed throughput is obtained from timed dispatches.
- Hamiltonian evolution is `exp(-i H t)` on bounded complex128 vectors with Hermitian validation. Golden phase feedback uses phi-derived phases, actual oracle masks and explicit oracle call counts.
- Eleven-dimensional norm is `sqrt(sum(phi**i * x_i**2))`; fold is `x/(1+sqrt(1+norm**2))`. Its inverse is `2*y/(1-norm(y)**2)`. Exact transport is separate: bit-preserving IEEE64 certificates encoded with Zeckendorf.
- The UCI registers physical constants as software kernel parameters; its h override binds normalized Hamiltonian evolution time. No receipt claims a change in the external physical constants.
- Large prime-gap indexes retain symbolic address expressions (including 2^100+) while resolved payloads are durable finite objects.

## Storage, folds and Docker

Default combined budget: 100,000,000,000 bytes. Example image reserve: 4,000,000,000 bytes, **a configured reserve rather than a measured build size**. A 10,000-bit basis witness occupies 1,250 payload bytes; packed records add 40 bytes before indexes, allocation, metadata and program traces. At 96 GB, the payload-only ceiling is 76.8 million, not a demonstrated usable capacity.

Witnesses are packed into content-addressed shards with a SQLite index and circuit-program trace. X/CNOT/SWAP basis-permutation execution records input, program and result addresses; replay independently verifies the program and result. Docker layers distribute the program; the volume holds cache shards. Representation dimension, folds/s, actual SHA256d/s and accepted pool shares are separate fields.

SCALE1–SCALE10 are tracked in `scaling_validation.py`: image budget; combined budget; native/overlay/pipeline availability; representation dimension; measured 10 EH/s floor; attestation; replay; trusted-head custody; observed genetic tuning; exact invariants. Unknown image size remains unknown. The supplied scaling derivation and its corrections remain verbatim under `docs/source_notes`; an earlier symbolic multiplier is not silently turned into executed hashes.

## Integration map

| Mechanism | Code | Status |
|---|---|---|
| Single independent iGPU and physical host composition | `src/chronos/igpu/{facade,fabric,overlay,remote}.py` | IMPLEMENTED |
| Exact Lucas/Pisot/Zeckendorf/Cassini/Binet datapath | `src/chronos/lucas*; src/chronos/igpu/kernels/lucas256.cl` | IMPLEMENTED |
| Lucas ladder and scaled workload windows | `src/chronos/igpu/scaled_plan.py` | IMPLEMENTED |
| Golden Quantum Hamiltonian/state/oracles/search | `src/chronos/golden_quantum/{quantum_state,oracles,search}.py` | IMPLEMENTED |
| S1–S6 solve-first and F1–F3 fallback | `src/chronos/igpu/golden_runtime.py` | IMPLEMENTED |
| Exact pair fold, selective unfold and native scale | `src/chronos/igpu/exact_fold.py` | IMPLEMENTED |
| 1–3D phase transforms and byte folding | `src/chronos/golden_quantum/data_folding.py` | IMPLEMENTED |
| Prime-gap persistence, Infinity Fold, large logical addresses | `src/chronos/golden_quantum/{memory,infinity_fold}.py; src/chronos/igpu/store.py` | IMPLEMENTED |
| Mandelbrot stabilization and coherence | `src/chronos/golden_quantum/{mandelbrot,coherence}.py` | IMPLEMENTED |
| UCI parameters and Hamiltonian binding | `src/chronos/golden_quantum/uci.py` | IMPLEMENTED |
| Tensor, MPS, original graphics/theory/academic math | `src/chronos/igpu/tensor_runtime.py; src/chronos/{engine,academic,theory}` | IMPLEMENTED |
| 11D phi geometry and exact transport certificates | `src/chronos/igpu/geometry11d.py` | IMPLEMENTED |
| QX command buffer, weak measurement and barrier/descriptor execution | `src/chronos/igpu/qx.py` | IMPLEMENTED |
| Certified MLA ingestion and five retrieval views | `src/chronos/igpu/contracts.py` | IMPLEMENTED |
| virtual_igpu_v1, tenants, admission, daemon/client | `src/chronos/igpu/{virtual_abi,service,remote}.py` | IMPLEMENTED |
| GPU SHA256d, unchanged target and host candidate verification | `src/chronos/igpu/kernels/sha256d.cl; src/chronos/igpu/fabric.py` | IMPLEMENTED |
| Swarm partition, vertical bounds, temporal pipeline | `src/chronos/igpu/control.py; src/chronos/igpu/overlay.py` | IMPLEMENTED |
| Guardian, genetic optimization and floor evaluator | `src/chronos/igpu/{control,scaling_validation}.py` | IMPLEMENTED |
| 100GB witness cache, attestation and replay | `src/chronos/igpu/witness_cache.py` | IMPLEMENTED |
| Hash-chain custody and optional HMAC evidence | `src/chronos/igpu/golden_runtime.py` | IMPLEMENTED |
| Paradigm thesis, schedule conformance and chaos | `src/chronos/paradigm` | IMPLEMENTED |
| Baseline and folded-witness benchmark | `benchmarks/run_standalone_elevation.py` | IMPLEMENTED |
| Production packaging and shutdown | `Dockerfile; compose.yaml; src/chronos/igpu/service.py` | IMPLEMENTED_TARGET_VALIDATION_PENDING |
| Native vendor/ASIC/MMIO/RTL execution and real sensor stack | `src/chronos/igpu/fabric.py` | UNBOUND_TARGET_INTERFACES |
| Repository-specific Chronus-1 binary ISA, H4/600-cell fabric and TT/MPO extensions | `docs/SOURCE_MANIFEST.json` | NOT_IMPLEMENTED_IN_THIS_RELEASE |
| Pool network job/acknowledgement transport | `src/chronos/golden_quantum/mining.py` | NOT_IMPLEMENTED_IN_THIS_RELEASE |

## Actual execution and remaining target checks

The release includes software tests, native C++ conformance of the OpenCL source, the public Bitcoin genesis-vector benchmark, an authenticated loopback service/client test, and the executable paradigm report. See `validation/RELEASE_REPORT.json`, JUnit XML and benchmark JSON for the executed results.

Physical OpenCL dispatch was not executed on this host: no compatible platform was available. Docker build, TLS container deployment, vendor/ASIC/MMIO/RTL binding, pool transport, hardware-root attestation and power sensors were not validated here. The explicit nonimplemented entries in the map are retained rather than called complete. This ZIP is not the original repository binary ISA/600-cell/TT-MPO implementation.

The baseline native source, graphics and academic/theory code are retained. Original source APIs already in the ZIP remain available. New formulas are explicit standalone implementations from the reviewed specifications; they are not represented as byte-for-byte canonical repository imports.

## Usage and verification

```bash
python -m pip install .
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m chronos.paradigm
PYTHONPATH=src python benchmarks/run_standalone_elevation.py --size 256 --runs 5
```

```python
from chronos import OneIGPU
from chronos.golden_quantum import NonceLease
with OneIGPU(db_path="prime.db") as gpu:
    exact = gpu.dispatch([10, 12, 15, 18, 20]); exact.verify()
    plan = gpu.scaled_plan(base_items=256, scale_index=15)
    folded = gpu.fold_exact([1, 2, 3, 4])
    assert folded.unfold_partial([0, 3]) == (1, 4)
    outcome = gpu.mine(bytes(76), 0, NonceLease(0, 256), max_evaluations=256)
    inventory = gpu.compose()

# Explicit physical host composition; fail closed if the device is unavailable.
# Requires a configured host OpenCL ICD and pyopencl (package extra [opencl]).
with OneIGPU(mode="host_gpu_overlay", require_accelerator=True) as gpu:
    result = gpu.dispatch([15]); result.verify()
```

### Authenticated service

Provide `CHRONOS_SERVICE_TOKEN` privately (minimum 32 characters). No token is embedded. Local-only execution:

```bash
python -m chronos.igpu.service --host 127.0.0.1 --db-path ./state/prime.db
```

`compose.yaml` requires `CHRONOS_TLS_DIR` with `cert.pem` and `key.pem`, readable by UID 10001; the certificate must cover the healthcheck host `127.0.0.1`. It also requires the private token. Non-loopback binds reject absent TLS. The included policy TOML is a constructor/CLI configuration reference, not an automatically loaded config file. Before deployment measure image size, set the cache image reserve to that measured figure, check certificates, validate mounted storage permissions and run target conformance. Pin the Python base image by digest in your deployment.

## Provenance and single record

`SOURCE_MANIFEST.json` lists all reviewed sources and how each was used. `source_notes/MANIFEST.json` hashes every unedited supplied note. The consolidated Notion record mirrors this implementation, pseudocode, map, validation and remaining target checks. No GitHub/repository retrieval is required to install or run this standalone package.

## ASIC-like mining extension

See ASIC_MINING.md and PUBLIC_TECHNIQUES.json. The main solve-first path can bind a prepared/fused native executor. Hardware driver interfaces remain explicit; physical ASIC execution is not inferred.
