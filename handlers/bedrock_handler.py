"""
Bedrock handler module for AWS Bedrock API interactions.

This module provides:
- Retry logic for rate-limited requests
- Streaming and non-streaming invoke helpers
- Response body stream reading utilities
"""

import logging
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("proxy_server")

# Retry configuration
RETRY_MAX_ATTEMPTS = 5
RETRY_MULTIPLIER = 1
RETRY_MIN_WAIT = 1
RETRY_MAX_WAIT = 16


def retry_on_rate_limit(exception) -> bool:
    """
    Check if exception is a rate limit error that should be retried.

    Args:
        exception: The exception to check

    Returns:
        True if the exception indicates a rate limit that should be retried
    """
    # Check for ClientError with 429 status code first (more reliable)
    if isinstance(exception, ClientError):
        error_code = exception.response.get("Error", {}).get("Code", "")
        http_status = exception.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )
        if error_code == "429" or http_status == 429:
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
    )


# Create the retry decorator with exponential backoff
bedrock_retry = retry(
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


@bedrock_retry
def invoke_bedrock_streaming(bedrock_client, body_json: str):
    """
    Invoke Bedrock streaming API with retry logic for rate limits.

    Note: This only retries the initial connection/request. Once streaming starts,
    errors during stream consumption cannot be retried as the stream is already open.

    Args:
        bedrock_client: The Bedrock client wrapper
        body_json: JSON string of the request body

    Returns:
        The streaming response from Bedrock
    """
    return bedrock_client.invoke_model_with_response_stream(body=body_json)


@bedrock_retry
def invoke_bedrock_non_streaming(bedrock_client, body_json: str):
    """
    Invoke Bedrock non-streaming API with retry logic for rate limits.

    Args:
        bedrock_client: The Bedrock client wrapper
        body_json: JSON string of the request body

    Returns:
        The response from Bedrock
    """
    return bedrock_client.invoke_model(body=body_json)


def read_response_body_stream(response_body) -> str:
    """
    Read response body stream and return as string.

    Args:
        response_body: The streaming response body from AWS SDK

    Returns:
        String containing the full response data
    """
    chunk_data = ""
    for event in response_body:
        if isinstance(event, bytes):
            chunk_data += event.decode("utf-8")
        else:
            chunk_data += str(event)
    return chunk_data
