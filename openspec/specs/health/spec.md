## ADDED Requirements

### Requirement: Health endpoint returns 200 OK

The system SHALL return an HTTP 200 status code when the `/health` endpoint is accessed.

#### Scenario: Successful health check
- **WHEN** a GET request is sent to `/health`
- **THEN** the response status code is 200
- **AND** the response body is a JSON object containing `{"status":"ok"}`