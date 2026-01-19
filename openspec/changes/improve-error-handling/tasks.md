# Implementation Tasks

## 1. Foundation: Exception Hierarchy
- [ ] 1.1 Create `utils/exceptions.py` with custom exception classes
  - [ ] 1.1.1 Add `ProxyError` base exception class
  - [ ] 1.1.2 Add network error classes: `NetworkError`, `TransientServerError`, `ConnectionTimeoutError`
  - [ ] 1.1.3 Add authentication error classes: `AuthenticationError`, `InvalidCredentialsError`, `TokenExpiredError`, `TokenFetchError`
  - [ ] 1.1.4 Add conversion error classes: `ConversionError`, `InvalidResponseStructureError`, `MissingFieldError`, `ValidationError`
  - [ ] 1.1.5 Add rate limit error class: `RateLimitError`
  - [ ] 1.1.6 Add docstrings to all exception classes with Args/Raises sections

- [ ] 1.2 Write unit tests for exception hierarchy
  - [ ] 1.2.1 Test exception inheritance from standard Python exceptions
  - [ ] 1.2.2 Test exception context (response, status_code, subaccount, etc.)
  - [ ] 1.2.3 Test exception chaining with `raise ... from err`
  - [ ] 1.2.4 Test exception string representation

- [ ] 1.3 Update token manager to use specific authentication errors
  - [ ] 1.3.1 Replace generic HTTP error handling with specific error types in `_fetch_new_token()`
  - [ ] 1.3.2 Raise `InvalidCredentialsError` for HTTP 401
  - [ ] 1.3.3 Raise `ConnectionTimeoutError` for timeout errors
  - [ ] 1.3.4 Raise `TokenFetchError` for other HTTP errors
  - [ ] 1.3.5 Include context (subaccount name, URL, status code) in exceptions

## 2. HTTP Error Handling Enhancement
- [ ] 2.1 Add helper functions to `utils/error_handlers.py`
  - [ ] 2.1.1 Add `_parse_error_body()` to extract JSON from HTTP response
  - [ ] 2.1.2 Add `_handle_400_error()` for bad request errors
  - [ ] 2.1.3 Add `_handle_401_error()` for unauthorized errors
  - [ ] 2.1.4 Add `_handle_403_error()` for forbidden errors
  - [ ] 2.1.5 Add `_handle_transient_server_error()` for 502, 503, 504 errors
  - [ ] 2.1.6 Add `_handle_500_error()` for internal server errors
  - [ ] 2.1.7 Add `_handle_generic_error()` for unknown status codes
  - [ ] 2.1.8 Add `_handle_no_response_error()` for HTTPError without response

- [ ] 2.2 Create centralized `handle_http_error()` function
  - [ ] 2.2.1 Accept HTTPError exception and context string as parameters
  - [ ] 2.2.2 Route to specific handler based on status code
  - [ ] 2.2.3 Return Flask Response with appropriate status code and JSON body
  - [ ] 2.2.4 Log all error details with trace ID and context
  - [ ] 2.2.5 Redact sensitive data from logs (tokens, credentials)

- [ ] 2.3 Update proxy_server.py route handlers to use centralized error handler
  - [ ] 2.3.1 Update `/v1/chat/completions` endpoint (non-streaming)
  - [ ] 2.3.2 Update `/v1/chat/completions` endpoint (streaming)
  - [ ] 2.3.3 Update `/v1/messages` endpoint (Claude API)
  - [ ] 2.3.4 Update `/v1/embeddings` endpoint
  - [ ] 2.3.5 Update `/v1/models` endpoint
  - [ ] 2.3.6 Replace manual HTTP status checks with `handle_http_error()` calls

## 3. Enhanced Retry Logic
- [ ] 3.1 Refactor retry detection logic
  - [ ] 3.1.1 Rename `retry_on_rate_limit()` to `should_retry_exception()`
  - [ ] 3.1.2 Add status code detection for 502, 503, 504 (in addition to 429)
  - [ ] 3.1.3 Add detection for connection and timeout errors
  - [ ] 3.1.4 Remove string matching fallback (or keep as legacy support)
  - [ ] 3.1.5 Update docstrings to reflect new retry criteria

- [ ] 3.2 Update `@bedrock_retry` decorator
  - [ ] 3.2.1 Use new `should_retry_exception()` function
  - [ ] 3.2.2 Update retry logging to include status code and retry reason
  - [ ] 3.2.3 Ensure exponential backoff is applied correctly
  - [ ] 3.2.4 Verify retry attempts are limited by `RETRY_MAX_ATTEMPTS`

- [ ] 3.3 Add retry tests
  - [ ] 3.3.1 Test retry on HTTP 429 (rate limit)
  - [ ] 3.3.2 Test retry on HTTP 502 (bad gateway)
  - [ ] 3.3.3 Test retry on HTTP 503 (service unavailable)
  - [ ] 3.3.4 Test retry on HTTP 504 (gateway timeout)
  - [ ] 3.3.5 Test no retry on HTTP 400, 401, 403 (client errors)
  - [ ] 3.3.6 Test retry on connection timeout
  - [ ] 3.3.7 Test exponential backoff timing

## 4. Semantic Converter Errors
- [ ] 4.1 Update Claude format converters in `proxy_helpers.py`
  - [ ] 4.1.1 Update `convert_openai_to_claude()` to raise specific errors
  - [ ] 4.1.2 Update `convert_claude_to_openai()` to raise `InvalidResponseStructureError` or `MissingFieldError`
  - [ ] 4.1.3 Update `convert_openai_to_claude37()` to raise specific errors
  - [ ] 4.1.4 Update `convert_claude37_to_openai()` to raise specific errors
  - [ ] 4.1.5 Update `convert_claude_chunk_to_openai()` to raise specific errors
  - [ ] 4.1.6 Update `convert_claude37_chunk_to_openai()` to raise specific errors

- [ ] 4.2 Update Gemini format converters in `proxy_helpers.py`
  - [ ] 4.2.1 Update `convert_openai_to_gemini()` to raise `ValidationError`
  - [ ] 4.2.2 Update `convert_gemini_to_openai()` to raise `InvalidResponseStructureError` or `MissingFieldError`
  - [ ] 4.2.3 Update `convert_gemini_response_to_claude()` to raise specific errors
  - [ ] 4.2.4 Update `convert_gemini_chunk_to_openai()` to raise specific errors

- [ ] 4.3 Add error context to converter exceptions
  - [ ] 4.3.1 Include response model name in error context
  - [ ] 4.3.2 Include field name for `MissingFieldError`
  - [ ] 4.3.3 Include expected vs actual type for type errors
  - [ ] 4.3.4 Include problematic snippet for structure errors
  - [ ] 4.3.5 Provide actionable error messages

- [ ] 4.4 Update converter error handling tests
  - [ ] 4.4.1 Update `TestConvertersErrorHandling` test class
  - [ ] 4.4.2 Update `TestConvertersResponseErrorHandling` test class
  - [ ] 4.4.3 Test that specific exceptions are raised for different error scenarios
  - [ ] 4.4.4 Test error context is included in exceptions
  - [ ] 4.4.5 Test error messages are actionable

## 5. Error Logging Enhancement
- [ ] 5.1 Implement consistent error logging format
  - [ ] 5.1.1 Add trace ID to all error logs
  - [ ] 5.1.2 Add request context (endpoint, model, subaccount) to error logs
  - [ ] 5.1.3 Add error type and message to error logs
  - [ ] 5.1.4 Ensure `exc_info=True` is used for exception logging
  - [ ] 5.1.5 Use appropriate log levels (ERROR for failures, WARNING for retries)

- [ ] 5.2 Implement sensitive data redaction
  - [ ] 5.2.1 Redact tokens from authentication error logs
  - [ ] 5.2.2 Redact credentials (client_secret, password) from logs
  - [ ] 5.2.3 Keep subaccount name in logs (not sensitive)
  - [ ] 5.2.4 Log token status (valid/expired) without exposing token value

- [ ] 5.3 Add error response logging
  - [ ] 5.3.1 Log HTTP status code for backend errors
  - [ ] 5.3.2 Log response headers (excluding sensitive headers)
  - [ ] 5.3.3 Log response body (truncated if >1KB)
  - [ ] 5.3.4 Log trace ID for correlation with request logs

- [ ] 5.4 Add logging tests
  - [ ] 5.4.1 Test that trace ID is included in all error logs
  - [ ] 5.4.2 Test that sensitive data is redacted from logs
  - [ ] 5.4.3 Test that error context is included in logs
  - [ ] 5.4.4 Test log levels are appropriate for error types

## 6. Integration Testing
- [ ] 6.1 Add integration tests for error handling
  - [ ] 6.1.1 Test error handling for invalid model names (400)
  - [ ] 6.1.2 Test error handling for invalid authentication tokens (401)
  - [ ] 6.1.3 Test error handling for rate limit scenarios (429)
  - [ ] 6.1.4 Test error handling for backend failures (500, 502, 503, 504)
  - [ ] 6.1.5 Test error handling for converter failures
  - [ ] 6.1.6 Test error handling for token fetch failures

- [ ] 6.2 Add streaming error handling tests
  - [ ] 6.2.1 Test error handling during streaming responses
  - [ ] 6.2.2 Test error propagation in streaming context
  - [ ] 6.2.3 Test client receives error events in SSE stream

## 7. Documentation
- [ ] 7.1 Update API documentation
  - [ ] 7.1.1 Document error response format (JSON structure)
  - [ ] 7.1.2 Document new optional error fields (type, details)
  - [ ] 7.1.3 Document status codes returned by proxy
  - [ ] 7.1.4 Document retry behavior and configuration

- [ ] 7.2 Update code documentation
  - [ ] 7.2.1 Add docstrings to all new exception classes
  - [ ] 7.2.2 Update docstrings for error handler functions
  - [ ] 7.2.3 Update docstrings for retry functions

- [ ] 7.3 Add migration guide
  - [ ] 7.3.1 Document exception hierarchy changes
  - [ ] 7.3.2 Document backward compatibility guarantees
  - [ ] 7.3.3 Document code changes required for existing clients (if any)

## 8. Validation and Deployment
- [ ] 8.1 Run existing test suite
  - [ ] 8.1.1 Run `make test` to ensure no regressions
  - [ ] 8.1.2 Run `make test-cov` to check coverage
  - [ ] 8.1.3 Fix any failing tests

- [ ] 8.2 Validate OpenSpec proposal
  - [ ] 8.2.1 Run `openspec validate improve-error-handling --strict`
  - [ ] 8.2.2 Fix any validation errors

- [ ] 8.3 Code review and approval
  - [ ] 8.3.1 Submit for code review
  - [ ] 8.3.2 Address review feedback
  - [ ] 8.3.3 Get approval for implementation

- [ ] 8.4 Deploy to staging environment
  - [ ] 8.4.1 Deploy changes to staging
  - [ ] 8.4.2 Monitor error logs and retry patterns
  - [ ] 8.4.3 Collect feedback from users
  - [ ] 8.4.4 Fix any issues found during monitoring

- [ ] 8.5 Deploy to production
  - [ ] 8.5.1 Deploy changes to production
  - [ ] 8.5.2 Monitor error rates and patterns
  - [ ] 8.5.3 Verify retry behavior is working as expected
  - [ ] 8.5.4 Document any post-deployment issues

## Dependencies
- Task 1 must be completed before Task 2 (exception hierarchy needed before HTTP error handlers)
- Task 2 must be completed before Task 3 (HTTP error handlers needed before retry logic integration)
- Task 4 can be done in parallel with Task 2 and Task 3
- Task 5 can be done in parallel with Tasks 2-4
- Task 6 depends on completion of Tasks 1-5
- Task 7 depends on completion of Tasks 1-6
- Task 8 is final phase after all implementation is complete

## Parallelizable Work
- Tasks 1.1, 1.2, and 1.3 can be done in parallel by different developers
- Tasks 2.1, 2.2, and 2.3 can be done sequentially (2.1 → 2.2 → 2.3)
- Tasks 4.1 and 4.2 can be done in parallel (Claude and Gemini converters)
- Tasks 5.1, 5.2, and 5.3 can be done in parallel
