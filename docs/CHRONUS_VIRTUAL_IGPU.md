# Chronus Virtual iGPU

Chronus Virtual iGPU is the product. Intel UHD, CUDA, ROCm, oneAPI, Metal,
OpenCL, Azure and Google Cloud are execution adapters. The canonical source
lives in PYTHIPhiMiner and is forked downstream into UnifiedEnterprise after
its ABI and evidence tests pass.

## Boundaries

- Kellogg owns tensor mathematics.
- Aethel and `HybaSubstrate` own fold custody, placement and persistence.
- Chronus owns admission, negotiation, scheduling, execution and evidence.
- Mining owns SHA256d truth and pool acknowledgement.

## Start

```bash
python -m chronus.virtual_igpu --store .chronus-virtual-igpu
```

Set `CHRONUS_VIGPU_TOKEN` to require bearer authentication. Use
`--require-hardware --no-emulator` when software execution is forbidden; the
daemon fails to start when no physical adapter is available.

## Protocol

Protocol: `virtual_igpu_v1`, JSON over HTTP.

- `GET /health`
- `GET /v1/adapters`
- `GET /v1/capabilities`
- `POST /v1/workloads`
- `GET /v1/workloads/{id}`
- `GET /v1/evidence`
- `GET /v1/attestation`

Every response is `{ "ok": true, "value": ... }` or
`{ "ok": false, "error": ... }`.

## Transaction

```text
validate ABI
→ admit deadline/quota
→ negotiate healthy capability
→ attest negotiation
→ execute selected adapter
→ verify result digest and attestation
→ persist through HybaSubstrate/Aethel
→ write content-addressed evidence
→ return result
```

No successful result is returned before persistence. Duplicate workload IDs,
expired deadlines, quota violations, absent capabilities, adapter errors,
digest failures and storage failures all fail closed.

## Adapter status

The CPU emulator is the deterministic executable reference. The Intel UHD
adapter wraps the measured OpenCL implementation from PRs #94/#95 and is
selected by identity and capability, not index. CUDA, ROCm, oneAPI, Metal,
other OpenCL vendors, Azure and Google Cloud have explicit adapter identities
and report unavailable until configured; they never simulate successful
execution.

This is an MVP truth boundary, not a claim that every declared adapter already
has a production kernel. Adapter health and capabilities are authoritative.