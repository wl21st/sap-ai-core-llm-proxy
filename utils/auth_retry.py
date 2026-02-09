"""Authentication retry utilities for the LLM proxy.

This module provides shared constants and functions for handling authentication
retry logic across the proxy (e.g., token invalidation and retry on 401/403 errors).
"""

AUTH_RETRY_MAX: int = 1
"""Maximum number of retries on authentication errors (401/403)."""

_AUTH_ERROR_FORMAT = "Authentication error ({status_code}) for {target}, invalidating credentials and retrying..."


def log_auth_error_retry(status_code: int, target: str) -> str:
    """Generate standardized auth error retry log message.

    Args:
        status_code: HTTP status code (401 or 403)
        target: Description of what failed (e.g., model name, subaccount)

    Returns:
        Formatted log message
    """
    return _AUTH_ERROR_FORMAT.format(status_code=status_code, target=target)
