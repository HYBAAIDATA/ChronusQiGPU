# Sovereign and enterprise readiness position — 12 October 2026

Scope: the products assigned to sovereign and enterprise duty — **CHRONUS**
(compute runtime), **THESEUS** (custody and storage, package
`hyba-theseus-storage`, code in `aethel/`) and **OVID** (data organisation,
package `hyba-ovid-data-organisation`, code in `hyba_db/`) — supported by
**Salamander** (outcome evidence), **Kellogg** (tensor mathematics) and
**TURING** (release verification). Deployment target: **Docker first**. Azure
follows after the Docker proof is green.

Branch: `sovereign-readiness` (based on `production-readiness`, PR #1).
Nothing here is on `main`.

## Bottom line

| Question | Position |
|---|---|
| Can the products run inside an air-gapped boundary with evidence? | **Yes, demonstrated in-process.** The proof pack refuses real egress, DNS, cloud storage and external ingestion. It runs THESEUS, OVID and CHRONUS on local storage, signs an attestation, and detects every tamper attempt (local run, commit `fcd92ec2`). |
| Has that proof run in Docker on an isolated network? | **Not yet.** The CI step exists, but GitHub Actions jobs are not starting because of an account billing hold. There is no Docker in the review sandbox. |
| Can we begin sovereign conversations? | **Yes, as an evaluation or design-partner pilot**, once the Docker proof is green in CI and the pack can be handed over. |
| Can we sign production sovereign contracts? | **Not yet.** Durability and isolation findings R03–R08 are open, Salamander's 12 gates are not qualified, CHRONUS is not certified, and nothing is published to a registry. |
| Accreditation (e.g. government security schemes)? | **None held or claimed.** |

## What changed in this pass (code, not documents)

| Criticism | Answer now | Where |
|---|---|---|
| "Air-gapped" was only a declared flag | Enforced at runtime: `HYBA_SOVEREIGN_MODE=air_gapped` installs a Python audit hook (PEP 578). It refuses socket connect, sendto and name lookups outside a non-global allowlist, and refuses cloud object storage and external ingestion. An invalid configuration refuses to start (exit 78). | `al_haras/sovereign_control.py`, `main.py` |
| Workers could escape the boundary | Supervised workers run through `python -m al_haras.sovereign_exec`. In sovereign mode the supervisor refuses to spawn an unbounded worker. | `al_haras/sovereign_exec.py`, `control_api.py` |
| Show denied external ingestion and cloud storage events | Every denial is recorded in the AL HARAS hash chain with kind, target, reason and role, and exported as `denied_events.json`. | proof pack |
| Exported tamper-evident audit chain | `audit.jsonl` is exported, and `verification.json` reports the first broken record. Five tamper attempts are all detected: edit, delete, truncate, a full re-hash without the key, and forged attestation counts. | `tamper_tests.json` |
| Air-gapped attestation | HMAC-SHA256 signed attestation of the policy digest, build commit, denial counts and the audit head hash. `python -m al_haras.sovereign_control verify` checks it offline. | `attestation.json` |
| "The hook is not network isolation" | Agreed, and it is reported separately. A child interpreter without the hook probes the network itself. `--require-network-isolation` fails the pack if any route out exists. The local sandbox has internet, and the pack correctly reported it as **REACHABLE**. | `network_probe.json` |
| Docker | `docker-compose.sovereign.yml` runs the proof on an `internal: true` network, with no mining service and no Stratum identity. The CI smoke job runs the same pack in the smoke image on `docker network create --internal`. | compose file, `azure-package.yml` |

Local proof run (no network isolation, `--skip-network-probe`): all 12
boundary and product checks pass. That covers loopback allowed; TCP, UDP, DNS,
HTTPS (urllib), asyncio, s3://, az://, gs:// and https ingestion refused; a
local storage path admitted; THESEUS put/restart/get; OVID write and
`verify_database`; a CHRONUS workload committed to THESEUS custody; and worker
egress refused into the same chain. Only the deliberate attempts appear as
denials. None of the products tried to reach the network on its own.

Tests: `tests/test_sovereign_control.py`, 20 tests. Enforcement runs in child
processes because audit hooks cannot be removed.

## Honest limits of the boundary

- The audit hook bounds **Python-level** network and storage use. Native code
  that calls libc `connect` directly (C extensions, ctypes) is not seen by it.
  The network layer — the Docker internal network, and later Azure private
  networking — is the real isolation, which is why it is probed and reported
  separately.
- The attestation is **symmetric** (HMAC). The holder of the key can verify it
  but not prove it to a third party. Asymmetric or hardware-rooted signing is
  future work.
- The 70-point sovereign checklist suggested in the external assessment has
  **not** been produced. This document is the evidence matrix that exists
  today.

## Evidence matrix

| Component | Role | Artifact verified | Tests | Production qualified | Open items |
|---|---|---|---|---|---|
| CHRONUS (iGPU) | compute | VERIFIED at 8aef16bf (wheel rebuilt and installed in isolation) | sovereign workload passes; 7 failing in `test_chronus_native_batch_route.py`, plus `test_chronus_namespace` | **No** — `RELEASE_STATUS` NOT_CERTIFIED, `publishable: false` | R07 cross-tenant virtual-memory handle overwrite |
| THESEUS | custody/storage | PASS | 249 source tests; 17 tenant-isolation tests (R02 fixed) | No | R01, R03 sealed commit boundary, R04 journal tail repair, R05 cross-process checks outside the lock, R06 fsync/readiness, R08 residency metadata only |
| OVID | data organisation | PASS | 119 tests; 5 graph-edge integrity tests (R09 fixed) | No | R01 ownership inverted, R10 numeric/quota bounds |
| Salamander | outcome evidence | artifact verified | — | **No** — `unqualified_readiness()` reports all 12 gates UNAVAILABLE | its outcome verifier is mining-specific; it needs a non-mining verifier before it can support sovereign duty |
| Kellogg | tensor maths | VERIFIED | — | No registry publication | — |
| TURING | release verification | PASS against Kellogg | — | No registry publication | — |
| Triad claims | — | — | — | — | R11: durability claims overstated; R12 fixed (vacuous assertions removed) |

Portfolio release audit (`packaging/portfolio_release_audit.py`): every
product is BLOCKED or at most QUALIFIED. There is no registry publication.

## Blockers, in order

1. **CI billing hold (owner only).** GitHub Actions refuses to start jobs:
   "recent account payments have failed or your spending limit needs to be
   increased". Until this is cleared, no CI evidence — including the Docker
   sovereign proof — can be produced.
2. **Run the Docker sovereign proof** (the CI step, or
   `docker compose -f docker-compose.sovereign.yml run --rm sovereign-proof`)
   and keep the pack plus key as the first buyer-facing evidence.
3. **Close THESEUS and OVID durability and isolation findings R03–R06, R08 and
   R01**, then **R07** in CHRONUS and **R10**. Rewrite the R11 claims to match
   the evidence.
4. **Salamander**: a non-mining outcome verifier, and real gate evidence
   instead of hard-coded UNAVAILABLE.
5. **CHRONUS certification** and registry publication for all six packages.
6. **Repo gates**: 12 of 14 pass on `fcd92ec2`. `privileged-path-audit` needs
   the owner's `MEDIATION_MANIFEST_KEY`. `conformance-vectors` is SKIP because
   fewer than two exact backends are available here. Both predate this work.
7. **Known failing tests outside this pass**: 13 in
   `tests/test_organism_integration.py` (CHRONUS/TURING/Salamander/THESEUS
   integration), 7 in `tests/test_production_api_contract.py`, 2 in
   `test_asi_core` and 1 in `test_toe_package`.

## What may be said to buyers

May say:

- In air-gapped mode the products enforce an egress, storage and ingestion
  boundary at runtime, record every refusal in a tamper-evident chain, and
  produce a signed attestation that can be verified offline.
- THESEUS, OVID and CHRONUS operate entirely on local storage inside that
  boundary.
- Each release artifact is rebuilt and verified from source by TURING.

Must not say:

- Any accreditation, certification or "sovereign approved" status.
- That the Docker or Azure deployment has been proven isolated, until the CI
  proof pack is green.
- That custody is crash-durable across all failure modes (R03–R06 are open).
- Any mining revenue, hash-rate or production hashing claim. The Docker smoke
  test executed 0 hashes because no MLA1517 device was attached.
