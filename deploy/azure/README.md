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
   `environmentName`, `registryName`, `image`, `storageBindingName`, `tenantId`,
   `clientId`, `clientSecret`, and `operatorObjectIds`. Keep `externalIngress=false`
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
code revision, a durable local POSIX filesystem, and TLS pool connectivity. Live runtime
requires `MLA1517_MMIO_DEVICE`, Stratum identity, `PYTHIA_BITCOIN_RPC_URL`, either
`PYTHIA_BITCOIN_RPC_AUTH` or `PYTHIA_BITCOIN_RPC_COOKIE`, and
`PYTHIA_MINING_SESSION_PATH`. Remote RPC must use HTTPS. Protect pool/node credentials
and back up the session; removing it can remove the external-block safety history.

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
