targetScope = 'subscription'

@minLength(3)
@maxLength(20)
@description('Short prefix used to namespace every resource (lowercase, alphanumeric, no hyphens).')
param environmentName string

@description('Azure region for all resources.')
param location string

@description('Resource group name to create (or reuse).')
param resourceGroupName string = 'rg-${environmentName}'

@description('Override the principal ID of the human deploying this — only used if `principalId` is non-empty. azd auto-fills this from `azd auth login`. Leave blank to skip developer RBAC.')
param principalId string = ''

@description('When true (default for Microsoft-internal MCAPS pilot subs), tags the RG with SecurityControl=Ignore so Defender / Azure Policy skip it. Set false in customer-owned subs.')
param mcapsPilotPosture bool = true

@description('Free-form tags to apply to the RG and propagate to every resource.')
param tags object = {}

// ── BYO Foundry — the deploy points at an existing Foundry resource ─────
@description('Existing Azure AI Foundry account name.')
param foundryAccountName string

@description('Resource group hosting the existing Foundry account.')
param foundryResourceGroup string

@description('https://<foundry>.openai.azure.com — sourced from the existing Foundry resource.')
param azureOpenAIEndpoint string

@description('wss://<foundry>.services.ai.azure.com/voice-live — sourced from the existing Foundry resource.')
param azureVoiceLiveEndpoint string

@description('Name of the realtime model deployment on the Foundry resource.')
param azureOpenAIDeploymentName string = 'gpt-realtime-1.5'

// ── Optional: Foundry Agent (rung 3) ────────────────────────────────────
@description('Foundry project name hosting the Voice Live Agent (leave blank to disable rung 3).')
param agentProjectName string = ''

@description('Foundry Agent ID for rung 3 (leave blank to disable rung 3).')
param agentId string = ''

// ── Mode ────────────────────────────────────────────────────────────────
@allowed([ 'realtime', 'voicelive', 'agent' ])
@description('Default rung shown when the page loads. The browser can still switch between any configured rung.')
param defaultMode string = 'voicelive'

var baseTags = union(tags, mcapsPilotPosture ? { SecurityControl: 'Ignore' } : {}, {
  'azd-env-name': environmentName
})

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: baseTags
}

module workload './modules/main.bicep' = {
  name: 'workload'
  scope: rg
  params: {
    environmentName:           environmentName
    location:                  location
    tags:                      baseTags
    principalId:               principalId
    foundryAccountName:        foundryAccountName
    foundryResourceGroup:      foundryResourceGroup
    azureOpenAIEndpoint:       azureOpenAIEndpoint
    azureVoiceLiveEndpoint:    azureVoiceLiveEndpoint
    azureOpenAIDeploymentName: azureOpenAIDeploymentName
    agentProjectName:          agentProjectName
    agentId:                   agentId
    defaultMode:               defaultMode
  }
}

// Outputs consumed by azd
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = workload.outputs.acrLoginServer
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = workload.outputs.acaEnvironmentId
output SERVICE_WEB_NAME string = workload.outputs.appName
output SERVICE_WEB_URI string = workload.outputs.appFqdn
output AZURE_CLIENT_ID string = workload.outputs.uamiClientId
