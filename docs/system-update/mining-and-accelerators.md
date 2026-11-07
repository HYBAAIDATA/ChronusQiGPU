# Native search and accelerator integrity

## Executable native search

`SHA256D_NONCE_SEARCH` searches a caller-supplied 80-byte Bitcoin-format header over a bounded half-open uint32 nonce range. The service partitions each request into 32 disjoint contiguous lanes and computes actual SHA-256d hashes using the host's Python/OpenSSL implementation. `workers` selects between 1 and 32 processes, limited by reported CPU count. The first 64 header bytes are hashed once per lane and reused as a SHA-256 midstate. Results contain tested counts, match counts, a bounded list of matches and an explicit `SOFTWARE_EXECUTION` mode.

The range is capped at 65,536 candidates per request. This is a bounded service workload, not a persistent pool protocol, block template builder, extraNonce generator, multi-node lease coordinator or automatic mining operation. Disjointness holds within a single request; separate or repeated requests can overlap. It does not claim a 32× speedup, ASIC parity, 10 EH/s, SIMD execution, non-overlap across a fleet, or zero stalls. A maximum of 32 matches is returned, with the full match count and a truncation flag.

The target is a 64-digit hexadecimal unsigned integer; hashes are compared using Bitcoin's little-endian integer convention. The result hash is reported in conventional reversed-byte display order. The current service uses `EXACT_Q5_RATIONAL` as its default representation label; this label is request metadata and is not a claim that SHA-256d is implemented using Q(sqrt(5)).

Run a local benchmark with `python benchmarks/benchmark_mining.py --candidates 16384 --workers 1`, then repeat with `--workers 2` or another available CPU count. It measures actual elapsed time including process creation. In one local Python 3.12/two-logical-CPU run, 16,384 candidates measured approximately 1.26 million SHA-256d hashes/s with one worker and 0.82 million hashes/s with two; these small-sample figures are not independent benchmarks, deployment commitments, or comparable to ASIC throughput. The benchmark also compares ordinary increments with an exact Zeckendorf decode/increment/re-encode baseline; it does not implement a constant-delay carry-free circuit.

The reversible `M15` map is defined over integers modulo 256, not over F257. Exhaustive byte-pair tests check `unfold(fold(x)) == x`. Reversibility is not cryptographic authentication and does not prove a candidate meets a target; the SHA-256d comparison is performed directly.

## Exact accelerator boundary

`chronus.backends.lattice` provides exact `(a + b*phi)/denominator` conversion, multiplication, trace and norm, a physical-adapter protocol, and full-element host parity verification. An integer denominator is necessary for general Q(sqrt(5)); Z[phi] alone cannot represent arbitrary rational elements. The correct values are `F_90 = 2880067194370816120` and `L_90 = 6440026026380244498`.

The norm and trace are useful invariants, not collision-resistant proofs of correct output. A device-supplied aggregate checksum cannot independently authenticate the device computation, and verification of arbitrary output cannot generally be reduced to constant work without an additional verified proof system. The implementation therefore checks each coefficient against an exact reference and fails closed on a mismatch.

An **experimental opt-in OpenCL GPU adapter** and packaged integer kernel implement `PV_LATTICE_FOLD`. Install the `accelerator` extra and set `CHRONUS_ENABLE_OPENCL_PV=1` before service startup. Startup selects an OpenCL-reported GPU, checks the packaged kernel digest, compiles it, and performs an L90 known-answer and exact host-parity test; missing dependencies, missing devices or failed checks prevent startup. Inputs are signed 64-bit integer coefficients with a positive arbitrary-precision denominator; the exact phi-power factors are calculated on the host. A four-limb signed 256-bit kernel performs the multiplications and sums. A batch is rejected on intermediate overflow, even where later cancellation might fit. Every output is checked against the arbitrary-precision host reference and the norm identity. The backend reports device details and `PHYSICAL_ACCELERATOR`; it does not fall back to an OpenCL CPU device.

The kernel and mapped buffer path are tested on a CPU OpenCL runtime, including signed boundaries, overflow and orders through 360. They have **not** been validated on a physical GPU. OpenCL `ALLOC_HOST_PTR` buffers are mapped/unmapped for transfer; allocation, page locking, alignment, actual DMA and zero-copy behavior are driver-dependent and are not guaranteed. The receipt explicitly reports `zero_copy_verified: false`. A source digest checked against a constant in the same software package is a consistency check, not a tamper-proof attestation. The default container does not install the optional accelerator dependencies or configure device passthrough. Device-reported identity and a KAT do not constitute independent physical-device attestation; PCI address is available only through the supported vendor extension and PCI device ID is not yet queried. Receipt fields are workload metadata, not a signed, immutable receipt.

The current kernel always uses 256-bit limb arithmetic, not separate dynamic 64/128/256 execution paths or workgroup promotion. `intermediate_width_counts` reports the minimum signed width needed by observed intermediates, not which hardware tier actually ran. The host still performs exact parity checks and data transfers; no constant-time verification, zero-copy DMA, or register-only behavior is claimed.

Workload values are JSON objects with `a`, `b`, and `denominator`. Inputs accept JSON integers or decimal strings (up to 1,024 digits); use strings when sending large numbers from JavaScript or other clients with limited integer precision. The returned coefficients and denominator are decimal strings, so 256-bit results are not silently rounded by JSON consumers. `order` is an integer from 0 to 360; `a` and `b` must fit signed 64 bits. For example:

```json
{"order": 90, "values": [{"a": "1", "b": "0", "denominator": "1"}]}
```
