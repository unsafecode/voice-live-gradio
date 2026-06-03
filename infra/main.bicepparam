using './main.bicep'

// All values are sourced from `.azure/<env>/.env` (written by `azd env set …`).
// First-run azd prompts for each `param ... = ''` value and persists the
// answer for subsequent runs.

param environmentName        = readEnvironmentVariable('AZURE_ENV_NAME', 'voicelive')
param location               = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param principalId            = readEnvironmentVariable('AZURE_PRINCIPAL_ID', '')

// Set to `true` for Microsoft-internal demo subs (MCAPS) so Defender / Policy
// skip the RG. Default `false` is the safe choice in a customer tenant.
param mcapsPilotPosture      = bool(readEnvironmentVariable('MCAPS_PILOT_POSTURE', 'false'))

// BYO Foundry — the existing Foundry resource you want this app to call.
// Required. Set via:
//   azd env set FOUNDRY_ACCOUNT_NAME       <your-foundry-account>
//   azd env set FOUNDRY_RESOURCE_GROUP     <rg-of-your-foundry>
//   azd env set AZURE_OPENAI_ENDPOINT      https://<your>.openai.azure.com
//   azd env set AZURE_VOICELIVE_ENDPOINT   wss://<your>.services.ai.azure.com/voice-live
//   azd env set AZURE_OPENAI_DEPLOYMENT_NAME gpt-realtime-1.5
param foundryAccountName        = readEnvironmentVariable('FOUNDRY_ACCOUNT_NAME', '')
param foundryResourceGroup      = readEnvironmentVariable('FOUNDRY_RESOURCE_GROUP', '')
param azureOpenAIEndpoint       = readEnvironmentVariable('AZURE_OPENAI_ENDPOINT', '')
param azureVoiceLiveEndpoint    = readEnvironmentVariable('AZURE_VOICELIVE_ENDPOINT', '')
param azureOpenAIDeploymentName = readEnvironmentVariable('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-realtime-1.5')

// Optional: rung 3 (Voice Live + Foundry Agent). Leave blank to hide it in /api/config.
param agentProjectName       = readEnvironmentVariable('AGENT_PROJECT_NAME', '')
param agentId                = readEnvironmentVariable('AGENT_ID', '')

param defaultMode            = readEnvironmentVariable('MODE', 'voicelive')
