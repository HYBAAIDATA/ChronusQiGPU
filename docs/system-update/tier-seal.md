# Tier seal and measured qualification

## External posture

Customer-visible surfaces (API, product console, sealed error messages) expose
**behavior only**:

- `tier` — measured convergence class (`TIER_GEOMETRIC` | `TIER_POLYNOMIAL` | `TIER_STATISTICAL`)
- `envelope` — max residual as a function of input size
- `qualification_evidence_hash` — hash of the qualification transcript
- `tier_contract_version` — envelope contract version
- `qualification_scope` — currently `reference_model_class` (class-level harness
  measurement; not a claim that the selected execution backend was re-probed
  for that submission)

When asked how scaling works, the external answer is:

> tier class is assigned by measured convergence behavior under our qualification harness

Legacy workload wire name for the scaling class is accepted on ingress and
emitted as `scaling.v1`. Scaling execution results on the API are rewritten to
sealed keys (`family`, `sequence_value`, `companion_value`); mechanism names
are not customer-visible. Envelope bounds are scoped to
`discrete_probe_sizes` only.

## Internal posture

Audit transcripts and the claim registry keep full provenance (mechanism
identities, probe family, cross-checks). The seal is one-way: audit wins
internally; seal wins externally. Process-local transcript storage supports
re-verify on subsequent class attachments; envelope breach suspends the tier.
Transcript signatures use process-local Ed25519 (not durable key custody).

## CI

`scripts/ci/check_mechanism_seal.py` fails the build if banned mechanism tokens
appear on product external surfaces (`frontend/app|components|lib`,
`src/chronus/service`, `console`).
