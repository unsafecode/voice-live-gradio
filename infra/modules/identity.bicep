// Shared User-Assigned Managed Identity.
// One identity for the ACA app + AcrPull + Foundry data-plane RBAC, so we
// have a single principalId to grant roles to. See azd-patterns SKILL §
// Shared UAMI Pattern.
param name string
param location string
param tags object

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

output resourceId string = uami.id
output principalId string = uami.properties.principalId
output clientId string = uami.properties.clientId
output name string = uami.name
