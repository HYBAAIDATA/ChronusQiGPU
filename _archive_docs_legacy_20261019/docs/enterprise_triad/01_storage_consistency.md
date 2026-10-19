# 01 — Storage Consistency

Scope: **single root**, local filesystem primary + replica, JSONL write-ahead journal. Not multi-master WAN.

## Atomicity

- A successful `put` is atomic from the caller’s perspective: either the new generation is durable on primary **and** journal-sealed, or the operation fails with no partial visible record.
- Implementation: write journal intent → write primary temp → fsync/replace → write replica → journal seal. Incomplete journal tails are dropped on recover.

## Visibility

- Readers see only sealed generations.
- In-flight puts are invisible until seal.
- `get` after successful `put` in the same process returns the new payload (read-your-writes).

## Crash

- Crash before journal seal → recover drops incomplete tail; prior generation remains.
- Crash after primary durable but before replica → heal from primary on open.
- Crash after seal with both copies → restart recovers identical bytes (A1).

## Concurrency

- Process-local lock + file lock (`msvcrt` on Windows, `fcntl` on Unix) around mutating paths.
- Concurrent put with conflicting generation/idempotency → `ConcurrencyConflict` or idempotent replay.
- Multi-process on one root: best-effort file lock; not a distributed consensus claim.

## Idempotency

- `idempotency_key` on put: replay with same key + same content digest returns existing record.
- Same key + different digest → `ConcurrencyConflict` (fail-closed).

## Replica divergence

- Primary good, replica bad → heal replica from primary.
- Replica good, primary bad → restore primary from replica.
- Both bad / MAC fail / digest fail → `UnrecoverableCustodyError` (fail-closed).

## Heal

- `heal()` recomputes digests, verifies MAC, restores missing side, appends `custody_events`.
- Heal is custody-only; it does not re-fold via Ovid unless payload was stored pre-fold (enterprise path stores envelope bytes).

## Fail-closed

- Unknown schema version → reject.
- MAC failure → reject (no “repair by trusting plaintext”).
- Quota exceed → `ResourceExhausted` before write.
- Read-only mode → `ReadOnlyModeError` on mutating calls.
- Hook deny → no durable write.
