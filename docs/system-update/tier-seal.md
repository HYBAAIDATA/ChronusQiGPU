# Tier seal and measured qualification

## External posture

Customer-visible surfaces (API, product console, sealed error messages) expose
**behavior only**:

- `tier` — measured convergence class (`TIER_GEOMETRIC` | `TIER_POLYNOMIAL` | `TIER_STATISTICAL`)
- `envelope` — max residual as a function of input size
- `qualification_evidence_hash` — hash of the qualification transcript
- `tier_contract_version` — envelope contract version

When asked how scaling works, the external answer is:

> tier class is assigned by measured convergence behavior under our qualification harness

Legacy workload wire name `LUCAS_PV_SCALING` is accepted on ingress and emitted
as `scaling.v1`.

## Internal posture

Audit transcripts and the claim registry keep full provenance (mechanism
identities, probe family, cross-checks). The seal is one-way: audit wins
internally; seal wins externally.

## CI

`scripts/ci/check_mechanism_seal.py` fails the build if banned mechanism tokens
appear on product external surfaces (`frontend/app|components|lib`,
`src/chronus/service`, `console`).
