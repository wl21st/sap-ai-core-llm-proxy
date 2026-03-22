## ADDED Requirements

### Requirement: Info endpoint returns proxy configuration details

The system SHALL return JSON details about the proxy configuration, including active subaccounts, default model, and related settings when the `/info` endpoint is accessed.

#### Scenario: Retrieve proxy info
- **WHEN** a GET request is sent to `/info`
- **THEN** the response status code is 200
- **AND** the response body is a JSON object containing `subaccounts`, `defaultModel`, and any other relevant configuration fields
- **AND** the returned data matches the structure defined in the configuration schema