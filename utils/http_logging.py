"""HTTP request/response logging utilities for transport layer debugging."""

import json
from typing import Dict, Any, Optional
from logging import Logger


def dump_http_request(
    logger: Logger,
    trace_id: str,
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Optional[Any] = None,
) -> None:
    """
    Dump HTTP request details to logger.

    Args:
        logger: Logger instance to use for logging
        trace_id: Unique trace identifier for request/response correlation
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Request headers dictionary
        payload: Request payload (will be JSON serialized if dict/list)
    """
    log_data = {
        "trace_id": trace_id,
        "type": "request",
        "method": method.upper(),
        "url": url,
        "headers": dict(headers),
    }

    # Add payload if present
    if payload is not None:
        if isinstance(payload, (dict, list)):
            log_data["payload"] = payload
        else:
            log_data["payload"] = str(payload)

    try:
        log_message = json.dumps(log_data, indent=2, ensure_ascii=False)
        logger.info(f"HTTP_REQUEST[{trace_id}]:\n{log_message}")
    except (TypeError, ValueError) as e:
        # Fallback to string representation if JSON serialization fails
        logger.info(f"HTTP_REQUEST[{trace_id}]: {log_data} (JSON serialization failed: {e})")


def dump_http_response(
    logger: Logger,
    trace_id: str,
    status_code: int,
    headers: Dict[str, str],
    payload: Optional[Any] = None,
    url: Optional[str] = None,
) -> None:
    """
    Dump HTTP response details to logger.

    Args:
        logger: Logger instance to use for logging
        trace_id: Unique trace identifier for request/response correlation
        status_code: HTTP status code
        headers: Response headers dictionary
        payload: Response payload (will be JSON serialized if dict/list)
        url: Optional URL for additional context
    """
    log_data = {
        "trace_id": trace_id,
        "type": "response",
        "status_code": status_code,
        "headers": dict(headers),
    }

    # Add URL if provided
    if url:
        log_data["url"] = url

    # Add payload if present
    if payload is not None:
        if isinstance(payload, (dict, list)):
            log_data["payload"] = payload
        else:
            log_data["payload"] = str(payload)

    try:
        log_message = json.dumps(log_data, indent=2, ensure_ascii=False)
        logger.info(f"HTTP_RESPONSE[{trace_id}]:\n{log_message}")
    except (TypeError, ValueError) as e:
        # Fallback to string representation if JSON serialization fails
        logger.info(f"HTTP_RESPONSE[{trace_id}]: {log_data} (JSON serialization failed: {e})")