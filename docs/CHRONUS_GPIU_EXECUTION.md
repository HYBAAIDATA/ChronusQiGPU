# Chronus GPIU: executable software blueprint

The ten-specialist blueprint is implemented through the existing Chronus ABI,
TURING quantum engine, Kellogg exact tensor engine and the Chronus–OVID–THESEUS
triad. This register distinguishes executable contracts from claims that still
need evidence. Owner declarations D3/D4/D6/D7/D9/D12/D13 govern.

## Two capacity offerings

1. **Independent Chronus GPU capacity** (`native_chronus_gpu`): Chronus supplies
   the execution plane without requiring a host GPU.
2. **Augment the customer's GPU estate** (`host_gpu_augmentation`): Chronus
   discovers a capable host accelerator and scales execution through it.

Manual adapter binding is **optional**. The existing runtime selects by advertised
capabilities and execution policy. A caller can optionally pin an adapter or
forbid software fallback. Receipts distinguish the requested mode from the
backend that actually executed. Missing host hardware never disables independent
Chronus capacity.

**Chronus executes; OVID owns authoritative folded state and checkpoints;
THESEUS supplies rebuildable database, search, graph and index projections.**
Pulvini supplies folding. Tenant admission, custody, verification and evidence
remain part of this same system. Existing compatibility hooks named THESEUS are
not evidence that authoritative ownership has moved from OVID.

### Run a Lucas/Pisot capacity request

From an installed environment or repository root:

```bash
python -m chronus.scaled_gpiu --mode independent --tenant example \
  --store-root /tmp/chronus-capacity --workload-id independent-1 \
  --base-items 1 --scale-index 12

python -m chronus.scaled_gpiu --mode host --tenant example \
  --store-root /tmp/chronus-capacity --workload-id augment-1 \
  --base-items 1 --scale-index 12
```

Both execute the same fused exact integer IR over the Lucas-scaled work window
and verify each chunk. Rung 12 executes 322 items for this request. The output
includes the plan, computed rows, exact Pisot-conjugate bound and actual receipts.
`--host-adapter-id` is optional; `--no-software-fallback` makes unavailable
augmentation fail closed. The default augmentation policy permits a clearly
labelled independent software fallback, as specified by
`CHRONUS_IGPU_ELEVATION.md`.

Lucas scale is an executed logical work multiplier; the plan deliberately does
not manufacture a physical throughput multiplier. Capacity purchasing, billing,
SLA and deployment remain the enclosing platform's responsibilities.

## Execution contracts

All requests use `virtual_igpu_v1`, the existing tenant admission, delivery modes,
memory plane, receipts, evidence ledger and control-plane verifier.

| Workload kind | Accepted software operation | Verification |
|---|---|---|
| `quantum_program` | Clifford, Clifford+T/Toffoli, exact MPS, rational-turn phases/Rz, explicit magic-T injection | TURING certified execution and replay |
| `exact_graph` | PEPS/TTN amplitude, norm, local map, expectation, exact bond reduction | Kellogg certificate replay; independent full bond-sum regressions |
| `hyperbolic_walk` | Hyperbolic weighted graph Laplacian, exact continuous-time evolution | Hermitian generator, exact symbolic replay; unitarity/composition regressions |
| `grid_geometry` | D4, components, cellular automata, directed graph morphisms | Independent coordinate, flood-fill, scalar-cell and edge-image oracles |
| `modular_geometry` | PSL(2,Z), geodesic/Jacobi evaluation, Cassini gradient or Hamiltonian step | Rational/symbolic replay and independently differentiated invariants |
| `exact_kernel` | Fused Fibonacci/Lucas/Padovan, golden stride and Cassini identity | Separate fast-doubling/recurrence oracle and little-endian uint32 digest |
| `algebraic_isa` | Z[phi] and GF(256) matrix dot-product arrays | Independent formal polynomial reduction |

Replay through the canonical engine validates the adapter boundary; it is not a
second independent implementation of quantum or tensor semantics. The separate
mathematical tests are listed in the verification section.

## All twenty directives

“Implemented” below refers to the specified admitted software contract. Bounds
are explicit, and a failed admission does not become approximate execution.

| ID | Directive | Executable implementation | Scope and outstanding qualification |
|---|---|---|---|
| 1.1 | Golden/quadratic/cyclotomic fields | `kellogg/algebraic_field.py`: exact rational polynomial residues, cyclotomic polynomials, inversion, conjugation, lcm-composita, Q8 and Z[phi] embeddings; TURING register dispatch | Conductors 1..256. Existing observational Float64 paths retain their contract; this does not replace every numeric register in the repository. |
| 1.2 | Exact unitary compilation | TURING `backends/cyclotomic.py` and Chronus `exact_quantum.py`: H, Toffoli, `phase:p/q`, `rz:p/q` in rational turns, including Rz global phase | Phases outside the admitted field refuse; no rounded substitute. |
| 2.1 | Symplectic stabilizers and magic resources | Existing TURING tableau supports the 1,024-qubit Clifford ABI. `magic_t` constructs both injection branches, checks probabilities 1/2, applies S correction and records resource consumption | Magic injection uses the bounded algebraic lane; it does not assert polynomial cost for arbitrary non-Clifford circuits. |
| 2.2 | Hyperbolic CTQW | TURING `HyperbolicGraphWalk`, Chronus `hyperbolic.py`: rational hyperbolic edge weights and exact `exp(-itH)` | Admitted graphs have 1..4 vertices. Continuous evolution has no discrete coin/shift. Arbitrary graph scale and search optimality are not established. |
| 3.1 | Exact MPS/PEPS/TTN | Existing MPS/MPO plus `kellogg/graph_network.py`, `graph_operations.py`, `graph_custody.py`: amplitudes, local maps, norms, observables, content-verified site checkpoints over existing custody providers | Graph ABI: 64 sites, 65,536 input values/intermediate elements, 1,000,000 scalar products. Generic contraction depends on graph width and admitted ranks. |
| 3.2 | Adaptive exact bonds | Exact rank factorization `A=C F`, absorption into neighboring site, zero discarded weight certificate; existing exact MPS rank reduction | Removes local exact dependencies. Cyclic PEPS global Schmidt-minimality and arbitrary 1,000-mode sub-exponential scaling are not claimed. |
| 4.1 | Fusion and tiling | `chronus/compiler/exact_kernel.py`: affine independent iteration contract, fused recurrences, bounded tile working set, native C SIMD pragma | Compiler execution verified. Cache residency, SIMD instruction selection and speedup require measurement on the selected target. |
| 4.2 | Portable exact IR | One validated AST emits C, OpenCL, Vulkan GLSL and Metal; uint32 modular overflow and digest order fixed. `portable_adapter.py` executes native C and OpenCL with recovery-safe caches | Native C and OpenCL CPU executed; Vulkan SPIR-V compiled/validated. Metal/device-specific AVX-512/AMX and physical GPU execution remain unqualified here. |
| 5.1 | Hyperbolic geodesics | `geometric_flow.py`: PSL(2,Z) images of vertical geodesics with exact Jacobi fields; existing modular metric primitive | Unit-speed and Jacobi laws tested. No change to the canonical mining coverage/acceptance contract or 11-D Float64 boundary. Integration of these trajectories as a new mining search plan remains open. |
| 5.2 | Cassini dynamics | Exact rational gradient of log-product potential; bounded line-search descent; separately declared symplectic-Euler Hamiltonian map | Singularities refuse. Discrete symplectic integration is not asserted to be the exact continuous ODE solution. |
| 6.1 | Lossless representation morphisms | `aethel/representation_views.py`: finite basis permutations, adjoints, composition, tensor products and immutable zero-copy views | Admitted invertible basis maps only. Arbitrary ARC feature extraction is not an invertible grid-to-tableau transformation. |
| 6.2 | Global consistency from local sections | `chronus/fleet/sections.py`: restriction, overlap agreement, exact domain cover, tenant/version checks, authoritative existence checks and admitted OVID manifest commit | Conflicting overlaps and cross-tenant references fail before publication. Finite execution domains; no blanket proof for all distributed code. |
| 7.1 | Software memory ring | `chronus/fleet/memory_ring.py`: eight-slot default, preallocated buffers, `recv_into`, ownership swap, borrowed-slot backpressure, payload digest, fencing and bounded receive deadline | Application payload copy count is zero. Socket transport is executable; kernel-bypass RDMA/verbs and NIC qualification are still separate unimplemented transport work. |
| 7.2 | Authority and audit | Existing HMAC AdmissionController gates ring/section/recovery mutations; tenant grants, nonce replay refusal, pre-mutation audit and generation revocation | Local transport/authentication scenarios tested. Off-loopback sockets require authenticated TLS. No claim of zero audit leakage against arbitrary hostile deployments. |
| 8.1 | Lyapunov cohort control | `salamander/cohort_control.py`: exact bounded-disturbance contraction model, invariant box, observed transition certificate; `CohortAutonomicLoop` samples caller-owned telemetry | Certificates apply only when actual observations satisfy the declared model. They do not certify unobserved thermal or fragmentation dynamics. |
| 8.2 | Autonomous fenced recovery | The loop selects a smaller Lucas lane count, requests canonical authority, journals intent, rotates worker fence, journals completion and checks postconditions | Lost completion or unfinished restart intent blocks blind retry. Exact tensor states are never truncated to fit. Deployment sensor/grant-provider wiring is explicit. |
| 9.1 | EUCLID D4 acceleration | `ChronusARCGeometry` submits EUCLID-selected symmetry operations; vector integer kernels and coordinate oracle preserve grid semantics | EUCLID owns learning and reward. This is execution evidence, not an ARC benchmark score or device speedup. |
| 9.2 | Topological primitives | `topology.py`: finite cellular rules and graph homomorphism/isomorphism; EUCLID executor's `topology()` consumes verified results | Bounded cells, steps and edges; work is proportional to admitted input, not universal O(1). |
| 10.1 | Software ISA and golden pipeline | `exact_kernel` runtime integration executes recurrence/stride/Cassini instructions. Existing `golden_stride.vhd` has FIFO depth fib(6)=8 | Software is the active offering per D12/D13. GHDL conformance is retained evidence; FPGA manufacturing is not required for independent Chronus. |
| 10.2 | Algebraic dot-product array | `algebraic_isa.py` implements bounded matrix products over Z[phi] and GF(256), exposed through the canonical ABI; registered RTL multiply remains available | Exact software integers do not overflow. No physical single-cycle or ASIC tape-out claim. |

## Compatibility and exactness

D6/D7 require exact execution. The blueprint's proposed singular-value truncation
is therefore implemented as exact rank reduction with **discarded weight zero**;
insufficient resources fail admission. Lossy truncation cannot silently acquire
an exact certificate. This is preservation of the owner's standing contract.

The Q8 graph lane and general cyclotomic register lane share Kellogg mathematical
ownership. TURING owns quantum semantics; EUCLID owns learning/reward. No second
quantum or learning authority is introduced into Chronus. Aethel view code has
no Kellogg dependency.

The ring is transient execution memory. Graph checkpoints use the existing
custody protocol, with durability supplied by the chosen provider. Resident
custody alone is not a durable deployment. OVID section commits use tenant-scoped
VirtualMemoryPlane references; THESEUS can rebuild projections from them.

## Verification and remaining work

Focused regressions are `tests/test_chronus_{cyclotomic,gpiu_exact,exact_kernel,
algebraic_isa,geometric_flow,hyperbolic,memory_ring,representation_sections,
topology}.py`, `tests/test_kellogg_graph_network.py` and
`tests/test_salamander_cohort_control.py`, with existing ABI, ARC, triad, fleet,
mode and remote delivery suites. TURING's entire suite is run from its package
directory. `python -m scripts.verify_chronus_rtl` checks the existing RTL.

The full original blueprint is **not universally qualified**: RDMA is not
implemented, emitted Metal kernels have not executed, physical accelerator
throughput has not been measured here, generic global PEPS rank optimality is
not established, and the new geodesic trajectory is not a mining plan. These
remain explicit work rather than inferred success. None is a prerequisite for
using the implemented independent software capacity path.

Repository-wide pre-existing failures include a missing episodic-memory fixture,
two platform contract assertions, import-graph handling of a null-containing
literal, and existing style/deployment findings. The workspace validation record
retains exact commands, input hashes, outcomes and baseline comparisons.

## Packaged triad and first workload

Owner D14 selects finite GPU tiers and a PYTHIA fleet. See
[GPU packaging](CHRONUS_GPU_PACKAGING.md) for executable commands and exact limits.
`chronus.triad.ChronusTriad` makes OVID custody required for its submissions and
provides rebuildable THESEUS discovery. The capacity CLI uses this composition;
historical authority profiles remain explicit compatibility surfaces.

PYTHIA's prepared SHA256d specialization reuses the first SHA256 block and its
existing golden-stride kernels. Serial software and parallel host batch receipts
separate the logical prefix through the first winner from actual hash evaluations.
Independent host verification checks every returned candidate. `PythiaFleet`
uses the canonical lease/fencing scheduler and this triad, retaining PYTHIA's
nonce ordering and pool/proof authority. It does not create physical ASIC capacity.

A 1,024-mode exact MPS regression now executes H/CX/T at bond dimension2, norm1,
with certificate replay. This is an executed bounded state family, not an
arbitrary-state scaling guarantee. The canonical production/reference boundary
also rejects cached research-only H4 topology outside its active authorization.
