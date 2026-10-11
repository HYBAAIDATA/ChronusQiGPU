# Chronus Virtual iGPU — Implementation Matrix

**Prepared against:** 2 October 2026 review & implementation prompt  
**Repository:** PYTHIPhiMiner (this workspace)  
**Continuation:** elevated ABI/runtime/adapters/evidence/memory aligned and green against software gates.

**BLUF:** Software runtime, versioned ABI (`virtual_igpu_v1`), standalone software adapter, optional OpenCL/Intel probe, fail-closed unavailable backends, content-addressed memory, runtime-signed receipts, miner bridge, sidecar wire protocol, and acceptance tests are **implemented in this repo** and **software-validated**. UnifiedEnterprise canonical ownership, multi-vendor physical kernels, Azure/GCP live runs, pool ack, and hardware-rooted attestation remain **external / PENDING gates** — not fabricated.

## Source resolution

| Repo | Status in this workspace |
| --- | --- |
| QuantumPhiEnterprise/PYTHIPhiMiner | **Active** — Chronus Virtual iGPU under `chronus/virtual_igpu/` |
| UnifiedEnterprise | **Not present / not readable** — inventory remains audit hypothesis until that repo is attached |
| Mining PRs #94 / #95 | Ancestors of HEAD; useful OpenCL/evidence paths preserved in `chronus/tensor_compute.py`, `bench/chronus_igpu_evidence.py` |

```bash
git rev-parse HEAD   # record at release
# PR #94 merge: 0ef9f8eafcd131376b564ac3028e830c574779ed
# PR #95 merge: 1ba0794fb40e4117601b4b1d5cecb87bf44a2569  (ancestor of HEAD: yes)
```

## Architecture planes

| Plane | Owner (this repo) | Notes |
| --- | --- | --- |
| Product identity | Chronus Virtual iGPU | Independent of any one physical GPU |
| Maths graphics | `chronus/v33` | Separate plane (Chronos GPU) |
| Control / runtime | `chronus/virtual_igpu/runtime.py` | attach → probe → negotiate → ready → submit/poll/cancel → drain |
| Workload ABI | `chronus/virtual_igpu/abi.py` | DeliveryMode, ExecutionPolicy, TrustClass, PortablePackage, ExecutionReceipt |
| Memory / custody | `chronus/virtual_igpu/memory.py` | Content-addressed objects + tenant isolation; Aethel fold when present |
| Operators | `chronus/virtual_igpu/operators.py` + adapter execute paths | fold/unfold, tensor, CGEMV, φ/Lucas/Pisot, SHA256d |
| Adapters | `chronus/virtual_igpu/adapters.py` | Software always; OpenCL UHD optional; CUDA/ROCm/oneAPI/Metal/OpenCL-generic **typed unavailable** |
| Evidence | `chronus/virtual_igpu/evidence.py` | Ledger + `validate_receipt` / `validate_evidence_artifact` |
| Client | `chronus/virtual_igpu/client.py` | embedded / local_sidecar / remote_service — **no silent local fallback** |
| Wire service | `chronus/virtual_igpu/wire.py` + `__main__.py` | stdlib HTTP JSON sidecar |
| Measurement | `chronus/measurement/` | Eleven-layer measurement |
| Physical evidence CLI | `bench/chronus_igpu_evidence.py` | Target-host only |
| Miner integration | `chronus/mining_bridge.py` | `submit_via_virtual_igpu` |
| Tensor OpenCL | `chronus/tensor_compute.py` | Declared output-shape validation before allocate/dispatch |

## Capability → implementation → caller → test → evidence gate

| Capability | Implementation | Production caller | Test | Evidence gate |
| --- | --- | --- | --- | --- |
| Standalone software execution | `CPUEmulatorAdapter` + `RuntimeDaemon` | `ChronusClient(embedded)` | `tests/test_virtual_igpu.py`, `tests/test_chronus_vigpu_acceptance.py` | **Software-validated** |
| Policy fail-closed required device | `RuntimeDaemon._select_adapter` | Workload `execution_policy` / `required_*` | acceptance | **Software-validated** |
| Preferred accelerator + reason | selection + `route_reason` on result | Client | unit + acceptance | **Software-validated** |
| Shape validation pre-dispatch | `abi.validate_declared_output_shape` + tensor_compute | OpenCL tensor path | acceptance | **Software-validated** |
| Lossless fold/unfold | Aethel Zeckendorf serialize when present; length-prefix fallback | runtime | unit roundtrip | **Software-validated** |
| Content-addressed memory + tenant isolation | `VirtualMemoryPlane` | runtime submit | unit | **Software-validated** |
| Quotas / admission | `Quota` + in-flight caps | runtime | unit | **Software-validated** |
| Idempotency key conflict | runtime package hash check | client | unit | **Software-validated** |
| Runtime-signed receipt | `ExecutionReceipt` + ledger + evidence file | runtime | acceptance `validate_receipt` | **Software-validated** |
| Content-hash integrity file | `store_root/evidence/<sha256>.json` | runtime | unit | **Software-validated** |
| Hardware-rooted attestation | — | — | negative tests raise / unavailable | **PENDING** (no mechanism) |
| Intel UHD OpenCL | `OpenCLUhdAdapter` probe + tensor runtime | evidence CLI | host-specific | **Device-bound PENDING** without target host |
| CUDA/ROCm/oneAPI/Metal full | `UnavailableAdapter` | — | typed unavailable | **PENDING** SDKs/kernels |
| Azure/GCP deploy | deployment layer only (`deploy/azure/…`); not a GPU capability | — | package validate | **PENDING** credentials/run |
| Pool acknowledgement | mining stack | — | protocol unit only | **PENDING** live pool |
| UnifiedEnterprise canonical package | external | installable client TBD | — | **PENDING** UE repo |
| Delivery-mode isolation | client embedded vs remote | ChronusClient | acceptance remote no-fallback | **Software-validated** |

## Trust model (explicit)

| Class | Meaning | When claimed |
| --- | --- | --- |
| `runtime_signed` | Content-addressed / optional HMAC chain | Default software path |
| `device_observed` | Adapter completed device-bound events | Physical adapter with observations |
| `hardware_rooted` | Verified attestation mechanism | **Never** without real mechanism |
| `unavailable` | Missing observation | Sensors/attestation absent |

CPU reference verification proves **output correctness**, not accelerator execution. Unkeyed content hash **cannot** authenticate adversarial edit+rehash (warned in validator).

## How to run

```bash
# Software gates
python -m pytest tests/test_virtual_igpu.py tests/test_chronus_vigpu_acceptance.py -q

# Embedded client
python -c "from chronus.virtual_igpu import ChronusClient, Workload, WorkloadKind; \
c=ChronusClient(); print(c.submit(Workload(id='1', kind=WorkloadKind.LUCAS_TRANSFORM, input={'n':10})).output)"

# Sidecar
python -m chronus.virtual_igpu --host 127.0.0.1 --port 8765

# Physical evidence (target host only)
python -m bench.chronus_igpu_evidence --size 512 --iterations 20 --stress-seconds 300 --sha256d-count 1048576
```

## Packaging note

This monorepo consumes Chronus in-tree. A separately installable `chronus-virtual-igpu` client package for UnifiedEnterprise is **PENDING** the UE repo + publish pipeline. No `sys.path` hacks are required when the monorepo root is on `PYTHONPATH` / installed editable.

## Claim boundaries

- Classical-silicon software execution is **real computation**, not a toy mock — substrate recorded as software.
- No quantum speedup, cryo hardware, or pool-accepted share claims from Virtual iGPU alone.
- SHA-256d remains the mining validity oracle; Chronus advice cannot mutate targets/coverage.
- Production-readiness is scoped to **software-validated embedded mode** on hosts that pass the software suite. Physical/cloud/pool remain external gates.
