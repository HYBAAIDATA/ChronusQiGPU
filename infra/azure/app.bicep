// Chronusv2 API (Dockerfile; docker-compose.yml service "chronus-api", port 8000)
// as a container web app on an EXISTING Linux App Service plan, running an image
// from an EXISTING Azure Container Registry (admin user enabled).
//
// Deployed by infra/azure/deploy_app.sh, from azure-pipelines.yml (deploy=true) or
// by hand. The app is closed to the internet: only the listed address ranges may
// call it. It is a single-process reference service with a local SQLite file that
// does not survive replacement (docs/system-update/azure-deployment.md); it is not
// a production deployment.

@description('Name of the Chronusv2 web app (globally unique).')
param webAppName string

@description('Existing Linux App Service plan that hosts the app.')
param planName string

@description('Existing Azure Container Registry that holds the image (admin user enabled).')
param registryName string

@description('Image repository in the registry.')
param imageRepository string = 'chronusv'

@description('Image tag to run (the pipeline uses its build id).')
param imageTag string

@secure()
@description('CHRONUS_TENANT_TOKENS: JSON object mapping tenant id to API token.')
param tenantTokensJson string

@secure()
@description('CHRONUS_JWT_SECRET: HMAC key for the tokens the service issues and accepts.')
param jwtSecret string

@description('Address ranges allowed to call the app, comma-separated CIDR. Empty: nobody.')
param allowedIpCidr string = ''

resource plan 'Microsoft.Web/serverfarms@2023-12-01' existing = {
  name: planName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

var allowedRanges = empty(allowedIpCidr) ? [] : split(allowedIpCidr, ',')
var allowRules = [for (cidr, i) in allowedRanges: {
  name: 'allowed-range-${i}'
  action: 'Allow'
  priority: 100 + i
  ipAddress: trim(cidr)
}]

resource site 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: plan.location
  kind: 'app,linux'
  tags: {
    workload: 'chronusv2'
    environment: 'demo'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'DOCKER|${registry.properties.loginServer}/${imageRepository}:${imageTag}'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      healthCheckPath: '/health/ready'
      ipSecurityRestrictionsDefaultAction: 'Deny'
      ipSecurityRestrictions: allowRules
      scmIpSecurityRestrictionsUseMain: false
      scmIpSecurityRestrictionsDefaultAction: 'Deny'
      appSettings: [
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          // Keep the SQLite file on the container's local disk, never on the
          // shared /home (SMB) storage (docs/system-update/azure-deployment.md).
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${registry.properties.loginServer}'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_USERNAME'
          value: registry.listCredentials().username
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_PASSWORD'
          value: registry.listCredentials().passwords[0].value
        }
        {
          name: 'CHRONUS_TENANT_TOKENS'
          value: tenantTokensJson
        }
        {
          name: 'CHRONUS_JWT_SECRET'
          value: jwtSecret
        }
      ]
    }
  }
}

output defaultHostName string = site.properties.defaultHostName
