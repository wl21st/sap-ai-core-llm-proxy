# Design: Re-authenticate on Error

## Architecture

The re-authentication logic will be implemented in the request handling layer, specifically where the backend API calls are made.

### 1. Token Manager Updates

- Add an `invalidate_token()` method to `TokenManager` to explicitly clear the cached token.

### 2. Request Handling Updates

The `proxy_claude_request_original` and `handle_non_streaming_request` functions (and potentially others using `make_backend_request`) need to be updated.

#### Workflow

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

### 3. Shared Logic

To avoid code duplication, we can introduce a wrapper function `execute_with_retry` or similar, but given the current structure where headers are constructed in `proxy_server.py`, explicit handling in the main flow might be clearer for now.

## Trade-offs

- **Latency**: A failed request + token fetch + retry will increase latency for that specific request. However, this is better than a failure.
- **Complexity**: Adds a retry loop to the request path.

## Alternatives Considered

- **Middleware**: Implementing this as a decorator or middleware. Given the explicit token management in `proxy_server.py`, a decorator might be hard to inject without refactoring `TokenManager` access.
