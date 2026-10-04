# Chronus algebraic substrate mining bridge

`chronus.mining_bridge.ChronusSubstrateMiningBridge` connects the existing
`quantum_compute_substrate.QuantumFoldTensorCore` to `mining.HashPipeline`.

## Execution objective

This is a search-optimisation layer for the complete mining fabric—not a
CPU-only experiment and not a capability ceiling. Its sealed search plan is
portable across:

- CPU reference execution;
- GPU and OpenCL execution;
- ASIC execution;
- Super ASIC execution.

`HashPipeline.grind_with_chronus_substrate()` scores the declared candidates,
applies the norm-preserving φ-tensor diffusion transform, seals the exact
resulting order, and dispatches it through the existing `grind()` method.
The active route—not the bridge—is responsible for hashing. The bridge does
not force fallback to CPU and does not limit accelerator scale.

## Consensus compatibility

The search optimiser may change representation, topology, scheduling,
partitioning, and execution order. The selected CPU/GPU/ASIC/Super ASIC route
computes the work. SHA-256d and the negotiated target remain the interoperable
proof boundary, and the pipeline independently rechecks any reported winner.
That boundary protects correctness; it is not a restriction on performance,
hardware design, search intelligence, or the objective of building dominant
mining technology.

Compression ratio and reconstruction error are diagnostics only. They are not
substitutes for measured hashrate, mining success, or pool acceptance.

## Verification

```bash
python -m compileall -q chronus/mining_bridge.py mining/hash_pipeline.py
python -m unittest -v tests.test_chronus_substrate_mining
python scripts/demo_chronus_substrate_mining.py
```