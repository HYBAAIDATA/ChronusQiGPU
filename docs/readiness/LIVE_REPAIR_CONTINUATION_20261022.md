# Live repair continuation — 2026-10-22

Status: **NOT production-qualified; NOT publication-approved.** This record is a
bounded continuation of the live system validation, not an all-offerings sign-off.

## Implemented repairs

- Custody authenticates each replica once per read, retaining HMAC, schema,
  tenant, path, digest and reconstruction checks on every read. No cross-read
  trust cache was introduced. Lease reconciliation starts its interval after
  completion, avoiding a slow full reconciliation starving every subsequent lease.
- Validation custody no longer uses the historical public signing key. It requires
  a private key and explicit signer, bounds and records subprocess failures,
  authenticates logs and source inventory, verifies source stability, and publishes
  atomically. Local HMAC custody is not independent attestation.
- Chronus virtual memory persists top-level binary payloads losslessly with an
  explicit codec and type-separated content identity. Unsupported payloads are
  rejected instead of silently stringified; caller-owned input and metadata are
  detached. Physical device transfers still require a real bound adapter.
- Tensor import no longer eagerly loads canonical mining integrations. The triad
  names its ordering lemma explicitly rather than relying on an ambiguous choice.
- Skill admission revalidates mutable graft files on each admission. Tampered or
  retired grafts are not re-enabled by rewriting their pinned manifests. Whole
  organism and repository-review fixtures now provide explicit scoped authority.
- TOE learning now emits the tenant-bound receipt required by CIaaS, binding the
  episode and actual observations to the actual learning report. Oversize learning
  requests are rejected before model mutation. A receipt does not imply durable
  persistence: unbound THESEUS remains explicitly unavailable.

## Executed validation

Separate regression selections, not an aggregate full-suite result:

| Selection | Result |
| --- | --- |
| Custody/replay/encoding/recovery/lease timing | 84 passed |
| Authorized whole-organism integration and restore | 23 passed |
| Skill admission, repository review, capability fabric, publication custody | 83 passed |
| Tensor/virtual-memory/triad/product contracts | 67 passed |
| Expanded TOE runtime, learning, custody and HTTP closeout | 105 passed |
| TOE receipt and virtual-iGPU targeted tests | 37 passed |
| Standalone enterprise packaging tests | 8 passed |
| Previously outstanding 96 regression nodes, rerun after repairs | 49 failed, 47 passed |

The packaging tests include a committed synthetic fixture and are not a release
artifact qualification of this owner-supplied source ZIP. The source ZIP has no
Git checkout identity; no commit identity was invented for it.

## Observed live execution

The isolated deployed snapshot `source-manifest-sha256:a4c2eccd9843a568e091a1a42816a96a5fa84ca35de947c7d4d3f75fdbcc8dd4`
produced 12 complete, TOE-linked 600-work waves by 14:57:58 UTC: 7,200 measured
hashes with strict custody and local Guardian authorization. Both readiness
probes returned HTTP 200. This is real external Braiins job execution on the
software `chronus_batch` route, not a physical-GPU throughput claim.

Seven abandoned custody write intents were recovered using authenticated existing
records and explicit offline recovery; reconciliation and mining-chain checks
then passed. Earlier failures and observations are retained rather than replaced.

## Open qualification gates

- The latest 96-node outstanding-regression selection still has 49 failures,
  including API contract drift, reference-only compatibility paths, missing
  external benchmark data, product boundary checks and checkout provenance.
  This selection is not an exhaustive list of all possible defects.
- No accepted external pool share or automatic failover outcome is established.
- No Docker engine, Docker socket or physical GPU device is available on this
  agent host; Docker and hardware acceleration qualification remain unexecuted.
- The 10 EH/s configuration is a ceiling, not demonstrated throughput. A
  600-coordinate software solver is not proof of 600 physical execution units
  or a measured quantum advantage.
- The local operator-signed validation authorization is time-limited and does
  not prove an external commercial entitlement.

Release remains blocked until the remaining gates are exercised and pass on the
intended target. Readiness is a scoped dependency probe, not release approval.

## Restart follow-up

A restart onto the second repair snapshot exposed a remaining scalability defect:
`TheseusPhysicalStore.verify` reparsed the entire address journal for each file.
A live stack capture identified this path; readiness correctly returned 503 while
startup verification was incomplete. The previous 200 observations are historical,
not a claim about this restart.

Reconciliation now uses one journal-membership snapshot scoped to one pass.
Per-object tenant, digest, mathematical address and both-replica checks remain
active. File identity/size/mtime/ctime are checked during and at the end of the
pass; journal mutation aborts verification. The validator cannot be reused after
the pass and no journal cache survives to the next pass. Mining health also reuses
one current lineage verdict within its result, instead of recomputing it twice.
The expanded batch/fault/tenant/recovery/registry selection passed 69 tests.

The standalone Kellogg benchmark is now explicitly scoped to the tensor core.
All modules are still attempted. The four declared consumer integration modules
remain visibly unavailable when their Chronus/TOE dependencies are blocked;
unrelated adapter exceptions and undeclared core dependency violations still fail
the gate. The product suite passed 48 tests and the scope/adversarial checks passed
3 tests. This is not a claim that consumer adapters run without their dependencies.

Fresh independent Braiins and ViaBTC protocol sessions authenticated and received
80-byte-header jobs at 15:10:55 UTC. Neither session submitted a share; these are
connection checks, not failover or pool-acceptance evidence.

## Final observations for this continuation

The final outstanding-regression rerun on the repaired tree completed with
**48 failed, 48 passed** (96 previously outstanding nodes; not the full root
suite). Remaining failures are retained in the audit bundle. No all-green claim
is made.

Snapshot `source-manifest-sha256:1b7732ef0f81cba2b7a08dcad25335e9d31a82e6375f4cdc3aa6b1ba64f0a46d`
executed fresh TOE-linked complete 600-work waves after the batch repair.
Both strict readiness endpoints returned HTTP 200 with `ready: true`. The last
restart's offline custody check found zero pending intents, passed reconciliation
and database verification, and verified the mining chain. Raw heartbeat counters
and causal-event counts are captured independently and need not be synchronized.

Docker was not simply assumed unavailable: official Docker 28.5.1 tooling was
installed into an isolated validation directory, an isolated daemon started,
and the real `hello-world` image was pulled. Container startup failed because
the process namespace lacked the matching `/proc` view; mounting a private
`/proc` was then denied by this host (`Operation not permitted`). This does not
qualify the application container, its image build, its Compose profile or its
GPU behavior. The temporary validation daemon was stopped. An appropriate
Docker-capable target is still needed; no host security requirement was disabled.

The continuation is tracked separately from merged PR #134 in draft PR #138.
The integration token cannot read Actions check runs (HTTP 403); no CI verdict
is inferred from pushing commits or opening the draft pull request.
