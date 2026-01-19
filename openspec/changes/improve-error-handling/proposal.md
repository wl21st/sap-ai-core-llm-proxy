# Change: Improve Error Handling

## Why

The current error handling in the proxy server has several limitations:

1. **Inconsistent HTTP Status Handling**: HTTP errors (400, 401, 403, 429, 500, 502, 503, 504) are handled inconsistently across different endpoints. Only 429 has a dedicated handler, while other status codes are processed ad-hoc with scattered try-except blocks.

2. **Limited Retry Logic**: The retry mechanism (`@bedrock_retry`) only handles rate limit errors (429) and uses string matching for detection. Transient network failures (502, 503, 504) are not retried, leading to unnecessary failures.

3. **Generic Converter Errors**: Format converters in `proxy_helpers.py` raise generic `ValueError` and `Exception` without semantic meaning. Clients receive unhelpful error messages like "Failed to convert" without understanding what went wrong.

4. **No Custom Exception Hierarchy**: The codebase lacks custom exception classes, making it difficult to categorize and handle different error types consistently.

5. **Authentication Error Handling**: Token manager has basic error handling but doesn't provide actionable error context for different authentication failure scenarios (e.g., invalid credentials, expired tokens, network timeouts).

## What Changes

- **Add Custom Exception Hierarchy**: Create semantic exception classes for network failures, authentication errors, conversion errors, and rate limits to enable granular error handling.

- **Holistic HTTP Status Handling**: Implement centralized handlers for all HTTP status codes (400, 401, 403, 429, 500, 502, 503, 504) with consistent error response formatting.

- **Enhanced Retry Logic**: Extend retry mechanism to include transient server errors (502, 503, 504) in addition to rate limits (429), with configurable retry policies.

- **Semantic Converter Errors**: Replace generic exceptions in format converters with specific error types that indicate the conversion failure reason (e.g., `InvalidResponseStructureError`, `MissingFieldError`, `TypeError`).

- **Improved Authentication Error Handling**: Enhance token manager to provide specific error types for authentication failures with actionable error messages.

- **Centralized Error Logging**: Implement consistent error logging with trace IDs, request context, and severity levels across all error scenarios.

## Impact

- **Affected specs**:
  - `error-handling` (new capability)

- **Affected code**:
  - `proxy_server.py` - Update all route handlers to use new error handling
  - `proxy_helpers.py` - Replace generic exceptions with semantic errors in converters
  - `auth/token_manager.py` - Enhance authentication error handling
  - `utils/error_handlers.py` - Add handlers for additional HTTP status codes
  - `utils/exceptions.py` - New file for custom exception hierarchy
  - `tests/` - Add comprehensive error handling tests

- **Breaking changes**: None - this is a non-breaking improvement to error handling
