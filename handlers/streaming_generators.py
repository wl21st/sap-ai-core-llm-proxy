"""Streaming generator functions for the LLM proxy.

This module contains generator functions that yield SSE-formatted streaming
responses from various LLM backends (Bedrock, Claude, Gemini, OpenAI).

Phase 6d: Streaming generators extraction
"""

import ast
import asyncio
import json
import logging
import random
import time
from typing import Any, AsyncGenerator, Generator

import httpx
import requests
from fastapi import Request

from proxy_helpers import Converters, Detector
from handlers.streaming_handler import (
    get_claude_stop_reason_from_gemini_chunk,
    get_claude_stop_reason_from_openai_chunk,
)
from utils.auth_retry import AUTH_RETRY_MAX, log_auth_error_retry

logger = logging.getLogger(__name__)
transport_logger = logging.getLogger("transport")
token_usage_logger = logging.getLogger("token_usage")


def is_gemini_2_5_pro_format(chunk: dict[str, Any]) -> bool:
    """Detect if a chunk matches Gemini-2.5-pro's streaming format.

    Gemini-2.5-pro sends chunks with the structure:
    {
      candidates: [{
        content: {
          parts: [{text: "..."}],
          role: "model"
        },
        finishReason: "...",
        index: 0
      }],
      usageMetadata: {...}
    }

    This is the raw JSON format that appears on each line of the response stream.

    Args:
        chunk: The parsed chunk dictionary

    Returns:
        True if the chunk appears to be in Gemini-2.5-pro format, False otherwise
    """
    if not isinstance(chunk, dict):
        return False

    candidates = chunk.get("candidates", [])
    if not candidates or not isinstance(candidates, list):
        return False

    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return False

    content = candidate.get("content", {})
    if not isinstance(content, dict):
        return False

    parts = content.get("parts", [])
    if not parts or not isinstance(parts, list):
        return False

    part = parts[0]
    if not isinstance(part, dict):
        return False

    return "text" in part


def _format_sse_event(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def generate_bedrock_streaming_response(
    response_body: Any,
    tid: str,
) -> AsyncGenerator[str, None]:
    """Generate streaming response from Bedrock SDK EventStream.

    This generator converts AWS Bedrock EventStream responses into Server-Sent
    Events (SSE) format compatible with the Anthropic Claude Messages API.

    Args:
        response_body: AWS Bedrock EventStream iterator yielding chunk events
        tid: Trace UUID for logging correlation

    Yields:
        SSE-formatted response strings (event + data lines)

    SSE Event Types:
        - message_start: Initial message metadata
        - content_block_start: Start of a content block
        - content_block_delta: Incremental content updates
        - content_block_stop: End of a content block
        - message_delta: Message-level updates (e.g., stop reason)
        - message_stop: End of message stream
        - error: Error information
    """
    try:
        for event in response_body:
            chunk = json.loads(event["chunk"]["bytes"])
            logger.debug("Streaming chunk: %s", chunk)

            # Log raw chunk from Bedrock
            transport_logger.info("CHUNK: tid=%s, %s", tid, json.dumps(chunk)[:200])

            chunk_type = chunk.get("type")

            # Handle different chunk types according to Claude streaming format
            if chunk_type == "message_start":
                response_line = _format_sse_event("message_start", chunk)
                transport_logger.info("CHUNK: tid=%s, %s", tid, response_line[:200])
                yield response_line
            elif chunk_type == "content_block_start":
                response_line = _format_sse_event("content_block_start", chunk)
                transport_logger.info("CHUNK: tid=%s, %s", tid, response_line[:200])
                yield response_line
            elif chunk_type == "content_block_delta":
                response_line = _format_sse_event("content_block_delta", chunk)
                transport_logger.info("CHUNK: tid=%s, %s", tid, response_line[:200])
                yield response_line
            elif chunk_type == "content_block_stop":
                response_line = _format_sse_event("content_block_stop", chunk)
                transport_logger.info("CHUNK: tid=%s, %s", tid, response_line[:200])
                yield response_line
            elif chunk_type == "message_delta":
                response_line = _format_sse_event("message_delta", chunk)
                transport_logger.info("CHUNK: tid=%s, %s", tid, response_line[:200])
                yield response_line
            elif chunk_type == "message_stop":
                response_line = _format_sse_event("message_stop", chunk)
                transport_logger.info("CHUNK: tid=%s, %s", tid, response_line[:200])
                yield response_line
                transport_logger.info("DONE: tid=%s, Stream finished successfully", tid)
                yield "data: [DONE]\n\n"
                break
            elif chunk_type == "error":
                response_line = _format_sse_event("error", chunk)
                transport_logger.info("ERR: tid=%s, %s", tid, response_line[:200])
                yield response_line
                break

    except Exception as e:
        logger.error("Error during streaming: %s", e, exc_info=True)
        error_chunk = {
            "type": "error",
            "error": {"type": "api_error", "message": str(e)},
        }
        yield _format_sse_event("error", error_chunk)


def _sync_iter_async_generator(
    async_gen: AsyncGenerator[Any, None],
) -> Generator[Any, None, None]:
    loop = asyncio.new_event_loop()
    try:
        while True:
            try:
                item = loop.run_until_complete(async_gen.__anext__())
            except StopAsyncIteration:
                break
            yield item
    finally:
        loop.run_until_complete(async_gen.aclose())
        loop.close()


async def generate_streaming_response(
    request: Request,
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    subaccount_name: str,
    tid: str,
) -> AsyncGenerator[str | bytes, None]:
    """Generate streaming response from backend API in OpenAI-compatible format."""
    payload_json_str: str = json.dumps(payload)
    transport_logger.info(
        "OUT_REQ_CHAT_ST: tid=%s, url=%s], body=%s",
        tid,
        url,
        payload_json_str,
    )

    buffer = ""
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    claude_metadata: dict[str, Any] = {}
    done_sent = False

    timeout_config = httpx.Timeout(600)
    async with httpx.AsyncClient(timeout=timeout_config) as client:
        async with client.stream(
            "POST", url, headers=headers, json=payload
        ) as response:
            try:
                response.raise_for_status()

                # --- Claude 3.7/4 Streaming Logic ---
                if Detector.is_claude_model(model) and Detector.is_claude_37_or_4(
                    model
                ):
                    logger.info(
                        "Using Claude 3.7/4 streaming for subAccount '%s'",
                        subaccount_name,
                    )
                    stop_reason_received = None
                    stream_id = f"chatcmpl-claude-{random.randint(10000000, 99999999)}"

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            try:
                                try:
                                    claude_dict_chunk = json.loads(line_content)
                                except json.JSONDecodeError:
                                    claude_dict_chunk = ast.literal_eval(line_content)

                                if "messageStart" in claude_dict_chunk:
                                    message_id = (
                                        claude_dict_chunk.get("messageStart", {})
                                        .get("message", {})
                                        .get("id", "")
                                    )
                                    if message_id:
                                        stream_id = f"chatcmpl-claude-{message_id}"
                                        logger.info(
                                            "Extracted stream ID from messageStart: %s",
                                            stream_id,
                                        )

                                if "messageStop" in claude_dict_chunk:
                                    stop_reason_received = claude_dict_chunk.get(
                                        "messageStop", {}
                                    ).get("stopReason", "end_turn")
                                    logger.info(
                                        "Received messageStop with stopReason: %s",
                                        stop_reason_received,
                                    )
                                    continue

                                if "metadata" in claude_dict_chunk:
                                    claude_metadata = claude_dict_chunk.get(
                                        "metadata", {}
                                    )
                                    logger.info("CHAT_RSP_ST_META: %s", claude_metadata)
                                    if isinstance(claude_metadata.get("usage"), dict):
                                        total_tokens = claude_metadata["usage"].get(
                                            "totalTokens", 0
                                        )
                                        prompt_tokens = claude_metadata["usage"].get(
                                            "inputTokens", 0
                                        )
                                        completion_tokens = claude_metadata[
                                            "usage"
                                        ].get("outputTokens", 0)
                                        logger.info(
                                            "Extracted token usage from metadata: prompt=%s, completion=%s, total=%s",
                                            prompt_tokens,
                                            completion_tokens,
                                            total_tokens,
                                        )
                                    continue

                                openai_sse_chunk_str = (
                                    chunk_converters.claude37_to_openai_chunk(
                                        claude_dict_chunk, model, stream_id
                                    )
                                )

                                if openai_sse_chunk_str:
                                    logger.info(
                                        "CHUNK: tid=%s, %s",
                                        tid,
                                        openai_sse_chunk_str[:200],
                                    )
                                    transport_logger.info(
                                        "CHUNK: tid=%s, %s", tid, openai_sse_chunk_str
                                    )
                                    yield openai_sse_chunk_str
                            except Exception as e:
                                logger.error(
                                    "Error processing Claude 3.7 chunk from '%s': %s",
                                    subaccount_name,
                                    e,
                                    exc_info=True,
                                )
                                error_payload = {
                                    "id": f"chatcmpl-error-{random.randint(10000000, 99999999)}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "content": "[PROXY ERROR: Failed to process upstream data]"
                                            },
                                            "finish_reason": "stop",
                                        }
                                    ],
                                }
                                yield f"{json.dumps(error_payload)}\n\n"

                    if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                        stop_reason_map = {
                            "end_turn": "stop",
                            "max_tokens": "length",
                            "stop_sequence": "stop",
                            "tool_use": "tool_calls",
                        }
                        stop_reason_key = (
                            stop_reason_received
                            if isinstance(stop_reason_received, str)
                            else "end_turn"
                        )
                        finish_reason = stop_reason_map.get(stop_reason_key, "stop")
                        final_usage_chunk = {
                            "id": stream_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": finish_reason,
                                }
                            ],
                            "usage": {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                            },
                        }
                        final_usage_chunk_str = (
                            f"data: {json.dumps(final_usage_chunk)}\n\n"
                        )
                        logger.info(
                            "Sending final chunk with finish_reason=%s and usage: %s...",
                            finish_reason,
                            final_usage_chunk_str[:200],
                        )
                        yield final_usage_chunk_str
                        logger.info(
                            "Sent final chunk: finish_reason=%s, prompt=%s, completion=%s, total=%s",
                            finish_reason,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                        )

                        user_id = (
                            request.headers.get("Authorization", "unknown")
                            if request
                            else "unknown"
                        )
                        if user_id and len(user_id) > 20:
                            user_id = f"{user_id[:20]}..."
                        ip_address = (
                            request.client.host
                            if request and request.client
                            else "unknown_ip"
                        )
                        token_usage_logger.info(
                            "User: %s, IP: %s, Model: %s, SubAccount: %s, PromptTokens: %s, CompletionTokens: %s, TotalTokens: %s (Streaming)",
                            user_id,
                            ip_address,
                            model,
                            subaccount_name,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                        )

                # --- Gemini Streaming Logic ---
                elif Detector.is_gemini_model(model):
                    logger.info(
                        "Using Gemini streaming for subAccount '%s'",
                        subaccount_name,
                    )
                    total_tokens = 0
                    prompt_tokens = 0
                    completion_tokens = 0
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        logger.info("Gemini raw line received: %s", line)

                        line_content = ""
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            logger.info("Gemini data line content: %s", line_content)
                        elif line.strip():
                            line_content = line.strip()
                            logger.info(
                                "Gemini line content (no prefix): %s", line_content
                            )

                        if line_content and line_content != "[DONE]":
                            try:
                                gemini_chunk = json.loads(line_content)
                                logger.info(
                                    "Gemini parsed chunk: %s",
                                    json.dumps(gemini_chunk, indent=2),
                                )

                                if is_gemini_2_5_pro_format(gemini_chunk):
                                    logger.info(
                                        "Detected Gemini-2.5-pro streaming format"
                                    )

                                openai_sse_chunk_str = (
                                    chunk_converters.gemini_to_openai_chunk(
                                        gemini_chunk, model
                                    )
                                )
                                if openai_sse_chunk_str:
                                    logger.info(
                                        "Gemini converted to OpenAI chunk: %s",
                                        openai_sse_chunk_str,
                                    )
                                    if not openai_sse_chunk_str.startswith("data: "):
                                        logger.error(
                                            "ERROR: Converter returned chunk without 'data: ' prefix: %s",
                                            openai_sse_chunk_str[:100],
                                        )
                                    yield openai_sse_chunk_str.encode("utf-8")
                                else:
                                    logger.info("Gemini chunk conversion returned None")

                                if "usageMetadata" in gemini_chunk:
                                    usage_metadata = gemini_chunk["usageMetadata"]
                                    total_tokens = usage_metadata.get(
                                        "totalTokenCount", 0
                                    )
                                    prompt_tokens = usage_metadata.get(
                                        "promptTokenCount", 0
                                    )
                                    completion_tokens = usage_metadata.get(
                                        "candidatesTokenCount", 0
                                    )
                                    logger.info(
                                        "Gemini token usage: prompt=%s, completion=%s, total=%s",
                                        prompt_tokens,
                                        completion_tokens,
                                        total_tokens,
                                    )

                            except json.JSONDecodeError as e:
                                logger.error(
                                    "Error parsing Gemini chunk from '%s': %s",
                                    subaccount_name,
                                    e,
                                    exc_info=True,
                                )
                                logger.error(
                                    "Problematic line content: %s", line_content
                                )
                                continue
                            except Exception as e:
                                logger.error(
                                    "Error processing Gemini chunk from '%s': %s",
                                    subaccount_name,
                                    e,
                                    exc_info=True,
                                )
                                logger.error(
                                    "Problematic chunk: %s",
                                    locals().get("gemini_chunk", "Failed to parse"),
                                )
                                error_payload = {
                                    "id": f"chatcmpl-error-{random.randint(10000000, 99999999)}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "content": "[PROXY ERROR: Failed to process upstream data]"
                                            },
                                            "finish_reason": "stop",
                                        }
                                    ],
                                }
                                yield f"data: {json.dumps(error_payload)}\n\n".encode(
                                    "utf-8"
                                )
                        elif line_content == "[DONE]":
                            done_sent = True
                            logger.info("Received [DONE] signal from Gemini backend")

                    if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                        final_usage_chunk = {
                            "id": f"chatcmpl-gemini-{random.randint(10000000, 99999999)}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [
                                {"index": 0, "delta": {}, "finish_reason": None}
                            ],
                            "usage": {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                            },
                        }
                        final_usage_chunk_str = (
                            f"data: {json.dumps(final_usage_chunk)}\n\n"
                        )
                        logger.info(
                            "[FIXED] Sending final Gemini usage chunk with data prefix: %s bytes, starts with: %s",
                            len(final_usage_chunk_str),
                            final_usage_chunk_str[:50],
                        )
                        if not final_usage_chunk_str.startswith("data: "):
                            logger.error(
                                "ERROR: Final usage chunk does not start with 'data: ': %s",
                                final_usage_chunk_str[:100],
                            )
                        yield final_usage_chunk_str.encode("utf-8")
                        logger.info(
                            "Sent final Gemini usage chunk: prompt=%s, completion=%s, total=%s",
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                        )

                        user_id = (
                            request.headers.get("Authorization", "unknown")
                            if request
                            else "unknown"
                        )
                        if user_id and len(user_id) > 20:
                            user_id = f"{user_id[:20]}..."
                        ip_address = (
                            request.client.host
                            if request and request.client
                            else "unknown_ip"
                        )
                        token_usage_logger.info(
                            "User: %s, IP: %s, Model: %s, SubAccount: %s, PromptTokens: %s, CompletionTokens: %s, TotalTokens: %s (Streaming)",
                            user_id,
                            ip_address,
                            model,
                            subaccount_name,
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                        )

                # --- Other Models (including older Claude) ---
                else:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            if Detector.is_claude_model(model):
                                buffer += chunk.decode("utf-8")
                                while "data: " in buffer:
                                    try:
                                        start = buffer.index("data: ") + len("data: ")
                                        end = buffer.index("\n\n", start)
                                        json_chunk_str = buffer[start:end].strip()
                                        buffer = buffer[end + 2 :]

                                        openai_sse_chunk_str = (
                                            Converters.convert_claude_chunk_to_openai(
                                                json_chunk_str, model
                                            )
                                        )
                                        yield openai_sse_chunk_str.encode("utf-8")

                                        try:
                                            claude_data = json.loads(json_chunk_str)
                                            if "usage" in claude_data:
                                                prompt_tokens = claude_data[
                                                    "usage"
                                                ].get("input_tokens", 0)
                                                completion_tokens = claude_data[
                                                    "usage"
                                                ].get("output_tokens", 0)
                                                total_tokens = (
                                                    prompt_tokens + completion_tokens
                                                )
                                        except json.JSONDecodeError:
                                            pass
                                    except ValueError:
                                        break
                                    except Exception as e:
                                        logger.error(
                                            "Error processing claude chunk: %s",
                                            e,
                                            exc_info=True,
                                        )
                                        break
                            else:
                                yield chunk
                                try:
                                    chunk_text = chunk.decode("utf-8")
                                    if "[DONE]" in chunk_text:
                                        done_sent = True
                                    if '"finish_reason":' in chunk_text:
                                        for line in chunk_text.strip().split("\n"):
                                            if (
                                                line.startswith("data: ")
                                                and line[6:].strip() != "[DONE]"
                                            ):
                                                try:
                                                    data = json.loads(line[6:])
                                                    if "usage" in data:
                                                        total_tokens = data[
                                                            "usage"
                                                        ].get("total_tokens", 0)
                                                        prompt_tokens = data[
                                                            "usage"
                                                        ].get("prompt_tokens", 0)
                                                        completion_tokens = data[
                                                            "usage"
                                                        ].get("completion_tokens", 0)
                                                except json.JSONDecodeError:
                                                    pass
                                except Exception:
                                    pass

                if not (
                    Detector.is_claude_model(model)
                    and Detector.is_claude_37_or_4(model)
                ):
                    user_id = (
                        request.headers.get("Authorization", "unknown")
                        if request
                        else "unknown"
                    )
                    if user_id and len(user_id) > 20:
                        user_id = f"{user_id[:20]}..."
                    ip_address = (
                        request.client.host
                        if request and request.client
                        else "unknown_ip"
                    )

                    token_usage_logger.info(
                        "User: %s, IP: %s, Model: %s, SubAccount: %s, PromptTokens: %s, CompletionTokens: %s, TotalTokens: %s (Streaming)",
                        user_id,
                        ip_address,
                        model,
                        subaccount_name,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                    )

                transport_logger.info("DONE: tid=%s, Streaming completed", tid)
                if not done_sent:
                    yield "data: [DONE]\n\n"

            except httpx.HTTPStatusError as http_err:
                logger.error(
                    "HTTP Error in streaming response:(%s): %s",
                    model,
                    http_err,
                    exc_info=True,
                )

                error_content: str = ""

                if http_err.response is not None:
                    status_code = http_err.response.status_code
                    error_content = http_err.response.text

                    if status_code == 429:
                        error_payload = {
                            "id": f"error-{random.randint(10000000, 99999999)}",
                            "object": "error",
                            "created": int(time.time()),
                            "model": model,
                            "error": {
                                "message": error_content,
                                "type": "rate_limit_error",
                                "code": status_code,
                                "subaccount": subaccount_name,
                            },
                        }
                        yield f"data: {json.dumps(error_payload)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    logger.error(
                        "Error response status: %s", http_err.response.status_code
                    )
                    logger.error(
                        "Error response headers: %s", dict(http_err.response.headers)
                    )
                    logger.error("Error response body: %s", http_err.response.text)
                    try:
                        logger.error("Error response body: %s", error_content)

                        try:
                            error_content = json.dumps(
                                http_err.response.json(), indent=2
                            )
                            logger.error("Error response JSON: %s", error_content)
                        except json.JSONDecodeError:
                            pass
                    except Exception as e:
                        logger.error(
                            "Could not read error response content: %s",
                            e,
                            exc_info=True,
                        )
                else:
                    status_code = 500
                    error_content = str(http_err)

                error_payload = {
                    "id": f"error-{random.randint(10000000, 99999999)}",
                    "object": "error",
                    "created": int(time.time()),
                    "model": model,
                    "error": {
                        "message": error_content,
                        "type": "http_error",
                        "code": status_code,
                        "subaccount": subaccount_name,
                    },
                }
                yield f"data: {json.dumps(error_payload)}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as http_err:
                logger.error(
                    "Error in streaming response from '%s': %s",
                    subaccount_name,
                    http_err,
                    exc_info=True,
                )
                error_payload = {
                    "id": f"error-{random.randint(10000000, 99999999)}",
                    "object": "error",
                    "created": int(time.time()),
                    "model": model,
                    "error": {
                        "message": str(http_err),
                        "type": "proxy_error",
                        "code": 500,
                        "subaccount": subaccount_name,
                    },
                }
                yield f"data: {json.dumps(error_payload)}\n\n"
                yield "data: [DONE]\n\n"


async def generate_claude_streaming_response(
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    subaccount_name: str,
    token_manager=None,
) -> AsyncGenerator[bytes, None]:
    """Generate streaming response in Anthropic Claude Messages API format."""
    logger.info(
        "Starting Claude streaming response for model '%s' using subAccount '%s'",
        model,
        subaccount_name,
    )
    logger.debug(
        "Forwarding payload to API (Claude streaming): %s",
        json.dumps(payload, indent=2),
    )
    logger.debug("Request URL: %s", url)
    logger.debug("Request headers: %s", headers)

    timeout_config = httpx.Timeout(600)

    if Detector.is_claude_model(model):
        logger.info(
            "Backend is Claude model, converting response format for '%s'",
            model,
        )
        try:
            success = False
            for attempt in range(AUTH_RETRY_MAX + 1):
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    async with client.stream(
                        "POST", url, headers=headers, json=payload
                    ) as http_response:
                        if http_response.status_code in [401, 403]:
                            if attempt == 0 and token_manager is not None:
                                logger.warning(
                                    log_auth_error_retry(
                                        http_response.status_code,
                                        f"model '{model}'",
                                    )
                                )
                                token_manager.invalidate_token()
                                new_token = token_manager.get_token()
                                headers["Authorization"] = f"Bearer {new_token}"
                                continue
                            logger.error(
                                log_auth_error_retry(
                                    http_response.status_code,
                                    f"model '{model}'",
                                )
                            )
                            http_response.raise_for_status()

                        http_response.raise_for_status()
                        logger.debug(
                            "Claude backend response status: %s",
                            http_response.status_code,
                        )

                        message_start_data = {
                            "type": "message_start",
                            "message": {
                                "id": f"msg_{random.randint(10000000, 99999999)}",
                                "type": "message",
                                "role": "assistant",
                                "content": [],
                                "model": model,
                                "stop_reason": None,
                                "stop_sequence": None,
                                "usage": {"input_tokens": 0, "output_tokens": 0},
                            },
                        }
                        message_start_event = f"event: message_start\ndata: {json.dumps(message_start_data)}\n\n"
                        yield message_start_event.encode("utf-8")

                        content_block_start_data = {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        }
                        content_block_start_event = f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
                        yield content_block_start_event.encode("utf-8")

                        chunk_count = 0
                        stop_reason = None

                        async for line in http_response.aiter_lines():
                            chunk_count += 1
                            if not line:
                                continue

                            line_str = line.strip()
                            logger.debug(
                                "Claude backend chunk %s: %s", chunk_count, line_str
                            )

                            if line_str.startswith("data: "):
                                data_content = line_str[6:].strip()

                                if data_content == "[DONE]":
                                    break

                                try:
                                    try:
                                        parsed_data = json.loads(data_content)
                                    except json.JSONDecodeError:
                                        parsed_data = ast.literal_eval(data_content)

                                    if "contentBlockDelta" in parsed_data:
                                        text_content = parsed_data["contentBlockDelta"][
                                            "delta"
                                        ].get("text", "")
                                        if text_content:
                                            delta_data = {
                                                "type": "content_block_delta",
                                                "index": 0,
                                                "delta": {
                                                    "type": "text_delta",
                                                    "text": text_content,
                                                },
                                            }
                                            delta_event = f"event: content_block_delta\ndata: {json.dumps(delta_data)}\n\n"
                                            yield delta_event.encode("utf-8")

                                    elif "contentBlockStop" in parsed_data:
                                        content_block_stop_data = {
                                            "type": "content_block_stop",
                                            "index": parsed_data[
                                                "contentBlockStop"
                                            ].get("contentBlockIndex", 0),
                                        }
                                        content_block_stop_event = f"event: content_block_stop\ndata: {json.dumps(content_block_stop_data)}\n\n"
                                        yield content_block_stop_event.encode("utf-8")

                                    elif "messageStop" in parsed_data:
                                        stop_reason = parsed_data["messageStop"].get(
                                            "stopReason", "end_turn"
                                        )

                                    elif "metadata" in parsed_data:
                                        usage_info = parsed_data.get(
                                            "metadata", {}
                                        ).get("usage", {})
                                        message_delta_data = {
                                            "type": "message_delta",
                                            "delta": {
                                                "stop_reason": stop_reason
                                                or "end_turn",
                                                "stop_sequence": None,
                                            },
                                            "usage": {
                                                "output_tokens": usage_info.get(
                                                    "outputTokens", 0
                                                )
                                            },
                                        }
                                        message_delta_event = f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
                                        yield message_delta_event.encode("utf-8")

                                        message_stop_event = f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
                                        yield message_stop_event.encode("utf-8")

                                except (
                                    json.JSONDecodeError,
                                    ValueError,
                                    SyntaxError,
                                ) as e:
                                    logger.warning(
                                        "Could not parse Claude backend data: %s, error: %s",
                                        data_content,
                                        e,
                                    )
                                    continue

                        logger.info(
                            "Claude backend conversion completed with %s chunks",
                            chunk_count,
                        )
                        success = True
                        break

            if not success:
                raise Exception("Failed to get valid response for Claude streaming")
        except Exception as e:
            logger.error(
                "Error in Claude backend conversion for '%s': %s",
                model,
                e,
                exc_info=True,
            )
            raise
        return

    logger.info("Converting non-Claude model '%s' stream to Claude format", model)

    message_start_data = {
        "type": "message_start",
        "message": {
            "id": f"msg_{random.randint(10000000, 99999999)}",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }
    message_start_event = (
        f"event: message_start\ndata: {json.dumps(message_start_data)}\n\n"
    )
    logger.debug("Sending message_start event: %s", message_start_event)
    yield message_start_event.encode("utf-8")

    content_block_start_data = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }
    content_block_start_event = (
        f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
    )
    logger.debug("Sending content_block_start event: %s", content_block_start_event)
    yield content_block_start_event.encode("utf-8")

    stop_reason = None
    chunk_count = 0

    try:
        success = False
        for attempt in range(AUTH_RETRY_MAX + 1):
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                async with client.stream(
                    "POST", url, headers=headers, json=payload
                ) as http_response:
                    if http_response.status_code in [401, 403]:
                        if attempt == 0 and token_manager is not None:
                            logger.warning(
                                log_auth_error_retry(
                                    http_response.status_code, f"model '{model}'"
                                )
                            )
                            token_manager.invalidate_token()
                            new_token = token_manager.get_token()
                            headers["Authorization"] = f"Bearer {new_token}"
                            continue
                        logger.error(
                            log_auth_error_retry(
                                http_response.status_code, f"model '{model}'"
                            )
                        )
                        http_response.raise_for_status()

                    http_response.raise_for_status()

                    async for line in http_response.aiter_lines():
                        chunk_count += 1
                        if not line:
                            continue

                        line_str = line.strip()
                        logger.debug(
                            "Streaming chunk %s for model '%s': %s",
                            chunk_count,
                            model,
                            line_str,
                        )

                        if line_str.startswith("data: "):
                            data_content = line_str[6:].strip()
                            if data_content == "[DONE]":
                                break

                            try:
                                parsed_data = json.loads(data_content)
                            except json.JSONDecodeError:
                                logger.warning(
                                    "Failed to parse chunk as JSON: %s", data_content
                                )
                                continue

                            if Detector.is_gemini_model(model):
                                delta_chunk = (
                                    Converters.convert_gemini_chunk_to_claude_delta(
                                        parsed_data
                                    )
                                )
                            else:
                                delta_chunk = (
                                    Converters.convert_openai_chunk_to_claude_delta(
                                        parsed_data
                                    )
                                )

                            if delta_chunk:
                                delta_event = f"event: content_block_delta\ndata: {json.dumps(delta_chunk)}\n\n"
                                yield delta_event.encode("utf-8")

                            if Detector.is_gemini_model(model):
                                stop_reason = get_claude_stop_reason_from_gemini_chunk(
                                    parsed_data
                                )
                            else:
                                stop_reason = get_claude_stop_reason_from_openai_chunk(
                                    parsed_data
                                )

                    success = True
                    break

        if not success:
            raise Exception("Failed to get valid response for Claude streaming")
    except Exception as e:
        logger.error(
            "Error in streaming response from '%s': %s",
            subaccount_name,
            e,
            exc_info=True,
        )
        raise

    content_block_stop_data = {"type": "content_block_stop", "index": 0}
    content_block_stop_event = (
        f"event: content_block_stop\ndata: {json.dumps(content_block_stop_data)}\n\n"
    )
    yield content_block_stop_event.encode("utf-8")

    message_delta_data = {
        "type": "message_delta",
        "delta": {
            "stop_reason": stop_reason or "end_turn",
            "stop_sequence": None,
        },
    }
    message_delta_event = (
        f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
    )
    yield message_delta_event.encode("utf-8")

    message_stop_event = (
        f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
    )
    yield message_stop_event.encode("utf-8")


def generate_streaming_response_sync(
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    subaccount_name: str,
    tid: str,
) -> Generator[str | bytes, None, None]:
    with requests.post(
        url, headers=headers, json=payload, stream=True, timeout=600
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                yield line + b"\n"
            else:
                yield f"{line}\n"


def generate_claude_streaming_response_sync(
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    subaccount_name: str,
    token_manager=None,
) -> Generator[bytes, None, None]:
    with requests.post(
        url, headers=headers, json=payload, stream=True, timeout=600
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                yield line + b"\n"
            else:
                yield f"{line}\n".encode("utf-8")


def generate_bedrock_streaming_response_sync(
    response_body: Any,
    tid: str,
) -> Generator[str, None, None]:
    async_gen = generate_bedrock_streaming_response(response_body, tid)
    return _sync_iter_async_generator(async_gen)
