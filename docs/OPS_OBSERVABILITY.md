# Operational Observability — Provenance & Unavailable-Value Contract

This document is the provenance matrix for the operational observability surface
(`GET /api/v1/telemetry/ops`, schema `pythia.ops_telemetry/1`, and the
Observability view in the operator frontend). Its rule is the spec's law:
every displayed value traces to a real backend/runtime source, and anything
that is not measured renders as an explicit unavailable marker — never zero,
never a placeholder, never an optimistic default.

## Transport

| Surface | Mechanism | Notes |
| --- | --- | --- |
| `GET /api/v1/telemetry/ops` | JSON snapshot, `pythia.ops_telemetry/1` | Canonical document. Unprivileged — composed only from already-public sources so the read-only/control separation holds. |
| `GET /api/v1/telemetry/stream` | Server-Sent Events | `{type:"ops", seq, ops, new_events}` every ~1.5 s, `: keepalive`, 120-tick bounded lifetime; EventSource auto-reconnects. |
| `GET /api/v1/telemetry/history?n=&kind=` | JSON, tail of `telemetry_history.jsonl` | Persisted append-only store, rotated at 16 MB to `.1`. |
| `GET /api/v1/telemetry/causal?n=` | JSON, tail of `causal_ledger.jsonl` | The canonical causal ledger, verbatim records. |
| `GET /api/v1/telemetry/session` | JSON, `mining_session.json` | Share log, cycles, pending submissions. |
| Frontend | `useOpsTelemetry()` | SSE primary; 3 s poll fallback when the stream is unreachable; UI shows transport + age, and a stale banner when `ageMs > 9 s`. |

## Provenance matrix

| Displayed field | Source of truth | Path |
| --- | --- | --- |
| Pool lifecycle (configured → connected → subscribed → authorized → receiving work → submitting → acknowledged) | `StratumRuntimeState.snapshot()` lifecycle flags | Worker → `GET /api/v1/stratum/status` → `ops.pool` |
| Active pool, endpoint, protocol, session id, worker name (redacted `XX***`) | `IntelligentPoolCoordinator._pool_snapshot()` (`pythia.pool_topology/1`) + runtime state | Same |
| Endpoint roster, configured order, TLS flag, active marker | `_pool_snapshot().endpoints` | Same |
| Connect attempts, last error, last selection, failover history (bounded deque, 24) | Coordinator `_pool_counters` / `_pool_history`, recorded by `production_transport.connect_with_failover` | Same |
| Job id, generation, received_at, age_ms, clean_jobs | `StratumRuntimeState.snapshot().job` | Same → `ops.job` |
| prevhash, version, nbits, ntime, extranonce1/2, merkle_branch, coinb1/2 | `Job` fields exported by `snapshot()` (added this change) | Same |
| Difficulty, share target, difficulty source | Runtime state difficulty tracking (`mining.set_difficulty`) | Same |
| Share funnel (candidates verified, submitted, accepted, rejected, unknown, stale dropped) | Submission outcome counters in runtime state | Same → `ops.shares` |
| Submit RTT (last/mean/p95) | Measured round-trip on `mining.submit` | Same |
| Persisted share log (last 64) | `mining_session.json` `share_log` | `GET /api/v1/telemetry/session` → `ops.shares.session` |
| Declared vs bound vs executing substrate | `readiness`/device snapshot + measured hashrate | `ops.execution.device` / `ops.execution.hashing` |
| Measured hashrate, hashes total/in-span, span, executions | `MiningCoordinator.measured_hashing()` → `HeartbeatEmitter` → `%LOCALAPPDATA%/pythia/hb/*.metrics.json` | `ops.execution.hashing` |
| Component map (agentic-mining, discovery, salamander, autonomous-supervisor, al-haras) | Metrics heartbeats + `/api/v1/system/status`, `/api/v1/security/status` | `ops.system.workers`, `ops.security` |
| Salamander healing state | `salamander_engine` real `step()` results published under metrics key `salamander` | `ops.healing.salamander` |
| Recovery authority (mode, freezes_speculation, faulted, active_recovery_id) | `RecoveryAuthority.snapshot()` | `ops.healing.authority` |
| Stratum event stream | `StratumEventLog` (in-memory ring + persisted) | `ops.events`, `new_events` on SSE |
| Causal timeline | `causal_ledger.jsonl` verbatim tail | `GET /api/v1/telemetry/causal` |
| Hashrate/event history | `telemetry_history.jsonl` appended by worker via `TelemetryHistory` | `GET /api/v1/telemetry/history` |
| Store evidence (path, exists, size, mtime, reason) | `_file_evidence` stat of each persisted store | `ops.sources` |

## Unavailable-value rendering

The frontend renders exactly these markers, in place of the field:

- `Unavailable` — source exists but did not report the field, or the source itself is absent.
- `Not connected` / `READY`/`IDLE` etc. — the runtime state string, verbatim.
- `Not running` — worker heartbeat file absent.
- `Not measured` — no metrics heartbeat yet.
- `No current job` — runtime reports no bound job.
- `No evidence` — persisted store file does not exist (with `reason` from `_file_evidence`).
- `Waiting for telemetry` — SSE and poll both unreachable.
- `stale` banner — last successful update older than `STALE_MS` (9 s); the view keeps showing the last real payload, visibly marked stale.

## Known honest absences (as of this change)

- `extranonce` row renders `Unavailable` on Braiins when the pool assigns an
  empty extranonce1 — the field is exported; the value is genuinely empty.
- `invalidated gen` renders `Unavailable` until a clean_jobs invalidation is
  recorded.
- Share pipeline counters are real zeros under shadow/disarmed mode — submits
  are genuinely not permitted, so submitted/accepted/rejected stay `0` and
  `last result`/`submit rtt` stay `Unavailable`. Zero is only ever shown when
  the counter exists and is zero.
- `al-haras guardian` shows the evaluated gate answer (`allowed`, `reason`,
  `policy_version`) or `unavailable` when the endpoint denies without payload.
- `hashes in span`/`window` render `Unavailable` only before the first metrics
  publish (~1 s); afterwards they carry the measured values.
