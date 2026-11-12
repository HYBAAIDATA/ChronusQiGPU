<!-- coderabbit-ai-generated:v1 -->

# Folded PV state execution

The optional `ChronusOpenCLFoldedAdapter` represents a scale index by its quotient and remainder modulo516. Its16-byte record stores a uint64 low quotient, uint16 remainder, two uint16 field coefficients and uint16 flags. Indices through `516*(2**64-1)+515` round-trip from a record alone. For larger indices, `fold_scale_index` retains the low quotient limb and the caller must retain all higher quotient limbs and supply them to `unfold_scale_record`; a16-byte record alone cannot preserve an arbitrary integer.

The LUT contains516 coefficient pairs and occupies2064 bytes. It uses explicit little-endian uint16 encoding, including residue256. Field scaling remains exact and contains no floating-point arithmetic.

The host divides the requested jump into an exact quotient and remainder. It validates source coefficient parity and epoch overflow before dispatch, then launches once and compares every returned byte with the exact host reference. Empty batches return without a launch. The adapter requires a physical OpenCL GPU when constructed normally; unavailable devices fail closed.

Local verification passed19 tests with one physical-GPU test skipped. A separate PoCL CPU reference execution passed45 exact cases across9 scales and5 jumps, including10**20. This confirms kernel parity on that runtime. It does not measure physical GPU throughput, mining hashes per second or a rival comparison.

`benchmarks/acceleration/folded_state_raw.json` records the six reference vectors, function hashes and measured integer median nanoseconds. Timing samples vary between runs.
