## Context

The current implementation of `proxy_claude_request` catches `ValueError` from the load balancer and returns a 400 Bad Request error. This is misleading when the cause is a missing model, which should correspond to a 404 Not Found.

## Goals / Non-Goals

**Goals:**
- Ensure requests for non-existent models return HTTP 404.
- Use a clear error type (`not_found_error`) in the response body.

**Non-Goals:**
- modifying the load balancer logic itself (other than potentially error messages if needed, but likely not).
- refactoring the entire error handling system.

## Decisions

- **Error Handling**: We will modify the `except ValueError` block in `blueprints/messages.py`. We will assume `ValueError` from `load_balance_url` primarily indicates a model resolution failure (missing model or configuration).
- **Response Format**: We will use the `create_error_response` helper with status code 404 and type `not_found_error`.

## Risks / Trade-offs

- **Risk**: If `load_balance_url` raises `ValueError` for other reasons (e.g. malformed config that isn't strictly "not found"), we might return 404 incorrectly.
- **Mitigation**: Review `load_balancer.py` to confirm `ValueError` usage. It seems to be used for "No Claude models available", "No subAccounts with model...", "No URLs for model...". These all align with "Resource Not Found" in the context of a proxy routing request. So 404 is appropriate.
