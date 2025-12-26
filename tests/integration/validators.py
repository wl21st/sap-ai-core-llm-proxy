"""
Response validation utilities for integration tests.

Provides validators for:
- Token usage validation
- SSE message format validation
- OpenAI-compatible response format
- Claude/Anthropic response format
- Common response attributes
"""

import json
from typing import Dict, Any, List, Optional

import requests

from auth import RequestValidator


class ResponseValidator:
    """Validates API responses from the proxy server."""

    @staticmethod
    def validate_token_usage(response_data: Dict[str, Any]) -> None:
        """
        Validate token usage structure and values.

        Args:
            response_data: Response JSON data

        Raises:
            AssertionError: If validation fails
        """
        assert "usage" in response_data, "Response missing 'usage' field"
        usage = response_data["usage"]

        assert "prompt_tokens" in usage, "Usage missing 'prompt_tokens'"
        assert "completion_tokens" in usage, "Usage missing 'completion_tokens'"
        assert "total_tokens" in usage, "Usage missing 'total_tokens'"

        prompt_tokens = usage["prompt_tokens"]
        completion_tokens = usage["completion_tokens"]
        total_tokens = usage["total_tokens"]

        assert isinstance(prompt_tokens, int), "prompt_tokens must be integer"
        assert isinstance(completion_tokens, int), "completion_tokens must be integer"
        assert isinstance(total_tokens, int), "total_tokens must be integer"

        assert prompt_tokens >= 0, "prompt_tokens must be non-negative"
        assert completion_tokens >= 0, "completion_tokens must be non-negative"
        assert total_tokens >= 0, "total_tokens must be non-negative"

        assert total_tokens >= prompt_tokens + completion_tokens, (
            f"total_tokens ({total_tokens}) < prompt_tokens ({prompt_tokens}) + completion_tokens ({completion_tokens})"
        )

    # Perfect! I can now provide you with detailed information about Anthropic's Message Stream SSE response format based on the code.
    # Anthropic Message Stream SSE Response Format
    # For Anthropic's Message Stream API, the SSE (Server-Sent Events) use both event: and data: fields. Here's the structure:
    # SSE Format
    # Each SSE message consists of two lines:
    # 1. event: - Specifies the event type
    # 2. data: - Contains the JSON payload
    # Followed by a blank line (\n\n) as separator.
    # Event Types
    # Based on the code (lines 1167-1210 in proxy_server.py), here are the Anthropic streaming event types:
    # 1. message_start - Signals the beginning of a message
    # 2. content_block_start - Signals the start of a content block
    # 3. content_block_delta - Contains incremental text/content updates
    # 4. content_block_stop - Signals the end of a content block
    # 5. message_delta - Contains message-level updates (like stop_reason)
    # 6. message_stop - Signals the end of the message
    # 7. error - Error event (if something goes wrong)
    # Examples
    # Here are real examples from the codebase:
    # 1. Message Start Event
    # event: message_start
    # data: {"type":"message_start","message":{"id":"msg_123","type":"message","role":"assistant","content":[],"model":"claude-3-5-sonnet-20241022"}}
    # 2. Content Block Start Event
    # event: content_block_start
    # data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}
    # 3. Content Block Delta Event (with text)
    # event: content_block_delta
    # data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}
    # 4. Content Block Stop Event
    # event: content_block_stop
    # data: {"type":"content_block_stop","index":0}
    # 5. Message Delta Event (with metadata/usage)
    # event: message_delta
    # data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":15}}
    # 6. Message Stop Event
    # event: message_stop
    # data: {"type":"message_stop"}
    # 7. Error Event
    # event: error
    # data: {"type":"error","error":{"type":"api_error","message":"Error message here"}}
    # 8. Done Signal (Optional)
    # data: [DONE]

    @staticmethod
    def validate_sse_response(
        model: str,
        response: requests.Response,
    ) -> tuple[int, list[str], int, list[str]]:
        event_chunk_count: int = 0
        event_chunk_list: list[str] = []
        data_chunk_count: int = 0
        data_chunk_list: list[str] = []

        assert response.status_code == 200

        for line in response.iter_lines():
            if line:
                line_str: str = line.decode("utf-8").strip()
                # Validate SSE format
                if line_str.startswith("data: "):
                    ResponseValidator.validate_sse_data_chunk(line)
                    data_chunk_count += 1
                    data_chunk_list.append(line_str)
                elif line_str.startswith("event: "):
                    ResponseValidator.validate_sse_event_chunk(line)
                    event_chunk_count += 1
                    event_chunk_list.append(line_str)
                else:
                    raise AssertionError(f"Undefined SSE line: {line}!")

        assert data_chunk_count > 0, (
            f"No data chunk received for model {model}, got: events={event_chunk_list}"
        )

        return event_chunk_count, event_chunk_list, data_chunk_count, data_chunk_list

    @staticmethod
    def validate_sse_event_chunk(chunk: bytes) -> None:
        """
        Validate SSE event format.

        Args:
            chunk: Raw SSE chunk bytes

        Raises:
            AssertionError: If validation fails
        """
        # SSE messages should start with event:
        assert chunk.startswith(b"event: "), (
            f"SSE event chunk must start with event:, got: {chunk[:30]}"
        )

        # Extract data content
        chunk_str: str = chunk.decode("utf-8").strip()

        # Skip "event: " (7 characters including space)
        index: int = chunk_str.find("event: ")
        event_type_str: str = chunk_str
        if index != -1:
            event_type_str = chunk_str[index + 7 :]

        # Check for [DONE] signal
        if event_type_str in [
            "message_start",
            "content_block_start",
            "content_block_delta",
            "content_block_stop",
            "message_delta",
            "message_stop",
            "error",
        ]:
            return
        else:
            raise AssertionError(f"SSE event type={event_type_str} is undefined!")

    @staticmethod
    def validate_sse_data_chunk(chunk: bytes) -> None:
        """
        Validate SSE data format.

        Args:
            chunk: Raw SSE chunk bytes

        Raises:
            AssertionError: If validation fails
        """
        # SSE messages should start with "event:
        assert chunk.startswith(b"data: "), (
            f"SSE data chunk must start with data:, got: {chunk[:30]}"
        )

        # Extract data content
        chunk_str: str = chunk.decode("utf-8").strip()

        # Skip "data: " (6 characters including space)
        index: int = chunk_str.find("data: ")
        data_json_str: str = chunk_str
        if index != -1:
            data_json_str = chunk_str[index + 6 :]

        # Check for [DONE] signal
        if data_json_str == "[DONE]":
            return

        # Otherwise, should be valid JSON
        try:
            data = json.loads(data_json_str)
            assert isinstance(data, dict), "SSE data must be a JSON object"
        except json.JSONDecodeError as e:
            raise AssertionError(f"SSE chunk contains invalid JSON: {e}")

    @staticmethod
    def validate_openai_format(response_data: Dict[str, Any]) -> None:
        """
        Validate OpenAI-compatible response format.

        Args:
            response_data: Response JSON data

        Raises:
            AssertionError: If validation fails
        """
        assert "id" in response_data, "Response missing 'id'"
        assert "object" in response_data, "Response missing 'object'"
        assert "created" in response_data, "Response missing 'created'"
        assert "model" in response_data, "Response missing 'model'"
        assert "choices" in response_data, "Response missing 'choices'"

        assert response_data["object"] == "chat.completion", (
            f"Expected object='chat.completion', got '{response_data['object']}'"
        )
        assert isinstance(response_data["choices"], list), "choices must be a list"
        assert len(response_data["choices"]) > 0, "choices must not be empty"

        choice = response_data["choices"][0]
        assert "index" in choice, "Choice missing 'index'"
        assert "message" in choice, "Choice missing 'message'"
        assert "finish_reason" in choice, "Choice missing 'finish_reason'"

        message = choice["message"]
        assert "role" in message, "Message missing 'role'"
        assert "content" in message, "Message missing 'content'"
        assert message["role"] == "assistant", (
            f"Expected role='assistant', got '{message['role']}'"
        )

    @staticmethod
    def validate_claude_format(response_data: Dict[str, Any]) -> None:
        """
        Validate Claude/Anthropic response format.

        Args:
            response_Response JSON data

        Raises:
            AssertionError: If validation fails
        """
        assert "id" in response_data, "Response missing 'id'"
        assert "type" in response_data, "Response missing 'type'"
        assert "role" in response_data, "Response missing 'role'"
        assert "content" in response_data, "Response missing 'content'"
        assert "model" in response_data, "Response missing 'model'"
        assert "stop_reason" in response_data, "Response missing 'stop_reason'"
        assert "usage" in response_data, "Response missing 'usage'"

        assert response_data["type"] == "message", (
            f"Expected type='message', got '{response_data['type']}'"
        )
        assert response_data["role"] == "assistant", (
            f"Expected role='assistant', got '{response_data['role']}'"
        )
        assert isinstance(response_data["content"], list), "content must be a list"
        assert len(response_data["content"]) > 0, "content must not be empty"

        # Validate usage
        usage = response_data["usage"]
        assert "input_tokens" in usage, "Usage missing 'input_tokens'"
        assert "output_tokens" in usage, "Usage missing 'output_tokens'"

    @staticmethod
    def validate_common_attributes(response_data: dict[str, Any]) -> None:
        """
        Validate common response attributes.

        Args:
            response_data: Response JSON data

        Raises:
            AssertionError: If validation fails
        """
        assert "id" in response_data, "Response missing 'id'"
        assert "model" in response_data, "Response missing 'model'"

        assert isinstance(response_data["id"], str), "id must be a string"
        assert len(response_data["id"]) > 0, "id must not be empty"
        assert isinstance(response_data["model"], str), "model must be a string"
        assert len(response_data["model"]) > 0, "model must not be empty"

    @staticmethod
    def validate_streaming_chunk(chunk_data: Dict[str, Any]) -> None:
        """
        Validate streaming chunk format.

        Args:
            chunk_data: Parsed chunk JSON data

        Raises:
            AssertionError: If validation fails
        """
        assert "id" in chunk_data, "Chunk missing 'id'"
        assert "object" in chunk_data, "Chunk missing 'object'"
        assert "created" in chunk_data, "Chunk missing 'created'"
        assert "model" in chunk_data, "Chunk missing 'model'"
        assert "choices" in chunk_data, "Chunk missing 'choices'"

        assert chunk_data["object"] == "chat.completion.chunk", (
            f"Expected object='chat.completion.chunk', got '{chunk_data['object']}'"
        )
        assert isinstance(chunk_data["choices"], list), "choices must be a list"

        if len(chunk_data["choices"]) > 0:
            choice = chunk_data["choices"][0]
            assert "index" in choice, "Choice missing 'index'"
            assert "delta" in choice, "Choice missing 'delta'"

    @staticmethod
    def extract_streaming_content(chunks: list[dict[str, Any]]) -> str:
        """
        Extract full content from streaming chunks.

        Args:
            chunks: List of parsed chunk data

        Returns:
            Full concatenated content
        """
        content_parts = []
        for chunk in chunks:
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta and delta["content"]:
                    content_parts.append(delta["content"])
        return "".join(content_parts)

    @staticmethod
    def get_final_chunk_with_usage(
        chunks: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Get the final chunk that contains usage information.

        Args:
            chunks: List of parsed chunk data

        Returns:
            Final chunk with usage, or None if not found
        """
        for chunk in reversed(chunks):
            if "usage" in chunk:
                return chunk
        return None
