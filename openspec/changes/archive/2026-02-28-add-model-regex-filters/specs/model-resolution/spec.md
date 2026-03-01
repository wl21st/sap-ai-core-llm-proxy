# Spec: Model Resolution

## Purpose
Logic for resolving model names to available deployments, handling fallbacks, and managing error states when models are unavailable.

## MODIFIED Requirements

### Requirement: Model Fallback and Validation
The system SHALL validate the requested model against configured subaccounts and deployment URLs, respecting model filters applied during config loading. If the model or its fallback is not found in any subaccount (including models that were filtered out), the system SHALL return a 404 Not Found error.

#### Scenario: Model Not Found
- **WHEN** client sends a request with `model: "non-existent-model"`
- **AND** "non-existent-model" is not configured in any subaccount
- **THEN** system logs "Model 'non-existent-model' and fallbacks not available in any subAccount"
- **AND** system returns HTTP 404
- **AND** response body contains error type "not_found_error"

#### Scenario: Model Found
- **WHEN** client sends a request with `model: "gpt-4"`
- **AND** "gpt-4" is configured in a subaccount
- **THEN** system processes the request successfully

#### Scenario: Model filtered out behaves as not configured
- **WHEN** client sends a request with `model: "gpt-4-test"`
- **AND** "gpt-4-test" was configured in deployment_models but filtered out by model_filters
- **THEN** system SHALL treat "gpt-4-test" as if it was never configured
- **AND** system logs "Model 'gpt-4-test' and fallbacks not available in any subAccount"
- **AND** system returns HTTP 404
- **AND** response body contains error type "not_found_error"

#### Scenario: Fallback model filtered out
- **WHEN** client sends a request with a model that has a fallback
- **AND** the primary model is not found but the fallback model was filtered out during config loading
- **THEN** system SHALL skip the filtered fallback and continue fallback chain
- **AND** if no valid fallback remains, system SHALL return HTTP 404
