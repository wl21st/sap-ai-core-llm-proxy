## ADDED Requirements

### Requirement: Background smoke test for authn status and re-auth across Anthropic, OpenAI, and embedding models

The system SHALL periodically check authentication status for each of the supported model providers (Anthropic, OpenAI, embedding) and initiate re-authentication when a failure is detected.

#### Scenario: Successful auth status check
- **WHEN** the background smoke test runs
- **THEN** it successfully retrieves an authentication status of "ok" from each provider
- **AND** no re-auth request is issued

#### Scenario: Detected authentication failure
- **WHEN** the background smoke test receives an authentication error from any provider
- **THEN** the system SHALL initiate a re-authentication flow for that provider
- **AND** upon successful re-auth, it updates the local cache and logs the event

### Requirement: Persist smoke test result history in SQLite

The system SHALL store each smoke test execution result (including timestamp, provider, status, and latency) in a local SQLite database.

#### Scenario: Insert result into database
- **WHEN** the background smoke test finishes execution
- **THEN** the result is inserted into a table named `smoke_test_results`
- **AND** the row includes columns `id`, `timestamp`, `provider`, `status`, `latency_ms`