# Capability: Token Fetching

## Purpose

Define how authentication tokens are fetched and how TLS certificate handling is applied during token retrieval.

## Requirements

### Requirement: Token fetching with TLS certificate handling
Token manager SHALL fetch authentication tokens from SAP AI Core using explicit TLS CA certificate handling to prevent failures when certifi is unavailable or misconfigured.

#### Scenario: Token fetched with resolved certificate
- **WHEN** token manager needs to fetch a token
- **THEN** token manager SHALL use the resolved CA certificate bundle for the HTTPS request

#### Scenario: Clear error on TLS certificate failure
- **WHEN** token fetch fails due to missing or invalid TLS certificate
- **THEN** proxy SHALL catch the error and return a message distinguishing TLS issues from authentication failures, including troubleshooting guidance

#### Scenario: Token fetch succeeds with fallback certificate
- **WHEN** default certifi path is unavailable but system certificate path is available
- **THEN** token manager SHALL use the system certificate and succeed
