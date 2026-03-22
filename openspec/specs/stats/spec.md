## ADDED Requirements

### Requirement: Stats endpoint returns request metrics

The system SHALL return JSON metrics about request volume, load‑balancer status, and uptime when the `/stats` endpoint is accessed.

#### Scenario: Retrieve statistics
- **WHEN** a GET request is sent to `/stats`
- **THEN** the response status code is 200
- **AND** the response body is a JSON object containing `requestCount`, `uptimeSeconds`, and `loadBalancerStatus`
- **AND** the values are non‑negative integers or strings as appropriate