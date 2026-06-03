// Workload-RG core: Log Analytics, ACA Environment, ACR.
//
// These are the pieces the container app depends on but the app module
// itself doesn't need to own. Outputs feed both `acr-rbac.bicep` (AcrPull)
// and `app.bicep` (env + registry + image).
param environmentName string
param location string
param tags object

@description('ACR SKU. Standard is sufficient for a single-image pilot.')
param acrSku string = 'Standard'

// Resource names. Keep them short + lowercase where the resource type
// demands it. uniqueString anchors to RG so re-deploys in the same env
// hit the same names.
var suffix = uniqueString(resourceGroup().id, environmentName)
var lawName = 'law-${environmentName}'
var acaEnvName = 'cae-${environmentName}'
var acrName = toLower(replace('cr${environmentName}${suffix}', '-', ''))

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: lawName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource acaEnv 'Microsoft.App/managedEnvironments@2024-10-02-preview' = {
  name: acaEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: acrSku
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output lawId string = law.id
output acaEnvironmentId string = acaEnv.id
output acaEnvironmentName string = acaEnv.name
output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output acrResourceId string = acr.id
