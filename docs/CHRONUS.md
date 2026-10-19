# Chronus architecture

Chronus is HYBA's canonical execution architecture and iGPU/compute-fabric plane. It is not CUDA, NVIDIA, OpenCL, Metal, ROCm, Vulkan, Intel, AMD, Apple, or any other vendor/runtime model.

Turing remains the independent mathematical/VQC computation substrate. PYTHIA may submit mining work to Chronus. Chronus owns execution semantics, device/fleet routing, resident state, memory, kernels, telemetry, topology, attestation and measured execution evidence.

## Canonical native authority

The native architecture authority is the repository's **Chronus-1** stack:

- `isa/chronus1.md` — normative Chronus-1 ISA;
- `abi/chronus1-abi.md` — normative kernel ABI;
- `.chronus` executable/container format;
- assembler/compiler/emulator and conformance corpus;
- deterministic trap, scheduling, memory and reconvergence semantics;
- Chronus topology, tensor, memory and fleet capabilities.

Chronus-1 is the architectural reference point. Vendor APIs do not define Chronus semantics and must not be used as the vocabulary for what a Chronus compute unit, lane, memory system, kernel, fleet or capability is.

## Foreign compatibility adapters

OpenCL, CUDA, Metal, ROCm, Vulkan and CPU/reference surfaces may exist only as **explicit adapters or evidence/reference paths** beneath the Chronus boundary where implemented. They are not Chronus-native architecture.

```text
PYTHIA / Turing / other authorised workloads
                |
                v
        Chronus-1 ISA + ABI
                |
        Chronus execution fabric
     topology / tensor / memory / fleet
                |
      +---------+---------+
      |                   |
Chronus implementation   optional foreign adapters
/native fleet            OpenCL/CUDA/Metal/etc.
      |                   |
      +---------+---------+
                |
        measured execution evidence
```

`chronus/engine.py` currently contains an OpenCL execution adapter retained for workloads that explicitly use that transport. Its presence must never be interpreted as making OpenCL the Chronus architecture. CUDA and Metal surfaces are likewise compatibility paths only. NVIDIA is a vendor, CUDA is that vendor's programming/runtime platform, and neither is a model for Chronus.

No compatibility adapter may silently become the canonical scheduler, memory model, topology definition, ISA, ABI or capability authority. No fallback may relabel CPU/OpenCL/CUDA/Metal execution as native Chronus execution.

## 600-way mining topology

The canonical mining search fabric is the H4/600-cell construction already present under `chronus/h4_600.py` and `chronus/cell600_bind.py`:

- 120 geometric 600-cell vertices;
- 600 tetrahedral cells;
- the 600 cell normals lifted/folded into the 11-dimensional Chronus search space;
- 600 logical search vertices/work shards over the nonce lease.

This supersedes treating the earlier 32-face dodecahedron/icosahedron overlay as the final production mining topology. The 32-face construction remains lineage/input geometry where required; it is not a competing canonical miner.

For mining, the required composition is:

```text
Stratum work
  -> PYTHIA planning/intelligence
  -> 600 logical 11D search vertices
  -> disjoint nonce leases
  -> Chronus execution fabric / fleet
  -> SHA256d local verification
  -> stale/epoch validation
  -> mining.submit
  -> literal pool acknowledgement
```

A logical vertex may be backed by one or many Chronus workers. Fleet scaling must preserve unique/disjoint work ownership, gap-free coverage, stale cancellation and evidence for reassignment.

## Performance and fleet truth

The engineering target may be the **governed 1e19 H/s hashrate ceiling (aggregate)**, but it is a target until measured. At 600 logical vertices that target corresponds to approximately 16.67 PH/s of aggregate provisioned capacity per logical vertex if allocated uniformly; it does not require one physical device per vertex.

Reported hashrate is always the sum of measured completed SHA256d work over measured time. A mathematical topology multiplier, tensor ratio, search-order advantage or configured fleet size is never substituted for measured hashrate. If one observed execution path measures 500 kH/s, `600 x 500 kH/s = 300 MH/s` is only the aggregate rate when 600 independent workers/lanes actually execute at that measured rate.

Chronus fleet capacity may be provisioned horizontally until the measured aggregate reaches the target. Telemetry must expose logical vertices, active vertices, worker allocation, nonce lease ownership, completed hashes, measured worker and aggregate hashrate, gaps/overlaps, stale cancellation and backend/implementation identity.

## Evidence doctrine

Chronus reports what actually ran. Device presence is not execution. Configuration is not measurement. A compatibility runtime being installed is not Chronus-native execution. Unknown hardware fields remain unavailable rather than inferred.

Physical/device/fleet claims require runtime evidence bound to the executed workload and device/fleet identity. Mining acceptance remains governed by exact SHA256d, the negotiated target, freshness/epoch validity and literal pool acknowledgement.

## Delivery

Chronus may be embedded or provisioned as a fleet/cloud execution service. Delivery mechanisms are transport/deployment concerns and do not alter the Chronus-1 ISA/ABI or its authority.

Historical and compatibility implementations remain provenance only where they conflict with this architecture. They must not be promoted back to canonical status without explicit owner approval.
