"""
Unified retry logic for rate-limited requests across the proxy.

This module provides:
- Centralized retry configuration
- Single retry_on_rate_limit() function with comprehensive error detection
- Retry decorator with exponential backoff
"""

import logging
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("proxy_server")

# Retry configuration (centralized)
RETRY_MAX_ATTEMPTS = 5
RETRY_MULTIPLIER = (
    2  # Exponential backoff multiplier (corrected from inconsistent values)
)
RETRY_MIN_WAIT = 1  # Minimum wait time in seconds
RETRY_MAX_WAIT = 16  # Maximum wait time in seconds


def retry_on_rate_limit(exception) -> bool:
    """
    Check if exception is a rate limit error that should be retried.

    Comprehensive detection for:
    - Botocore ClientError with 429 status code or rate limit error codes
    - String pattern matching for rate limit/throttling/token messages
    - Different error code formats from various AWS SDKs

    Args:
        exception: The exception to check

    Returns:
        True if the exception indicates a rate limit that should be retried
    """
    # Check for ClientError with HTTP 429 or throttling error codes
    if isinstance(exception, ClientError):
        error_response = exception.response or {}
        error_info = error_response.get("Error", {})
        error_code = error_info.get("Code", "")
        error_message = error_info.get("Message", "").lower()
        http_status = error_response.get("ResponseMetadata", {}).get("HTTPStatusCode")

        # Check HTTP status code
        if http_status == 429:
            return True

        # Check for known throttling/rate limit error codes
        if error_code in [
            "429",
            "ThrottlingException",
            "TooManyRequestsException",
            "RequestLimitExceeded",
        ]:
            return True

        # Check error message for rate limit indicators
        if "too many tokens" in error_message or "rate limit" in error_message:
            return True

    # Fallback to string matching for other exception types
    error_message = str(exception).lower()
    return (
        "too many tokens" in error_message
        or "rate limit" in error_message
        or "throttling" in error_message
        or "too many requests" in error_message
        or "exceeding the allowed request" in error_message
        or "rate limited by ai core" in error_message
        or "429" in error_message
    )


# Create the retry decorator with exponential backoff
unified_retry = retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(
        multiplier=RETRY_MULTIPLIER, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT
    ),
    retry=retry_on_rate_limit,
    before_sleep=lambda retry_state: logger.warning(
        f"Rate limit hit, retrying in {retry_state.next_action.sleep if retry_state.next_action else 'unknown'} seconds "
        f"(attempt {retry_state.attempt_number}/{RETRY_MAX_ATTEMPTS}): {str(retry_state.outcome.exception()) if retry_state.outcome else 'unknown error'}"
    ),
)
