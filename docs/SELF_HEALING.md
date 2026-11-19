# Self-healing: what exists, what is on, what is not

Status as of 2026-11-18. This page is the source of truth for self-healing
claims in this repository. Anything not listed under "Implemented" is not
implemented.

## Implemented and on by default

### THESEUS durable storage self-healing (`chronus.storage.self_heal`)

- **Where it runs:** `DurableTheseusService` (SQLite custody), and so the
  `ProductionTriad` (Chronus-OVID-THESEUS) read and open paths.
- **How it works:** every stored object gets a Reed-Solomon parity sidecar
  (systematic RS(48, 32) over GF(257), table `object_parity`). When a payload
  fails its SHA-256 content address, at open time (`verify_store`) or on read
  (`reconstruct`), the store corrects it from parity. The repair is accepted
  only if the corrected bytes hash to the content address. It is then written
  back, and a `REPAIRED` row goes into `self_heal_events`. Failed attempts are
  recorded as `UNREPAIRABLE` and the store fails closed exactly as before.
  A sidecar whose digest or scheme/dimensions fail verification is never used
  for repair. It is rebuilt from the verified payload (`PARITY_REGENERATED`),
  even if the size limit has since been lowered. A repeated identical failure
  is recorded once.
- **Bounds:** up to 8 corrupted bytes per 32-byte block. It does not repair a
  changed length, metadata/journal rows, SQLite page corruption
  (`PRAGMA integrity_check` still fails closed), or a lost database or disk.
  Parity sits in the same file, so this is not a replacement for replication
  or backups.
- **Configuration:**
  - `CHRONUS_SELF_HEALING=1|0` (default `1`). `0` restores strict fail-closed
    behaviour with no parity written.
  - `CHRONUS_SELF_HEALING_MAX_BYTES` (default `262144`, capped at 1 MiB, the encoder limit). Larger objects get no
    parity, because encoding is pure Python (about 0.2 s per 256 KiB).
  - `DurableTheseusService(path, self_healing=False)` overrides per instance.
- **Visibility:** `DurableTheseusService.evidence()["self_healing"]` and
  `self_heal_events()`. `ProductionTriad.production_posture()` includes it.
- **Existing databases:** the new tables are created on open, so this is
  additive. Objects written before this change get parity the next time the
  same content is stored. Until then they have no parity and fail closed.
- **Tests:** `tests/test_self_healing.py` injects faults straight into the
  SQLite file and checks repair on reopen and on read, fail-closed beyond the
  bound and on a length change, parity tampering, disabled mode, the size
  bound, and the production triad through a storage fault.

### Other implemented repair primitives (explicit calls, not automatic)

- `chronus.security.al_haras.reed_solomon`: RS(n, k) over GF(257) with
  Berlekamp-Welch decoding. `DSW4DInstantonMonopoleHealer`, the
  `/al-haras/heal|protect|repair` routes, `CNISelfHealingEngine` and the orbital
  mesh drill call it. "DSW instanton / monopole" is a name only; the mechanism
  is this classical code.
- `hardware_t_isa` `T_DSW_HEAL` / `scrub`: RS(24, 16) repair of the simulated
  register file.
- `chronus.storage.erasure` and `ProtectedTheseusService`
  (`ProductionTriad.protect_payload`): XOR single-erasure recovery of one
  missing or corrupt shard file. This is opt-in and only covers shard files.
- `chronus.fleet.recovery`: requeue and recovery path for faulted fleet leases.

## Named in code or docs but not a repair mechanism

- `MiningAdminEngine.execute_dsw_heal` (and the `/v1/mining/admin` heal route,
  `sdk.heal_mining_anomaly`): only clears the flag set by `inject_anomaly`.
  It now returns `"simulated": true, "repair_performed": false`.
- `DSW1CycleInstantonCobordism.heal_trace`: sets every value to the mean. It
  does not recover original values.
- `DSWInstantonSelfHealer` in `src/chronus/chronus_gpiu-v36.py` (legacy
  monolith): a no-op that always reports success. Its "I27 PASS" proves
  nothing.

## Not implemented (aspirational)

- **Salamander** as a separate remediation subsystem (bounded, authorised
  remediation and optimisation). It is not in this checkout. `hyba_mcp`
  registers no Salamander tools.
- Self-healing of metadata, journal or whole-database loss. That needs
  replication or backup restore; neither is automated here.
- Any CI "auto-repair" workflow. None exists in `.github/workflows` or
  `.agents`. CI failures are not fixed automatically.
