// The two docker-compose.yml services of Chronus_Redux as container web apps on an
// EXISTING Linux App Service plan, running images from an EXISTING Azure Container
// Registry (admin user enabled):
//   api - Dockerfile, port 8000 (compose service "api")
//   web - frontend/Dockerfile, port 3000 (compose service "web"), which reaches the
//         api through CHRONUS_BACKEND_URL as in docker-compose.yml.
//
// Deployed by infra/azure/deploy_app.sh, from azure-pipelines.yml (deploy=true) or by
// hand. Both apps are closed to the internet: only the listed address ranges may call
// them, and the api also accepts the web app through its network integration subnet.
// The api is a single-process reference service with a local SQLite file that does not
// survive replacement (docs/system-update/azure-deployment.md); this is a demo
// deployment, not a production one.

@description('Name of the api web app (globally unique).')
param apiAppName string

@description('Name of the web console app (globally unique).')
param webAppName string

@description('Existing Linux App Service plan that hosts both apps.')
param planName string

@description('Existing Azure Container Registry that holds the images (admin user enabled).')
param registryName string

@description('Image repository of the api in the registry.')
param apiImageRepository string = 'chronus-redux-api'

@description('Image repository of the web console in the registry.')
param webImageRepository string = 'chronus-redux-web'

@description('Image tag to run for both apps (the pipeline uses the commit id).')
param imageTag string

@secure()
@description('CHRONUS_TENANT_TOKENS: JSON object mapping tenant id to API token.')
param tenantTokensJson string

@secure()
@description('CHRONUS_JWT_SECRET: HMAC key for the tokens the api issues and accepts.')
param jwtSecret string

@description('Address ranges allowed to call both apps, comma-separated CIDR. Empty: nobody.')
param allowedIpCidr string = ''

@description('Existing subnet (delegated to Microsoft.Web/serverFarms, Microsoft.Web service endpoint) the web console joins to reach the api. Empty: no integration.')
param integrationSubnetId string = ''

resource plan 'Microsoft.Web/serverfarms@2023-12-01' existing = {
  name: planName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

var tags = {
  workload: 'chronus-redux'
  environment: 'demo'
}
var allowedRanges = empty(allowedIpCidr) ? [] : split(allowedIpCidr, ',')
var allowRules = [for (cidr, i) in allowedRanges: {
  name: 'allowed-range-${i}'
  action: 'Allow'
  priority: 100 + i
  ipAddress: trim(cidr)
}]
var webConsoleRule = empty(integrationSubnetId) ? [] : [
  {
    name: 'web-console'
    action: 'Allow'
    priority: 90
    vnetSubnetResourceId: integrationSubnetId
  }
]
var registrySettings = [
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
]

resource api 'Microsoft.Web/sites@2023-12-01' = {
  name: apiAppName
  location: plan.location
  kind: 'app,linux,container'
  tags: tags
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: 'DOCKER|${registry.properties.loginServer}/${apiImageRepository}:${imageTag}'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      healthCheckPath: '/health/ready'
      ipSecurityRestrictionsDefaultAction: 'Deny'
      ipSecurityRestrictions: concat(webConsoleRule, allowRules)
      scmIpSecurityRestrictionsUseMain: false
      scmIpSecurityRestrictionsDefaultAction: 'Deny'
      appSettings: concat(registrySettings, [
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          // Keep the SQLite file on the container's local disk, never on the shared
          // /home (SMB) storage (docs/system-update/azure-deployment.md).
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'CHRONUS_WORKLOAD_DB_PATH'
          value: '/var/lib/chronus/workloads.sqlite3'
        }
        {
          name: 'CHRONUS_TENANT_TOKENS'
          value: tenantTokensJson
        }
        {
          name: 'CHRONUS_JWT_SECRET'
          value: jwtSecret
        }
      ])
    }
  }
}

resource web 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: plan.location
  kind: 'app,linux,container'
  tags: tags
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientAffinityEnabled: false
    virtualNetworkSubnetId: empty(integrationSubnetId) ? null : integrationSubnetId
    siteConfig: {
      linuxFxVersion: 'DOCKER|${registry.properties.loginServer}/${webImageRepository}:${imageTag}'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      vnetRouteAllEnabled: !empty(integrationSubnetId)
      healthCheckPath: '/'
      ipSecurityRestrictionsDefaultAction: 'Deny'
      ipSecurityRestrictions: allowRules
      scmIpSecurityRestrictionsUseMain: false
      scmIpSecurityRestrictionsDefaultAction: 'Deny'
      appSettings: concat(registrySettings, [
        {
          name: 'WEBSITES_PORT'
          value: '3000'
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          // docker-compose.yml: CHRONUS_BACKEND_URL points the console at the api.
          name: 'CHRONUS_BACKEND_URL'
          value: 'https://${api.properties.defaultHostName}'
        }
        {
          name: 'PORT'
          value: '3000'
        }
        {
          name: 'HOSTNAME'
          value: '0.0.0.0'
        }
      ])
    }
  }
}

output apiHostName string = api.properties.defaultHostName
output webHostName string = web.properties.defaultHostName
