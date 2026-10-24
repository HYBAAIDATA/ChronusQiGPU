# HYBA backend evidence remediation

## Scope and release posture

This change targets **PhiEnterprise1/EuclidPhiEnterprise**, baseline
`75ece7ed9d66aad22c3e2564e85cb62b00fc8dfb`. It does not modify or deploy the
separate AI Studio repository. This repository's production control surface is
`chronus/mla1517_platform/python/control_api.py`, not the AI Studio TypeScript
`Landing_Page/artifacts/api-server/src` tree.

**Release posture: HARDENING_VERIFIED_MINING_WITHHELD.** A unit-test fixture
satisfying a predicate is not evidence that real hardware or a pool is active.
This review branch is not a deployment certificate or a completed R1–R7 release.

## Implemented contracts

- R1: one conservative status predicate also drives `/ready-to-mine`. Physical
  hardware, a live ready worker, enabled submission, a connected authorized pool,
  an accepted pool response younger than 300 seconds, accepted shares, canonical
  readiness and a non-emulated measured device receipt are all required. Missing
  or NOT_RUN evidence withholds the certificate. CPU/logical substrate is not
  physical iGPU proof. No speedup is claimed.
- R2: boot-measured immutable elevation snapshot, deterministic digest, retained
  last-good document on refresh failure. Initial measurement failure is explicitly
  UNVERIFIED/NOT_RUN, never a fabricated VERIFIED document or a 404. Mode A is
  **CPU reference arithmetic**, not a measured Chronus GPU benchmark: 3,000
  Zeckendorf roundtrips, Cassini identity at eight canonical rungs per seed, two
  SHA-256 reference vectors and the 80-byte Genesis #0 header. Timing changes on
  reboot; reads of one boot snapshot have identical digests.
- R3: secrets-mapped HttpOnly sessions, CSRF Origin checks, founder-only enterprise
  mutations, separate approver role, five-minute single-use request-bound grants,
  allowlisted pool metadata, bounded configuration and no-hardware disarmed/503
  storage. Legacy guardian mediation is retained, including on v1 start/stop
  aliases. Direct legacy configuration cannot enable submission; config changes
  revoke live intent. Endpoint allowlists are checked again before canonical
  start. Target observation revokes submission and stops workers before auditing.
- R4: backend treasury overview returns null values with OFFLINE when no observer
  exists. Withdraw requires founder plus independent request-bound approval and
  fails 503 without an HSM/TPM signer. No client key/signature is accepted. There
  is no installed treasury signing or wallet-observation adapter in this change.
- R5: detected corrupt custody sides are retained under a SHA-256/HMAC incident
  manifest, marked SEV-1, and access is latched closed. Existing missing-replica
  recovery remains separate. No automatic quarantine clear or re-seal API exists.
  Manual quorum recovery must retain the incident and create a new generation.
  PostgreSQL integration remains DESIGN ONLY. This is not proof of a 10-of-12
  drive drill, GRF2/database roundtrip, or external recovery ceremony.
- R6: explicit exact release-rung validator distinct from legacy capacity
  multiples; stride is ordering-only, saves_hashes=False. Heuristics are labelled
  search heuristic / telemetry, not proof. Health and elevation expose that
  boundary. Zero-allocation tensor execution remains NOT_RUN. No authority is
  transferred to a VQC by this adapter. The requested independent 12/12, 6/6 and
  9/9 suites have not been run or relabelled as this focused test suite.
- R7: Decimal cost accounting with 25% positive verified-gain share and a zero-fee
  gate; only receipt-backed verified rows from a canonical customer adapter enter
  summary accounting. The installed adapter currently reports no ledger, so the
  endpoints remain OFFLINE with no fabricated customers or savings. Authenticated
  evidence export verifies every manifest-listed byte before creating a ZIP.

JSON responses include Route and observation/provenance fields. Unknown rates
and devices are null/not_observed, not invented measurements. Mutation receipts
carry audit_hash; if audit is unavailable, execution is refused and the refusal
explicitly reports unavailable audit evidence. ZIP is a binary response carrying
X-Content-SHA256, not a JSON response. External reverse-proxy path routing is not
changed or tested by these Python routes.

## Deployment requirements — no default credentials

Use the deployment secret store, not source files or frontend environment values:

- `HYBA_PUBLIC_ORIGIN`: the exact public **HTTPS origin**, without a path. Same
  origin frontend deployment is required; no permissive CORS fallback is added.
- `HYBA_AUTH_PRINCIPALS_JSON`: JSON mapping principal IDs to
  `{ "role": "founder_ceo" | "approver" | "operator", "token_sha256": "<64 hex>" }`.
  Tokens must be independently generated high-entropy operator credentials, not
  human passwords. SHA-256 here verifies bearer entropy, not a password KDF.
  Founder and approver must be distinct people and separately issued credentials.
- `HYBA_AUDIT_HMAC_KEY`: at least 32 random bytes, hex encoded. Keep stable across
  restarts and protected separately from the database. Rotation requires an
  explicit audit migration; a new key must not silently bless the old chain.
- `HYBA_ENTERPRISE_STATE`: durable private deployment-owned directory, preferably
  an absolute path. Never a shared or attacker-writable directory.
- Existing canonical pool environment secrets, identity binding, hardware
  qualification and `PYTHIA_M3_REQUIRED=1` admission remain mandatory. New cookies
  do not replace an AL HARAS subscription or its bearer/tenant/actor checks.

The __Host-hyba_session cookie is Secure, HttpOnly, SameSite=Strict, Path=/,
with a one-hour session bound to the current secrets mapping. Sessions and grants
are in-memory; restart invalidates them. Secret-map changes invalidate sessions.
No operator bearer is persisted in JavaScript storage. Guardian subscription
credentials remain a separate existing browser boundary; do not place pool,
wallet, or signing secrets in the frontend.

HMAC chaining detects record edits and sequence gaps. **Whole-database rollback
or suffix truncation still requires an external retained head anchor**; this
patch does not claim WORM/HSM audit custody. Back up the private database and
anchor heads using the deployment's existing external authority before relying
on it as a regulatory retention control.

## Operator journey

1. POST `/api/auth/login` with `{principal_id,credential}` over HTTPS. Use Origin
   matching HYBA_PUBLIC_ORIGIN and retain the cookie. GET `/api/auth/me` confirms
   the server-assigned role. Logout is POST `/api/auth/logout` with the same Origin.
2. GET `/api/mining/pools` returns only poolId/label/region/feeNote inside `pools`;
   hostnames and passwords stay in the server catalog/secret store.
3. Founder POST `/api/mining/configure` with `{poolId,hashrate_hps,shares_target}`,
   the cookie, guardian subscription headers and guardian `observation`. The
   target is an integer 1..10000 and rate is bounded. No hardware saves a zero-rate
   disarmed configuration and returns 503 NO_ATTACHED_MINING_HARDWARE.
4. An independently authenticated approver POSTs `/api/approvals` with
   `{action:"mining.start",request_digest:<config_digest returned by configure>}`.
   Founder POSTs `/api/mining/start` with `{approval_id}` and guardian observation.
   Config changes invalidate the grant. A grant is single-use and expires in five
   minutes. 202 START_REQUESTED is **not** ACTIVE mining proof.
5. The target observer accumulates accepted-share deltas across counter resets.
   When the target is reached it disables live intent, stops workers and emits
   MINING_AUTO_DISARM. Restart with a governed policy disarms before monitoring.
6. Withdrawal grant action is `treasury.withdraw`; the digest is SHA-256 of
   compact sorted-key UTF-8 JSON `{amount,destination,network}`. Founder supplies
   the same fields and approval_id. Without an installed signer it returns 503,
   even with valid dual authorization. No client signature/private key field is
   accepted. No funds are moved by this review branch.
7. GET `/api/evidence/pack` as founder exports the current UTC date directory
   beneath evidence/. DIGESTS.json format is `{ "files": { "relative/path":
   "<sha256>" } }`. Only listed files are exported, at most 256 files and 32 MiB.
   Symlinks, traversal, missing files and mismatches are rejected. Compare the
   downloaded ZIP hash with X-Content-SHA256, then check each file against DIGESTS.

The control-session form uses real login/logout. A complete dual-approval UI,
customer provisioning workflow and treasury view are not supplied by this patch;
use the documented API journey until the dedicated UI exists. The old start
button cannot bypass an absent approval; the backend refuses it.

## Validation and promotion checklist

Run the new workflow against a full checkout without isolated imports. Locally:

```
python -m unittest discover -s tests -p test_hyba_enterprise_remediation.py -v
```

`HYBA_ISOLATED_HANDLER_TEST=1` is an explicit partial-checkout test mode, stubbing
only boot imports system_fabric, autonomous_supervisor and al_haras_pythia. The
HTTP handler, runtime configuration, pool catalog, exact arithmetic and enterprise
contracts remain real source. Hardware/pool/treasury service adapters in those
HTTP tests are explicitly labelled fixtures. This mode is not a production boot,
full guardian integration, frontend build, or live yield measurement.

Before merge/promotion require:

- Full-checkout CI and the existing control, guardian, runtime, custody, OVID,
  golden-fold, Chronus and offline Stratum regression suites. Review old tests
  expecting silent corruption healing against the new explicit quarantine policy.
- Frontend typecheck/build and browser journey; scan the **built bundle**, not
  merely selected source files, for fake offsets and leaked pool secrets.
- External proxy probes for /healthz and /ready-to-mine, authenticated API journey
  and three identical elevation digests on the deployed Git version.
- Real silicon, fresh accepted pool ACK, positive accepted shares and ready=200
  before permitting ACTIVE; no simulated substitute.
- Installed canonical customer ledger, treasury observer, independently governed
  HSM/TPM signing and externally anchored audit chain before financial release.
- Quorum-authorized custody recovery, 10-of-12 drills, database exactness and
  zero-allocation/authority proof suites with their actual logs and counts.

Never convert any of these missing external gates into a green badge.
