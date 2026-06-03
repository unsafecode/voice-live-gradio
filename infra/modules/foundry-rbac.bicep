// Cross-scope RBAC on the EXISTING Foundry account in its own RG.
// The shared UAMI gets Cognitive Services User (both Realtime + Voice Live
// data-plane token); the deploying user gets the same role so the portal
// works. Role GUIDs pinned per azd-patterns SKILL § RBAC — assign once.
param foundryAccountName string
param uamiPrincipalId string
param deployingUserObjectId string = ''

var roleCogSvcUser = 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
var roleCogSvcOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
var roleAzureAIUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User (aka Foundry User) — needed for Agent rung

resource foundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: foundryAccountName
}

// UAMI: Cognitive Services User — broad enough to mint tokens for the
// Voice Live + Realtime endpoints with DefaultAzureCredential.
resource uamiCogSvcUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, uamiPrincipalId, roleCogSvcUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCogSvcUser)
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// UAMI: Cognitive Services OpenAI User — needed specifically for the
// Realtime model endpoint (the legacy OpenAI subdomain enforces this role).
resource uamiOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, uamiPrincipalId, roleCogSvcOpenAIUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCogSvcOpenAIUser)
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// UAMI: Azure AI User — needed for the Foundry Agent rung
// (`https://ai.azure.com/.default` scope). Harmless when the Agent rung
// is disabled.
resource uamiAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, uamiPrincipalId, roleAzureAIUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIUser)
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Deploying user: Cognitive Services User so they can poke the resource
// from the portal during smoke-tests.
resource userCogSvcUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployingUserObjectId)) {
  scope: foundry
  name: guid(foundry.id, deployingUserObjectId, roleCogSvcUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCogSvcUser)
    principalId: deployingUserObjectId
    principalType: 'User'
  }
}
