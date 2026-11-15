---
name: verify-galois-invariant
description: Verify exact F_257[phi] parity, period-516 closure, and emit a deterministic microbenchmark JSON artifact.
---
1. Never use floating-point types (`float`, `double`) or lossy approximations in scale or manifold arithmetic.
2. Verify that all F_257 residues use at least 16-bit unsigned storage (`uint16_t` / `ushort` / `array('H')`) to accommodate residue 256 without overflow.
3. Run the parity test suite against reference vectors (`10^4`, `10^5`, `10^12`, `10^15`, `10^18`, `10^20`) and record `function_sha256` and `median_ns`.
