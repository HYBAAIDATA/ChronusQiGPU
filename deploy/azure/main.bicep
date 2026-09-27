targetScope = 'resourceGroup'

@description('Existing Container Apps environment, in this resource group.')
param environmentName string
@description('Existing ACR, in this resource group; admin credentials are not used.')
param registryName string
@description('Immutable repository@sha256:digest, without the registry hostname.')
param image string
param location string = resourceGroup().location
param appName string = 'pythia-control'
@description('Enable only after authentication has been deployed and tested internally.')
param externalIngress bool = false
@description('Existing environment Azure Files storage binding for durable control configuration.')
param storageBindingName string
param tenantId string
param clientId string
@secure()
param clientSecret string
@minLength(1)
@description('Entra object IDs of explicitly authorized operators.')
param operatorObjectIds array

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${appName}-pull'
  location: location
}
var acrPullRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
resource pullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, pullIdentity.id, acrPullRole)
  properties: {
    roleDefinitionId: acrPullRole
    principalId: pullIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${pullIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: externalIngress
        allowInsecure: false
        targetPort: 3000
        transport: 'http'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: pullIdentity.id
        }
      ]
      secrets: [
        {
          name: 'entra-client-secret'
          value: clientSecret
        }
      ]
    }
    template: {
      containers: [
      {
        name: 'control'
        image: '${registry.properties.loginServer}/${image}'
        resources: {
          cpu: json('0.5')
          memory: '1Gi'
        }
        env: [
          {
            name: 'PYTHIA_AUTOSTART_WORKERS'
            value: '0'
          }
          {
            name: 'PYTHIA_LIVE_SUBMIT'
            value: '0'
          }
        ]
        volumeMounts: [
          {
            volumeName: 'config'
            mountPath: '/var/lib/pythia'
          }
        ]
        probes: [for kind in [
          'Startup'
          'Liveness'
          'Readiness'
        ]: {
          type: kind
          httpGet: {
            path: '/healthz'
            port: 3000
          }
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 6
        }]
      }]
      volumes: [
        {
          name: 'config'
          storageType: 'AzureFile'
          storageName: storageBindingName
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
  dependsOn: [pullRole]
}
resource auth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = {
  parent: app
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureActiveDirectory'
      excludedPaths: ['/healthz']
    }
    httpSettings: {
      requireHttps: true
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: clientId
          clientSecretSettingName: 'entra-client-secret'
          openIdIssuer: 'https://login.microsoftonline.com/${tenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [
            clientId
            'api://${clientId}'
          ]
          defaultAuthorizationPolicy: {
            allowedPrincipals: {
              identities: operatorObjectIds
            }
          }
        }
      }
    }
  }
}
output url string = 'https://${app.properties.configuration.ingress.fqdn}'
output miningReady bool = false
