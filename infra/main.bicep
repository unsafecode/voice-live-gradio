// =============================================================================
// voice-live-gradio — Azure deploy (subscription scope)
//
// Provisions a single Container App that serves the unified demo UI
// (MODE=demo) backed by an existing Azure AI Foundry account. Reuses the
// caller's Foundry resource — does NOT provision a Foundry account or model
// deployment. Designed for MCAPS pilot subscriptions; flip
// `mcapsPilotPosture` to false in a customer-owned tenant.
//
// Inclusion order: rg → identity → core → app + cross-RG RBAC
// =============================================================================
targetScope = 'subscription'

@minLength(1)
@maxLength(20)
@description('AZD environment name; used as suffix for resource names.')
param environmentName string

@description('Azure region for the workload resource group + child resources.')
param location string

@description('Name of an existing Azure AI Foundry / Cognitive Services account that hosts the Realtime + Voice Live models. Reused — not created.')
param foundryAccountName string

@description('Resource group that contains the existing Foundry account above.')
param foundryResourceGroup string

@description('Realtime model deployment name on the Foundry account (e.g. gpt-realtime-2).')
param foundryRealtimeDeployment string

@description('Optional: Object ID of the deploying user — gets Cognitive Services User on the Foundry account so the portal works. Leave blank for non-interactive CI.')
param deployingUserObjectId string = ''

@description('Optional: Foundry project name to surface as AGENT_PROJECT_NAME inside the container (Agent rung). Leave blank to hide the Agent tab.')
param agentProjectName string = ''

@description('Optional: Foundry agent ID for the Agent rung. Leave blank to hide the Agent tab.')
param agentId string = ''

@description('When true (default), tags the RG with SecurityControl=Ignore so Defender for Cloud / Azure Policy skip the pilot. Flip to false in a customer-owned subscription.')
param mcapsPilotPosture bool = true

@description('Free-form tags merged onto the RG and propagated to every resource.')
param tags object = {}

var rgName = 'rg-${environmentName}'
var baseTags = union(
  tags,
  { 'azd-env-name': environmentName },
  mcapsPilotPosture ? { SecurityControl: 'Ignore' } : {}
)

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgName
  location: location
  tags: baseTags
}

module identity './modules/identity.bicep' = {
  name: 'identity'
  scope: rg
  params: {
    name: 'id-${environmentName}'
    location: location
    tags: baseTags
  }
}

module core './modules/core.bicep' = {
  name: 'core'
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    tags: baseTags
  }
}

// AcrPull lives in the workload RG (with the ACR).
module acrRbac './modules/acr-rbac.bicep' = {
  name: 'acr-rbac'
  scope: rg
  params: {
    acrName: core.outputs.acrName
    uamiPrincipalId: identity.outputs.principalId
  }
}

// Foundry RBAC lives in rg-infra (with the Foundry account).
module foundryRbac './modules/foundry-rbac.bicep' = {
  name: 'foundry-rbac'
  scope: resourceGroup(foundryResourceGroup)
  params: {
    foundryAccountName: foundryAccountName
    uamiPrincipalId: identity.outputs.principalId
    deployingUserObjectId: deployingUserObjectId
  }
}

// `dependsOn: [acrRbac, foundryRbac]` pre-empts the 30-60s RBAC propagation
// race that bricks the first revision when AcrPull lands after the image
// pull is attempted.
module app './modules/app.bicep' = {
  name: 'app'
  scope: rg
  dependsOn: [
    acrRbac
    foundryRbac
  ]
  params: {
    environmentName: environmentName
    location: location
    tags: baseTags
    acaEnvironmentId: core.outputs.acaEnvironmentId
    acrLoginServer: core.outputs.acrLoginServer
    uamiResourceId: identity.outputs.resourceId
    uamiClientId: identity.outputs.clientId
    foundryAccountName: foundryAccountName
    foundryRealtimeDeployment: foundryRealtimeDeployment
    agentProjectName: agentProjectName
    agentId: agentId
  }
}

output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_LOCATION string = location
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = core.outputs.acrLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = core.outputs.acrName
output APP_FQDN string = app.outputs.fqdn
output APP_URL string = 'https://${app.outputs.fqdn}'
output AZURE_CLIENT_ID string = identity.outputs.clientId
output AZURE_OPENAI_ENDPOINT string = 'https://${foundryAccountName}.openai.azure.com'
output AZURE_VOICELIVE_ENDPOINT string = 'wss://${foundryAccountName}.services.ai.azure.com/voice-live'
