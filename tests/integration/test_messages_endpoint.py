"""
Integration tests for /v1/messages endpoint (Claude Messages API).

Tests the Claude-specific Messages API endpoint against a running proxy server.
"""

import pytest

from .test_validators import ResponseValidator


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.claude
@pytest.mark.parametrize(
    "model",
    [
        "anthropic--claude-4.5-sonnet",
        "sonnet-4.5",
    ],
)
class TestMessagesEndpoint:
    """Tests for Claude /v1/messages endpoint."""

    def test_messages_non_streaming(self, proxy_client, proxy_url, model, max_tokens):
        """Test Claude Messages API non-streaming."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello Claude"}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        # Validate Claude format
        validator = ResponseValidator()
        validator.validate_claude_format(data)

        # Check content
        assert len(data["content"]) > 0, "Content is empty"
        assert data["content"][0]["type"] == "text", (
            "First content block should be text"
        )
        assert len(data["content"][0]["text"]) > 0, "Text content is empty"

    def test_messages_streaming(self, proxy_client, proxy_url, model, max_tokens):
        """Test Claude Messages API streaming."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": max_tokens,
                "stream": True,
            },
            stream=True,
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        chunks = []
        for line in response.iter_lines():
            if line:
                chunks.append(line)

        assert len(chunks) > 0, f"No streaming chunks received for model {model}"

    def test_messages_response_format(self, proxy_client, proxy_url, model, max_tokens):
        """Validate Anthropic response format."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        validator = ResponseValidator()
        validator.validate_claude_format(data)

        # Check specific Claude fields
        assert data["type"] == "message", (
            f"Expected type='message', got '{data['type']}'"
        )
        assert data["role"] == "assistant", (
            f"Expected role='assistant', got '{data['role']}'"
        )
        assert "stop_reason" in data, "Missing stop_reason"
        assert "usage" in data, "Missing usage"

    def test_messages_token_usage(self, proxy_client, proxy_url, model, max_tokens):
        """Validate token usage in Claude format."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Count to 5"}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Claude uses input_tokens and output_tokens
        assert "usage" in data, "Missing usage field"
        usage = data["usage"]
        assert "input_tokens" in usage, "Missing input_tokens"
        assert "output_tokens" in usage, "Missing output_tokens"

        assert usage["input_tokens"] > 0, "input_tokens should be > 0"
        assert usage["output_tokens"] > 0, "output_tokens should be > 0"

    def test_messages_streaming_sse_format(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """Validate SSE format for Claude streaming."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": max_tokens,
                "stream": True,
            },
            stream=True,
        )

        ResponseValidator.validate_sse_response(model, response)

    def test_messages_with_system_prompt(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """Test Messages API with system prompt."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "system": "You are a helpful assistant.",
                "messages": [{"role": "user", "content": "Who are you?"}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        validator = ResponseValidator()
        validator.validate_claude_format(data)

    def test_messages_multiple_turns(self, proxy_client, proxy_url, model, max_tokens):
        """Test Messages API with multiple conversation turns."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "What is 2+2?"},
                    {"role": "assistant", "content": "4"},
                    {"role": "user", "content": "What is 3+3?"},
                ],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        validator = ResponseValidator()
        validator.validate_claude_format(data)

    @pytest.mark.smoke
    def test_messages_smoke(self, proxy_client, proxy_url, model, max_tokens):
        """Quick smoke test for Messages endpoint."""
        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": max_tokens,
                "stream": False,
            },
        )

        assert response.status_code == 200, (
            f"Messages smoke test failed for {model}: {response.text}"
        )
        data = response.json()
        assert "content" in data
        assert len(data["content"]) > 0
        assert data["content"][0]["text"]


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.openai
class TestMessagesEndpointFallback:
    """Test Messages endpoint with non-Claude models (should fallback or error)."""

    @pytest.mark.parametrize("model", ["gpt-4.1", "gpt-5", "gemini-2.5-pro"])
    def test_non_claude_model_handling(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """Test how Messages endpoint handles non-Claude models."""
        if model == "gpt-5":
            json_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_completion_tokens": 1024,
                "reasoning_effort": "low",
                "stream": False,
            }
        else:
            json_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": max_tokens,
                "stream": False,
            }

        response = proxy_client.post(
            f"{proxy_url}/v1/messages",
            json=json_data,
        )

        # The endpoint might:
        # 1. Return 400 (model not supported for this endpoint)
        # 2. Return 200 with converted response
        # 3. Fallback to a Claude model

        # We accept either success or appropriate error
        assert response.status_code in [200, 400, 404], (
            f"Unexpected status code {response.status_code} for non-Claude model {model}"
        )

        if response.status_code == 200:
            # If successful, validate it's a proper Claude format
            data = response.json()
            validator = ResponseValidator()
            validator.validate_claude_format(data)
