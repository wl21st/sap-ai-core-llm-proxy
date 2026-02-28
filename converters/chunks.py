"""Streaming chunk conversion helpers."""

from __future__ import annotations

import json
import random
import time
from logging import Logger

from converters.mappings import STOP_REASON_MAP
from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


def claude_to_openai_chunk(chunk: str, model: str) -> str:
    """Convert a Claude SSE chunk to OpenAI chunk format."""
    try:
        data = json.loads(chunk.replace("data: ", "").strip())

        openai_chunk = {
            "choices": [{"delta": {}, "finish_reason": None, "index": 0}],
            "created": int(time.time()),
            "id": data.get("message", {}).get("id", "chatcmpl-unknown"),
            "model": model,
            "object": "chat.completion.chunk",
            "system_fingerprint": "fp_36b0c83da2",
        }

        if data.get("type") == "content_block_delta":
            openai_chunk["choices"][0]["delta"]["content"] = data["delta"]["text"]
        elif (
            data.get("type") == "message_delta"
            and data["delta"].get("stop_reason") == "end_turn"
        ):
            openai_chunk["choices"][0]["finish_reason"] = "stop"

        return f"data: {json.dumps(openai_chunk)}\n\n"
    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s", e)
        return 'data: {"error": "Invalid JSON format"}\n\n'
    except Exception as e:
        logger.error("Error processing chunk: %s", e)
        return 'data: {"error": "Error processing chunk"}\n\n'


def claude37_to_openai_chunk(
    claude_chunk: dict | str, model_name: str, stream_id: str | None = None
) -> str | None:
    """Convert Claude 3.7/4 /converse-stream chunk to OpenAI SSE chunk."""
    try:
        if stream_id is None:
            stream_id = f"chatcmpl-claude-{random.randint(10000000, 99999999)}"
        created_time = int(time.time())

        openai_chunk_payload = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model_name,
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
        }

        if isinstance(claude_chunk, str):
            try:
                claude_chunk = json.loads(claude_chunk)
            except json.JSONDecodeError as e:
                logger.error("JSON decode error: %s", e)
                return None

        if not isinstance(claude_chunk, dict) or not claude_chunk:
            logger.warning("Invalid or empty Claude chunk received: %s", claude_chunk)
            return None

        chunk_type = next(iter(claude_chunk))

        if chunk_type == "messageStart":
            role = claude_chunk.get("messageStart", {}).get("role", "assistant")
            openai_chunk_payload["choices"][0]["delta"]["role"] = role
        elif chunk_type == "contentBlockDelta":
            text_delta = (
                claude_chunk.get("contentBlockDelta", {}).get("delta", {}).get("text")
            )
            if text_delta is not None:
                openai_chunk_payload["choices"][0]["delta"]["content"] = text_delta
            else:
                logger.debug(
                    "Ignoring contentBlockDelta without text: %s", claude_chunk
                )
                return None
        elif chunk_type == "messageStop":
            stop_reason = claude_chunk.get("messageStop", {}).get("stopReason")
            finish_reason = STOP_REASON_MAP["claude_to_openai"].get(stop_reason)
            if finish_reason:
                openai_chunk_payload["choices"][0]["finish_reason"] = finish_reason
                openai_chunk_payload["choices"][0]["delta"] = {}
            else:
                logger.warning(
                    "Unmapped or missing stopReason in messageStop: %s. Chunk: %s",
                    stop_reason,
                    claude_chunk,
                )
                return None
        elif chunk_type in [
            "contentBlockStart",
            "contentBlockStop",
            "metadata",
            "messageStop",
        ]:
            logger.debug("Ignoring Claude chunk type for OpenAI stream: %s", chunk_type)
            return None
        else:
            logger.warning(
                "Unknown Claude 3.7/4 chunk type encountered: %s. Chunk: %s",
                chunk_type,
                claude_chunk,
            )
            return None

        return f"data: {json.dumps(openai_chunk_payload)}\n\n"

    except Exception as e:
        logger.error(
            "Error converting Claude 3.7/4 chunk to OpenAI format: %s",
            e,
            exc_info=True,
        )
        logger.error(
            "Problematic Claude chunk: %s",
            json.dumps(claude_chunk, indent=2),
        )
        error_payload = {
            "id": f"chatcmpl-error-{random.randint(10000000, 99999999)}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": "[PROXY ERROR: Failed to convert upstream chunk - "
                        f"{str(e)}]"
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        return f"data: {json.dumps(error_payload)}\n\n"


def gemini_to_openai_chunk(gemini_chunk: dict | str, model_name: str) -> str | None:
    """Convert Gemini streaming chunk to OpenAI SSE chunk."""
    try:
        stream_id = f"chatcmpl-gemini-{random.randint(10000000, 99999999)}"
        created_time = int(time.time())

        openai_chunk_payload = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created_time,
            "model": model_name,
            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
        }

        if isinstance(gemini_chunk, str):
            try:
                gemini_chunk = json.loads(gemini_chunk)
            except json.JSONDecodeError as e:
                logger.error("JSON decode error: %s", e)
                return None

        if not isinstance(gemini_chunk, dict):
            logger.warning("Invalid Gemini chunk received: %s", gemini_chunk)
            return None

        candidates = gemini_chunk.get("candidates", [])

        if not candidates and "usageMetadata" in gemini_chunk:
            openai_chunk_payload["usage"] = {
                "prompt_tokens": gemini_chunk["usageMetadata"].get(
                    "promptTokenCount", 0
                ),
                "completion_tokens": gemini_chunk["usageMetadata"].get(
                    "candidatesTokenCount", 0
                ),
                "total_tokens": gemini_chunk["usageMetadata"].get("totalTokenCount", 0),
            }
            return f"data: {json.dumps(openai_chunk_payload)}\n\n"

        if not candidates:
            return None

        first_candidate = candidates[0]

        if "finishReason" in first_candidate:
            gemini_finish_reason = first_candidate["finishReason"]
            finish_reason = STOP_REASON_MAP["gemini_to_openai"].get(
                gemini_finish_reason, "stop"
            )
            openai_chunk_payload["choices"][0]["finish_reason"] = finish_reason

        content = first_candidate.get("content", {})
        parts = content.get("parts", [])
        if parts and "text" in parts[0]:
            openai_chunk_payload["choices"][0]["delta"]["content"] = parts[0]["text"]
        if "usageMetadata" in gemini_chunk:
            usage_metadata = gemini_chunk["usageMetadata"]
            openai_chunk_payload["usage"] = {
                "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
                "total_tokens": usage_metadata.get("totalTokenCount", 0),
            }

        return f"data: {json.dumps(openai_chunk_payload)}\n\n"

    except Exception as e:
        logger.error(
            "Error converting Gemini chunk to OpenAI format: %s",
            e,
            exc_info=True,
        )
        error_payload = {
            "id": f"chatcmpl-error-{random.randint(10000000, 99999999)}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": "[PROXY ERROR: Failed to convert upstream chunk - "
                        f"{str(e)}]"
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        return f"data: {json.dumps(error_payload)}\n\n"
