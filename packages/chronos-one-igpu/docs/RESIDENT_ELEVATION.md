# Resident ONE iGPU — v3.10

The original owner, Lucas engine and Chronos solver are preserved. A resident
logical device executes without GPU silicon on CPU/NumPy/exact/native-C hosts,
including ordinary Docker and cloud instances. This is a software accelerator
contract, not a new OS driver, CUDA-compatible device or extra physical cores.

Resident host binding defaults to auto: bind Apple Metal on macOS or OpenCL
elsewhere when executable, otherwise retain independent native residency and
record the absence reason. `host_binding="native"` suppresses probing. Explicit
`host_binding="opencl"` or `"metal"` fails closed on absence.

Host composition can also be explicit: `gpu.bind_host_gpu("opencl")` executes the actual
Lucas/SHA256d kernels; `gpu.bind_host_gpu("metal")` binds the existing Apple MLX
floating tensor operations on macOS. A request for a physical GPU fails closed
if its executor is absent. Binding is done before starting resident workloads.
Metal does not execute exact family or SHA256d kernels in this release. CUDA
and full GPU structured eigensolving remain unbound. No M5 core count is assumed.

`ResidentConfig(virtual_units=8000)` scales the logical scheduling address space.
`ResidentConfig(base_units=80,scale_index=10)` derives 80*L10 logical units.
Eight thousand logical lanes do not become eight thousand silicon cores. Physical
units, actual worker limits, bounded in-flight work and elapsed execution are
reported separately. Virtual lanes map deterministically over bounded tiles.

```python
from chronos import OneIGPU, ResidentConfig
with OneIGPU() as gpu:
    session = gpu.resident(ResidentConfig(virtual_units=8000))
    receipt = session.execute("intrinsics", {"nodes": [
        {"op": "binet_exact", "n": 31}, {"op": "lucas", "n": 31}]})
    assert session.verify(receipt, {"nodes": [
        {"op": "binet_exact", "n": 31}, {"op": "lucas", "n": 31}]})
```

Resident workloads support exact typed nodes, original Lucas dispatch and tiled
matmul/add/Hadamard/scale. The same facade retains quantum states/Hamiltonians,
phase feedback, S1–S6/F1–F3, MPS, tensors, prime/infinity memory, geometry,
coherence, Mandelbrot, UCI, QX, storage and mining. They are not reimplemented.

The bounded queue settles submitted work on cancellation, refuses expired
deadlines, preserves contiguous coverage and validates exact/tensor outputs.
Partial receipts are explicitly cancelled. Unexpected worker failures propagate;
the ABI does not automatically repeat partially failed work. Inputs are snapped
canonically; output size and active work are bounded. Physical adapter queues
are serialized; no thread-per-logical-lane allocation occurs.

Projection is `1+(left mod 2^b)` after Q^k over two 128-bit digest coordinates.
Each rung has exactly K=2^(256-b) DIGEST preimages. Free high-left bits and all
right bits enumerate the fiber; the matrix inverse constructs each digest.
This is not a finite bound on arbitrary headers, not the independent floating
Vector11D fold, and not a claim of cryptographic collision resistance. With
b=8 only eight address bits remain. Certificates bind the full digest, policy
and two coordinates and reject reuse across colliding headers. Consensus
security remains open; multiplying difficulty by K does not resolve it.

Lean compiles generic modular inverses, injectivity and constructive fiber
coordinates without sorry; full cardinality and fast-doubling equivalence are
not fully compiler-proven. See the receipt and T1–T10 ledger.

Historical measurements remain scoped to their original comparisons. The
v3.9 warm result is a distinct v3.8.1→v3.9 comparison, not evidence alone that
the earlier v3.8→v3.8.1 measurement was false. No new throughput gain is claimed
for this increment. See `FEEDBACK_AUDIT-v3.10.json` for every carried gap.
