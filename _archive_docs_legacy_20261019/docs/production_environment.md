# Production environment: configuration before launch

`.github/workflows/production.yml` is manual-only and explicitly does not launch
services, connect to pools or storage, or enable live submission. It validates the
canonical runtime configuration and publishes a value-free report. `CONFIGURED`
is not proof of deployment, valid credentials, connectivity, writable storage,
hardware availability, or live mining. No long-running runtime belongs in this
GitHub-hosted preflight job.

## GitHub environment inputs

The workflow references the `production` environment from the provisioning
handoff. Confirm that this is the intended environment and its approval rules
before dispatching. Repository configuration does not prove that it exists or
that values have been provisioned.

Environment secrets:

- `VIABTC_USER`, `VIABTC_PASSWORD`
- `BRAIINS_USER`, `BRAIINS_PASSWORD`
- `EUCLID_ADMIN_API_KEY`
- `PYTHIA_STORAGE_INTEGRITY_KEY_HEX` (at least 32 bytes encoded as hex)
- `PYTHIA_STORAGE_CUSTODY_KEY_HEX` (at least 32 bytes encoded as hex)
- `PYTHIA_M3_AL_HARAS_TOKEN`

Environment variables (non-secret configuration):

- `PYTHIA_STORAGE_DB` (absolute path on the eventual runtime host)
- `PYTHIA_STORAGE_ROOT` (absolute path)
- `PYTHIA_STORAGE_CUSTODY_ROOT` (absolute path)
- `PYTHIA_STORAGE_TENANT`
- `PYTHIA_M3_ACTOR`

Secret values stay out of command arguments, logs, reports, and commits. The
workflow maps the original pool secret names to `MLA1517_*` variables consumed by
the runtime, with ViaBTC primary and Braiins failover. Endpoints still come from
the pool catalog unless the deployment overrides the canonical endpoint settings.
The user's real `PYTHIA.001` worker is no longer misclassified as a placeholder;
other example identities remain rejected. Pool authorization must still confirm
that it is a real account/worker. This change does not relax consensus, M3,
control authentication, or live-submit approval.

## Storage scope

The existing canonical stack expects THESEUS/M3 storage paths, integrity/custody
keys, tenancy and AL HARAS authorization. Do not map a PostgreSQL hostname to
`PYTHIA_STORAGE_DB`, which is a path. The proposed `PHYLAXIS_DB_*` and
`PHYLAXIS_STORAGE_*` external-service adapter is not implemented by this change.
It needs the intended backend/API, real endpoints and a reviewed integration.
The preflight rejects populated `PHYLAXIS_*` variables when invoked locally
instead of silently asserting that they are wired.

## Validation and launch sequence

1. Provision the inputs above using the approved secret manager or GitHub UI.
2. Dispatch `Production environment preflight (no mining)` and review its report.
3. Install project/substrate dependencies on the dedicated runtime host using
   `bash scripts/ci_install.sh "dev"`; plain `pip install -e .` does not stage all
   in-tree substrate distributions.
4. Set canonical environment values securely, with workers disabled initially.
   Run existing offline behavioral tests and
   `python scripts/production_preflight.py --profile application --strict`.
5. Start the installed API entrypoint `pythia-api --host 127.0.0.1 --port 8080` on
   that host. Do not pass unsupported pool/DB/storage CLI flags. Verify health,
   authentication, storage reconciliation and metrics with real host evidence.
6. Complete device and live preflight on the intended host; they require the
   actual device, strict M3 configuration and identity-bound approval. Keep live
   submission disabled until operator approval is recorded.
7. Demonstrate storage writes/readback, monitoring, memory/performance metrics and
   restart/recovery before production promotion. Do not infer success from CI
   configuration checks.

## Rollback

Stop supervised workers and disable live submission through the governed control
path, restore the previously qualified package/configuration, and verify health
and custody reconciliation before restarting. Revert this PR to remove its
preflight and worker-name correction; it does not mutate deployed state or data.
