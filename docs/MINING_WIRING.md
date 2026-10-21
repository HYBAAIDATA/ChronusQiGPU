# Mining wiring — observed edges, missing joins, and qualification

Base source: `4f71b5647e5cacd053e9a9d545ab5f26d38b4f34`.
Runtime candidate: `80fe0d413255c45b910da4599e4d276bc9098321`.
Implementation review: [draft PR #128](https://github.com/PhiEnterprise1/EuclidPhiEnterprise/pull/128).

**Production/publication HOLD.** This map does not turn parallel entrypoints into one verified deployment. HYBA products remain enterprise-first; mining is an optional governed workload. TOE is domain-general, not a mining-specific reasoning fork.

## Entrypoint distinction

- `mining/production_miner.py` has its own Stratum V1 loop and direct/AETHEL/scaled executor selection. Its name alone does not establish that it is the deployed canonical miner.
- `mining/__init__.py` identifies `chronus/mla1517_platform` as the canonical production boundary. `chronus/mla1517/mining/coordinator.py` wraps that platform with leases, measured optimisation and recovery authority.
- `Intelligence/agentic_mining.py` explicitly says **research/simulation lifecycle — not the production miner** and names the TypeScript server as its production reference. Its local phase-four target checks do not transmit pool shares. This lineage/entrypoint distinction is unresolved, not evidence that all three are serially wired.
- `salamander/runtime.py` is an observing supervisor bridge, not a second recovery actuator. No new network/pool writer was introduced.

## Edge inventory

`UNAVAILABLE` means no common durable/service receipt was established for that edge. A request ID, local hash or certificate is not silently upgraded to the five-field tenant-bound TOE service receipt.

| Caller → callee | Actual payload/result | Fail-closed boundary | Identity / receipt | Evidence scope |
| --- | --- | --- | --- | --- |
| production `run` → `StratumV1Client.connect_and_authorize` | endpoint, worker/password; subscribe result and boolean auth | invalid subscribe/auth/protocol errors; live-submit environment gates unchanged | JSON-RPC integer request ID; durable receipt UNAVAILABLE | localhost socket fixture only |
| `ProductionMiner._run_session` → `build_job_header` / `stratum_bridge.build_header80` | MiningJob, extranonces → 80-byte header | malformed fields/length rejected | job ID + local generation; durable receipt UNAVAILABLE | source + new fixture tests |
| `_run_session` → `strict_quantum.certify_work_window` / `verify_certificate` | header prefix, base nonce, count → exact work-window certificate | certificate rejection raises ProtocolError | certificate in execution metadata; not a pool validity certificate | existing software path; no hardware claim |
| `_run_session` → executor `execute` | header, negotiated target, base, bounded count → winner/digest/hash count/metadata | one in-flight worker; cancellation drains call; no second session on same instance | metadata; no universal service receipt supplied | new event-loop/cancellation tests |
| scaled adapter → Hendrix scheduler / FourLayerMiningStack | disjoint scheduled nonce order, header/fold/target → measured hash result | scale/memory/fold/digest/provenance checks | schedule and implementation digests in execution receipt | caller test blocked by missing exported TURING core; no device qualification |
| scaled adapter → `TOESystem.record_decision` | preparation/error/completion context → hash-linked provenance | `verify_provenance()` required | `TOEProvenanceRecord.provenance_hash` / prev_hash | local provenance, not tenant-bound CIAAS receipt |
| miner candidate → independent SHA256d → `client.submit` | exact header+winner; target check; mining.submit params → pool boolean | independent digest/target recheck; superseded generation rejected | job generation + RPC response; pool outcome recorded by actual response only | stale-target rejection tested; real pool acceptance not exercised |
| Chronus `_refresh_work_identity` → agentic controller | canonical subscription/session/job/target → WorkIdentity; bind/clear | missing subscription/session/job/target or identity mismatch disables leased work | session/generation/fingerprint; causal coordinates | source trace; full canonical caller rerun still blocked |
| Chronus observation → TOEMiningAdapter → decision frame/signal | job + real vault state/node/sequence → context, causal signal, face/throttle guidance | absence only for explicitly permitted operations; forbidden consensus vocabulary rejected | boundary token (`TOE-BND-...` on violation), decision evidence | source trace; consensus suite collection blocked in export |
| Chronus → ClosedLoopOptimizer | measured completed windows, route/rate and bounded trial → selected window | locked while healer active; no inferred reward | optimisation history/events; independent outcome verification not implied | real optimizer in fixture tests; no four-hour deployment proof |
| Chronus identity mismatch → SalamanderMiningHealer → RecoveryGovernor | diagnosis and allow-listed callbacks → actual dispatch and ACK | governor required; authorization denial/missing dependency/incomplete dispatch cannot ACK success; safety lock remains | one canonical recovery_id shared by ACK and audit | new real-governor fixture tests, not live failover |
| healer post-observe → targeted governor observation → evidence ledger → resume | identity/target/lease snapshot → recovery audit + ExecutionRecord → matching work rebind | missing/active leases or changed generation/fingerprint prevent healthy resume; no unlock before rebind | recovery_id + evidence_sha256; measured elapsed time | seven-stage fixture, no hardware or custody certificate |
| MiningAutonomyBridge → local durable evidence mirror / optional outcome verifier | measured snapshot and reported recovery/optimisation events | no independent verifier → UNAVAILABLE, not self-certified recovery | local hash-chain evidence; LOCAL_MIRROR_NOT_CANONICAL_THESEUS | source review, not canonical custody acceptance |
| Intelligence agentic research lifecycle → TOESystem | six research phases and local precomputed candidate checks | research status preserved; cannot confer pool acknowledgement | local provenance records | research edge only; live join NOT QUALIFIED |

## Changes in this candidate

1. `production_miner.py:425`: negotiated-target changes advance work generation. Stale candidates are rejected before submission, rather than sharing the current generation with a replaced target.
2. `production_miner.py:492–528`: a single dedicated worker executes each hash window outside the asyncio reader loop. Awaited cancellation drains that native call before teardown; it does not kill a wedged driver. Optional scaled imports are deferred until that mode is selected.
3. `mining_healer.py:294`: the governor dispatches real callbacks rather than no-op labels followed by out-of-band mutation. The optimizer safety inhibit remains on denial. Missing governor/adapter/generation/action completion is an error, not an ACK.
4. `mining_healer.py:387`: lease clearance is actually observed; missing observation is not `True`.
5. `recovery_authority.py:269`: an optional recovery_id scopes healthy observation; a healed identity must not verify unrelated open recoveries or clear unrelated fault state.
6. `mining_healer.py:432,546`: elapsed time is measured, not fixed at 1 ms; unlocking follows matching-generation/fingerprint rebind. Resume avoids recursively calling the healer via `_refresh_work_identity`.

## Explicitly unclosed joins

- No live canonical Stratum/regtest recovery + governor + healer + optimizer end-to-end drill. The new TCP fixture tests the separate V1 client and window isolation, not that combined chain.
- No production difficulty-jump trigger/precedence proof. The current healer observation still does not compute a difficulty-jump ratio; its existing recovery path is identity-mismatch driven.
- No held-out TOE/Hendrix/geodesic ordering-lift result. SHA256d remains sole local validity judge and pool ACK remains external. No speedup or yield is inferred from ordering or certificates.
- No direct join from the standalone V1 miner to the Chronus governor/supervisor established in this review. Do not create a second governor or pool writer to make a diagram appear connected.
- The mining Gate F JSON remains a synthetic numeric scaffold with operator sign-off PENDING, not a real telemetry/anomaly/drift qualification pack.
- Redis/shared multi-process quotas, deployed TLS/identity/limits, metrics/SLO alerting, canonical THESEUS custody/audit export, restore/rollback and legal/operator approvals remain unqualified. Redis/container/SLA work is explicitly deferred here, not accepted as an authorised production waiver.

## Reproduction

See [closeout report](production/MINING_CLOSEOUT_20261020.md) and [logs, manifests and JUnit](../release-evidence/mining-closeout-20261020/). All local tests avoid paid workflows/mainnet and use unique basetemps with `-p no:cacheprovider`. Full Gate A and installed-package/hardware qualification require a complete source/dependency closure.
