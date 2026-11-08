# Chronus web console

This Next.js application is an evidence-first product preview, not a production-qualified multi-tenant control plane. Legacy views contained simulated telemetry, hard-coded performance numbers, and unsupported compliance or hardware claims. Those views have been replaced or quarantined; remaining functionality is not release-qualified.

## Run locally

Requirements: Node.js 20.9+ and pnpm.

```bash
pnpm install --frozen-lockfile
```

Set `CHRONUS_BACKEND_URL` in the frontend service environment to the base URL of a Chronus API instance, then start the app:

```bash
pnpm dev
```

The web proxy forwards API requests to the configured URL. If the variable is unset or the service is unreachable, the UI reports that explicitly; it does not substitute mock operational success. The workload page accepts a bearer token at request time and does not store it.

## Evidence and release posture

- The overview reads `/health/ready`. A successful readiness probe is not a product, security, compliance, performance, or production-capacity qualification.
- Workload results are shown from API responses. Native reference execution and associated records may be process-local; do not use this preview with sensitive production payloads.
- Receipt verification reports only the verifier's result. It is not a release gate or external certification.
- Tenant, connector, hardware, benchmark, and policy claims require independent implementation review and reproducible evidence before being described as production capabilities.

## Build

```bash
pnpm build
```
