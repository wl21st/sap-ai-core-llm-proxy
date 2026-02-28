"""OpenAI-format conversion helpers."""

from __future__ import annotations

import json
import random
import time
from logging import Logger

from converters.mappings import STOP_REASON_MAP
from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


def from_claude(response: dict, model: str) -> dict:
    """Convert a Claude response to OpenAI chat completion format."""
    from proxy_helpers import Detector

    if Detector.is_claude_37_or_4(model):
        logger.info(f"Detected Claude 3.7/4 model ('{model}'), using from_claude37.")
        return from_claude37(response, model)

    logger.info(f"Using standard Claude conversion for model '{model}'.")

    try:
        logger.info(f"Raw response from Claude API: {json.dumps(response, indent=4)}")

        if "content" not in response or not isinstance(response["content"], list):
            raise ValueError(
                "Invalid response structure: 'content' is missing or not a list"
            )

        first_content = response["content"][0]
        if not isinstance(first_content, dict) or "text" not in first_content:
            raise ValueError("Invalid response structure: 'content[0].text' is missing")

        openai_response = {
            "choices": [
                {
                    "finish_reason": response.get("stop_reason", "stop"),
                    "index": 0,
                    "message": {
                        "content": first_content["text"],
                        "role": response.get("role", "assistant"),
                    },
                }
            ],
            "created": int(time.time()),
            "id": response.get("id", "chatcmpl-unknown"),
            "model": response.get("model", "claude-v1"),
            "object": "chat.completion",
            "usage": {
                "completion_tokens": response.get("usage", {}).get("output_tokens", 0),
                "prompt_tokens": response.get("usage", {}).get("input_tokens", 0),
                "total_tokens": response.get("usage", {}).get("input_tokens", 0)
                + response.get("usage", {}).get("output_tokens", 0),
            },
        }
        logger.debug(
            f"Converted response to OpenAI format: {json.dumps(openai_response, indent=4)}"
        )
        return openai_response
    except Exception as e:
        logger.error(f"Error converting Claude response to OpenAI format: {e}")
        return {"error": "Invalid response from Claude API", "details": str(e)}


def from_claude37(response: dict, model_name: str = "claude-3.7") -> dict:
    """Convert a Claude 3.7/4 /converse response to OpenAI format."""
    try:
        logger.debug(
            f"Raw response from Claude 3.7/4 API: {json.dumps(response, indent=2)}"
        )

        if not isinstance(response, dict):
            raise ValueError("Invalid response format: response is not a dictionary")

        output = response.get("output")
        if not isinstance(output, dict):
            raise ValueError(
                "Invalid response structure: 'output' field is missing or not a dictionary"
            )

        message = output.get("message")
        if not isinstance(message, dict):
            raise ValueError(
                "Invalid response structure: 'output.message' field is missing or not a dictionary"
            )

        content_list = message.get("content")
        if not isinstance(content_list, list) or not content_list:
            raise ValueError(
                "Invalid response structure: 'output.message.content' is missing, not a list, or empty"
            )

        first_content_block = content_list[0]
        if (
            not isinstance(first_content_block, dict)
            or "text" not in first_content_block
        ):
            block_type = (
                first_content_block.get("type", "unknown")
                if isinstance(first_content_block, dict)
                else "not a dict"
            )
            logger.warning(
                "First content block is not of type 'text' or missing 'text' key. "
                f"Type: {block_type}. Content: {first_content_block}"
            )
            content_text = None
            for block in content_list:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and "text" in block
                ):
                    content_text = block["text"]
                    logger.info(
                        "Found text content in block at index %s",
                        content_list.index(block),
                    )
                    break
            if content_text is None:
                raise ValueError(
                    "No text content block found in the response message content"
                )
        else:
            content_text = first_content_block["text"]

        message_role = message.get("role", "assistant")

        usage = response.get("usage")
        if not isinstance(usage, dict):
            logger.warning(
                "Usage information missing or invalid in Claude response. Setting tokens to 0."
            )
            usage = {}

        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        total_tokens = usage.get("totalTokens", input_tokens + output_tokens)

        prompt_tokens_details = {}
        if "cacheReadInputTokens" in usage or "cacheCreationInputTokens" in usage:
            prompt_tokens_details["cached_tokens"] = usage.get(
                "cacheReadInputTokens", 0
            )
            if usage.get("cacheCreationInputTokens", 0) > 0:
                prompt_tokens_details["cache_creation_tokens"] = usage.get(
                    "cacheCreationInputTokens", 0
                )

        claude_stop_reason = response.get("stopReason")
        finish_reason = STOP_REASON_MAP["claude_to_openai"].get(
            claude_stop_reason or "", "stop"
        )

        openai_response = {
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "index": 0,
                    "message": {"content": content_text, "role": message_role},
                }
            ],
            "created": int(time.time()),
            "id": f"chatcmpl-claude-{random.randint(10000000, 99999999)}",
            "model": model_name,
            "object": "chat.completion",
            "usage": {
                "completion_tokens": output_tokens,
                "prompt_tokens": input_tokens,
                "total_tokens": total_tokens,
            },
        }

        if prompt_tokens_details:
            openai_response["usage"]["prompt_tokens_details"] = prompt_tokens_details
            logger.debug(
                f"Added prompt_tokens_details to response: {prompt_tokens_details}"
            )

        logger.debug(
            f"Converted response to OpenAI format: {json.dumps(openai_response, indent=2)}"
        )
        return openai_response

    except Exception as e:
        logger.error(
            f"Error converting Claude 3.7/4 response to OpenAI format: {e}",
            exc_info=True,
        )
        logger.error(
            f"Problematic Claude response structure: {json.dumps(response, indent=2)}"
        )
        return {
            "object": "error",
            "message": "Failed to convert Claude 3.7/4 response to OpenAI format. "
            f"Error: {str(e)}. Check proxy logs for details.",
            "type": "proxy_conversion_error",
            "param": None,
            "code": None,
        }


def from_gemini(response: dict, model_name: str = "gemini-pro") -> dict:
    """Convert a Gemini generateContent response to OpenAI format."""
    try:
        logger.debug(f"Raw response from Gemini API: {json.dumps(response, indent=2)}")

        if not isinstance(response, dict):
            raise ValueError("Invalid response format: response is not a dictionary")

        candidates = response.get("candidates", [])
        if not candidates:
            raise ValueError("Invalid response structure: no candidates found")

        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise ValueError(
                "Invalid response structure: candidate is not a dictionary"
            )

        content = first_candidate.get("content", {})
        if not isinstance(content, dict):
            raise ValueError("Invalid response structure: content is not a dictionary")

        parts = content.get("parts", [])
        if not parts:
            raise ValueError("Invalid response structure: no parts found in content")

        first_part = parts[0]
        if not isinstance(first_part, dict) or "text" not in first_part:
            raise ValueError("Invalid response structure: no text found in first part")

        content_text = first_part["text"]

        gemini_finish_reason = first_candidate.get("finishReason", "STOP")
        finish_reason = STOP_REASON_MAP["gemini_to_openai"].get(
            gemini_finish_reason, "stop"
        )

        usage_metadata = response.get("usageMetadata", {})
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
        total_tokens = usage_metadata.get(
            "totalTokenCount", prompt_tokens + completion_tokens
        )

        openai_response = {
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "index": 0,
                    "message": {"content": content_text, "role": "assistant"},
                }
            ],
            "created": int(time.time()),
            "id": f"chatcmpl-gemini-{random.randint(10000000, 99999999)}",
            "model": model_name,
            "object": "chat.completion",
            "usage": {
                "completion_tokens": completion_tokens,
                "prompt_tokens": prompt_tokens,
                "total_tokens": total_tokens,
            },
        }

        logger.debug(
            f"Converted response to OpenAI format: {json.dumps(openai_response, indent=2)}"
        )
        return openai_response

    except Exception as e:
        logger.error(
            f"Error converting Gemini response to OpenAI format: {e}",
            exc_info=True,
        )
        logger.error(
            f"Problematic Gemini response structure: {json.dumps(response, indent=2)}"
        )
        return {
            "object": "error",
            "message": "Failed to convert Gemini response to OpenAI format. "
            f"Error: {str(e)}. Check proxy logs for details.",
            "type": "proxy_conversion_error",
            "param": None,
            "code": None,
        }
