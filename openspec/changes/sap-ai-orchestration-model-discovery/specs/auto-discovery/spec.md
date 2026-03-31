## MODIFIED Requirements

### Requirement: Auto-Discovery of Deployments
The system SHALL support automatically discovering all available deployments in a subaccount. Discovery is triggered when:
- the subaccount has `auto_discover: true` set explicitly, OR
- the subaccount has no `deployment_models` and no `model_to_deployment_ids` configured (implicit discovery)

Discovery fetches all RUNNING deployments from SAP AI Core regardless of `scenario_id` (both model-serving and orchestration deployments are included).

#### Scenario: Subaccount with no explicit mappings — implicit discovery
- **WHEN** the proxy starts with a subaccount config that lacks both `deployment_models` and `model_to_deployment_ids`
- **THEN** it SHALL fetch all deployments from SAP AI Core
- **AND** SHALL register each deployment with a non-None `model_name` in `model_to_deployment_urls`

#### Scenario: Subaccount with explicit auto_discover flag
- **WHEN** a subaccount has `auto_discover: true` and also has `deployment_models`
- **THEN** discovery SHALL run AND merge results with manual config
- **AND** manual `deployment_models` URLs take precedence for any overlapping model name

#### Scenario: Orchestration deployment included in discovery
- **WHEN** discovery runs and finds a deployment with `scenario_id: orchestration`
- **THEN** its `configuration_name` SHALL be used as the model name (if `backend_details.model.name` is absent)
- **AND** it SHALL be registered in `model_to_deployment_urls` under that name

## MODIFIED Requirements

### Requirement: Model Name Aliasing
The system SHALL support mapping raw backend model names to user-friendly aliases. Aliasing applies to both model-serving and orchestration deployments discovered via the API.

#### Scenario: Aliasing execution for model-serving deployment
- **WHEN** a deployment is discovered with backend model `anthropic--claude-3.5-sonnet`
- **THEN** it SHALL be registered under `anthropic--claude-3.5-sonnet`
- **AND** it SHALL be registered under configured aliases like `sonnet-3.5` and `claude-3.5-sonnet`
- **AND** requests to any of these names SHALL be routed to that deployment

#### Scenario: Aliasing execution for orchestration deployment
- **WHEN** a deployment is discovered with `configuration_name: ail-auto-orchestration`
- **AND** `ail-auto-orchestration` has configured aliases
- **THEN** it SHALL be registered under `ail-auto-orchestration` and each alias
- **WHEN** `ail-auto-orchestration` has no configured aliases
- **THEN** it SHALL be registered only under `ail-auto-orchestration`
