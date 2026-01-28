"""Streaming response handlers for the LLM proxy.

This module contains helper functions for handling streaming responses
from various LLM backends (Claude, Gemini, OpenAI) and converting them
to a common format.

Phase 6a: Helper functions extraction
"""

import json
import logging
import random

logger = logging.getLogger(__name__)


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
