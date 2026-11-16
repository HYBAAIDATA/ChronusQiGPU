# Experimental PULVINI/HERMES service route — private access contract

**Status:** source implemented on PR #138, integrated on the existing
`chronus.service.routers.tensor` router included by `create_app()`.
Current-head integration tests, authenticated live deployment, release
approval and performance qualification: **UNVERIFIED**.

## Access and host requirements

The route is **disabled by default**. A deployment operator can opt it in with:

```bash
CHRONUS_PULVINI_API_ENABLED=1
```

This flag only enables the bounded reference algorithm. It is not certification
of accelerator access, physical quantum computation, production service-level
objectives, commercially meaningful speedup or signed evidence.

**Endpoint:** `POST /v1/tensor/pulvini/linear`

- Uses the existing AL HARAS `get_current_identity` boundary through
  `require_roles(DEVELOPER, TENANT_ADMIN, ADMIN, SYSTEM_ADMIN)`.
- Requires a nonempty trusted principal tenant ID; the client **does not**
  choose the tenant ID or any SQLite database path.
- Both vectors are float64, 1–4,096 elements each, exactly matching shapes.
- `depth` is an integer between 0 and 16; `alpha`/`beta` must be finite.
- No raw input is persisted or handed to the mining side. Work is performed
  in a thread pool. The bounded result is returned to the authenticated caller.
- 401 for missing/invalid Bearer credentials, 403 for role/tenant failure,
  422 for malformed or non-finite source, 503 when feature flag is absent.
- CPU/NumPy is the only demonstrated backend. Per-call `elapsed_ns` and
  retained-kernel accounting are **local software observations**.

## Example request (authorized internal development only)

```json
{
  "left": [0.5, 1.5, -2.0, 3.0],
  "right": [1.0, -2.0, 4.0, 0.5],
  "alpha": 2.0,
  "beta": -1.0,
  "depth": 3
}
```

Expected numerical `output`: `[0.0, 5.0, -8.0, 5.5]`.
Returned fields include `metrics.backend` = `numpy-reference-folded-channels`,
`physical_accelerator_measured=false`,
`net_storage_savings_measured=false`,
`source_attestation=UNVERIFIED_UNSIGNED`,
`production_qualification=UNVERIFIED`,
`raw_input_persisted=false`.

## Operator and claim authority

CHRONUS owns execution; PULVINI owns reversible fold semantics and all
retained kernels; OVID owns versioned transformation, THESEUS custody and
AL HARAS authorization. The reference route does not turn OVID into durable
custody, bypass user principal verification or claim a physical accelerator.

To certify it, execute exact-head FastAPI integration tests with a real
authorised principal, demonstrate denial of missing/insufficient roles and
cross-tenant resource access, and measure matched real workload total costs.
Do not publish the source code, mathematical kernels, proprietary dataset
bytes, private archive names, or internal mining paths to customers.
