## ADDED Requirements

### Requirement: Orchestration Deployment Model Name Extraction
The system SHALL extract a model name from orchestration deployments by falling back to `configuration_name` when `backend_details.model.name` is absent.

#### Scenario: Orchestration deployment without backend model name
- **WHEN** `fetch_all_deployments()` processes a deployment that has no `backend_details.model.name`
- **AND** the deployment has a non-empty `configuration_name`
- **THEN** the returned record's `model_name` field SHALL be set to the value of `configuration_name`

#### Scenario: Standard model-serving deployment unchanged
- **WHEN** `fetch_all_deployments()` processes a deployment that has `backend_details.model.name` set
- **THEN** the returned record's `model_name` field SHALL be set to `backend_details.model.name`
- **AND** `configuration_name` SHALL NOT override it

#### Scenario: Deployment with neither backend model name nor configuration name
- **WHEN** `fetch_all_deployments()` processes a deployment with no `backend_details.model.name` and no `configuration_name`
- **THEN** the returned record's `model_name` field SHALL be `None`
- **AND** the deployment SHALL still appear in the results list (not silently dropped)

### Requirement: Auto-Discover Flag in SubAccount Config
The system SHALL support an optional `auto_discover` boolean field in `SubAccountConfig` (and its corresponding Pydantic schema) defaulting to `False`.

#### Scenario: Explicit auto_discover true
- **WHEN** a subaccount's config has `"auto_discover": true`
- **THEN** the proxy SHALL run deployment discovery for that subaccount at startup regardless of whether `deployment_models` is present

#### Scenario: No deployment mappings and no auto_discover
- **WHEN** a subaccount has no `deployment_models`, no `model_to_deployment_ids`, and `auto_discover` is absent/false
- **THEN** the proxy SHALL run deployment discovery for that subaccount at startup (implicit discovery)

#### Scenario: Backward compatibility — manual config only
- **WHEN** a subaccount has `deployment_models` configured and `auto_discover` is absent/false
- **THEN** the proxy SHALL NOT run deployment discovery for that subaccount
- **AND** the proxy SHALL use only the manually configured URLs

### Requirement: Startup Discovery Execution
The system SHALL run deployment discovery for eligible subaccounts during the FastAPI lifespan startup phase, after config loading and before `ProxyGlobalContext.initialize()`.

#### Scenario: Successful discovery populates model URLs
- **WHEN** discovery runs for a subaccount and `fetch_all_deployments()` returns deployments with non-None `model_name`
- **THEN** each deployment's `deployment_url` SHALL be added to `SubAccountConfig.model_to_deployment_urls[model_name]`
- **AND** the model SHALL be available for routing after startup

#### Scenario: Discovery failure does not crash startup
- **WHEN** `fetch_all_deployments()` raises an exception for a subaccount
- **THEN** the proxy SHALL log a WARNING including the subaccount name and exception message
- **AND** the proxy SHALL continue startup with whatever manual URLs were configured
- **AND** the proxy SHALL NOT raise the exception

#### Scenario: Discovery skipped for deployments with no model name
- **WHEN** a discovered deployment has `model_name` of `None`
- **THEN** that deployment SHALL be skipped and not added to `model_to_deployment_urls`
- **AND** a DEBUG log SHALL record the skipped deployment ID

### Requirement: Manual Config Takes Precedence in Merge
The system SHALL merge discovered deployment URLs into `model_to_deployment_urls` such that manually configured URLs for a given model are preserved and not overwritten.

#### Scenario: Model already configured manually — discovered URL appended only if new
- **WHEN** `model_to_deployment_urls` already contains entries for `model_name`
- **AND** discovery finds additional URLs for the same `model_name`
- **THEN** discovered URLs not already in the list SHALL be appended
- **AND** the existing manual URLs SHALL remain at the front of the list

#### Scenario: New model discovered — added to routing table
- **WHEN** discovery finds a deployment with `model_name` not present in `model_to_deployment_urls`
- **THEN** the model SHALL be added to `model_to_deployment_urls` with the discovered URL
- **AND** model aliases (if any) SHALL be registered using the existing alias mechanism
