// All role assignments in one module so `dependsOn: [rbac]` on the ACA
// app can pre-empt RBAC propagation races (per azd-patterns skill).

@description('Principal ID of the workload UAMI.')
param uamiPrincipalId string

@description('ACR resource name in this resource group.')
param acrName string

@description('Existing Foundry account name (any RG).')
param foundryAccountName string

@description('Resource group of the existing Foundry account.')
param foundryResourceGroup string

@description('Optional human deploying — gets dev RBAC on the Foundry. Empty = skip.')
param developerPrincipalId string = ''

// ── Stable Azure role definition IDs ────────────────────────────────────
var acrPullRoleId               = '7f951dda-4ed3-4680-a7ca-43fe172d538d'   // AcrPull
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'   // Cognitive Services User (Voice Live + Realtime)
var azureAIUserRoleId           = '53ca6127-db72-4b80-b1b0-d745d6d5456d'   // Azure AI User (Foundry Agent)

// ── Existing resources we attach assignments to ─────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

// ── Workload UAMI: AcrPull on the local ACR ────────────────────────────
resource acrPullForUami 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name:  guid(acr.id, uamiPrincipalId, acrPullRoleId)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId:      uamiPrincipalId
    principalType:    'ServicePrincipal'
  }
}

// ── Workload UAMI: Cognitive Services User + Azure AI User on the BYO Foundry (cross-RG) ──
module foundryRbacUami './rbac-foundry.bicep' = {
  name: 'foundry-rbac-uami'
  scope: resourceGroup(foundryResourceGroup)
  params: {
    foundryAccountName:       foundryAccountName
    principalId:              uamiPrincipalId
    principalType:            'ServicePrincipal'
    cognitiveServicesUserId:  cognitiveServicesUserRoleId
    azureAIUserId:            azureAIUserRoleId
  }
}

// ── Developer (optional) — same Foundry roles so local dev hits the same backend ─
module foundryRbacDev './rbac-foundry.bicep' = if (!empty(developerPrincipalId)) {
  name: 'foundry-rbac-dev'
  scope: resourceGroup(foundryResourceGroup)
  params: {
    foundryAccountName:       foundryAccountName
    principalId:              developerPrincipalId
    principalType:            'User'
    cognitiveServicesUserId:  cognitiveServicesUserRoleId
    azureAIUserId:            azureAIUserRoleId
  }
}
