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

### 3. Shared Logic

To avoid code duplication, we can introduce a wrapper function or decorator, but explicit handling is preferred for clarity given the different paths (SDK vs manual).

## Trade-offs

- **Latency**: A failed request + token fetch + retry will increase latency for that specific request. However, this is better than a failure.
- **Complexity**: Adds a retry loop to the request path.

## Alternatives Considered

- **Middleware**: Implementing this as a decorator or middleware. Given the explicit token management in `proxy_server.py`/`blueprints/messages.py`, a decorator might be hard to inject without refactoring `TokenManager` access.