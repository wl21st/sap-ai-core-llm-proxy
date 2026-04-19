## ADDED Requirements

### Requirement: Foundation Model List Discovery
The system SHALL fetch the list of available foundation models from `GET /v2/lm/foundation-models` for each configured subaccount at startup and cache the result in memory for a configurable TTL (default 24 hours).

#### Scenario: Successful model discovery at startup
- **WHEN** the proxy starts with valid subaccount credentials
- **THEN** it calls `GET /v2/lm/foundation-models` for each subaccount
- **AND** it stores the union of all returned model names in an in-memory model registry
- **AND** the registry is available before the first request is served

#### Scenario: Discovery failure at startup
- **WHEN** `GET /v2/lm/foundation-models` returns an error for a subaccount
- **THEN** the proxy logs a warning with the error details
- **AND** continues startup using any successfully fetched models from other subaccounts
- **AND** optionally uses a hardcoded static model list as fallback

### Requirement: Models Endpoint Response
The system SHALL serve the discovered model list at `GET /v1/models` in OpenAI-compatible format, listing all foundation models available across all configured subaccounts.

#### Scenario: Models endpoint returns discovered models
- **WHEN** a client sends `GET /v1/models`
- **THEN** the response contains an OpenAI-compatible model list object with all discovered model IDs
- **AND** each entry includes at minimum `id`, `object: "model"`, and `created` fields

#### Scenario: Model list refreshed after TTL
- **WHEN** the model registry TTL has expired (default 24h)
- **AND** a client calls `GET /v1/models` or a new inference request arrives
- **THEN** the proxy re-fetches `GET /v2/lm/foundation-models` in the background
- **AND** serves the previous cached list until the refresh completes

### Requirement: Static Fallback Model List
The system SHALL support a static fallback model list that is used when `GET /v2/lm/foundation-models` is unavailable or not yet fetched.

#### Scenario: Static fallback used when discovery unavailable
- **WHEN** the foundation model API is unreachable
- **THEN** the proxy falls back to the hardcoded static list of known models
- **AND** logs a warning that discovery failed and fallback is in use
