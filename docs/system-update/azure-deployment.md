# Azure deployment foundation

## What is delivered

`infra/azure/main.bicep` declares a resource-group-scoped foundation: Azure Container Registry, a user-assigned managed identity with registry pull and Key Vault secret-read roles, Key Vault with RBAC and purge protection, Log Analytics, workspace-based Application Insights, and Key Vault audit diagnostics. The template creates **no application, GPU, database, network isolation, backup policy, or regional failover**. The image is a single-process reference service, not a sovereign production deployment.

No Azure resources were provisioned by this change: the working environment did not contain Azure CLI credentials or a subscription context. Creating these resources incurs ongoing charges. Purge protection prevents immediate deletion of the Key Vault after it is created.

## Provision in an authorized subscription

The operator needs the Azure CLI with Bicep, permission to deploy the resource types and create role assignments, an existing resource group, and an approved region. For a UAE deployment, `uaenorth` is an example, not a guarantee of data residency or service availability. Review costs and organizational Azure Policy first.

```bash
az login
az account set --subscription '<subscription-id>'
az deployment group validate --resource-group '<resource-group>' \
  --template-file infra/azure/main.bicep \
  --parameters location=uaenorth environment=dev
az deployment group what-if --resource-group '<resource-group>' \
  --template-file infra/azure/main.bicep \
  --parameters location=uaenorth environment=dev
az deployment group create --resource-group '<resource-group>' \
  --template-file infra/azure/main.bicep \
  --parameters location=uaenorth environment=dev
```

The resource prefix must be lowercase alphanumeric, 2–12 characters. Registry and vault names include a deterministic subscription/resource-group suffix. Azure policies, resource-provider registration, naming availability, regional SKU support, and role permissions must be checked in the target subscription.

## Optional GitHub Actions deployment

The `Azure foundation deployment` workflow is manual only. Configure a GitHub environment named `azure-foundation` with appropriate required reviewers, and configure GitHub OIDC federation on an Azure identity whose subject is `repo:hybadatadevops1/Chronusv2:environment:azure-foundation`. Set environment secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID`. Grant the identity deployment permissions including resource-scoped role assignment creation. The workflow performs Azure validation and what-if immediately before deployment; environment approval occurs before these steps, so independently review the what-if output before dispatch if approval of the exact change set is required.

## Runtime limitations

The container uses a single worker, a non-root identity, and a SQLite file under `/var/lib/chronus`. Its filesystem is ephemeral unless a suitable persistent local filesystem is mounted. A container restart retains a container's writable layer, but replacement, scale-out, and failover do not. **Do not mount the SQLite database on Azure Files/SMB and assume distributed locking or high availability.** Process-local Ed25519 keys and receipts do not survive restart. There is no provisioning, rotation, or managed-identity retrieval of tenant tokens in the service. The template's Key Vault and registry currently allow public network endpoints; RBAC is not a substitute for private networking. Application Insights is provisioned but the service is not yet instrumented to send traces to it.

Production deployment needs a reviewed topology, shared transactional storage, durable signing-key and receipt custody, managed identity/secret integration, private ingress/egress, image provenance and scanning, backups and recovery, observability and alerting, and workload-specific security and performance validation. Sovereign requirements must be assessed for each customer and jurisdiction.

## CI evidence scope

CI checks Python 3.10–3.12 tests and coverage, scoped active-code lint and compilation, package build, dependency audit, medium/high-confidence static security findings, Bicep compilation, and a container HTTP/restart smoke test. These are engineering checks—not independent certification, a complete security assessment, release qualification, or proof of hardware execution. The manual Azure workflow is not an application deployment.
