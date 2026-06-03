// Cross-RG Foundry RBAC helper. Bicep requires role assignments to be
// authored at the same scope as the existing resource they target — we
// hop into the Foundry's RG with `scope: resourceGroup(...)`.

@description('Existing Foundry account name in this RG.')
param foundryAccountName string

@description('Principal that receives Cognitive Services User + Azure AI User.')
param principalId string

@allowed([ 'ServicePrincipal', 'User', 'Group' ])
@description('Principal type — ServicePrincipal for MIs, User for humans.')
param principalType string

param cognitiveServicesUserId string
param azureAIUserId string

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

resource cogServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name:  guid(foundry.id, principalId, cognitiveServicesUserId)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserId)
    principalId:      principalId
    principalType:    principalType
  }
}

resource azureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name:  guid(foundry.id, principalId, azureAIUserId)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAIUserId)
    principalId:      principalId
    principalType:    principalType
  }
}
