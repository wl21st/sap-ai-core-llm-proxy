# Design: Re-authenticate on Error

## Architecture

The re-authentication logic will be implemented in the request handling layer, specifically where the backend API calls are made.

### 1. Token Manager Updates

- Add an `invalidate_token()` method to `TokenManager` in `auth/token_manager.py` to explicitly clear the cached token.

### 2. Request Handling Updates

The `proxy_claude_request` and `proxy_claude_request_original` functions in `blueprints/messages.py` need to be updated.

#### Workflow for `proxy_claude_request_original` (Manual Token Management)

1. **Attempt 1**: Make backend request with existing logic (using cached token).
2. **Check Result**:
    - If success (200 OK): Return result.
    - If error 401 or 403:
        - Log the auth error.
        - Call `token_manager.invalidate_token()`.
        - **Attempt 2**:
            - Fetch new token (via `token_manager.get_token()`).
            - Update `Authorization` header.
            - Retry `make_backend_request`.
    - If other error: Return error.

#### Workflow for `proxy_claude_request` (SDK)

The SDK (`gen_ai_hub`) handles tokens internally. We need to investigate if the SDK exposes a way to invalidate the token or if we need to recreate the client.
If `AIAPIAuthenticatorException` is thrown, it indicates a failure to *get* a token. We should catch this and potentially retry if it's considered transient, or return a clear error.
For 401/403 from the SDK call (`invoke_bedrock_streaming`), the SDK might already handle retries. If not, we might need to recreate the `bedrock_client` to force a new token fetch.

### 3. Streaming Retry Implementation

The streaming path (`generate_claude_streaming_response` in `handlers/streaming_generators.py`) also implements retry logic for 401/403 errors:
- The function accepts an optional `token_manager` parameter
- Before making the streaming request, it checks if a 401/403 response is received
- If so, it invalidates the token and retries with a fresh token
- The retry logic is implemented for both Claude and non-Claude (Gemini/OpenAI) model backends

**Limitation**: The streaming retry only works for the original implementation path (`proxy_claude_request_original`). The SDK path (`proxy_claude_request`) handles streaming differently through the Bedrock SDK's `invoke_bedrock_streaming` function.

### 4. Shared Logic

To avoid code duplication, we can introduce a wrapper function or decorator, but explicit handling is preferred for clarity given the different paths (SDK vs manual).

## Trade-offs

- **Latency**: A failed request + token fetch + retry will increase latency for that specific request. However, this is better than a failure.
- **Complexity**: Adds a retry loop to the request path.

## Alternatives Considered

- **Middleware**: Implementing this as a decorator or middleware. Given the explicit token management in `proxy_server.py`/`blueprints/messages.py`, a decorator might be hard to inject without refactoring `TokenManager` access.

## Implementation Notes

- **Retry Limit**: Currently hardcoded to 1 retry (`AUTH_RETRY_MAX = 1`) to avoid infinite loops and excessive latency.
- **Error Message Standardization**: A helper function `_log_auth_error_retry()` is used across all retry locations to ensure consistent log formatting.
- **Thread Safety**: Token invalidation uses existing locks (`self._lock` in TokenManager) to protect shared state.