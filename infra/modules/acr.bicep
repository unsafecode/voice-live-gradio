@description('Container Registry name. Must be globally unique, lowercase alphanumeric, 5-50 chars.')
param name string

@description('Azure region.')
param location string

@description('Tags to apply.')
param tags object = {}

@allowed([ 'Basic', 'Standard', 'Premium' ])
@description('ACR SKU. Basic is enough for pilots; bump to Standard if you exceed 10 GB storage.')
param sku string = 'Basic'

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name:     name
  location: location
  tags:     tags
  sku: { name: sku }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    anonymousPullEnabled: false
  }
}

output name string = acr.name
output id string = acr.id
output loginServer string = acr.properties.loginServer
