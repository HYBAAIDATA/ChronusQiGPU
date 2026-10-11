# Chronus First Workload — `chronus.first-workload/1`

Status: **DECLARED — owner approval delegated** (`owner_approval:
"delegated — declared by Devin under owner delegation (@bollingertm,
2026-10-06)"`). The readiness audit (`QuantumPhi2/PhiMiner` @ `1fde89ec`,
P0.1) required an owner-approved workload contract: I/O schema, success
criteria, reproduction procedure. This document is that contract; the
executor is `scripts/chronus_first_workload.py`, which emits a JSON
verdict bound to the executing commit.

## Workload definition

Chronus's workload shape is
`submit → select adapter → execute → receipt/evidence → durable ledger →
validate/replay`.

| Field | Value |
|---|---|
| `workload_id` | `chronus.first-workload/1` |
| Kind | `sha256d_scan` (bit-exact oracle — the strongest verification surface) |
| Tenant | `chronus-first-workload` |
| Policy | `standalone_software` (embedded daemon; no device claim) |
| Input | `header80_hex`: Bitcoin genesis block header (80 bytes, wire order); `start_nonce`: 2083236637 (genesis nonce − 256); `count`: 512; `target_hex`: real difficulty-1 `00000000ffff0000…0000` |
| `constraints` | `{"custody": "required"}` → THESEUS custody commit via `_commit_custody`, fail-closed |
| Expected output | `hits[0].nonce == 2083236893` (the real genesis nonce), `checked == 257`, `hits[0].hash_hex == 6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000`, `engine == "hashlib_sha256d"` |
| Verification | `receipt.verification` carries `recomputed=true`, `verifier=recompute:sha256d_scan:hashlib`, `verdict=match` — the runtime recomputes the scan without consulting the adapter before ledgering |
| Ledger | `EvidenceLedger` JSONL record (hash-chained `chain_prev`→`chain_digest`) + content-addressed evidence file `evidence/<digest>.json` where `sha256(bytes) == digest` + tenant artifact via `memory.retrieve` |
| Custody | `TheseusFileCustody` — `OperationalRecord(vigpu_execution_evidence)` committed and re-verified; run-local HMAC key, not a production credential |
| Replay | Fresh `RuntimeDaemon` over the same store re-submits the identical workload → identical `output` payload, identical `input_digest` (canonical request hash), `verdict=match`, ledger chain resumed (record n+1's `chain_prev` = record n's `chain_digest`) |

## Why this workload

`sha256d_scan` is Chronus's mining-native kind: it exercises the complete
contract surface (admission → adapter selection → execution → independent
recompute → receipt → ledger → custody → replay) with a bit-exact oracle —
the strongest possible verification claim on a software plane — and a
result anyone can reproduce with two `hashlib.sha256` calls. Scanning the
genesis nonce neighbourhood makes the outcome meaningful (it re-finds the
real block-0 hit at real difficulty-1) rather than a synthetic self-check.

## Success criteria

1. `result.status == "ok"` and the measured output equals the pinned
   `EXPECTED` table (hit nonce, `checked`, digest).
2. `receipt.verification.verdict == "match"` with `recomputed == true` —
   independent recompute ran and agreed.
3. `validate_receipt` accepts with the contract's bound identity fields
   (`workload_id`, `requested_policy`, `delivery_mode`, `actual_backend`).
4. The ledger record's `chain_digest` re-derives from `chain_prev` +
   `content_hash`; the evidence file re-digests to its filename stem; the
   tenant artifact is retrievable.
5. Custody: `metrics.custody.state == "committed"` and the executor
   re-verifies the committed `record_id` against `TheseusFileCustody`.
6. Replay: a fresh daemon produces an identical output payload and
   `input_digest`, and its ledger carries both records (chain resumed
   from disk). Attempt-level digests (`output_digest`, `evidence_digest`)
   intentionally bind wall/device timing — they differ per attempt by
   design and are not replay invariants.

## Reproduction

```
python scripts/chronus_first_workload.py --workdir <dir>
```

Exit 0 and `verdict: "pass"` in the emitted JSON. The verdict binds
`git_head`, per-stage digests, and both `output_digest` values (original +
replayed).

## Explicitly not claimed

- Hardware execution: `standalone_software` on the CPU emulator only; the
  contract asserts no device, no `hardware_rooted`, no accelerator claim.
- Custody is the THESEUS file plane with a run-local key — durable
  custody *mechanics* verified, not a deployed production custody root.
- Wire coverage: the sidecar HTTP and `mining_bridge` routes funnel
  through the same `submit` (exercised in PR #90's wire test); this
  contract exercises the embedded path.
