# Design: Improved Error Handling

## Context

The SAP AI Core LLM Proxy currently has inconsistent error handling across different components:

- **Network/HTTP Errors**: Only HTTP 429 has a dedicated handler; other status codes (400, 401, 403, 500, 502, 503, 504) are handled ad-hoc in each route handler.
- **Retry Logic**: Limited to rate limit errors (429) using string matching; transient server errors (502, 503, 504) are not retried.
- **Converter Errors**: Generic `ValueError` and `Exception` are raised in format converters without semantic meaning.
- **Authentication Errors**: Token manager has basic error handling but lacks specific error types for different failure scenarios.
- **No Exception Hierarchy**: The codebase uses only standard Python exceptions, making granular error handling difficult.

**Stakeholders**:
- Proxy server users (applications consuming the proxy API)
- Proxy server developers (maintaining and extending error handling)
- SAP AI Core operators (monitoring and troubleshooting issues)

## Goals / Non-Goals

### Goals
1. **Consistent Error Handling**: Provide unified handling for all HTTP status codes (400, 401, 403, 429, 500, 502, 503, 504).
2. **Semantic Error Types**: Create custom exception classes that indicate the nature of the error (network, authentication, conversion, rate limit).
3. **Enhanced Retry Logic**: Extend retry mechanism to include transient server errors (502, 503, 504) in addition to rate limits (429).
4. **Actionable Error Messages**: Provide detailed, actionable error messages to clients for debugging and troubleshooting.
5. **Centralized Error Logging**: Implement consistent error logging with trace IDs, request context, and severity levels.

### Non-Goals
1. **Breaking API Changes**: This improvement should be non-breaking for existing clients.
2. **Retry All Errors**: Only retry transient errors (429, 502, 503, 504), not client errors (400, 401, 403).
3. **External Service Integration**: This change is internal to the proxy; no changes to SAP AI Core or external services.

## Decisions

### Decision 1: Custom Exception Hierarchy

**What**: Create a custom exception hierarchy in `utils/exceptions.py` with semantic error types.

**Why**:
- Enables granular exception handling (e.g., catch only authentication errors, not all errors).
- Provides meaningful error types for logging and monitoring.
- Allows clients to understand error categories programmatically.

**Implementation**:
```python
# Base exception for all proxy errors
class ProxyError(Exception):
    """Base exception for all proxy-related errors."""

# Network-related errors
class NetworkError(ProxyError):
    """Base class for network-related errors."""

class TransientServerError(NetworkError):
    """Transient server errors (502, 503, 504) that can be retried."""

class ConnectionTimeoutError(NetworkError):
    """Timeout when connecting to backend service."""

# Authentication errors
class AuthenticationError(ProxyError):
    """Base class for authentication-related errors."""

class InvalidCredentialsError(AuthenticationError):
    """Invalid client credentials."""

class TokenExpiredError(AuthenticationError):
    """Authentication token has expired."""

class TokenFetchError(AuthenticationError):
    """Failed to fetch authentication token."""

# Conversion errors
class ConversionError(ProxyError):
    """Base class for format conversion errors."""

class InvalidResponseStructureError(ConversionError):
    """Backend response structure does not match expected format."""

class MissingFieldError(ConversionError):
    """Required field is missing from response or request."""

class ValidationError(ConversionError):
    """Request validation failed (e.g., invalid model, missing parameters)."""

# Rate limit errors
class RateLimitError(ProxyError):
    """Rate limit exceeded (HTTP 429)."""
```

**Alternatives considered**:
- Use standard Python exceptions only: Rejected because they don't provide semantic meaning.
- Use third-party exception libraries (e.g., `requests.exceptions`): Rejected because they are HTTP-specific and don't cover all proxy error scenarios.

### Decision 2: Centralized HTTP Status Handler

**What**: Create a centralized HTTP error handler in `utils/error_handlers.py` that handles all HTTP status codes consistently.

**Why**:
- Eliminates code duplication across route handlers.
- Ensures consistent error response format.
- Simplifies adding new status code handlers in the future.

**Implementation**:
```python
def handle_http_error(http_err: HTTPError, context: str = "request") -> Response:
    """Handle HTTP errors consistently across all endpoints.

    Args:
        http_err: The HTTPError exception from requests library.
        context: Description of the request context for logging.

    Returns:
        A Flask response object with appropriate status code and error details.
    """
    if http_err.response is None:
        return _handle_no_response_error(http_err, context)

    status_code = http_err.response.status_code
    response_body = _parse_error_body(http_err.response)

    # Route to specific handler based on status code
    if status_code == 400:
        return _handle_400_error(response_body, context)
    elif status_code == 401:
        return _handle_401_error(response_body, context)
    elif status_code == 403:
        return _handle_403_error(response_body, context)
    elif status_code == 429:
        return handle_http_429_error(http_err, context)
    elif status_code in (502, 503, 504):
        return _handle_transient_server_error(status_code, response_body, context)
    elif status_code == 500:
        return _handle_500_error(response_body, context)
    else:
        return _handle_generic_error(status_code, response_body, context)
```

**Alternatives considered**:
- Use Flask `@app.errorhandler` decorator: Rejected because it doesn't work well with nested exceptions and doesn't provide enough context for logging.
- Keep per-endpoint error handling: Rejected because it leads to code duplication and inconsistent behavior.

### Decision 3: Enhanced Retry Logic

**What**: Extend the `retry_on_rate_limit` function to include transient server errors (502, 503, 504) and use status code detection instead of string matching.

**Why**:
- Transient server errors are temporary and should be retried automatically.
- Status code detection is more reliable than string matching.
- Reduces unnecessary failures for transient issues.

**Implementation**:
```python
def should_retry_exception(exception) -> bool:
    """Check if exception should be retried.

    Args:
        exception: The exception to check.

    Returns:
        True if exception should be retried, False otherwise.
    """
    # Check for ClientError with retryable status codes
    if isinstance(exception, ClientError):
        http_status = exception.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return http_status in (429, 502, 503, 504)

    # Check for HTTPError with retryable status codes
    if isinstance(exception, HTTPError) and exception.response is not None:
        return exception.response.status_code in (429, 502, 503, 504)

    # Check for connection/timeout errors
    if isinstance(exception, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True

    # Fallback to string matching for legacy compatibility
    error_message = str(exception).lower()
    retryable_patterns = [
        "too many tokens", "rate limit", "throttling",
        "too many requests", "exceeding the allowed request",
        "rate limited by ai core", "connection refused",
        "connection timeout", "read timeout"
    ]
    return any(pattern in error_message for pattern in retryable_patterns)
```

**Alternatives considered**:
- Retry all 5xx errors: Rejected because 500 errors are typically application bugs, not transient issues.
- Retry on timeout only: Rejected because other transient errors (502, 503, 504) should also be retried.

### Decision 4: Semantic Converter Errors

**What**: Replace generic exceptions in format converters with specific error types from the custom exception hierarchy.

**Why**:
- Provides clear indication of what went wrong during conversion.
- Enables clients to handle specific conversion errors programmatically.
- Improves debugging with actionable error messages.

**Implementation**:
```python
# Example in proxy_helpers.py
def convert_claude_to_openai(response: dict, model: str) -> dict:
    """Convert Claude response to OpenAI format.

    Args:
        response: Claude API response.
        model: Model name for routing.

    Returns:
        OpenAI-compatible response.

    Raises:
        InvalidResponseStructureError: If response structure is invalid.
        MissingFieldError: If required field is missing.
    """
    # Check response structure
    if not isinstance(response, dict):
        raise InvalidResponseStructureError(
            f"Expected dict, got {type(response).__name__}",
            response=response
        )

    # Check required fields
    required_fields = ["id", "type", "role", "content"]
    for field in required_fields:
        if field not in response:
            raise MissingFieldError(
                f"Missing required field: {field}",
                response=response
            )

    # ... conversion logic ...
```

**Alternatives considered**:
- Keep generic exceptions: Rejected because they don't provide semantic meaning.
- Return error objects instead of raising exceptions: Rejected because it breaks Python exception handling conventions.

### Decision 5: Enhanced Authentication Error Handling

**What**: Enhance token manager to raise specific authentication error types based on the failure scenario.

**Why**:
- Provides actionable error messages for different authentication failures.
- Enables clients to distinguish between expired tokens, invalid credentials, and network issues.

**Implementation**:
```python
def _fetch_new_token(self) -> str:
    """Fetch new token from SAP AI Core.

    Raises:
        InvalidCredentialsError: If client credentials are invalid (401).
        TokenFetchError: If token fetch fails for other reasons.
        ConnectionTimeoutError: If token endpoint times out.
    """
    try:
        response = requests.post(token_url, headers=headers, timeout=15)
        response.raise_for_status()

        # ... token extraction logic ...

    except requests.exceptions.Timeout as err:
        raise ConnectionTimeoutError(
            f"Timeout connecting to token endpoint for subaccount '{self.subaccount.name}'",
            url=token_url,
            timeout=15
        ) from err

    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            raise InvalidCredentialsError(
                f"Invalid client credentials for subaccount '{self.subaccount.name}'",
                subaccount=self.subaccount.name
            ) from err
        else:
            raise TokenFetchError(
                f"HTTP error {err.response.status_code} fetching token for '{self.subaccount.name}'",
                status_code=err.response.status_code,
                subaccount=self.subaccount.name
            ) from err

    except Exception as err:
        raise TokenFetchError(
            f"Unexpected error fetching token for '{self.subaccount.name}': {err}",
            subaccount=self.subaccount.name
        ) from err
```

**Alternatives considered**:
- Keep existing generic error handling: Rejected because it doesn't provide actionable error information.
- Return error codes instead of raising exceptions: Rejected because it breaks Python exception handling conventions.

## Risks / Trade-offs

### Risk 1: Increased Complexity
**Risk**: Adding custom exception hierarchy increases code complexity.

**Mitigation**:
- Keep exception hierarchy simple and flat (3-4 levels deep).
- Provide clear docstrings for each exception type.
- Add comprehensive tests for exception handling.

### Risk 2: Breaking Changes
**Risk**: Changes to exception types could break existing code that catches specific exceptions.

**Mitigation**:
- Ensure new exceptions inherit from standard Python exceptions (e.g., `ValueError`, `ConnectionError`).
- Maintain backward compatibility by catching parent exception types.
- Document all exception changes in migration guide.

### Risk 3: Over-Retrying
**Risk**: Retrying transient server errors could lead to increased latency or infinite retry loops.

**Mitigation**:
- Limit retry attempts with `RETRY_MAX_ATTEMPTS`.
- Use exponential backoff with `RETRY_MAX_WAIT` to avoid overwhelming the server.
- Log all retry attempts for monitoring.

## Migration Plan

### Phase 1: Exception Hierarchy (1-2 days)
1. Create `utils/exceptions.py` with custom exception classes.
2. Add unit tests for all exception types.
3. Update token manager to raise specific authentication errors.

### Phase 2: Enhanced HTTP Error Handling (2-3 days)
1. Implement centralized HTTP error handler in `utils/error_handlers.py`.
2. Add handlers for status codes 400, 401, 403, 500, 502, 503, 504.
3. Update all route handlers in `proxy_server.py` to use centralized handler.

### Phase 3: Enhanced Retry Logic (1-2 days)
1. Extend `retry_on_rate_limit` to include transient server errors.
2. Replace string matching with status code detection.
3. Update `@bedrock_retry` decorator to use new retry logic.
4. Add tests for retry behavior.

### Phase 4: Semantic Converter Errors (2-3 days)
1. Update all converters in `proxy_helpers.py` to raise specific errors.
2. Ensure error messages are actionable and include context.
3. Add tests for converter error handling.

### Phase 5: Rollout and Monitoring (1-2 days)
1. Deploy to staging environment.
2. Monitor error logs and retry patterns.
3. Collect feedback from users.
4. Fix any issues found during monitoring.

### Rollback Plan
If critical issues are discovered:
1. Revert changes to `proxy_server.py`, `proxy_helpers.py`, `auth/token_manager.py`.
2. Restore previous error handling implementation.
3. Document issues and schedule fix for next release.

## Open Questions

1. **Retry Configuration**: Should retry parameters (max attempts, wait times) be configurable via `config.json`?
2. **Error Logging Level**: What logging level should be used for each error type (DEBUG, INFO, WARNING, ERROR)?
3. **Client Error Detail**: Should detailed error information be included in client responses for 4xx errors, or should we log detailed info server-side only?

These questions will be answered during implementation based on operational requirements and user feedback.
