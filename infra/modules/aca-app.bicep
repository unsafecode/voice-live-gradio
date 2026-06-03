// Single-service ACA app: the web shell. Placeholder image on first
// provision; `azd deploy` patches it via the `azd-service-name: web` tag.

@description('Container App name.')
param name string

@description('Azure region.')
param location string

@description('Tags. Must include the `azd-service-name: web` tag so azd deploy can find this app.')
param tags object

@description('ACA managed environment resource ID.')
param acaEnvironmentId string

@description('ACR login server (e.g. <name>.azurecr.io).')
param acrLoginServer string

@description('UAMI resource ID — bound to the app for pull + Foundry calls.')
param uamiResourceId string

@description('UAMI client ID — surfaced via AZURE_CLIENT_ID so DefaultAzureCredential picks it up.')
param uamiClientId string

@description('Existing Foundry resource OpenAI endpoint.')
param azureOpenAIEndpoint string

@description('Existing Foundry resource Voice Live endpoint.')
param azureVoiceLiveEndpoint string

@description('Realtime model deployment name.')
param azureOpenAIDeploymentName string

@description('Foundry project name for rung 3 (may be empty).')
param agentProjectName string

@description('Foundry Agent ID for rung 3 (may be empty).')
param agentId string

@description('Default rung shown on page load: realtime | voicelive | agent')
param defaultMode string

@description('Whether to expose the agent rung in /api/config.')
param enableAgentRung bool

@description('Placeholder image used until `azd deploy` swaps it.')
param placeholderImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Container port that the FastAPI/uvicorn process listens on.')
param targetPort int = 8080

var envVars = [
  { name: 'MODE',                          value: defaultMode }
  { name: 'AZURE_CLIENT_ID',               value: uamiClientId }
  { name: 'AZURE_OPENAI_ENDPOINT',         value: azureOpenAIEndpoint }
  { name: 'AZURE_VOICELIVE_ENDPOINT',      value: azureVoiceLiveEndpoint }
  { name: 'AZURE_OPENAI_DEPLOYMENT_NAME',  value: azureOpenAIDeploymentName }
  { name: 'AZURE_OPENAI_API_VERSION',      value: '2025-04-01-preview' }
  { name: 'AZURE_VOICELIVE_API_VERSION',   value: '2025-10-01' }
  { name: 'AGENT_PROJECT_NAME',            value: enableAgentRung ? agentProjectName : '' }
  { name: 'AGENT_ID',                      value: enableAgentRung ? agentId : '' }
  { name: 'HOST',                          value: '0.0.0.0' }
  { name: 'PORT',                          value: string(targetPort) }
  { name: 'LOG_LEVEL',                     value: 'INFO' }
]

resource app 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name:     name
  location: location
  tags:     tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uamiResourceId}': {} }
  }
  properties: {
    environmentId: acaEnvironmentId
    configuration: {
      ingress: {
        external:    true
        targetPort:  targetPort
        transport:   'auto'
        allowInsecure: false
        traffic: [ { weight: 100, latestRevision: true } ]
      }
      registries: [
        {
          server:   acrLoginServer
          identity: uamiResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name:  'web'
          image: placeholderImage
          resources: {
            cpu:    json('1.0')
            memory: '2.0Gi'
          }
          env: envVars
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: targetPort
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: targetPort
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        // `1` for pilots (avoids cold-start surprises during deploy testing).
        // Switch to `0` for production cost savings if traffic is sparse.
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output name string = app.name
output id string = app.id
output fqdn string = app.properties.configuration.ingress.fqdn
