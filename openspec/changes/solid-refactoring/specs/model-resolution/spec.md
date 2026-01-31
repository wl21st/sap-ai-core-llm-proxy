## MODIFIED Requirements

### Requirement: Model Fallback and Validation
The system SHALL validate the requested model against configured subaccounts and deployment URLs using the `ModelHandlerRegistry` to determine model type. If the model or its fallback is not found in any subaccount, the system SHALL return a 404 Not Found error.

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

#### Scenario: Model type detection via registry
- **WHEN** the load balancer resolves a model to a deployment URL
- **THEN** model type detection SHALL use `ModelHandlerRegistry.get_handler(model)`
- **AND** the handler SHALL determine the appropriate endpoint and conversion logic

## ADDED Requirements

### Requirement: Registry-based model resolution
The system SHALL use the `ModelHandlerRegistry` to determine model type during URL resolution, replacing direct calls to `Detector` methods in the load balancer.

#### Scenario: Load balancer handler lookup
- **WHEN** `load_balance_url()` needs to determine model type
- **THEN** it SHALL call `ModelHandlerRegistry.get_handler(model)`
- **AND** it SHALL NOT use if/elif chains with `Detector.is_claude_model()`, `Detector.is_gemini_model()`, etc.

### Requirement: Handler-provided endpoint selection
Each model handler SHALL specify its required API endpoint, eliminating endpoint selection logic from the load balancer.

#### Scenario: Endpoint from handler
- **WHEN** a request needs to be routed to a backend
- **THEN** the handler returned by the registry SHALL provide the endpoint path
- **AND** the load balancer SHALL append this path to the deployment URL
