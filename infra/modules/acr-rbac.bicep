// AcrPull on the workload ACR for the shared UAMI.
// Lives in the workload RG (with the ACR). See azd-patterns SKILL §
// ACR + ACA Registry Binding for why every UAMI bound to an ACA needs this.
param acrName string
param uamiPrincipalId string

var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acr 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: acrName
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, uamiPrincipalId, roleAcrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}
