## ADDED Requirements

### Requirement: Auto-Discovery of Deployments
The system SHALL support automatically discovering all available deployments in a subaccount without requiring explicit `deployment_ids` or `deployment_models` configuration.

#### Scenario: Subaccount with no explicit mappings
- **WHEN** the proxy starts with a subaccount config that lacks `deployment_ids/models` (or has a flag enabled)
- **THEN** it fetches all deployments from SAP AI Core
- **AND** registers them in the load balancer using their `backend_details.model.name`

### Requirement: Model Name Aliasing
The system SHALL support mapping raw backend model names to user-friendly aliases.

#### Scenario: Aliasing execution
- **WHEN** a deployment is discovered with backend model `anthropic--claude-3.5-sonnet`
- **THEN** it is registered under `anthropic--claude-3.5-sonnet`
- **AND** it is registered under configured aliases like `sonnet-3.5` and `claude-3.5-sonnet`
- **AND** requests to any of these names are routed to that deployment

### Requirement: SDK Extraction Update
(Same as before, but critical for enabling the above)
The SDK utility SHALL extract `backend_details.model.name`.

## MODIFIED Requirements

### Requirement: Config Parsing Strategy
The config parser SHALL NOT fail or warn if `deployment_ids` is missing, provided auto-discovery is enabled/implicit.
