# PYTHIA client handover audit

> **Superseded (2026-09-28).** This is a dated record. `mining/production_miner.py`, which it audits, was retired to `legacy/`; the canonical miner is `mla1517_platform_v3.4/python` (see `docs/PRODUCTION_MINING_RUNBOOK.md`).

**Scope:** `PHIDATA2/PYTHIA`, production Stratum V1 path, branch
`production/stratum-mining-hardening`.

**Audit posture:** evidence-led. Static implementation contracts are now green; live operational evidence remains a separate gate. A repository implementation, a mock-pool
acceptance, and a real pool acceptance are three different claims. This audit
does not convert one into another.

## Executive finding

The production workflow is implemented in `mining/production_miner.py` and is
traceable end to end:

```text
runtime-only pool configuration
  -> endpoint parsing and TLS selection
  -> TCP/TLS connect
  -> mining.subscribe
  -> mining.authorize
  -> set_target / set_difficulty
  -> mining.notify
  -> extranonce2 allocation
  -> coinbase and Merkle reconstruction
  -> exact 80-byte header
  -> AETHEL store -> Tensor fold -> TURING nonce schedule -> iGPU/OpenCL SHA-256d search
  -> independent target check
  -> stale-job check
  -> mining.submit
  -> pool boolean acknowledgement
  -> accepted/rejected counter
```

The local mock-pool contract is covered by
`tests/test_production_miner.py`. Import usage, required calls, offline network isolation,
Genesis hashing, header construction, target conversion, and CPU search are audited by
`scripts/audit_production_contracts.py`. The real-pool acceptance contract remains an
operational gate and is not evidenced by source code alone.

## Log and evidence review

The committed `logs/` tree contains only the `logs/profile/` directory; there
are no committed Stratum session logs, benchmark JSON results, accepted-share
receipts, or pool response records to inspect. Therefore the repository does
not currently prove that ViaBTC or Braiins has accepted a live share.

The handover evidence pack must contain redacted runtime output showing:

```text
Stratum authorized
Job received
Hasher backend=opencl
Share result accepted=True
```

Do not commit passwords, extranonce values, full worker secrets, or private
pool identifiers to the evidence pack.

## Contract audit

| Contract | Implementation | Evidence | Status |
|---|---|---|---|
| Secret isolation | Runtime `PYTHIA_POOL_SPECS`; no credentials in Git | Static review | Green |
| Endpoint parsing | `parse_endpoint` | Unit test | Green |
| TLS selection | `stratum+ssl` / `stratum+tls` | Unit test; live TLS still pending | Amber |
| Subscribe | `StratumV1Client.connect_and_authorize` | Mock-pool test | Green |
| Authorize | Correlated JSON-RPC response with `result == true` | Mock-pool test | Green |
| Difficulty/target | Exact integer target conversion | Unit test | Green |
| Extranonce update | `mining.set_extranonce` invalidates current job | Code path + audit | Green |
| Job validation | Nine-field `mining.notify` parser | Code path | Green |
| Coinbase/Merkle | Deterministic reconstruction | Header/vector tests | Amber until pool fixture |
| Header | Exact 80-byte serialization | Length gate + existing vectors | Green |
| Hashing | AETHEL/Tensor/TURING/iGPU adapter -> `HashPipeline` -> independent digest recheck | Existing vectors + adapter wiring + independent digest recheck | Green in code; host run pending |
| Target acceptance | Device result rechecked by hashlib | Hasher implementation | Green |
| Stale jobs | Generation comparison before submit | Code path | Green |
| Submission | `mining.submit` only after proof gate | Code path | Green |
| Pool acknowledgement | Only `result == true` increments accepted | Code path | Green |
| Reconnect | Ordered pool failover and backoff | Code path | Amber until forced-failure test |
| Runtime health | Logs/counters | No committed runtime evidence | Amber |
| Real accepted share | ViaBTC/Braiins response | Not yet captured | Red |

## Canonical versus legacy paths

The repository contains more than one mining surface. The handover operator must
use only:

```bash
python -m mining.production_miner
```

The older `mining_runtime.py` / MMIO coordinator remains a separate hardware
integration path. Its `submit_record` contract deliberately refuses to treat a
raw MLA1517 state record as a valid standard-pool proof without a negotiated
algorithm adapter. It must not be reported as equivalent to the new nonce-search
path.

The older `scripts/live_miner.py` path must not be used for the handover run
until it is either retired or brought under the same production client and
safety gates.

## Mandatory handover run

1. Run `python scripts/audit_production_contracts.py`; require JSON `status: green`.
2. Run the offline benchmark with `--backend opencl` and archive its JSON output.
3. Run the complete repository CI and focused production tests.
4. Run a two-minute dry run against the configured primary pool.
5. Confirm `authorized`, `job received`, and non-zero measured device work.
6. Enable live submission only through the approval environment gate.
7. Run with ViaBTC primary and Braiins secondary failover.
8. Capture at least one real `result: true` response.
9. Force a disconnect and confirm the next pool is attempted.
10. Confirm a stale job is never submitted after a new generation arrives.
11. Redact secrets and archive the final evidence with commit SHA, timestamp,
    endpoint label, backend, device identity, accepted/rejected counts, and
    exit reason.

## Sign-off rule

The client handover status is **implementation complete / production evidence
pending** until a real pool acceptance receipt exists. The system must not be
labelled `mining successfully` on the basis of the mock test, a hashrate number,
or a connected socket alone.
