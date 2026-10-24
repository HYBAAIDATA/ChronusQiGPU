# Integrated live wiring: scoped execution evidence

## Release verdict

**Not production- or publication-qualified.** This report closes specific integration defects; it does not replace whole-repository, all-offering, Docker, performance, or external accepted-share qualification.

## Implemented repairs

- Bridge-free mining now supplies real normalized Stratum observations to TOE. It does not invent a 64-byte vault observation. Source `stratum_job` and node sentinel `-1` are explicitly digest-bound; hardware observations retain their separate contract.
- TOE inference runs off the Stratum event loop. Results that complete after an identity change are discarded.
- `intelligence.require_toe` is an explicit strict-boolean runtime policy. Required TOE blocks dispatch/precompute without a valid current frame. Plans queued before the requirement cannot borrow later TOE provenance.
- Recovery rebinding clears prior TOE context, frame, and signal.
- Correct the TOE purity-confidence boundary for at most eight machine ulps, preserving raw purity and the correction in diagnostics; genuinely invalid purity remains unavailable.
- Distinguish von Neumann density entropy from Born-distribution measurement entropy. A broad pure state must not trip a mixedness safety signal merely because measurement outcomes are distributed.
- The independent Chronus batch bootstrap dispatches a complete 600-assignment logical topology wave when configuration permits. Configured upper bounds and safety derating still take precedence.
- Hendrix exact-count dispatch is not an M32 kernel epoch. Its coprime/bijection certificate remains required. M32 alignment checks remain unchanged for M32.
- Canonical explicit-batch leases use exact counts rather than padding 600 to 608; legacy M32 leases keep padding. Overlap, identity, freshness, terminal-state, and independent proof checks remain enforced.
- Docker context now preserves the hash-verified mandatory structural corpus and manifest while excluding other mutable artifacts. Missing corpus caused an actual isolated deployment startup failure; it was not bypassed by disabling training.

## External-pool observation

`integrated-live-observation.json` records the actual observed completion, with source-manifest revision, plan/execution IDs and TOE frame references:

- Braiins authorized the real supplied worker and sent live jobs.
- Strict custody and AL HARAS authorization were enabled using a locally provisioned owner-delegated deployment, fresh private keys and bounded tenant admission. This is not an externally issued entitlement or third-party attestation.
- Live submission was enabled and bound to the configured pool identity; no share submission or pool acceptance is established by this capture.
- The retained causal records join a real TOE observation to a plan with 600 nonempty logical shards, 600 assigned nonces, and a `COMPLETE` 600-hash `chronus_batch` execution.
- The executor was `chronus-software-fabric`. No 600-device physical parallelism, quantum speedup, solved preimage, or achieved 10 EH/s is claimed.
- Heartbeat and causal records have different publication times; this is not an atomic multi-source snapshot.

## Continued observation exposed another deployment limit

After the complete wave, the underlying custody plane reached its default 64 MiB tenant quota. Recording failed closed. The outer admitted storage quota was 1,000,000,000 bytes, but the underlying custody override had not been configured. The explicit custody limits were then aligned with that already admitted bound without deleting failed-run records. Restart reconciliation and long-duration retention/capacity remain separate operational gates; increasing a bounded quota is not a retention solution.

The earlier failed isolated deployment, quota failures, and successful completion must all be retained. A successful short interval does not erase later failures.

## Qualification

- Latest focused production-entry/integration qualification: **60 passed**. The production entry tests use an explicitly controlled local Stratum pool; its accepted response is not external pool acceptance.
- Affected lease, agentic, TOE and static Docker-corpus regression suite: **129 passed** (overlapping coverage; do not sum suite counts).
- Changed Python source passes Ruff E9/F checks.
- Docker engine is unavailable on the agent host; static packaging checks are not a built or running container.
- Full TOE product release qualification, all enterprise offerings, independent performance advantage, dedicated MMIO Salamander, sustained retention, and external accepted shares remain open.

## Evidence integrity

The live source ran from a separate copied deployment tree with a content manifest, not an actively edited checkout. Private environments, pool credentials, integrity keys and local signing keys are excluded from public evidence. Checksums permit integrity checking relative to a captured manifest; they are not independent witnesses or pool-signed proofs.
