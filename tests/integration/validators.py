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

        assert (
            total_tokens >= prompt_tokens + completion_tokens
        ), f"total_tokens ({total_tokens}) < prompt_tokens ({prompt_tokens}) + completion_tokens ({completion_tokens})"

    @staticmethod
    def validate_sse_chunk(chunk: bytes) -> None:
        """
        Validate SSE message format.

        Args:
            chunk: Raw SSE chunk bytes

        Raises:
            AssertionError: If validation fails
        """
        # SSE messages should start with ""
        assert chunk.startswith(b"data: "), f"SSE chunk must start with '', got: {chunk[:20]}"

        # Extract data content
        data_str = chunk[6:].decode("utf-8").strip()

        # Check for [DONE] signal
        if data_str == "[DONE]":
            return

        # Otherwise, should be valid JSON
        try:
            data = json.loads(data_str)
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

        assert response_data["object"] == "chat.completion", f"Expected object='chat.completion', got '{response_data['object']}'"
        assert isinstance(response_data["choices"], list), "choices must be a list"
        assert len(response_data["choices"]) > 0, "choices must not be empty"

        choice = response_data["choices"][0]
        assert "index" in choice, "Choice missing 'index'"
        assert "message" in choice, "Choice missing 'message'"
        assert "finish_reason" in choice, "Choice missing 'finish_reason'"

        message = choice["message"]
        assert "role" in message, "Message missing 'role'"
        assert "content" in message, "Message missing 'content'"
        assert message["role"] == "assistant", f"Expected role='assistant', got '{message['role']}'"

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

        assert response_data["type"] == "message", f"Expected type='message', got '{response_data['type']}'"
        assert response_data["role"] == "assistant", f"Expected role='assistant', got '{response_data['role']}'"
        assert isinstance(response_data["content"], list), "content must be a list"
        assert len(response_data["content"]) > 0, "content must not be empty"

        # Validate usage
        usage = response_data["usage"]
        assert "input_tokens" in usage, "Usage missing 'input_tokens'"
        assert "output_tokens" in usage, "Usage missing 'output_tokens'"

    @staticmethod
    def validate_common_attributes(response_data: Dict[str, Any]) -> None:
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

        assert chunk_data["object"] == "chat.completion.chunk", f"Expected object='chat.completion.chunk', got '{chunk_data['object']}'"
        assert isinstance(chunk_data["choices"], list), "choices must be a list"

        if len(chunk_data["choices"]) > 0:
            choice = chunk_data["choices"][0]
            assert "index" in choice, "Choice missing 'index'"
            assert "delta" in choice, "Choice missing 'delta'"

    @staticmethod
    def extract_streaming_content(chunks: List[Dict[str, Any]]) -> str:
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
    def get_final_chunk_with_usage(chunks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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