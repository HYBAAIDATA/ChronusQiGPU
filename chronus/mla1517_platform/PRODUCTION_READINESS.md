# MLA1517 production-readiness statement

## Ready in this build

- Exact promoted algebraic primitives.
- Content-addressed MLA objects.
- Cassini, Lucas, Fibonacci, and Zeckendorf validation on write/read.
- SQLite WAL storage with full synchronous commits and foreign-key enforcement.
- Deterministic CLI and stable JSON schema.
- Python reference tests and C++ conformance tests.
- Docker-native POSIX shared-memory ring transport with cross-process verification.
- Progressive structured-mining profile with sparse winner-vault writes.
- Extended algebra identity tests.
- Non-root production Docker recipe.
- Explicit evidence boundary and hypothesis quarantine.

## Not yet production-ready

- CUDA/HIP accelerator: unavailable toolchain in the build environment.
- Rust runtime: source scaffold exists but compiler/toolchain is unavailable.
- Multi-node M32 fabric: specification only.
- Physical GPU silicon: not built.
- Government deployment: requires security review, key management, audit integration, and operational controls.
- Hyperscaler deployment: requires load, fault, tenancy, and cost benchmarks.

The correct status is **production-ready reference software core**, not production-ready dedicated hardware.

## Docker-native execution engine

The independent-container mode uses a native C++ transport path:

- `/dev/shm`/POSIX shared memory is the 32-way transport region.
- The 12 execution nodes and 20 Aethel memory nodes exchange 64-byte 11D hot descriptors.
- The ring uses sequence-numbered lock-free slots and acquire/release atomics.
- Cross-process pointers are never shared; the ring passes sequence positions and fixed descriptors.
- D1 supports deterministic ghost payloads for idle geometry benchmarks and real workload descriptors when active.
- Python remains the control-plane/reference layer; the C++ engine owns the high-throughput shared-memory path.

The 64-byte descriptor is an 11D state plus one routing slot. Exact/cold state remains in Aethel. This preserves the 11D ontology while giving the hot path one cache-line-sized transport unit.

## Progressive structured-mining profile

When the target predicate is defined over the MLA1517 algebraic state, mining uses progressive instantiation:

1. Generate D1 with `partition_id + 32 * step`.
2. Apply the cheap D2/D6 structured sieve.
3. Compute D3-D5 only for survivors.
4. Verify D10 Cassini on the exact Fibonacci state.
5. Write complete 11D winners to the sparse Aethel vault.

Failed candidates remain local to the execution lane and never cross the memory boundary. The 12 physical execution nodes own the 32 logical partitions round-robin. The 20 dodecahedral nodes are event-driven vault destinations for completed winners, proofs, and checkpoints.

The native profile supports AVX2 batch nonce generation with a scalar fallback and optional `MLA1517_PIN_THREADS=1` CPU affinity. `MLA1517_WORKLOAD=structured_mining` selects it in `Dockerfile.native`.

Cassini is used as the exact recurrence-integrity seal. It validates the folded Fibonacci state; the mining target remains the declared workload predicate.

### Fibonacci-void difficulty

The structured target can be broadcast as:

```txt
DIFFICULTY_MASK = (1 << difficulty_bits) - 1
ANCHOR_MASK     = 1 << difficulty_bits
```

A candidate passes the void target when the masked lower Zeckendorf dimensions are zero and the anchor bit is present. An optional `POLYHEDRAL_MASK` and target value adds sparse geometry-specific resonance constraints.

The implementation exposes:

```txt
MLA1517_DIFFICULTY_BITS
MLA1517_POLYHEDRAL_MASK
MLA1517_POLYHEDRAL_TARGET
```

The check is a native bitwise predicate. The exact D5 code is generated from the integer recurrence representation; Binet remains the fast algebraic projection, not an unsafe floating-point authority for exact high-index reconstruction.

## SIMT warp and UMA hardware contract

The custom-iGPU target defines a 32-lane SIMT warp for the M32 logical partition. The hardware contract is:

- lane `0..31` maps to `partition_id`;
- `nonce = lane + 32 * step`;
- one warp ballot produces the 32-bit D5 acceptance mask;
- active lanes compact by prefix rank without serial winner scans;
- winning lanes route by prime address to one of 20 Aethel memory destinations;
- the 12 icosahedral execution nodes are the arithmetic execution groups around the 32-lane warp;
- the 20 dodecahedral nodes are UMA vault destinations for winners, proofs, and checkpoints.

The software conformance binary `simt_warp` verifies 640,000 lanes with zero recorded branch-divergence events, 13,623 ballot-selected winners, and complete UMA routing.

The silicon design should use a fixed-point golden projection or exact recurrence/Q-matrix unit for bounded D5 generation. A Binet projection unit may be a fast front-end, but exact Fibonacci/Zeckendorf logic remains the correctness path at high indices. UMA removes PCIe transfer; it does not remove coherence, atomic publication, or host-memory latency, so the vault uses explicit sequence publication.

## Host GPU overlay

MLA1517 is a GPU/accelerator architecture. It may run in integrated mode or as an overlay that scales and schedules work on a host GPU. The current build includes a deterministic host-GPU tiling contract and CPU fallback. Actual CUDA/HIP/Vulkan/Metal execution remains pending a compatible accelerator toolchain and benchmark.

## Host-to-silicon and pool coordination layer

The host-side FPGA bridge is implemented as an explicit C ABI:

```text
host/mla1517_mmio.h
host/mla1517_mmio.c
host/libmla1517_mmio.so
```

The bridge writes `DIFFICULTY_MASK` and `base_step`, starts/stops the engine,
and polls the 20 Aethel vault slots using an even/odd sequence publication
protocol plus a double-read snapshot. It returns the exact 64-byte hot
descriptor only after the sequence is stable. A UIO/PCIe mapping is supplied
explicitly by deployment; `/dev/mem` is never opened implicitly.

The Python `ctypes` layer is:

```text
chronus/mla1517/hardware.py
```

The asynchronous coordinator is:

```text
python/manifold_pool_coordinator.py
```

It implements JSON-lines Stratum subscription, authorization, job tracking,
request correlation, reconnect, and Braiins → ViaBTC failover. The
MLA1517-to-standard-Stratum formatter is intentionally fail-closed: a
Cassini-sealed 11D record is not automatically a valid share for a public
pool's unrelated proof-of-work algorithm. Submission requires a negotiated
algorithm adapter that supplies exact `stratum_params`. This prevents invalid
shares from being broadcast.

The coordinator is packaged in `Dockerfile.headless_miner`. `--submit` is an
explicit opt-in, and the default is dry/validation mode.

### Native Aethel / PRIME-DB path

The C11 host layer now exposes a dual-output path:

```text
MMIO vault
   ├── Path A: stable VaultRecord -> Python/Stratum
   └── Path B: 64-byte MLA1517_State -> /dev/shm SPSC ring
                                      -> PRIME-DB consumer
                                      -> vertex_00.db ... vertex_19.db
```

The SPSC ring uses cache-line-separated atomic head/tail counters and a
64-byte state layout. Reopening a ring does not reset its counters, and a full
ring applies backpressure before a vault record is consumed. PRIME-DB validates
D10 before routing `D7 % 20`, publishes a persistent cursor only after the
state write, and supports explicit `msync` plus `fsync` barriers.
`NativePrimeDB.find_resonant_blocks()` invokes the C query callback and returns
only D5-mask matches to Python.

Deployment files are `Dockerfile.primedb`, `docker-compose.yml`, and
`docker/primedb-entrypoint.sh`. The compose configuration shares the
coordinator IPC namespace with PRIME-DB and uses a host bind mount for the
database directory. mmap visibility and NVMe durability remain separate
properties; the sync interval is explicit.

### Out-of-band telemetry

`host/telemetry_shm.{h,c}` defines cache-line-separated relaxed counters for
the 32 logical partitions, topological voids, and accepted shares. The
optional `telemetry` container maps this block and exposes a WebSocket feed at
`/ws/topology`. It also reads the twenty persistent vertex cursors from the
read-only PRIME-DB bind mount and reports bounded saturation against the
configured capacity.

Telemetry is deliberately not described as a zero-cost guarantee: relaxed
atomic increments are non-blocking producer operations, while the observer
still performs ordinary mapped reads and JSON/WebSocket work outside the
compute path.

### Salamander supervisory plane

`salamander_engine.py` is an explicit-control supervisory loop. It senses
per-lane Cassini faults, Stratum drops, and vertex-cursor imbalance. When
`MLA1517_SALAMANDER_ENABLE=1` is set, it may invoke only the declared MMIO
actions: lane quarantine/restore and polyhedral-mask update. The default is
observe-only.

Salamander does not claim to infer thermal or voltage failure from a Cassini
counter alone; it treats the counter as an integrity signal requiring an
operator-defined policy. It does not mount the Docker socket or rewrite
`--cpuset-cpus` in place. Container affinity remains a deployment control.

### EuclidCore governance

`euclid_core.py` adds a deterministic measured policy over four explicit
polyhedral-mask arms. Salamander evaluates the previous epoch, updates the
active arm's bounded reward, then selects the next arm. The reward is based on
observed test-rate delta and penalties for integrity faults, network drops,
and storage imbalance. EuclidCore is disabled by default and requires
`MLA1517_EUCLIDCORE_ENABLE=1`.

The implementation deliberately does not call the result “optimal,” alter the
problem definition, or claim that test-rate equals valid external mining
hash-rate. It is an auditable control experiment with a deterministic seed.

### Legacy Stratum translation boundary

The requested compatibility serializer is present and tested:

```py
format_mla1517_to_stratum_share(
    raw_11d_buffer,
    worker_name,
    job_id,
    extranonce2,
)
```

It decodes the proposed legacy layout:

```text
<IffIIfIIfiII
```

and emits the expected `mining.submit` JSON line with byte-reversed uint32
nonce and time fields. A second formatter decodes the actual MLA1517 hot
descriptor:

```text
<Q14I
```

This distinction is required because the current RTL/C ABI stores D1 as a
uint64 and D2-D11 as uint32 values; it is not the proposed float-heavy
12-field layout.

Both serializers are transport adapters only. They cannot make a nonce satisfy
a public pool's independent SHA-256d or other proof-of-work target. The live
coordinator therefore remains fail-closed until an algorithm-specific,
negotiated pool adapter supplies the complete valid share parameters.

### Corrected Salamander protocol (v2.5)

The supervisory contract is now implemented as a separately testable control
plane in `python/salamander_control.py` and wired to `salamander_engine.py`:

- a 20 Hz tick (`TICK_MS=50`) reads a versioned, magic-checked seqlock
  snapshot; the observer copies bytes and retries if the sequence changes or
  is odd, rather than using `from_buffer` on a live map;
- per-lane cumulative Cassini counters feed an exponential leaky bucket with
  `FAULT_TAU_MS=60000`, `FAULT_TRIP=3.0`, and `REARM_HYST=0.5` hysteresis;
- lane changes are staged, committed at a warp boundary, and accepted by the
  control plane only after `COMMIT_ACK`; at most one transaction is attempted
  per supervisory tick;
- the McLaren controller never reduces the active lane count below 24. At the
  floor it enters degraded mode instead of excising another lane;
- every acknowledged retirement records its lane watermark in an orphan
  min-heap, and readmission starts with a fresh watermark after a 60-second
  probation and three self-test passes;
- the Michie policy uses one candidate at a time, a 20-second dwell, and
  accept-or-revert evaluation. EuclidCore remains available as the explicit
  deterministic measured policy when `MLA1517_SALAMANDER_POLICY=euclid`;
- failover requests are dampened by a 30-second cooldown and expose a
  10-second secondary-route dwell before a future switch-back;
- the default tick is 50 ms, but the supervisor remains observe-only unless
  `MLA1517_SALAMANDER_ENABLE=1` is explicitly set.

The 49-test regression suite covers bucket decay/rearm, minimum-lane
protection, ACK-gated retirement, Michie dwell acceptance, and failover
cooldown in addition to the native storage, telemetry, MMIO, RTL-contract,
and protocol tests. This validates the control-plane state machine and its
software ABI; it is not a claim that unbuilt silicon, Docker, Rust, or an HDL
simulator has executed in this environment.

### Agentic mining workflow — five-intelligence measured implementation (v2.7)

`python/agentic_mining.py` implements the five decision-theoretic roles over
measured state only:

1. `GeomEncoder` produces deterministic coordinates and a content digest from
   measured telemetry; it does not train or invent embeddings.
2. `TopologicalRegime` computes exact connected-component and cycle invariants
   on the fixed 32-lane M32 graph.
3. `MeasuredForwardIndex` returns a forward result only when that action and
   regime have a real before/after telemetry record.
4. `CommissionedSCM` returns causal effects only for deliberate interventions
   that have been recorded in the same regime. It never infers causality from
   correlation alone.
5. `ObservedCounterfactuals` scores only actions with observed support in the
   same regime. Unsupported actions raise `SupportViolation`.

`MiningAgent.tick()` composes the stack as:

```text
measure → exact geometry → exact topology → observed-support lookup
→ Salamander veto → optional ACK-gated actuation
```

There is no generated trajectory, synthetic world model, probabilistic mask
selector, heuristic quantum claim, or implicit hardware write. A failed
acknowledgement returns the safe action. Policy learning is not performed from
invented data; new capability enters through measured transitions and
commissioned interventions.

This is the correct production boundary: mathematics is implemented exactly
where the contract is exact, while any physical effect that depends on the
rig, silicon, power system, pool, or workload must be measured on that system
before it is admitted to the decision path.

## Exact quantum subsystem boundary

The canonical quantum subsystem is `chronus/mla1517/quantum.py`, exposed through
`chronus/mla1517/accelerator.py`. It is not a simulator or a floating-point
approximation: amplitudes use exact rational coordinates over `Q(sqrt(2))` with
an exact imaginary component. Tensor products, unitary gates, CNOT, exact
normalization, and discrete Pauli-Z Hamiltonian evolution are implemented.

An unavailable iGPU exact-arithmetic kernel fails closed with
`AcceleratorUnavailable`; it does not silently use a CPU approximation. General
Hamiltonian exponentials outside the declared exact domain fail closed. The
physical iGPU/OpenCL kernel remains a separate hardware implementation stage
and must provide the same exact arithmetic contract before being enabled.

## End-to-end exact GPU and persistence gate

`kernels/mla1517_lucas_pisot_scale.cl` is the canonical OpenCL payload for the
exact bounded Lucas/Pisot ladder `(10, 12, 15, 18, 20, 31, 50, 76)`. The host
entry point is `chronus/mla1517/scaling.py::OpenCLLadderExecutor`. It discovers a
real OpenCL device, submits the scale vector, reads exact uint64 Fibonacci,
Lucas, and Padovan results, and verifies every result against the exact Python
reference. Missing OpenCL, mismatched results, or a CPU fallback are failures.

`scripts/strict_hardware_gate.py` then persists each verified tensor-state
record through PRIME-DB and reloads/validates it. `MLA1517_STRICT_HARDWARE_CI=1`
adds this gate to `make test`; without that flag, CI is explicitly reference
software only and cannot claim GPU activity.

## Live GPU-to-Stratum measurement boundary

The live measurement deployment is intentionally separate from the general compose stack:

- `docker-compose.gpu.yml` requests an explicit GPU device with `capabilities: [gpu]` and maps `/dev/dri` for iGPU hosts.
- `Dockerfile.lucas-scaling` supplies the OpenCL ICD loader and `pyopencl`; the vendor runtime is a host deployment responsibility.
- `scripts/measure_lucas_scaling.py` requires `--live`, `MLA1517_ENABLE_LIVE_SUBMIT=1`, `MLA1517_LIVE_APPROVAL_ID`, credentials, and a negotiated `module:factory` Stratum adapter.
- No generic tensor-to-nonce mapping is assumed. The adapter must construct a complete consensus-valid submission for the current job.
- Acceptance is counted only when the remote pool returns JSON-RPC `result: true`.
- Pool difficulty or target is mandatory for effective accepted-share-equivalent H/s; difficulty 1 is never assumed.
- Missing OpenCL, missing adapter, missing target, a rejected rung, or a disconnected pool fails closed. There is no sleep-based timing, simulated output, or CPU fallback.
