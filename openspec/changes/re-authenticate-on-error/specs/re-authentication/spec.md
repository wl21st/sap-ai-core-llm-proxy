# Capability: Re-authentication

## ADDED Requirements

### Requirement: Re-authenticate on 401/403 Errors

The proxy MUST automatically re-authenticate and retry the request when the backend returns a 401 Unauthorized or 403 Forbidden error.

#### Scenario: Token Expired or Revoked

- **GIVEN** a valid request with a cached but now invalid backend token
- **WHEN** the proxy forwards the request to the backend
- **AND** the backend returns HTTP 401 or 403
- **THEN** the proxy should invalidate the cached token
- **AND** fetch a new token from the authentication service
- **AND** retry the request with the new token
- **AND** return the successful response to the client
