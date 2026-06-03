// Container App that serves the unified switcher UI (MODE=demo).
// Adapted from the canonical azd-patterns aca-app.bicep, with the
// voice-live-gradio env contract wired in.
//
// Pinned to single replica because FastRTC opens a per-session WebRTC
// signaling channel that cannot be load-balanced safely without sticky
// sessions. Scale up only after wiring session affinity in ACA ingress.
param environmentName string
param location string
param tags object
param acaEnvironmentId string
param uamiResourceId string
param uamiClientId string
param acrLoginServer string
param foundryAccountName string
param foundryRealtimeDeployment string
param agentProjectName string = ''
param agentId string = ''

@description('ACS endpoint (https://<resource>.<region>.communication.azure.com) used by voicelive_demo/rtc.py to mint TURN credentials. Leave blank to disable TURN (only works on localhost; ACA needs TURN).')
param acsEndpoint string = ''

@description('Image to start with. azd deploy will patch this to the real ACR image right after provision.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('CPU cores. 1 vCPU is plenty for the demo; bumping this up does not reduce audio latency.')
param cpu string = '1.0'

@description('Memory in Gi. 2Gi covers PyAV + FastRTC buffers comfortably.')
param memory string = '2.0Gi'

@description('Tag bound to the azure.yaml service entry. MUST match — azd deploy locates the ACA by this tag.')
param serviceTag string = 'app'

var appName = 'ca-${environmentName}'

resource app 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: appName
  location: location
  tags: union(tags, { 'azd-service-name': serviceTag })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: acaEnvironmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 7860
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
        // WebRTC + WebSockets need sticky sessions even at minReplicas=1
        // (revision rollovers happen between requests; sticky keeps a
        // user pinned to the live revision).
        stickySessions: {
          affinity: 'sticky'
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: uamiResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: concat(
            [
              { name: 'MODE', value: 'demo' }
              { name: 'HOST', value: '0.0.0.0' }
              { name: 'PORT', value: '7860' }
              { name: 'AZURE_CLIENT_ID', value: uamiClientId }
              {
                name: 'AZURE_OPENAI_ENDPOINT'
                value: 'https://${foundryAccountName}.openai.azure.com'
              }
              {
                name: 'AZURE_VOICELIVE_ENDPOINT'
                value: 'wss://${foundryAccountName}.services.ai.azure.com/voice-live'
              }
              {
                name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
                value: foundryRealtimeDeployment
              }
              { name: 'AZURE_OPENAI_API_VERSION', value: '2025-04-01-preview' }
              { name: 'AZURE_VOICELIVE_API_VERSION', value: '2025-10-01' }
              // Keeping cognitive-services scope explicit so future
              // sovereign-cloud overrides only have to touch one place.
              {
                name: 'AZURE_COGNITIVE_SERVICES_SCOPE'
                value: 'https://cognitiveservices.azure.com/.default'
              }
              { name: 'AZURE_AI_SCOPE', value: 'https://ai.azure.com/.default' }
            ],
            !empty(agentProjectName) ? [{ name: 'AGENT_PROJECT_NAME', value: agentProjectName }] : [],
            !empty(agentId) ? [{ name: 'AGENT_ID', value: agentId }] : [],
            !empty(acsEndpoint) ? [{ name: 'ACS_ENDPOINT', value: acsEndpoint }] : []
          )
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/'
                port: 7860
              }
              initialDelaySeconds: 30
              periodSeconds: 30
              failureThreshold: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
