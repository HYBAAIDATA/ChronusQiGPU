# L-HRAS Gap Analysis

Maps the "L-HRAS: The Guardian" blueprint onto what this repository
implements (`al_haras/` subscription boundary + `l_hras/` guardian
conjunction over the `toe`/`aethel`/`kellogg` substrates), what is
tested, and what is deliberately not claimed.

## Implemented — blueprint Part → code

| Blueprint element | Module | Notes |
|---|---|---|
| Result monad + Part XIII error taxonomy | `l_hras/result.py` | Every operator returns `Ok`/`Err` with a typed code; refusals are values, not exceptions. |
| Explicit inputs/outputs | `l_hras/types.py` | `Request`, `Response`, `TrustRoot`, `PolicyBundle`, `ThreatModel`, `SSOConfig`, adversary classes, `signed_request`. |
| Config schema + provenance (Part III, TP1) | `l_hras/config.py` + `config.example.toml` | `validate_config` fails closed when any threshold lacks provenance; `load_config` returns `Result`. |
| Substrate boundary | `l_hras/substrates.py` | Every `CONSUME:` over `toe`/`aethel`/`kellogg` lives here — the only repo coupling point (lift-ready). |
| Attestation / Merkle chain (Part XI) | `l_hras/attestation.py` | `Attester`, composite Merkle root, `attest_compose`. |
| Aethel certificate store (Part XI) | `l_hras/store.py` | `aethel_write` — Zeckendorf-folded blocks at Fibonacci indices, Cassini quadruple verified per write. |
| 11D fold + Zeckendorf certificate (Part XI) | `l_hras/fold.py` | Klein→Poincaré round-trip with `fold_tolerance`. |
| Six intelligences (Part VIII) | `l_hras/intelligences.py` | Entangled in F4 over the substrate operators. |
| Five modes + swarm (Part VII) | `l_hras/modes.py` | Multiply / Entangle / Swarm / Honey_Pot / Willow_Expose. |
| Seven topologies (Part IX) | `l_hras/topologies.py` | Poincaré, P-vs-NP, Yang–Mills, Riemann, BSD, Hodge, Navier–Stokes evaluators. |
| Detection plane (Part X) | `l_hras/detection.py` | Anomaly, purity gate, throttle, adversary tracking/escalation. |
| SIEM/SOAR/TI/SSO/policy engine (Part XII) | `l_hras/integration.py` | Emission skeletons — see "Not established" for receipts. |
| Compliance / break-glass / audit (Part XII) | `l_hras/governance.py` | Break-glass policy, compliance mappings, audit log. |
| Metrics/health/alerts/monitors (Part XII) | `l_hras/observability.py` | In-process registries; export to OTel is not wired. |
| Code/config integrity, witness mode (Part XII) | `l_hras/selfdefense.py` | Self-attestation of config and code digests. |
| Federation (Part XII) | `l_hras/federation.py` | `federate`/`share_threat`/`tenant_isolate` primitives. |
| initialize/stand/respond (Parts IV–VI) | `l_hras/guardian.py` | `respond()` = attestation → policy → detection → five modes → six intelligences → seven topologies → fold → certificate → aethel write → verdict. |
| Claims register + invariant catalog (XIV–XV) | `l_hras/claims.py` | Every claim names its operator and test. |
| Deployment entry (Part XVII) | `l_hras/run.py` | `python -m l_hras.run --config config.toml`. |

## Integration into the AL HARAS boundary (this PR)

`al_haras/runtime.py`: when `AL_HARAS_ENABLE_LHRAS=true` and
`AL_HARAS_LHRAS_CONFIG` points at a valid config.toml, every request that
passes subscription admission is additionally evaluated through
`l_hras.guardian.respond`. The request must carry
`lhras_attestation = {token, payload_digest}` signed under the L-HRAS
trust root; the digest is rebound server-side against the reconstructed
request (a signature over a mismatched digest refuses as
`FORGERY_DETECTED`). Any `Err` or disallowed response becomes a 403
verdict carrying the error code, recorded on the audit chain as
`LHRAS:<code>`. A misconfigured/absent config fails closed — the API
returns 503, not a silently weaker guardian.

## Test coverage — what exists and what is missing

| Dimension | Status | Where |
|---|---|---|
| Blueprint property/invariant matrix | **Present** | `tests/test_l_hras.py` — the Part XVI matrix verbatim (104 tests). |
| Adversarial cases | **Present** | Forgery, unsigned/malformed attestation, break-glass abuse, replay `jti`, per-class topology bounds. |
| Unit (per module) | **Present** | `tests/test_l_hras.py`, `tests/test_al_haras.py`. |
| Integration (boundary → verdict → ledger) | **Present** | `tests/test_al_haras.py`, `tests/test_al_haras_pythia_wiring.py`. |
| End-to-end vertical slice | **Present** | `scripts/lhras_vertical_slice.py` — one command, clean checkout, emits an evidence pack. |
| Reproducible benchmark harness | **Present** | `scripts/lhras_benchmark.py` — fixed workload, named baselines, trials + CI95, JSON report. |
| Independent/third-party execution | **Not established** | All evidence is developer-run; no red-team reproduction yet. |
| Real SIEM/SOAR/TI/SSO receipts | **Not established** | `integration.py` emits structured events; no Splunk/Okta/CrowdStrike/ServiceNow round-trip is demonstrated. |
| Hardware (MLA1517) validation | **Not established** | All measurements are native-Python; physical execution pending. |
| Ablation study (Fibonacci/Cassini/Zeckendorf vs. conventional) | **Not established** | Required to justify the unusual primitives. |
| Fail-closed blast-radius analysis | **Partial** | Documented per-component; no production outage modelling. |

## Measured numbers on this host (benchmark harness output)

From `scripts/lhras_benchmark.py` (Windows dev host, in-memory audit —
`audit_durable: false`):

| Path | mean | p95 | ops/s |
|---|---|---|---|
| Raw HMAC verify (baseline) | 0.0024 ms | 0.0024 ms | ~417k |
| Plain JSONL append (baseline) | 0.050 ms | 0.097 ms | ~20k |
| Entitlement verify | 0.014 ms | 0.020 ms | ~71k |
| Full boundary evaluate | 0.055 ms | 0.067 ms | ~18k |
| L-HRAS `respond()` conjunction | ~2.47 s | ~2.97 s | ~0.4 |
| `initialize()+stand()` cold start | ~19 ms | ~20 ms | ~52 |

Interpretation, stated narrowly: the subscription boundary adds ~5.8× a
bare HMAC check and ~273× a dict policy lookup — tens of microseconds, a
negligible gate tax. The Guardian conjunction is the expensive stage at
~2.5 s/request on this host — the cost profile is dominated by the
counterfactual and topology evaluators. It is a **decision-time control
plane**, not a per-packet filter; positioning it as inline request
filtering would be a dishonest claim.

## Fixes carried from the review (this PR)

- Unauthenticated boundary denials write to a volatile in-memory chain —
  the durable ledger cannot be flooded by unauthenticated traffic.
- Durable appends are O(1): tail-only verification under the exclusive
  lock; full-chain verify happens at construction.
- Corrupt spools quarantine to `<file>.corrupt-<ts>` and resume on a fresh
  chain whose first record is `audit_quarantined`.
- Windows hosts degrade to in-memory audit and report
  `audit_durable: false` instead of dropping connections.
- Signature-first entitlement verification (no claim-probing oracle),
  optional `jti` replay protection, provider exception names no longer
  leak into `reason`.
- `al_haras_gateway.ts` renamed `authenticated` → `resonance_valid`; the
  legacy test script's broken import and "AUTHENTICATION SUCCESS" wording
  corrected.

## Not established — honest boundaries

- **Hardware verification / TPM / SGX**: none; attestation is software
  HMAC under configured keys.
- **WORM storage**: the JSONL spool is hash-chained append-only, not
  immutable storage; export to customer-controlled evidence storage.
- **Cross-instance replay**: `jti` registry is per-process; production
  needs a shared nonce store.
- **Independent red-team reproduction**: developer-executed only.
- **Production SIEM/SOAR/SSO receipts**: emitters exist; no live
  third-party integration is demonstrated.
- **Certification**: no FIPS/Common Criteria/pentest claims.
- **"Fail closed" blast radius**: refusing is cheap; the operational cost
  of a refusal storm in a revenue path is not modelled.
