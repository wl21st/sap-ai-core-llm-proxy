# Spec: Deployment URL Lookup

## ADDED Requirements

### Requirement: Deployment ID Configuration

The system MUST allow users to configure `model_to_deployment_ids` and automatically resolve the corresponding Deployment URLs using the SAP AI Core SDK at startup.

#### Scenario: User provides Deployment ID in config

Given a valid `config.json` with `model_to_deployment_ids` mapping "gpt-4" to "d12345"
And the subaccount credentials are valid
When the proxy server starts
Then it should query SAP AI Core for deployment "d12345"
And it should resolve the deployment URL "https://.../deployments/d12345"
And it should successfully route requests for "gpt-4" to that URL.

#### Scenario: Deployment ID not found

Given a config with an invalid Deployment ID "bad-id"
When the proxy server starts
Then it should log an error indicating the deployment could not be found
And it should not crash the entire server (optional, or fail fast).

#### Scenario: Backward Compatibility

Given a config with `deployment_models` (URLs)
When the proxy server starts
Then it should continue to work as before without SDK lookup.
