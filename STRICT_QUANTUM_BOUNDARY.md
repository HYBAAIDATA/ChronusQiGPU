# STRICT_QUANTUM_BOUNDARY.md

## Purpose

PYTHIA is a Bitcoin SHA256d miner. The following literature is used to define
engineering boundaries and audit metadata; none of it authorizes a consensus
shortcut, a fabricated performance claim, or a speculative quantum code path.

## Six explicit categories

1. **SHA256d mining boundary** — SHA-256 circuit optimization is research
   context, not a replacement for Bitcoin's complete-header double-SHA256
   predicate. Source: [arXiv:2401.10902](https://arxiv.org/abs/2401.10902).
2. **Quantum-search theory** — Grover cost estimates and physical-resource
   caveats remain theoretical reference material. Source: [arXiv:2603.25519](https://arxiv.org/abs/2603.25519).
3. **Signature migration** — quantum risk to ECDSA/BLS signatures is a wallet
   and protocol-migration concern, not a mining escalation. Source: [arXiv:2606.14484](https://arxiv.org/abs/2606.14484).
4. **Quantum-sampling PoW** — boson-sampling consensus replaces Bitcoin's
   consensus mechanism and is not an adapter for PYTHIA. Source: *Quantum
   Science and Technology* 10, 025020 (2025).
5. **Proof-of-quantum-work blockchains** — a separate consensus design, not
   Bitcoin mining. Source: [arXiv:2503.14462](https://arxiv.org/abs/2503.14462).
6. **QRNG claims** — deterministic classical partitioning remains sufficient
   for correctness; QRNG entropy is not a mining advantage. Source: InspireHEP,
   “QRNG-Derived Quantum Entropy in Bitcoin PoW” (September 2026).

## Additional algorithmic references

- Search-space expansion: *Enhancing Bitcoin Mining Using Quantum Search Space
  Expansion and Non-Unitary Operator* (InspireHEP, July 2026).
- Optimal Grover horizon: [arXiv:2110.00878](https://arxiv.org/abs/2110.00878).
  PYTHIA uses the ~16-minute reference only as `WORK_WINDOW_MAX_S = 960`, a
  bounded refresh safety limit, not as a measured optimum.
- Quantum-miner race dynamics and the 51% threshold: [arXiv:2607.23952](https://arxiv.org/abs/2607.23952).
- Timestamp manipulation: [arXiv:2403.08023](https://arxiv.org/abs/2403.08023).

## Enforced implementation boundary

- Every candidate uses the complete negotiated 80-byte header and independent
  double-SHA256 target comparison.
- `extraNonce` is a coinbase/Merkle-root input, not the 32-bit header nonce; it
  remains job-scoped and is not wired into the solver as a shortcut.
- Merkle recomputation and midstate reuse are schedule-cost metadata only.
  The active OpenCL payload implements first-block SHA-256 midstate caching
  (host precomputes the SHA-256 midstate of the 64-byte header prefix once per
  job; kernel contract `KERNEL_BETA_MIDSTATE = 0.5`). The `ScheduleFingerprint`
  rejects divergence: `beta_midstate != kernel_beta_midstate` raises ValueError.
  Device-backed equivalence (midstate kernel vs reference kernel, and vs
  hashlib) is verified by `test_midstate_kernel_matches_reference_and_hashlib`
  and `test_opencl_midstate_vs_reference_kernel` in `tests/test_hash_pipeline.py`,
  plus the `BitcoinHasher.__init__` self-check.
- Timestamp anomalies pause and revalidate work; they never increase work or
  claim an advantage.
- No literature estimate is a measured device result, pool acceptance, hashrate,
  or proof that a quantum adversary changes the 51% threshold.

## Explicitly out of scope

`NonceRegionTracker` substrate (distribution-based nonce allocation per the
Big Step classical analogue) is intentionally out of scope for this PR. Tracked
as follow-up in PR #10 review follow-up.
