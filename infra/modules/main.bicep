// Resource-group-scope orchestrator. Composes UAMI + ACR + LAW + ACA env
// + ACA app + RBAC for the single `web` service. The Foundry resource is
// BYO (referenced via parameters, not provisioned here) so the same Bicep
// can target any existing Foundry account.

@description('Short prefix used to namespace every resource (lowercase, alphanumeric).')
param environmentName string

@description('Azure region for all resources.')
param location string

@description('Tags applied to every resource (already carries SecurityControl=Ignore in MCAPS subs).')
param tags object

@description('Optional principal ID of the human deploying — gets Cognitive Services User + Azure AI User for local development against the same Foundry. Skipped when empty.')
param principalId string = ''

// ── BYO Foundry ─────────────────────────────────────────────────────────
param foundryAccountName string
param foundryResourceGroup string
param azureOpenAIEndpoint string
param azureVoiceLiveEndpoint string
param azureOpenAIDeploymentName string

// ── Optional Foundry Agent (rung 3) ─────────────────────────────────────
param agentProjectName string
param agentId string

param defaultMode string

// Deterministic short suffix so re-runs land on the same resources.
var token = uniqueString(subscription().id, resourceGroup().id, environmentName)
var prefix = toLower(environmentName)
var rungAgent = !empty(agentProjectName) && !empty(agentId)

// ── UAMI ────────────────────────────────────────────────────────────────
module uami './uami.bicep' = {
  name: 'uami'
  params: {
    name:     '${prefix}-id-${token}'
    location: location
    tags:     tags
  }
}

// ── Log Analytics + App Insights ────────────────────────────────────────
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-law-${token}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: 1 }
  }
}

// ── ACR ─────────────────────────────────────────────────────────────────
module acr './acr.bicep' = {
  name: 'acr'
  params: {
    name:     '${prefix}acr${token}'
    location: location
    tags:     tags
  }
}

// ── ACA Environment ─────────────────────────────────────────────────────
resource acaEnv 'Microsoft.App/managedEnvironments@2024-10-02-preview' = {
  name: '${prefix}-env-${token}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: listKeys(law.id, '2023-09-01').primarySharedKey
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

// ── RBAC — assign BEFORE the ACA app so the first revision can pull the image ──
module rbac './rbac.bicep' = {
  name: 'rbac'
  params: {
    uamiPrincipalId:        uami.outputs.principalId
    acrName:                acr.outputs.name
    foundryAccountName:     foundryAccountName
    foundryResourceGroup:   foundryResourceGroup
    developerPrincipalId:   principalId
  }
}

// ── ACA App ─────────────────────────────────────────────────────────────
module web './aca-app.bicep' = {
  name: 'web'
  // Pre-empt the AcrPull RBAC propagation race (azd-patterns skill rule).
  dependsOn: [ rbac ]
  params: {
    name:                       '${prefix}-web-${token}'
    location:                   location
    tags:                       union(tags, { 'azd-service-name': 'web' })
    acaEnvironmentId:           acaEnv.id
    acrLoginServer:             acr.outputs.loginServer
    uamiResourceId:             uami.outputs.id
    uamiClientId:               uami.outputs.clientId
    azureOpenAIEndpoint:        azureOpenAIEndpoint
    azureVoiceLiveEndpoint:     azureVoiceLiveEndpoint
    azureOpenAIDeploymentName:  azureOpenAIDeploymentName
    agentProjectName:           agentProjectName
    agentId:                    agentId
    defaultMode:                defaultMode
    enableAgentRung:            rungAgent
  }
}

output acrLoginServer string = acr.outputs.loginServer
output acaEnvironmentId string = acaEnv.id
output appName string = web.outputs.name
output appFqdn string = 'https://${web.outputs.fqdn}'
output uamiClientId string = uami.outputs.clientId
