"""Streaming response handlers for the LLM proxy.

This module contains helper functions for handling streaming responses
from various LLM backends (Claude, Gemini, OpenAI) and converting them
to a common format.

Phase 6a: Helper functions extraction
Phase 6b: Non-streaming request helper
"""

import json
import logging
import random
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)
transport_logger = logging.getLogger("transport")


def get_claude_stop_reason_from_gemini_chunk(gemini_chunk: dict) -> str | None:
    """Extract and map the stop reason from a final Gemini chunk.

    Args:
        gemini_chunk: The Gemini response chunk dictionary

    Returns:
        Mapped stop reason string or None if no finish reason found
    """
    finish_reason = gemini_chunk.get("candidates", [{}])[0].get("finishReason")
    if finish_reason:
        stop_reason_map = {
            "STOP": "end_turn",
            "MAX_TOKENS": "max_tokens",
            "SAFETY": "stop_sequence",
            "RECITATION": "stop_sequence",
            "OTHER": "stop_sequence",
        }
        return stop_reason_map.get(finish_reason, "stop_sequence")
    return None


def get_claude_stop_reason_from_openai_chunk(openai_chunk: dict) -> str | None:
    """Extract and map the stop reason from a final OpenAI chunk.

    Args:
        openai_chunk: The OpenAI response chunk dictionary

    Returns:
        Mapped stop reason string or None if no finish reason found
    """
    finish_reason = openai_chunk.get("choices", [{}])[0].get("finish_reason")
    if finish_reason:
        stop_reason_map = {
            "stop": "end_turn",
            "length": "max_tokens",
            "content_filter": "stop_sequence",
            "tool_calls": "tool_use",
        }
        return stop_reason_map.get(finish_reason, "stop_sequence")
    return None


def parse_sse_response_to_claude_json(response_text: str) -> dict:
    """Parse SSE response text and reconstruct Claude JSON response.

    This function processes Server-Sent Events (SSE) formatted response text
    from Claude's streaming API and reconstructs it into a standard JSON response.

    Args:
        response_text: The SSE response text containing data: prefixed lines

    Returns:
        dict: Claude JSON response format with id, type, role, content,
              model, stop_reason, stop_sequence, and usage fields
    """
    import ast

    content = ""
    usage = {}
    stop_reason = "end_turn"

    lines = response_text.strip().split("\n")
    for line in lines:
        if line.startswith("data: "):
            data_str = line[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                # Handle both JSON and Python dict literal formats
                if data_str.startswith("{"):
                    data = json.loads(data_str)
                else:
                    data = ast.literal_eval(data_str)

                if "contentBlockDelta" in data:
                    delta_text = data["contentBlockDelta"]["delta"].get("text", "")
                    content += delta_text
                elif "metadata" in data:
                    usage = data["metadata"].get("usage", {})
                elif "messageStop" in data:
                    stop_reason = data["messageStop"].get("stopReason", "end_turn")

            except (json.JSONDecodeError, ValueError, SyntaxError) as e:
                logger.warning(f"Failed to parse SSE data line: {data_str}, error: {e}")
                continue

    # Build Claude response format
    response_data = {
        "id": f"msg_{random.randint(10000000, 99999999)}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": "claude-3-5-sonnet-20241022",  # Default, will be overridden
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
        },
    }

    return response_data


@dataclass
class BackendRequestResult:
    """Result of a backend API request.

    Attributes:
        success: Whether the request was successful
        response_data: The response data (if successful)
        error_message: Error message (if failed)
        status_code: HTTP status code
        is_sse_response: Whether the response was in SSE format
        headers: Response headers (optional)
    """

    success: bool
    response_data: dict | None = None
    error_message: str | None = None
    status_code: int = 200
    is_sse_response: bool = False
    headers: dict | None = None


def make_backend_request(
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    tid: str,
    is_claude_model_fn,
    timeout: int = 600,
) -> BackendRequestResult:
    """Make a generic backend request with standardized error handling and logging.

    Args:
        url: The endpoint URL
        headers: Request headers
        payload: Request body
        model: Model identifier
        tid: Trace ID
        is_claude_model_fn: Function to check if model is a Claude model
        timeout: Request timeout in seconds

    Returns:
        BackendRequestResult object
    """
    logger.info(f"OUT_REQ: tid={tid}, model={model}, url={url}")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)

        # Log basic response info
        logger.info(
            f"OUT_RSP: tid={tid}, status={response.status_code}, headers={dict(response.headers)}"
        )

        response.raise_for_status()

        # Handle empty response
        if not response.text or not response.content:
            logger.error(f"Empty response from backend for {model}")
            return BackendRequestResult(
                success=False,
                error_message="Empty response from backend API",
                status_code=500,
            )

        # Handle SSE processing for Claude models if needed
        response_data = None
        is_sse = False
        response_headers = dict(response.headers)

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type and is_claude_model_fn(model):
            # Parse SSE response
            logger.info(f"OUT_RSP_BODY: tid={tid} (SSE stream, parsing...)")
            response_data = parse_sse_response_to_claude_json(response.text)
            is_sse = True
        else:
            # Standard JSON response
            logger.info(f"OUT_RSP_BODY: tid={tid}, body={response.text}")
            response_data = response.json()

        return BackendRequestResult(
            success=True,
            response_data=response_data,
            status_code=response.status_code,
            is_sse_response=is_sse,
            headers=response_headers,
        )

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code if http_err.response else 500
        error_msg = str(http_err)
        response_headers = (
            dict(http_err.response.headers) if http_err.response else None
        )

        logger.error(
            f"HTTP error in backend request({model}): {http_err}", exc_info=True
        )

        # Try to parse error body as JSON
        response_data = None
        try:
            if http_err.response:
                response_data = http_err.response.json()
        except Exception:
            pass

        return BackendRequestResult(
            success=False,
            error_message=error_msg if not response_data else None,
            status_code=status_code,
            response_data=response_data,
            headers=response_headers,
        )

    except requests.exceptions.Timeout:
        logger.error(f"Timeout connecting to backend for {model}")
        return BackendRequestResult(
            success=False,
            error_message="Connection timed out",
            status_code=500,
        )

    except Exception as err:
        logger.error(f"Error in backend request({model}): {err}", exc_info=True)
        return BackendRequestResult(
            success=False,
            error_message=str(err),
            status_code=500,
        )
