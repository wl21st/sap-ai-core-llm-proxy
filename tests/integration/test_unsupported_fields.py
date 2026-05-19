"""
Integration tests for /v1/messages endpoint with unsupported Anthropic fields.

Tests the Claude Messages API endpoint against a running proxy server to verify
that unsupported fields (metadata, output_config, context_management) are stripped
before reaching Bedrock.

These tests hit the PROXY SERVER, not Bedrock directly.
For direct Bedrock API tests, see tests/api/
"""

import pytest
from .test_validators import ResponseValidator


@pytest.mark.integration
@pytest.mark.real
@pytest.mark.claude
class TestUnsupportedFieldsStripping:
    """
    Verify that unsupported Anthropic-specific fields are stripped by proxy
    before forwarding to Bedrock, and that requests still succeed.
    """

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic--claude-4.5-sonnet",
            "sonnet-4.5",
        ],
    )
    async def test_metadata_field_stripped(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Test that 'metadata' field is stripped before reaching Bedrock.

        Anthropic supports metadata field, but Bedrock does not.
        The proxy should strip it and still return a successful response.

        If metadata was NOT stripped, Bedrock would reject the request with a 400 error.
        Success proves the field was removed before reaching Bedrock.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": max_tokens,
                "stream": False,
                "metadata": {
                    "user_id": "test-user-123",
                    "session_id": "session-456",
                },
            },
        )

        # Request should succeed despite metadata field
        # If Bedrock received metadata, it would return 400 Bad Request
        assert response.status_code == 200, (
            f"Request with metadata field failed: {response.status_code} {response.text}"
        )

        data = response.json()
        validator = ResponseValidator()
        validator.validate_claude_format(data)

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic--claude-4.5-sonnet",
            "sonnet-4.5",
        ],
    )
    async def test_output_config_field_stripped(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Test that 'output_config' field is stripped before reaching Bedrock.

        Anthropic supports output_config field, but Bedrock does not.
        The proxy should strip it and still return a successful response.

        If output_config was NOT stripped, Bedrock would reject the request with a 400 error.
        Success proves the field was removed before reaching Bedrock.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Tell me a joke"}],
                "max_tokens": max_tokens,
                "stream": False,
                "output_config": {
                    "type": "text",
                },
            },
        )

        # Request should succeed despite output_config field
        # If Bedrock received output_config, it would return 400 Bad Request
        assert response.status_code == 200, (
            f"Request with output_config field failed: {response.status_code} {response.text}"
        )

        data = response.json()
        validator = ResponseValidator()
        validator.validate_claude_format(data)

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic--claude-4.5-sonnet",
            "sonnet-4.5",
        ],
    )
    async def test_context_management_field_stripped(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Test that 'context_management' field is stripped before reaching Bedrock.

        Anthropic supports context_management field, but Bedrock does not.
        The proxy should strip it and still return a successful response.

        If context_management was NOT stripped, Bedrock would reject the request with a 400 error.
        Success proves the field was removed before reaching Bedrock.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "What is 2+2?"}],
                "max_tokens": max_tokens,
                "stream": False,
                "context_management": {
                    "type": "auto",
                },
            },
        )

        # Request should succeed despite context_management field
        # If Bedrock received context_management, it would return 400 Bad Request
        assert response.status_code == 200, (
            f"Request with context_management field failed: {response.status_code} {response.text}"
        )

        data = response.json()
        validator = ResponseValidator()
        validator.validate_claude_format(data)

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic--claude-4.5-sonnet",
            "sonnet-4.5",
        ],
    )
    async def test_all_unsupported_fields_stripped(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Test that all unsupported fields are stripped when sent together.

        Verifies the proxy can handle requests with multiple unsupported fields
        and strips them all before sending to Bedrock.

        If any of these fields were NOT stripped, Bedrock would reject with 400 error.
        Success proves all fields were removed before reaching Bedrock.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": max_tokens,
                "stream": False,
                "metadata": {"user_id": "user-123"},
                "output_config": {"type": "text"},
                "context_management": {"type": "auto"},
            },
        )

        # Request should succeed despite all unsupported fields
        # If Bedrock received any of these, it would return 400 Bad Request
        assert response.status_code == 200, (
            f"Request with multiple unsupported fields failed: {response.status_code} {response.text}"
        )

        data = response.json()
        validator = ResponseValidator()
        validator.validate_claude_format(data)

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic--claude-4.5-sonnet",
            "sonnet-4.5",
        ],
    )
    async def test_context_management_in_thinking_stripped(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Test that 'context_management' within thinking config is stripped.

        When thinking is enabled, nested context_management should be removed
        before reaching Bedrock.

        If context_management in thinking was NOT stripped, Bedrock would reject with 400 error.
        Success proves the field was removed before reaching Bedrock.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Solve this problem"}],
                "max_tokens": max_tokens,
                "stream": False,
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 5000,
                    "context_management": {
                        "type": "auto",
                    },
                },
            },
        )

        # Request should succeed
        # If Bedrock received context_management in thinking, it would return 400 Bad Request
        assert response.status_code == 200, (
            f"Request with thinking context_management failed: {response.status_code} {response.text}"
        )

        data = response.json()
        validator = ResponseValidator()
        validator.validate_claude_format(data)

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic--claude-4.5-sonnet",
            "sonnet-4.5",
        ],
    )
    async def test_unsupported_fields_with_streaming(
        self, proxy_client, proxy_url, model, max_tokens
    ):
        """
        Test that unsupported fields are stripped during streaming requests.

        Verifies that even in streaming mode, unsupported fields are removed
        before reaching Bedrock.

        If any unsupported fields were NOT stripped, Bedrock would reject with 400 error.
        Success proves all fields were removed before reaching Bedrock.
        """
        response = await proxy_client.post(
            f"{proxy_url}/v1/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Write a poem"}],
                "max_tokens": max_tokens,
                "stream": True,
                "metadata": {"request_id": "req-789"},
                "output_config": {"type": "text"},
                "context_management": {"type": "auto"},
            },
        )

        # Streaming request should succeed
        # If Bedrock received any of these fields, it would return 400 Bad Request
        assert response.status_code == 200, (
            f"Streaming request with unsupported fields failed: {response.status_code} {response.text}"
        )

        # Consume stream to verify it works
        chunks = []
        async for line in response.aiter_lines():
            if line:
                chunks.append(line)

        assert len(chunks) > 0, "No streaming chunks received"
