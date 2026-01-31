"""
Bedrock handler module for AWS Bedrock API interactions.

This module provides:
- Streaming and non-streaming invoke helpers
- Response body stream reading utilities
- Retry logic imported from unified utils.retry module
"""

import logging
from utils.retry import unified_retry

logger = logging.getLogger("proxy_server")

# Retry decorator imported from unified module
bedrock_retry = unified_retry


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
