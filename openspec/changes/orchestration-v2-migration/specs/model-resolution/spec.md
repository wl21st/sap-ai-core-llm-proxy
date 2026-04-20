## MODIFIED Requirements

### Requirement: Model Fallback and Validation
The system SHALL validate the requested model name against the foundation model registry (populated from `GET /v2/lm/foundation-models` or the static fallback list). If the model name is not found in the registry after alias resolution, the system SHALL return a 404 Not Found error.

#### Scenario: Model Not Found
- **WHEN** client sends a request with `model: "non-existent-model"`
- **AND** "non-existent-model" does not resolve to any known foundation model alias
- **THEN** system logs "Model 'non-existent-model' not available in foundation model registry"
- **AND** system returns HTTP 404
- **AND** response body contains error type "not_found_error"

#### Scenario: Model Found in Registry
- **WHEN** client sends a request with `model: "gpt-4o"`
- **AND** "gpt-4o" is present in the foundation model registry
- **THEN** system passes the model name directly in the Orchestration V2 request body and processes the request

#### Scenario: Model resolved via alias
- **WHEN** client sends a request with `model: "claude-3.5-sonnet"` (alias)
- **AND** the alias map resolves it to `anthropic--claude-3.5-sonnet`
- **AND** `anthropic--claude-3.5-sonnet` is in the foundation model registry
- **THEN** the canonical name is used in the Orchestration V2 request body

#### Scenario: Model filtered out behaves as not configured
- **WHEN** client sends a request with a model excluded by `model_filters` config
- **THEN** system SHALL treat that model as unavailable
- **AND** system returns HTTP 404 with error type "not_found_error"
