"""Streaming generator functions for the LLM proxy.

This module contains generator functions that yield SSE-formatted streaming
responses from various LLM backends (Bedrock, Claude, Gemini, OpenAI).

Phase 6d: Streaming generators extraction
"""

import ast
import json
import logging
import random
import time
from typing import Any, Generator, Iterator

import requests
from flask import request

from config import ProxyGlobalContext
from proxy_helpers import Converters, Detector
from handlers.streaming_handler import (
    get_claude_stop_reason_from_gemini_chunk,
    get_claude_stop_reason_from_openai_chunk,
)
from utils.auth_retry import AUTH_RETRY_MAX, log_auth_error_retry

logger = logging.getLogger(__name__)
transport_logger = logging.getLogger("transport")
token_usage_logger = logging.getLogger("token_usage")


def generate_bedrock_streaming_response(
    response_body: Iterator[dict],
    tid: str,
) -> Generator[str, None, None]:
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

    Example:
        ```
        event: content_block_delta
        data: {"type": "content_block_delta", "delta": {"text": "Hello"}}

        ```

    Notes:
        - Each SSE event follows the format: "event: <type>\\ndata: <json>\\n\\n"
        - Errors during streaming are sent as SSE error events (HTTP status
          cannot be changed after streaming starts)
        - Stream terminates with [DONE] signal after message_stop event
    """
    try:
        for event in response_body:
            chunk = json.loads(event["chunk"]["bytes"])
            logger.debug(f"Streaming chunk: {chunk}")

            # Log raw chunk from Bedrock
            transport_logger.info(f"CHUNK: tid={tid}, {json.dumps(chunk)[:200]}")

            chunk_type = chunk.get("type")

            # Handle different chunk types according to Claude streaming format
            if chunk_type == "message_start":
                response_line = f"event: message_start\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                transport_logger.info(f"CHUNK: tid={tid}, {response_line[:200]}")
                yield response_line
            elif chunk_type == "content_block_start":
                response_line = f"event: content_block_start\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                transport_logger.info(f"CHUNK: tid={tid}, {response_line[:200]}")
                yield response_line
            elif chunk_type == "content_block_delta":
                response_line = f"event: content_block_delta\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                transport_logger.info(f"CHUNK: tid={tid}, {response_line[:200]}")
                yield response_line
            elif chunk_type == "content_block_stop":
                response_line = f"event: content_block_stop\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                transport_logger.info(f"CHUNK: tid={tid}, {response_line[:200]}")
                yield response_line
            elif chunk_type == "message_delta":
                response_line = f"event: message_delta\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                transport_logger.info(f"CHUNK: tid={tid}, {response_line[:200]}")
                yield response_line
            elif chunk_type == "message_stop":
                response_line = f"event: message_stop\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                transport_logger.info(f"CHUNK: tid={tid}, {response_line[:200]}")
                yield response_line
                transport_logger.info(f"DONE: tid={tid}, Stream finished successfully")
                yield "data: [DONE]\n\n"
                break
            elif chunk_type == "error":
                # Handle error chunks in the stream
                response_line = (
                    f"event: error\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                )
                transport_logger.info(f"ERR: tid={tid}, {response_line[:200]}")
                yield response_line
                break

    except Exception as e:
        # Errors during streaming can only be sent as SSE events
        logger.error(f"Error during streaming: {e}", exc_info=True)
        error_chunk = {
            "type": "error",
            "error": {"type": "api_error", "message": str(e)},
        }
        yield f"event: error\ndata: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"


def generate_streaming_response(
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    subaccount_name: str,
    tid: str,
) -> Generator[str | bytes, None, None]:
    """Generate streaming response from backend API in OpenAI-compatible format.

    This is the main streaming generator that handles all backend model types
    (Claude 3.7/4, Gemini, older Claude, OpenAI) and converts their streaming
    responses to OpenAI's Server-Sent Events (SSE) format.

    Args:
        url: Backend API endpoint URL
        headers: HTTP headers to forward to backend
        payload: Request payload to send to backend
        model: Model name (used for format detection/conversion)
        subaccount_name: Name of the selected subAccount (for logging)
        tid: Trace UUID for logging correlation

    Yields:
        SSE-formatted response chunks as strings or bytes

    Processing Flow:
        1. Makes streaming HTTP request to backend (10-minute timeout)
        2. Detects backend model type (Claude 3.7/4, Gemini, older Claude, OpenAI)
        3. Iterates over backend response stream (iter_lines or iter_content)
        4. Converts chunks to OpenAI SSE format using appropriate converter
        5. Tracks token usage from metadata/usage chunks
        6. Yields converted SSE chunks in real-time
        7. Sends final chunk with finish_reason and usage information
        8. Terminates with [DONE] signal

    Token Tracking:
        - Claude 3.7/4: Extracted from metadata.usage chunk (totalTokens, inputTokens, outputTokens)
        - Gemini: Extracted from usageMetadata (totalTokenCount, promptTokenCount, candidatesTokenCount)
        - Older Claude: Extracted from usage field (input_tokens, output_tokens)
        - OpenAI: Extracted from chunks with finish_reason

    Error Handling:
        - HTTP errors: Yields error payload as SSE data chunk
        - Chunk parsing errors: Yields error payload with [PROXY ERROR] message
        - Rate limit (429): Delegates to handle_http_429_error()
        - Generic errors: Yields error payload with proxy_error type

    Notes:
        - Stream-specific timeout: 600 seconds (10 minutes)
        - Avoids duplicate [DONE] signals using done_sent flag
        - Token usage logged to token_usage_logger at stream end
        - Cannot change HTTP status once streaming starts
    """
    # Log the raw request body and payload being forwarded
    payload_json_str: str = json.dumps(payload)
    # Log request being sent to LLM service
    transport_logger.info(
        f"OUT_REQ_CHAT_ST: tid={tid}, url={url}], body={payload_json_str}"
    )

    buffer = ""
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    claude_metadata = {}  # For Claude 3.7 metadata
    chunk = None  # Initialize chunk variable to avoid reference errors
    done_sent = False  # Track if [DONE] was already sent by backend

    # Make streaming request to backend
    with requests.post(
        url, headers=headers, json=payload, stream=True, timeout=600
    ) as response:
        try:
            response.raise_for_status()

            # --- Claude 3.7/4 Streaming Logic ---
            if Detector.is_claude_model(model) and Detector.is_claude_37_or_4(model):
                logger.info(
                    f"Using Claude 3.7/4 streaming for subAccount '{subaccount_name}'"
                )
                stop_reason_received = None  # Track the stop reason from messageStop
                # Initialize stream_id with fallback, will be replaced if messageStart has an ID
                stream_id = f"chatcmpl-claude-{random.randint(10000000, 99999999)}"
                # Initialize token counters (will be updated if metadata chunk is received)
                total_tokens = 0
                prompt_tokens = 0
                completion_tokens = 0

                for line_bytes in response.iter_lines():
                    if line_bytes:
                        line = line_bytes.decode("utf-8")
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            # logger.info(f"Raw data chunk from Claude API: {line_content}")
                            try:
                                line_content = ast.literal_eval(line_content)
                                line_content = json.dumps(line_content)
                                claude_dict_chunk = json.loads(line_content)

                                # Extract ID from messageStart chunk to replace fallback ID
                                if "messageStart" in claude_dict_chunk:
                                    message_id = (
                                        claude_dict_chunk.get("messageStart", {})
                                        .get("message", {})
                                        .get("id", "")
                                    )
                                    if message_id:
                                        # Replace fallback ID with the actual message ID from Claude
                                        stream_id = f"chatcmpl-claude-{message_id}"
                                        logger.info(
                                            f"Extracted stream ID from messageStart: {stream_id}"
                                        )
                                    else:
                                        logger.warning(
                                            f"messageStart has no ID, continuing with fallback: {stream_id}"
                                        )

                                # Check if this is a messageStop chunk - capture stop reason but don't send yet
                                if "messageStop" in claude_dict_chunk:
                                    stop_reason_received = claude_dict_chunk.get(
                                        "messageStop", {}
                                    ).get("stopReason", "end_turn")
                                    logger.info(
                                        f"Received messageStop with stopReason: {stop_reason_received}"
                                    )
                                    # Don't send this chunk yet - wait for metadata to combine with usage
                                    continue

                                # Check if this is a metadata chunk by looking for 'metadata' key directly
                                if "metadata" in claude_dict_chunk:
                                    claude_metadata = claude_dict_chunk.get(
                                        "metadata", {}
                                    )
                                    logger.info(f"CHAT_RSP_ST_META: {claude_metadata}")
                                    # Extract token counts immediately
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
                                            f"Extracted token usage from metadata: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                                        )
                                    # Don't process this chunk further, just continue to next
                                    continue

                                # Convert chunk to OpenAI format, passing the consistent stream_id
                                openai_sse_chunk_str = (
                                    Converters.convert_claude37_chunk_to_openai(
                                        claude_dict_chunk, model, stream_id
                                    )
                                )

                                if openai_sse_chunk_str:
                                    # Log client chunk sent
                                    logger.info(
                                        f"CHUNK: tid={tid}, {openai_sse_chunk_str[:200]}"
                                    )
                                    transport_logger.info(
                                        f"CHUNK: tid={tid}, {openai_sse_chunk_str}"
                                    )
                                    yield openai_sse_chunk_str
                            except Exception as e:
                                logger.error(
                                    f"Error processing Claude 3.7 chunk from '{subaccount_name}': {e}",
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

                # Send final chunk with BOTH finish_reason and usage information
                if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                    # Map Claude stop reason to OpenAI finish_reason
                    stop_reason_map = {
                        "end_turn": "stop",
                        "max_tokens": "length",
                        "stop_sequence": "stop",
                        "tool_use": "tool_calls",
                    }
                    finish_reason = stop_reason_map.get(stop_reason_received, "stop")

                    # Use the same stream_id for the final usage chunk
                    final_usage_chunk = {
                        "id": stream_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": {}, "finish_reason": finish_reason}
                        ],
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                    }
                    final_usage_chunk_str = f"data: {json.dumps(final_usage_chunk)}\n\n"
                    logger.info(
                        f"Sending final chunk with finish_reason={finish_reason} and usage: {final_usage_chunk_str[:200]}..."
                    )
                    yield final_usage_chunk_str
                    logger.info(
                        f"Sent final chunk: finish_reason={finish_reason}, prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                    )

                    # Log token usage
                    user_id = request.headers.get("Authorization", "unknown")
                    if user_id and len(user_id) > 20:
                        user_id = f"{user_id[:20]}..."
                    ip_address = request.remote_addr or request.headers.get(
                        "X-Forwarded-For", "unknown_ip"
                    )
                    token_usage_logger.info(
                        f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                        f"PromptTokens: {prompt_tokens}, CompletionTokens: {completion_tokens}, TotalTokens: {total_tokens} (Streaming)"
                    )

            # --- Gemini Streaming Logic ---
            elif Detector.is_gemini_model(model):
                logger.info(
                    f"Using Gemini streaming for subAccount '{subaccount_name}'"
                )
                # Initialize token counters (will be updated if usage metadata is received)
                total_tokens = 0
                prompt_tokens = 0
                completion_tokens = 0
                for line_bytes in response.iter_lines():
                    if line_bytes:
                        line = line_bytes.decode("utf-8")
                        logger.info(f"Gemini raw line received: {line}")

                        # Process Gemini streaming lines
                        line_content = ""
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            logger.info(f"Gemini data line content: {line_content}")
                        elif line.strip():
                            # Handle lines without "" prefix
                            line_content = line.strip()
                            logger.info(
                                f"Gemini line content (no prefix): {line_content}"
                            )

                        if line_content and line_content != "[DONE]":
                            try:
                                gemini_chunk: dict[str, Any] = json.loads(line_content)
                                logger.info(
                                    f"Gemini parsed chunk: {json.dumps(gemini_chunk, indent=2)}"
                                )

                                # Convert chunk to OpenAI format
                                openai_sse_chunk_str = (
                                    Converters.convert_gemini_chunk_to_openai(
                                        gemini_chunk, model
                                    )
                                )
                                if openai_sse_chunk_str:
                                    logger.info(
                                        f"Gemini converted to OpenAI chunk: {openai_sse_chunk_str}"
                                    )
                                    # Verify chunk starts with "data: "
                                    if not openai_sse_chunk_str.startswith("data: "):
                                        logger.error(
                                            f"ERROR: Converter returned chunk without 'data: ' prefix: {openai_sse_chunk_str[:100]}"
                                        )
                                    yield openai_sse_chunk_str.encode("utf-8")
                                else:
                                    logger.info("Gemini chunk conversion returned None")

                                # Extract token usage from usageMetadata if available
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
                                        f"Gemini token usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                                    )

                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Error parsing Gemini chunk from '{subaccount_name}': {e}",
                                    exc_info=True,
                                )
                                logger.error(
                                    f"Problematic line content: {line_content}"
                                )
                                continue
                            except Exception as e:
                                logger.error(
                                    f"Error processing Gemini chunk from '{subaccount_name}': {e}",
                                    exc_info=True,
                                )
                                logger.error(
                                    f"Problematic chunk: {gemini_chunk} if 'gemini_chunk' in locals() else 'Failed to parse'"
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

                # Send final chunk with usage information before [DONE] for Gemini
                if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                    final_usage_chunk = {
                        "id": f"chatcmpl-gemini-{random.randint(10000000, 99999999)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                    }
                    final_usage_chunk_str = f"data: {json.dumps(final_usage_chunk)}\n\n"
                    logger.info(
                        f"[FIXED] Sending final Gemini usage chunk with data prefix: {len(final_usage_chunk_str)} bytes, starts with: {final_usage_chunk_str[:50]}"
                    )
                    # Verify chunk starts with "data: "
                    if not final_usage_chunk_str.startswith("data: "):
                        logger.error(
                            f"ERROR: Final usage chunk does not start with 'data: ': {final_usage_chunk_str[:100]}"
                        )
                    yield final_usage_chunk_str.encode("utf-8")
                    logger.info(
                        f"Sent final Gemini usage chunk: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                    )

                    # Log token usage
                    user_id = request.headers.get("Authorization", "unknown")
                    if user_id and len(user_id) > 20:
                        user_id = f"{user_id[:20]}..."
                    ip_address = request.remote_addr or request.headers.get(
                        "X-Forwarded-For", "unknown_ip"
                    )
                    token_usage_logger.info(
                        f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                        f"PromptTokens: {prompt_tokens}, CompletionTokens: {completion_tokens}, TotalTokens: {total_tokens} (Streaming)"
                    )

            # --- Other Models (including older Claude) ---
            else:
                for chunk in response.iter_content(chunk_size=128):
                    if chunk:
                        if Detector.is_claude_model(model):  # Older Claude
                            buffer += chunk.decode("utf-8")
                            while "data: " in buffer:
                                try:
                                    start = buffer.index("data: ") + len("data: ")
                                    end = buffer.index("\n\n", start)
                                    json_chunk_str = buffer[start:end].strip()
                                    buffer = buffer[end + 2 :]

                                    # Convert Claude chunk to OpenAI format
                                    openai_sse_chunk_str = (
                                        Converters.convert_claude_chunk_to_openai(
                                            json_chunk_str, model
                                        )
                                    )
                                    yield openai_sse_chunk_str.encode("utf-8")

                                    # Parse token usage if available
                                    try:
                                        claude_data = json.loads(json_chunk_str)
                                        if "usage" in claude_data:
                                            prompt_tokens = claude_data["usage"].get(
                                                "input_tokens", 0
                                            )
                                            completion_tokens = claude_data[
                                                "usage"
                                            ].get("output_tokens", 0)
                                            total_tokens = (
                                                prompt_tokens + completion_tokens
                                            )
                                    except json.JSONDecodeError:
                                        pass
                                except ValueError:
                                    break  # Not enough data in buffer
                                except Exception as e:
                                    logger.error(
                                        f"Error processing claude chunk: {e}",
                                        exc_info=True,
                                    )
                                    break
                        else:  # OpenAI-like models
                            yield chunk
                            try:
                                # Try to extract token counts from final chunk
                                if chunk:
                                    chunk_text = chunk.decode("utf-8")
                                    # Check if [DONE] was sent by backend
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

            # Log token usage at the end of the stream (only for non-Claude 3.7/4 models)
            # Claude 3.7/4 models already log their token usage after sending the final usage chunk
            if not (
                Detector.is_claude_model(model) and Detector.is_claude_37_or_4(model)
            ):
                user_id = request.headers.get("Authorization", "unknown")
                if user_id and len(user_id) > 20:
                    user_id = f"{user_id[:20]}..."
                ip_address = request.remote_addr or request.headers.get(
                    "X-Forwarded-For", "unknown_ip"
                )

                # Log with subAccount information
                token_usage_logger.info(
                    f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                    f"PromptTokens: {prompt_tokens if 'prompt_tokens' in locals() else 0}, "
                    f"CompletionTokens: {completion_tokens if 'completion_tokens' in locals() else 0}, "
                    f"TotalTokens: {total_tokens} (Streaming)"
                )

            # Standard stream end
            transport_logger.info(f"DONE: tid={tid}, Streaming completed")
            # Only send [DONE] if backend didn't already send it
            if not done_sent:
                yield "data: [DONE]\n\n"

        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP Error in streaming response:({model}): {http_err}", exc_info=True
            )

            error_content: str = ""

            if http_err.response is not None:
                response = http_err.response
                status_code = response.status_code
                error_content = response.text

                # Handle HTTP 429 (Too Many Requests) specifically
                if status_code == 429:
                    from utils.error_handlers import handle_http_429_error

                    return handle_http_429_error(
                        http_err, f"streaming request for {model}"
                    )

                logger.error(f"Error response status: {response.status_code}")
                logger.error(f"Error response headers: {dict(response.headers)}")
                logger.error(f"Error response body: {response.text}")
                try:
                    logger.error(f"Error response body: {error_content}")

                    # Try to parse as JSON for better formatting
                    try:
                        error_content = json.dumps(response.json(), indent=2)
                        logger.error(f"Error response JSON: {error_content}")
                    except json.JSONDecodeError:
                        pass
                except Exception as e:
                    logger.error(
                        f"Could not read error response content: {e}", exc_info=True
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
                f"Error in streaming response from '{subaccount_name}': {http_err}",
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
            # Use strings directly without referencing chunk to avoid errors
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"


def generate_claude_streaming_response(
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    subaccount_name: str,
    token_manager=None,
) -> Generator[bytes, None, None]:
    """Generate streaming response in Anthropic Claude Messages API format.

    This generator converts any backend model's streaming response to the
    Anthropic Claude Messages API format with proper SSE events.

    Args:
        url: Backend API endpoint URL
        headers: HTTP headers to forward to backend
        payload: Request payload to send to backend
        model: Model name (used for format detection/conversion)
        subaccount_name: Name of the selected subAccount (for logging)
        token_manager: Optional token manager for retry on auth errors

    Yields:
        SSE-formatted response bytes (event + data lines)

    Processing Flow (Backend is Claude):
        1. Sends message_start event with initial metadata
        2. Sends content_block_start event
        3. Iterates over Claude backend chunks
        4. Converts contentBlockDelta → content_block_delta events
        5. Converts contentBlockStop → content_block_stop event
        6. Extracts stop_reason from messageStop chunk
        7. Sends message_delta event with stop_reason and token usage
        8. Sends message_stop event

    Processing Flow (Backend is Gemini/OpenAI):
        1. Sends message_start event with initial metadata
        2. Sends content_block_start event
        3. Iterates over backend chunks
        4. Converts chunks to Claude delta format using:
           - convert_gemini_chunk_to_claude_delta() for Gemini
           - convert_openai_chunk_to_claude_delta() for OpenAI
        5. Extracts stop_reason from finish chunks
        6. Sends content_block_stop event
        7. Sends message_delta event with stop_reason
        8. Sends message_stop event

    Retry Logic:
        - If the backend returns 401 or 403, the token manager (if provided)
          will be used to invalidate the current token and fetch a fresh one
        - The request will be retried exactly once with the new credentials
        - This handles cases where cached tokens become invalid before expiry

    Notes:
        - 10-minute timeout for streaming requests
        - Backend-specific chunk parsing (JSON or ast.literal_eval)
        - Token usage available only in Claude backend (metadata.usage)
        - Yields bytes (not strings) for Flask Response
    """
    logger.info(
        f"Starting Claude streaming response for model '{model}' using subAccount '{subaccount_name}'"
    )
    logger.debug(
        f"Forwarding payload to API (Claude streaming): {json.dumps(payload, indent=2)}"
    )
    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request headers: {headers}")

    # If the backend is already a Claude model, we need to convert the response format.
    if Detector.is_claude_model(model):
        logger.info(
            f"Backend is Claude model, converting response format for '{model}'"
        )
        try:
            success = False
            for attempt in range(AUTH_RETRY_MAX + 1):
                with requests.post(
                    url, headers=headers, json=payload, stream=True, timeout=600
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
                        else:
                            logger.error(
                                log_auth_error_retry(
                                    http_response.status_code, f"model '{model}'"
                                )
                            )
                            http_response.raise_for_status()

                    http_response.raise_for_status()
                    logger.debug(
                        f"Claude backend response status: {http_response.status_code}"
                    )

                    # Process the response while the connection is still open
                    # Send message_start event
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

                    # Send content_block_start event
                    content_block_start_data = {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "text", "text": ""},
                    }
                    content_block_start_event = f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
                    yield content_block_start_event.encode("utf-8")

                    chunk_count = 0
                    stop_reason = None

                    for line in http_response.iter_lines():
                        chunk_count += 1
                        if not line:
                            continue

                        line_str = line.decode("utf-8", errors="ignore").strip()
                        logger.debug(f"Claude backend chunk {chunk_count}: {line_str}")

                        if line_str.startswith("data: "):
                            data_content = line_str[
                                6:
                            ].strip()  # Remove 'data: ' prefix

                            # Handle different data formats
                            if data_content == "[DONE]":
                                break

                            try:
                                # Try to parse as JSON first
                                try:
                                    parsed_data = json.loads(data_content)
                                except json.JSONDecodeError:
                                    # If JSON parsing fails, try to evaluate as Python dict
                                    # This handles the case where single quotes are used instead of double quotes
                                    parsed_data = ast.literal_eval(data_content)

                                # Convert Claude backend format to standard Claude API format
                                if "contentBlockDelta" in parsed_data:
                                    # Extract text from the delta and format it the same way as OpenAI conversion
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
                                        "index": parsed_data["contentBlockStop"].get(
                                            "contentBlockIndex", 0
                                        ),
                                    }
                                    content_block_stop_event = f"event: content_block_stop\ndata: {json.dumps(content_block_stop_data)}\n\n"
                                    yield content_block_stop_event.encode("utf-8")

                                elif "messageStop" in parsed_data:
                                    stop_reason = parsed_data["messageStop"].get(
                                        "stopReason", "end_turn"
                                    )

                                elif "metadata" in parsed_data:
                                    # Extract token usage information
                                    usage_info = parsed_data.get("metadata", {}).get(
                                        "usage", {}
                                    )
                                    message_delta_data = {
                                        "type": "message_delta",
                                        "delta": {
                                            "stop_reason": stop_reason or "end_turn",
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

                            except (json.JSONDecodeError, ValueError, SyntaxError) as e:
                                logger.warning(
                                    f"Could not parse Claude backend data: {data_content}, error: {e}"
                                )
                                continue

                    logger.info(
                        f"Claude backend conversion completed with {chunk_count} chunks"
                    )
                    success = True
                    break

            if not success:
                raise Exception("Failed to get valid response for Claude streaming")
        except Exception as e:
            logger.error(
                f"Error in Claude backend conversion for '{model}': {e}", exc_info=True
            )
            raise
        return

    # For other models, we need to convert the stream to Claude's event format.
    logger.info(f"Converting non-Claude model '{model}' stream to Claude format")

    # 1. Send message_start event
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
    logger.debug(f"Sending message_start event: {message_start_event}")
    yield message_start_event.encode("utf-8")

    # 2. Send content_block_start event
    content_block_start_data = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }
    content_block_start_event = (
        f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
    )
    logger.debug(f"Sending content_block_start event: {content_block_start_event}")
    yield content_block_start_event.encode("utf-8")

    stop_reason = None
    chunk_count = 0
    delta_count = 0

    try:
        success = False
        for attempt in range(AUTH_RETRY_MAX + 1):
            with requests.post(
                url, headers=headers, json=payload, stream=True, timeout=600
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
                    else:
                        logger.error(
                            log_auth_error_retry(
                                http_response.status_code, f"model '{model}'"
                            )
                        )
                        http_response.raise_for_status()

                http_response.raise_for_status()
                logger.debug(f"Backend response status: {http_response.status_code}")
                logger.debug(f"Backend response headers: {dict(http_response.headers)}")

                # 3. Iterate and yield content_block_delta events
                for line in http_response.iter_lines():
                    chunk_count += 1
                    logger.debug(f"Processing backend chunk {chunk_count}: {line}")

                    if not line or not line.strip().startswith(b"data:"):
                        logger.debug(f"Skipping non-data line {chunk_count}: {line}")
                        continue

                    line_str = line.decode("utf-8", errors="ignore")[5:].strip()
                    logger.debug(f"Extracted line content: {line_str}")

                    if line_str == "[DONE]":
                        logger.info(f"Received [DONE] signal at chunk {chunk_count}")
                        break

                    try:
                        backend_chunk = json.loads(line_str)
                        logger.debug(
                            f"Parsed backend chunk: {json.dumps(backend_chunk, indent=2)}"
                        )

                        claude_delta = None
                        if Detector.is_gemini_model(model):
                            logger.debug("Converting Gemini chunk to Claude delta")
                            claude_delta = (
                                Converters.convert_gemini_chunk_to_claude_delta(
                                    backend_chunk
                                )
                            )
                            if not stop_reason:
                                stop_reason = get_claude_stop_reason_from_gemini_chunk(
                                    backend_chunk
                                )
                                if stop_reason:
                                    logger.debug(
                                        f"Extracted stop reason from Gemini: {stop_reason}"
                                    )
                        else:  # Assume OpenAI-compatible
                            logger.debug("Converting OpenAI chunk to Claude delta")
                            claude_delta = (
                                Converters.convert_openai_chunk_to_claude_delta(
                                    backend_chunk
                                )
                            )
                            if not stop_reason:
                                stop_reason = get_claude_stop_reason_from_openai_chunk(
                                    backend_chunk
                                )
                                if stop_reason:
                                    logger.debug(
                                        f"Extracted stop reason from OpenAI: {stop_reason}"
                                    )

                        if claude_delta:
                            delta_count += 1
                            delta_event = f"event: content_block_delta\ndata: {json.dumps(claude_delta)}\n\n"
                            logger.debug(
                                f"Sending content_block_delta {delta_count}: {delta_event}"
                            )
                            yield delta_event.encode("utf-8")
                        else:
                            logger.debug(f"No delta extracted from chunk {chunk_count}")

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Could not decode JSON from stream chunk {chunk_count}: {line_str}, error: {e}"
                        )
                        continue
                    except Exception as e:
                        logger.error(
                            f"Error processing chunk {chunk_count}: {e}", exc_info=True
                        )
                        continue

                logger.info(
                    f"Processed {chunk_count} chunks, generated {delta_count} deltas"
                )
                success = True
                break

        if not success:
            raise Exception("Failed to get valid response for streaming request")

    except requests.exceptions.HTTPError as e:
        logger.error(
            f"HTTP error in Claude streaming conversion({model}): {e}",
            exc_info=True,
        )
        if hasattr(e, "response") and e.response:
            logger.error(f"Error response status: {e.response.status_code}")
            logger.error(f"Error response body: {e.response.text}")
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error in Claude streaming conversion for '{model}': {e}",
            exc_info=True,
        )
        raise

    # 4. Send stop events
    logger.debug(f"Sending stop events with stop_reason: {stop_reason}")

    content_block_stop_event = f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    logger.debug(f"Sending content_block_stop event: {content_block_stop_event}")
    yield content_block_stop_event.encode("utf-8")

    message_delta_data = {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason or "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 0},  # Token usage is not available in most streams
    }
    message_delta_event = (
        f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
    )
    logger.debug(f"Sending message_delta event: {message_delta_event}")
    yield message_delta_event.encode("utf-8")

    message_stop_event = (
        f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
    )
    logger.debug(f"Sending message_stop event: {message_stop_event}")
    yield message_stop_event.encode("utf-8")

    logger.info(
        f"Claude streaming response completed for model '{model}' with {delta_count} content deltas"
    )
