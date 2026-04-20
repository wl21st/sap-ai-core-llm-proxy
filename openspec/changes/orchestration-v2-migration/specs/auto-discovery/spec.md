## MODIFIED Requirements

### Requirement: Auto-Discovery of Deployments
The system SHALL support automatically discovering the orchestration service deployment URL for each subaccount. If `orchestration_url` is not explicitly configured, the proxy SHALL auto-discover the URL by fetching running deployments and identifying the orchestration service deployment.

#### Scenario: Explicit orchestration URL configured
- **WHEN** the proxy starts with a subaccount that has `orchestration_url` explicitly set in config
- **THEN** it uses the provided URL directly without making any discovery API call

#### Scenario: Auto-discovery when orchestration URL not provided
- **WHEN** the proxy starts with a subaccount config that lacks `orchestration_url`
- **THEN** it fetches all deployments from `GET /v2/lm/deployments`
- **AND** identifies the deployment running the orchestration service configuration
- **AND** registers that deployment URL as `orchestration_url` for the subaccount

### Requirement: Model Name Aliasing
The system SHALL support mapping user-provided model names to canonical Orchestration V2 model names via a configurable alias map.

#### Scenario: Aliasing execution
- **WHEN** a request arrives with model name `claude-3.5-sonnet`
- **THEN** it is resolved to the canonical Orchestration V2 name `anthropic--claude-3.5-sonnet`
- **AND** the canonical name is used in the `llm_module_config.model_name` field

## REMOVED Requirements

### Requirement: SDK Extraction Update
**Reason**: Deployment-based model extraction via `backend_details.model.name` is replaced by the foundation model discovery API (`GET /v2/lm/foundation-models`). The Bedrock SDK client pool is no longer used.
**Migration**: Use `FoundationModelDiscovery` (new capability) to enumerate available models.

### Requirement: Config Parsing Strategy
**Reason**: The requirement to tolerate missing `deployment_ids` is superseded. The new config schema uses `orchestration_url` instead of `deployment_ids`. The parser SHALL accept `orchestration_url` (required or auto-discovered) and SHALL NOT require `deployment_ids`.
**Migration**: Remove `deployment_ids` from config; add `orchestration_url` or enable auto-discovery.
