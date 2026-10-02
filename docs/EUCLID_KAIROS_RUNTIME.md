# EUCLID/Kairos local runtime

This package is a new, fail-closed equivalence implementation. It is not
represented as a byte-for-byte recovery of unavailable archive files. See
`euclid/recovery_manifest.json`.

## Supported surface

- `euclid.runtime.EuclidRuntime` is the only supported composition root.
- Kairos is local, deterministic and single-session.
- Evidence and checkpoints use deterministic JSON, domain-separated SHA-256
  seals, atomic replacement and owner-only file permissions.
- Learning is routed through `LearningService`, which coordinates existing
  engines. A reward is applied only when its authority is explicit.
- Organs pass CAPABLE, HEALTHY, PERMITTED, CONFIDENT and SAFE gates before
  dispatch. World integration has a separate four-gate decision.
- Creator-scoped grants can be revoked. Provider identity, modality and
  deployment must match exactly.
- Full runtime checkpoints preserve rights, world state and the shared
  evidence chain. Restore verifies both the seal and deterministic replay.
- `euclid.memory_database.MemoryDatabase` supplies scoped transactional
  working/episodic/semantic/archival memory, replay protection, tombstones,
  hash-linked events, integrity verification and online backups.
- Governed adapters expose reasoning proposals, repository status,
  self-healing proposals and bounded mining policy without granting direct
  world mutation.

## Production gates

`euclid.production_harness.run_production_gates()` verifies that networking
and federation remain disabled, organ authority remains bounded, sealed state
round-trips exactly, durable memory is configured and tampered checkpoints are
rejected.

`EuclidRuntime.production(...)` creates the local memory database under the
configured state directory. The SQLite file is owner-only where the platform
supports POSIX permissions. Application-level encryption is deliberately not
misrepresented: production deployments requiring encryption at rest must use
an encrypted volume or SQLCipher.

## Training, genetic mining and self-healing evidence

- `euclid.training_pipeline.TrainingPipeline` separates training cases from
  held-out evaluation and a null control. Its report does not claim external
  validation or general intelligence.
- `chronus.seam.genetic_mining` performs deterministic population evolution
  over dispatch geometry only. It cannot access or alter headers, targets,
  hashes, credentials or share validity.
- `euclid.self_healing_evidence` hashes protected Python trees before and
  after diagnosis. Proposal-only diagnosis passes; any mutation or applied
  repair fails the gate.
- `euclid.evidence_bundle` seals runtime, memory, training, genetic-mining and
  self-healing evidence into one fail-closed release artifact.

## Mining boundary

The existing `chronus/mla1517/mining/euclid_support.py` remains the sole
mining adapter. EUCLID may advise only HOLD, REDUCE or RESTORE for bounded
dispatch breadth. It has no authority over headers, nonce semantics, SHA-256d,
targets, credentials, share validation, submission or pool acknowledgement.

## Disabled surfaces

Federation, public network APIs, distributed persistence, multi-user Kairos,
arbitrary code execution and self-modification remain disabled. There is no
claim of AGI, consciousness, emergence, quantum advantage or production
network deployment.

## Test

```bash
python -m unittest -v tests.test_euclid_runtime
```