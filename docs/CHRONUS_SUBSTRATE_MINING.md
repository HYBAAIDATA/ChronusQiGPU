# Chronus algebraic substrate mining bridge

`chronus.mining_bridge.ChronusSubstrateMiningBridge` connects the existing
`quantum_compute_substrate.PhiTensorCore` to `mining.HashPipeline`.

## Authority boundary

The bridge has **ORDER_ONLY** authority. It may return a deterministic
permutation of a bounded nonce window. It cannot change:

- the 80-byte Bitcoin header;
- any nonce value or the candidate set;
- the target;
- SHA-256d;
- share validation or submission;
- pool credentials or acknowledgements.

`HashPipeline.grind_with_chronus_substrate()` scores the declared candidates,
applies the norm-preserving φ-tensor diffusion transform, seals the exact
resulting order, and dispatches it through the existing `grind()` method.
The active hashing backend computes every selected SHA-256d digest and the
pipeline independently rechecks any reported winner.

Compression ratio and reconstruction error are diagnostics only. They are not
hashrate, mining-success, quantum-advantage, or pool-acceptance claims.

## Verification

```bash
python -m compileall -q chronus/mining_bridge.py mining/hash_pipeline.py
python -m unittest -v tests.test_chronus_substrate_mining
python scripts/demo_chronus_substrate_mining.py
```