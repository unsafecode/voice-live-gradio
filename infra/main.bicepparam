using './main.bicep'

// Operator: keep this file environment-agnostic. Concrete values come from
// `azd env set` (see README "Deploy to Azure" section). The `${VAR}` shape
// is azd's built-in env-var substitution; we use it for plain strings only.
//
// Per azd-patterns SKILL § "azd env set + JSON arrays/objects", we do NOT
// pass arrays or objects through this file — they'd get triple-escaped.
param environmentName = '${readEnvironmentVariable('AZURE_ENV_NAME', 'voice-live-demo')}'
param location = '${readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')}'
param foundryAccountName = '${readEnvironmentVariable('AZURE_FOUNDRY_ACCOUNT_NAME', '')}'
param foundryResourceGroup = '${readEnvironmentVariable('AZURE_FOUNDRY_RESOURCE_GROUP', '')}'
param foundryRealtimeDeployment = '${readEnvironmentVariable('AZURE_FOUNDRY_REALTIME_DEPLOYMENT', 'gpt-realtime-2')}'
param deployingUserObjectId = '${readEnvironmentVariable('AZURE_PRINCIPAL_ID', '')}'
param agentProjectName = '${readEnvironmentVariable('AGENT_PROJECT_NAME', '')}'
param agentId = '${readEnvironmentVariable('AGENT_ID', '')}'
param mcapsPilotPosture = bool('${readEnvironmentVariable('MCAPS_PILOT_POSTURE', 'true')}')
