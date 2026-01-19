# Error Handling Specification

This specification defines requirements for comprehensive error handling in the SAP AI Core LLM Proxy, including network failures, rate limits, authentication errors, and converter semantics.

## ADDED Requirements

### Requirement: Custom Exception Hierarchy

The system SHALL provide a custom exception hierarchy to enable granular error handling across all proxy components.

#### Scenario: Network Error Detection
- **GIVEN** a network connection fails or times out
- **WHEN** the error occurs in token manager or backend request
- **THEN** raise `NetworkError` or its subclass (`ConnectionTimeoutError`, `TransientServerError`)
- **AND** the exception includes context (URL, timeout, status code)

#### Scenario: Authentication Error Detection
- **GIVEN** authentication fails during token fetch
- **WHEN** the failure is due to invalid credentials
- **THEN** raise `InvalidCredentialsError` with subaccount name
- **WHEN** the failure is due to token expiration
- **THEN** raise `TokenExpiredError`
- **WHEN** the failure is due to other HTTP errors
- **THEN** raise `TokenFetchError` with status code

#### Scenario: Conversion Error Detection
- **GIVEN** a format conversion fails in converters
- **WHEN** the response structure is invalid
- **THEN** raise `InvalidResponseStructureError` with response context
- **WHEN** a required field is missing
- **THEN** raise `MissingFieldError` with field name and context
- **WHEN** request validation fails
- **THEN** raise `ValidationError` with validation details

#### Scenario: Rate Limit Error Detection
- **GIVEN** a rate limit error occurs (HTTP 429)
- **WHEN** the error is detected from backend response
- **THEN** raise `RateLimitError` with retry information from headers

### Requirement: Holistic HTTP Status Handling

The system SHALL handle all HTTP status codes consistently across all endpoints with centralized error handlers.

#### Scenario: HTTP 400 Bad Request
- **GIVEN** a client sends an invalid request
- **WHEN** backend returns HTTP 400
- **THEN** log error with request context and trace ID
- **AND** return JSON error response with status 400
- **AND** include error message from backend or generic message

#### Scenario: HTTP 401 Unauthorized
- **GIVEN** authentication credentials are invalid
- **WHEN** backend returns HTTP 401
- **THEN** log error with request context
- **AND** return JSON error response with status 401
- **AND** include error message about invalid credentials

#### Scenario: HTTP 403 Forbidden
- **GIVEN** client is not authorized for requested resource
- **WHEN** backend returns HTTP 403
- **THEN** log error with request context
- **AND** return JSON error response with status 403
- **AND** include error message about insufficient permissions

#### Scenario: HTTP 429 Rate Limit
- **GIVEN** rate limit is exceeded
- **WHEN** backend returns HTTP 429
- **THEN** call existing `handle_http_429_error` handler
- **AND** log detailed headers and response body
- **AND** return JSON error response with status 429
- **AND** include `Retry-After` header from backend response

#### Scenario: HTTP 500 Internal Server Error
- **GIVEN** backend encounters an unexpected error
- **WHEN** backend returns HTTP 500
- **THEN** log error with request context and response body
- **AND** return JSON error response with status 500
- **AND** include generic error message (avoid exposing backend details)

#### Scenario: HTTP 502 Bad Gateway
- **GIVEN** backend gateway fails
- **WHEN** backend returns HTTP 502
- **THEN** log error as warning (transient error)
- **AND** trigger retry logic if retry attempts remain
- **AND** return error response if all retries exhausted

#### Scenario: HTTP 503 Service Unavailable
- **GIVEN** backend service is temporarily unavailable
- **WHEN** backend returns HTTP 503
- **THEN** log error as warning (transient error)
- **AND** trigger retry logic if retry attempts remain
- **AND** return error response if all retries exhausted

#### Scenario: HTTP 504 Gateway Timeout
- **GIVEN** backend gateway times out
- **WHEN** backend returns HTTP 504
- **THEN** log error as warning (transient error)
- **AND** trigger retry logic if retry attempts remain
- **AND** return error response if all retries exhausted

#### Scenario: Unknown HTTP Status Code
- **GIVEN** backend returns an unexpected HTTP status code
- **WHEN** status code is not handled by specific handlers
- **THEN** log error with status code and response body
- **AND** return JSON error response with the backend status code
- **AND** include error message from backend if available

#### Scenario: No Response Error
- **GIVEN** network connection fails before receiving response
- **WHEN** HTTPError has no response attribute
- **THEN** log error with exception details
- **AND** return JSON error response with status 500
- **AND** include generic error message about connection failure

### Requirement: Enhanced Retry Logic

The system SHALL automatically retry transient network failures (HTTP 429, 502, 503, 504) and connection errors with exponential backoff.

#### Scenario: Rate Limit Retry
- **GIVEN** backend returns HTTP 429
- **WHEN** retry count is less than maximum attempts
- **THEN** wait exponentially (4s, 8s, 16s) before retry
- **AND** log retry attempt with attempt number and wait time
- **AND** extract `Retry-After` header if present
- **AND** return error response after exhausting retries

#### Scenario: Transient Server Error Retry
- **GIVEN** backend returns HTTP 502, 503, or 504
- **WHEN** retry count is less than maximum attempts
- **THEN** wait exponentially before retry
- **AND** log retry attempt with status code
- **AND** return error response after exhausting retries

#### Scenario: Connection Error Retry
- **GIVEN** network connection fails or times out
- **WHEN** retry count is less than maximum attempts
- **THEN** wait exponentially before retry
- **AND** log retry attempt with error details
- **AND** raise `ConnectionError` after exhausting retries

#### Scenario: Retry Configuration
- **GIVEN** retry logic is configured
- **WHEN** checking retry configuration
- **THEN** use `RETRY_MAX_ATTEMPTS = 4` (1 original + 3 retries)
- **AND** use `RETRY_MULTIPLIER = 2` for exponential backoff
- **AND** use `RETRY_MIN_WAIT = 4` seconds
- **AND** use `RETRY_MAX_WAIT = 16` seconds

#### Scenario: No Retry on Client Errors
- **GIVEN** backend returns HTTP 400, 401, or 403
- **WHEN** these status codes are received
- **THEN** do not retry the request
- **AND** return error response immediately
- **AND** log error with status code

### Requirement: Semantic Converter Errors

The system SHALL provide semantic error types for format converter failures with actionable error messages.

#### Scenario: Invalid Response Structure Error
- **GIVEN** backend response structure does not match expected format
- **WHEN** converting response from Claude/Gemini/OpenAI format
- **THEN** raise `InvalidResponseStructureError`
- **AND** include actual type received vs expected type
- **AND** include the problematic response snippet
- **AND** log error with full response context

#### Scenario: Missing Field Error
- **GIVEN** a required field is missing from response or request
- **WHEN** attempting to access the field during conversion
- **THEN** raise `MissingFieldError`
- **AND** include the name of the missing field
- **AND** include the context (response or request)
- **AND** log error with field path and context

#### Scenario: Validation Error
- **GIVEN** request validation fails (e.g., invalid model, missing parameters)
- **WHEN** validating request before conversion
- **THEN** raise `ValidationError`
- **AND** include the validation rule that failed
- **AND** include the invalid value
- **AND** provide suggestion for valid values if applicable

#### Scenario: Type Conversion Error
- **GIVEN** a field has an unexpected type
- **WHEN** converting field to expected type
- **THEN** raise `TypeError` (or `ValidationError` for schema violations)
- **AND** include the field name
- **AND** include expected type vs actual type
- **AND** log error with field context

### Requirement: Enhanced Authentication Error Handling

The system SHALL provide specific authentication error types with actionable error messages for different failure scenarios.

#### Scenario: Invalid Credentials Error
- **GIVEN** client credentials (client_id, client_secret) are invalid
- **WHEN** token endpoint returns HTTP 401
- **THEN** raise `InvalidCredentialsError`
- **AND** include subaccount name in error message
- **AND** log error with sensitive data redacted
- **AND** propagate error to client as 401 error

#### Scenario: Token Fetch Timeout Error
- **GIVEN** token endpoint request times out
- **WHEN** connection timeout occurs (15 second default)
- **THEN** raise `ConnectionTimeoutError`
- **AND** include token endpoint URL
- **AND** include timeout duration
- **AND** log error with timeout details

#### Scenario: Token Fetch Network Error
- **GIVEN** network connection to token endpoint fails
- **WHEN** connection error occurs
- **THEN** raise `TokenFetchError` with `NetworkError` as cause
- **AND** include token endpoint URL
- **AND** log error with network details
- **AND** trigger retry if configured

#### Scenario: Token Response Parse Error
- **GIVEN** token endpoint returns invalid JSON or missing fields
- **WHEN** parsing token response
- **THEN** raise `TokenFetchError` with `JSONDecodeError` or `MissingFieldError` as cause
- **AND** include response body if available
- **AND** log error with response details

### Requirement: Consistent Error Logging

The system SHALL log all errors consistently with trace IDs, request context, and severity levels.

#### Scenario: Error Logging Format
- **GIVEN** an error occurs during request processing
- **WHEN** logging the error
- **THEN** include trace ID for correlation
- **AND** include request context (endpoint, model, subaccount)
- **AND** include error type and message
- **AND** include stack trace for exceptions (using `exc_info=True`)
- **AND** use appropriate log level (ERROR for failures, WARNING for retries)

#### Scenario: Sensitive Data Redaction
- **GIVEN** logging authentication or token-related errors
- **WHEN** logging error details
- **THEN** redact sensitive data (tokens, secrets, passwords)
- **AND** log subaccount name but not credentials
- **AND** log token status but not token value

#### Scenario: Error Response Logging
- **GIVEN** backend returns an error response
- **WHEN** logging error details
- **THEN** log HTTP status code
- **AND** log response headers (excluding sensitive headers)
- **AND** log response body (truncated if too large)
- **AND** log trace ID for correlation

### Requirement: Backward Compatibility

The system SHALL maintain backward compatibility with existing error handling to avoid breaking client applications.

#### Scenario: Exception Inheritance
- **GIVEN** custom exceptions are added
- **WHEN** existing code catches parent exception types (e.g., `ValueError`, `ConnectionError`)
- **THEN** custom exceptions inherit from standard Python exceptions
- **AND** existing exception handlers continue to work
- **AND** no code changes required for existing clients

#### Scenario: Error Response Format
- **GIVEN** clients expect specific error response format
- **WHEN** returning error responses
- **THEN** maintain existing JSON structure (`{"error": "message"}`)
- **AND** add optional fields (type, details) without breaking existing parsers
- **AND** document new optional fields in API documentation
