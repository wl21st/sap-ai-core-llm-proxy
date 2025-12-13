"""
Error handling utilities for SAP AI Core LLM Proxy.

This module provides consistent error handling across all endpoints.
"""

import logging
from flask import jsonify, Response
from requests.exceptions import HTTPError


def handle_http_429_error(http_err: HTTPError, context: str = "request") -> Response:
    """Handle HTTP 429 (Too Many Requests) errors consistently across all endpoints.

    This function logs detailed information about rate limit errors and returns
    a properly formatted Flask response with retry information.

    Args:
        http_err: The HTTPError exception from the requests library.
        context: Description of the request context for logging (e.g., "embedding request").

    Returns:
        A Flask response object with status code 429.
        
    Example:
        >>> try:
        ...     response = requests.post(url, ...)
        ...     response.raise_for_status()
        ... except requests.exceptions.HTTPError as e:
        ...     if e.response.status_code == 429:
        ...         return handle_http_429_error(e, "chat completion")
    """
    logging.error(f"HTTP 429 Rate Limit Error for {context}")
    logging.error(f"HTTP 429 Response Headers:")

    # Dump all response headers to console for debugging
    for header_name, header_value in http_err.response.headers.items():
        logging.error(f"  {header_name}: {header_value}")

    # Log response body if available
    try:
        response_body = http_err.response.text
        logging.error(f"HTTP 429 Response Body: {response_body}")
    except Exception as body_err:
        logging.error(f"Could not read 429 response body: {body_err}")

    # Return 429 error to client with retry information
    error_response = {
        "error": "Rate limit exceeded",
        "status_code": 429,
        "message": "Too many requests. Please retry after some time.",
        "headers": dict(http_err.response.headers)
    }

    # Create Flask response with the original 429 headers copied
    flask_response = jsonify(error_response)
    flask_response.status_code = 429

    # Map both x-retry-after and Retry-After headers to retry-after in response
    for header_name, header_value in http_err.response.headers.items():
        header_lower = header_name.lower()
        if header_lower in ['x-retry-after', 'retry-after']:
            flask_response.headers['Retry-After'] = header_value
            logging.info(f"Set Retry-After header to: {header_value}")
            break

    return flask_response