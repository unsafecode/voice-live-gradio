// Azure Communication Services resource — only used for its Network
// Traversal API (mints short-lived TURN credentials per session).
//
// ACA ingress only allows inbound HTTP/HTTPS/WS, so FastRTC's WebRTC
// widget needs a TURN relay or ICE negotiation hangs at "Connecting…"
// forever. ACS gives us an Azure-native, Entra-authenticated TURN
// service with a free tier and ~$0.40/GB beyond that.
//
// Auth path: the workload UAMI gets `Contributor` on this resource so
// `azure.communication.networktraversal.aio.CommunicationRelayClient`
// can mint creds with `DefaultAzureCredential` (no connection strings).
param name string
@description('ACS data location — controls where customer data is processed. NOT the resource location (ACS resources are always `global`). Defaults to `Europe` to match the rest of the demo running in swedencentral.')
param dataLocation string = 'Europe'
param tags object = {}

@description('UAMI principalId that gets Contributor on this ACS resource so it can call get_relay_configuration() with Entra auth.')
param uamiPrincipalId string

resource acs 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: name
  location: 'global'
  tags: tags
  properties: {
    dataLocation: dataLocation
  }
}

// `Contributor` is the documented data-plane role for ACS data APIs.
// See: https://learn.microsoft.com/azure/communication-services/concepts/authentication
var contributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b24988ac-6180-42a0-ab88-20f7382dd24c'
)

resource uamiContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acs
  name: guid(acs.id, uamiPrincipalId, contributorRoleId)
  properties: {
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleId
  }
}

output endpoint string = 'https://${acs.properties.hostName}'
output name string = acs.name
