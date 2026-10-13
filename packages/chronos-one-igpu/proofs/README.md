# Formal execution status — v3.10

Lean 4.19.0 executed `proofs/lean/Projection.lean` successfully. The receipt is
`validation/v3.10.0-lean.json`. Modular Q-step inverses, iteration injectivity,
constructive low-coordinate surjection and unique fiber coordinates are compiled
without sorry or new axioms. Trusted Lean axioms are propext and Quot.sound.

This is a subset, not all T1–T10. Fast-doubling equivalence, full finite-fiber
cardinality, sequence/encoding formalization, SHA256 distribution, consensus
security and physical throughput/energy remain outside these compiled proofs.

Run `LEAN_BIN=/path/to/lean python scripts/check_formal_proofs.py`. Compiler
absence or failure exits nonzero, with a status receipt. CI uses a hash-pinned
Lean toolchain and runs the same command. Its remote run remains not performed.
