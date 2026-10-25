# Azure deployment preparation

This deploys the **control application**. It does not provision or validate a mining device.
The live runtime currently requires a local MLA1517 MMIO device and a verified Bitcoin
RPC observer. The iGPU/tensor integration and a remote worker protocol are not yet release
qualified. Do not interpret HTTP health as mining readiness.

## Prerequisites and deployment

1. Use an Azure subscription/resource group with an existing Container Apps environment,
   ACR, and an environment Azure Files binding. Grant the deployment identity permission
   to assign AcrPull. Configure the file share to permit UID/GID 10001 access.
2. Register a single-tenant Entra application. Require assignment in its enterprise app;
   supply a nonempty list of operator object IDs. Set the web redirect URI to
   `https://<container-app-host>/.auth/login/aad/callback` after the internal first deployment.
   In the app registration's Authentication settings, enable **ID tokens** for implicit
   issuance — the Container Apps built-in auth flow needs them. Supply the client secret
   through a secured deployment parameter, never a committed file.
3. Build from the repository root:

   ```sh
   docker build -f deploy/azure/Dockerfile -t <registry>.azurecr.io/pythia:<commit-sha> .
   docker push <registry>.azurecr.io/pythia:<commit-sha>
   az bicep build --file deploy/azure/main.bicep
   az deployment group what-if --resource-group <group> --template-file deploy/azure/main.bicep --parameters @secure-parameters.json
   az deployment group create --resource-group <group> --template-file deploy/azure/main.bicep --parameters @secure-parameters.json
   ```

   Set `image` to `pythia@sha256:<pushed-image-digest>`. Required parameters are
   `environmentName`, `registryName`, `image`, `storageBindingName`, `stratumUser`
   (the pool worker identity; the control API refuses to boot without it), `adminApiKey`
   (the operator key every state-changing request must present, at least 32 characters:
   `openssl rand -hex 32`; without it control is closed), `tenantId`, `clientId`,
   `clientSecret`, and `operatorObjectIds`. Keep `externalIngress=false`
   for the first deployment so the app cannot become public before auth is configured.
4. Test from the environment: unauthorized requests must redirect to Entra or return
   401/403; an authenticated but unassigned identity must be denied. An assigned operator
   must be able to load the UI. Verify these before changing `externalIngress` to true.
5. Verify `/healthz`, frontend load, audit persistence across a revision restart, and
   `/api/v1/ready-to-mine` (expect mining unavailable without hardware). Keep workers and live
   submission disabled. Never horizontally scale a file-backed mining session.

Rollback by redeploying the previous immutable image digest. Back up configuration and
state before schema changes; image rollback does not undo state changes.

## Hardware worker release gate

Use a separate Linux host with the verified MMIO/OpenCL device and drivers, the same
code revision, a durable local POSIX filesystem, and TLS pool connectivity. The image
already carries the host driver (`libmla1517_mmio.so`); live runtime needs
`MLA1517_MMIO_DEVICE` (the device's register block) and the Stratum identity. Without a
node the pool's own jobs are the chain evidence; a configured `PYTHIA_BITCOIN_RPC_URL`
(HTTPS when remote) takes precedence. Protect pool/node credentials and back up the
session; removing it can remove the external-block safety history.

### Hardware Gate & Fail-Closed Rules
- **Authentication**: Control API refuses boot without `stratumUser` and `adminApiKey`.
- **Fail-Closed Mining**: When mining device (`MLA1517_MMIO_DEVICE` or OpenCL device) is absent, mining endpoints fail-closed (`/ready-to-mine` returns 503 unavailable); they NEVER silently fall back to CPU mining.
- **Horizontal Scaling Prohibited**: Horizontal scaling of file-backed mining sessions is FORBIDDEN (`minReplicas=1`, `maxReplicas=1`).
- **HTTP Health vs Mining Readiness**: `/healthz` PASS indicates control liveness only; it does NOT indicate mining readiness.

## Live smoke

`python scripts/docker_smoke.py --image <image>` runs the image as deployed against a
scripted Stratum pool, with a register block on a bind mount fed by
`scripts/smoke_vault_feeder.py`, and checks boot, the operator UI, the durable volume,
`POST /api/v1/mining/start`, the pool session, continuous vault observation and the
evidence snapshot. CI runs it on every pull request (`Azure packaging` workflow) and
publishes the stage table to the job summary and the logs as the `docker-live-smoke`
artifact. The feeder writes ABI-shaped fixtures, not MLA1517 output; the host's own
integrity checks gate them, so the smoke never hashes and never submits.

The hosted control app does **not** yet operate that separate host remotely. Do not
expose the standalone Python control API directly; its current authorization boundary
in this deployment is Container Apps authentication. Do not enable live submission
until device conformance, pool acceptance, restart/reorg handling and lifecycle tests
have passed on the actual host. No Azure deployment or hardware certification was
performed in the editing workspace.

References:
- https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2024-03-01/containerapps
- https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2024-03-01/containerapps/authconfigs
- https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull
