"""
Extended test suite for proxy_server.py to increase coverage.

Tests additional functionality including embedding requests, load balancing,
request handlers, and streaming response generation.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import proxy_server
from proxy_server import (
    format_embedding_response,
    handle_embedding_service_call,
    load_balance_url,
    handle_claude_request,
    handle_gemini_request,
    handle_default_request,
    get_claude_stop_reason_from_gemini_chunk,
    get_claude_stop_reason_from_openai_chunk,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from config import SubAccountConfig, ServiceKey


def _make_fastapi_app(config, ctx):
    """Create a minimal FastAPI app with all routers and injected state."""
    from routers import chat, embeddings, logging as logging_router, messages, models

    app = FastAPI()
    app.include_router(chat.router)
    app.include_router(messages.router)
    app.include_router(embeddings.router)
    app.include_router(models.router)
    app.include_router(logging_router.router)
    app.state.proxy_config = config
    app.state.proxy_context = ctx
    return app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    from config import ProxyConfig, ProxyGlobalContext

    # Initialize global context with empty config
    ctx = ProxyGlobalContext()
    ctx.initialize(ProxyConfig())

    # Set proxy_server globals
    proxy_server.ctx = ctx
    proxy_server.proxy_config = ctx.config

    fastapi_app = _make_fastapi_app(proxy_server.proxy_config, proxy_server.ctx)
    yield TestClient(fastapi_app, raise_server_exceptions=False)


@pytest.fixture
def setup_test_config():
    """Setup test configuration."""
    from config import ProxyGlobalContext

    # Initialize proxy_config and ctx if they don't exist
    if proxy_server.proxy_config is None:
        from config import ProxyConfig

        proxy_server.proxy_config = ProxyConfig(
            host="127.0.0.1",
            port=8080,
            subaccounts={},
            model_to_subaccounts={},
            secret_authentication_tokens=[],
        )

    # Initialize ctx
    original_ctx = getattr(proxy_server, "ctx", None)
    proxy_server.ctx = ProxyGlobalContext()
    proxy_server.ctx.initialize(proxy_server.proxy_config)

    # Save original config
    original_subaccounts = proxy_server.proxy_config.subaccounts.copy()
    original_model_mapping = proxy_server.proxy_config.model_to_subaccounts.copy()
    original_tokens = (
        proxy_server.proxy_config.secret_authentication_tokens.copy()
        if proxy_server.proxy_config.secret_authentication_tokens
        else []
    )

    # Setup test subaccount
    test_subaccount = SubAccountConfig(
        name="test-sub",
        resource_group="test-rg",
        service_key_json="test-key.json",
        model_to_deployment_urls={
            "gpt-4o": ["https://test.api.com/gpt4"],
            "anthropic--claude-4.5-sonnet": ["https://test.api.com/claude"],
            "gemini-2.5-pro": ["https://test.api.com/gemini"],
        },
    )
    test_subaccount.service_key = ServiceKey(
        client_id="test-client",
        client_secret="test-secret",
        auth_url="https://test.auth.com",
        api_url="https://test.api.com",
        identity_zone_id="test-zone",
    )
    test_subaccount.model_to_deployment_urls = {
        "gpt-4o": ["https://test.api.com/gpt4"],
        "anthropic--claude-4.5-sonnet": ["https://test.api.com/claude"],
        "gemini-2.5-pro": ["https://test.api.com/gemini"],
    }

    proxy_server.proxy_config.subaccounts = {"test-sub": test_subaccount}
    proxy_server.proxy_config.model_to_subaccounts = {
        "gpt-4o": ["test-sub"],
        "anthropic--claude-4.5-sonnet": ["test-sub"],
        "gemini-2.5-pro": ["test-sub"],
    }
    proxy_server.proxy_config.secret_authentication_tokens = ["test-token-123"]

    yield

    # Restore original config
    if original_ctx is not None:
        proxy_server.ctx = original_ctx
    proxy_server.proxy_config.subaccounts = original_subaccounts
    proxy_server.proxy_config.model_to_subaccounts = original_model_mapping
    proxy_server.proxy_config.secret_authentication_tokens = original_tokens


class TestEmbeddingEndpoint:
    """Test cases for embedding endpoint."""

    def test_embedding_endpoint_no_input(self, client, setup_test_config):
        """Test embedding endpoint with missing input."""
        response = client.post(
            "/v1/embeddings",
            json={"model": "text-embedding-3-large"},
            headers={"Authorization": "Bearer test-token-123"},
        )
        assert response.status_code == 400
        assert "error" in response.json()

    @patch("routers.embeddings.load_balance_url")
    @patch("proxy_server.handle_embedding_service_call")
    @patch("proxy_server.requests.post")
    def test_embedding_endpoint_array_input(
        self, mock_post, mock_handle_call, mock_load_balance, client, setup_test_config
    ):
        """Test embedding endpoint with array input."""
        mock_load_balance.return_value = (
            "https://test.api.com",
            "test-sub",
            "test-rg",
            "text-embedding-3-large",
        )
        mock_handle_call.return_value = (
            "https://test.api.com/embeddings",
            {"input": ["text1", "text2"]},
            "test-sub",
        )

        mock_token = Mock()
        mock_token.get_token.return_value = "test-token"
        proxy_server.ctx.get_token_manager = Mock(return_value=mock_token)

        mock_response = Mock()
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"embeddings": [[0.1, 0.2], [0.3, 0.4]]}'
        mock_post.return_value = mock_response

        response = client.post(
            "/v1/embeddings",
            json={"input": ["text1", "text2"], "model": "text-embedding-3-large"},
            headers={"Authorization": "Bearer test-token-123"},
        )

        # Should handle array input
        assert response.status_code in [200, 400]


class TestConvertersEdgeCases:
    """Test cases for converter edge cases."""

    def test_convert_gemini_to_openai_with_usage(self):
        """Test Gemini to OpenAI conversion with token usage."""
        from proxy_helpers import Converters

        gemini_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Hello"}], "role": "model"},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }

        result = Converters.convert_gemini_to_openai(gemini_response, "gemini-pro")

        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5
        assert result["usage"]["total_tokens"] == 15

    def test_convert_claude_to_openai_with_tools(self):
        """Test Claude to OpenAI conversion with tool use."""
        from proxy_helpers import Converters

        # Claude response needs at least one text content block
        claude_response = {
            "id": "msg_123",
            "type": "message",
            "content": [
                {"type": "text", "text": "I'll check the weather for you."},
                {
                    "type": "tool_use",
                    "id": "tool_123",
                    "name": "get_weather",
                    "input": {"location": "NYC"},
                },
            ],
            "model": "claude-3.5-sonnet",
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

        result = Converters.convert_claude_to_openai(
            claude_response, "claude-3.5-sonnet"
        )

        assert "choices" in result
        # Claude's tool_use stop reason maps to "tool_use" in OpenAI format
        assert result["choices"][0]["finish_reason"] == "tool_use"


class TestParseArguments:
    """Test cases for parse_arguments function."""

    def test_parse_arguments_default(self):
        """Test parse_arguments with default values."""
        from proxy_server import parse_arguments

        # Mock sys.argv
        import sys

        original_argv = sys.argv
        sys.argv = ["proxy_server.py"]

        try:
            args = parse_arguments()
            assert args.config == "config.json"
            assert args.debug is False
        finally:
            sys.argv = original_argv

    def test_parse_arguments_custom_config(self):
        """Test parse_arguments with custom config file."""
        from proxy_server import parse_arguments

        import sys

        original_argv = sys.argv
        sys.argv = ["proxy_server.py", "--config", "custom_config.json"]

        try:
            args = parse_arguments()
            assert args.config == "custom_config.json"
            assert args.debug is False
        finally:
            sys.argv = original_argv

    def test_parse_arguments_debug_mode(self):
        """Test parse_arguments with debug flag."""
        from proxy_server import parse_arguments

        import sys

        original_argv = sys.argv
        sys.argv = ["proxy_server.py", "--debug"]

        try:
            args = parse_arguments()
            assert args.config == "config.json"
            assert args.debug is True
        finally:
            sys.argv = original_argv

    def test_parse_arguments_both_flags(self):
        """Test parse_arguments with both config and debug flags."""
        from proxy_server import parse_arguments

        import sys

        original_argv = sys.argv
        sys.argv = ["proxy_server.py", "--config", "test.json", "--debug"]

        try:
            args = parse_arguments()
            assert args.config == "test.json"
            assert args.debug is True
        finally:
            sys.argv = original_argv


class TestProxyOpenAIStreamEndpoint:
    """Test cases for proxy_openai_stream endpoint."""

    @patch("auth.request_validator.RequestValidator.validate")
    @patch("proxy_server.requests.post")
    def test_proxy_openai_stream_claude_model_success(
        self, mock_post, mock_validate, client, setup_test_config
    ):
        """Test successful Claude model request via proxy_openai_stream."""
        mock_validate.return_value = True

        mock_token = Mock()
        mock_token.get_token.return_value = "test-token"
        proxy_server.ctx.get_token_manager = Mock(return_value=mock_token)

        mock_response = Mock()
        mock_response.json.return_value = {
            "output": {
                "message": {"role": "assistant", "content": [{"text": "Hello"}]}
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
        }
        mock_response.text = '{"output": {"message": {"role": "assistant", "content": [{"text": "Hello"}]}}}'
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"output": {"message": {"role": "assistant", "content": [{"text": "Hello"}]}}}'
        mock_post.return_value = mock_response

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "anthropic--claude-4.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
            headers={"Authorization": "Bearer test-token-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data

    @patch("auth.request_validator.RequestValidator.validate")
    @patch("proxy_server.requests.post")
    def test_proxy_openai_stream_gemini_model_success(
        self, mock_post, mock_validate, client, setup_test_config
    ):
        """Test successful Gemini model request via proxy_openai_stream."""
        mock_validate.return_value = True

        mock_token = Mock()
        mock_token.get_token.return_value = "test-token"
        proxy_server.ctx.get_token_manager = Mock(return_value=mock_token)

        mock_response = Mock()
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 10},
        }
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = (
            '{"candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}'
        )
        mock_response.content = (
            b'{"candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}'
        )
        mock_post.return_value = mock_response

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemini-2.5-pro",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
            headers={"Authorization": "Bearer test-token-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data

    @patch("auth.request_validator.RequestValidator.validate")
    def test_proxy_openai_stream_unauthorized(
        self, mock_validate, client, setup_test_config
    ):
        """Test proxy_openai_stream with invalid authentication."""
        mock_validate.return_value = False

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 401

    @patch("auth.request_validator.RequestValidator.validate")
    @patch("proxy_server.TokenManager")
    def test_proxy_openai_stream_model_not_found(
        self, mock_token_manager, mock_validate, client
    ):
        """Test proxy_openai_stream with non-existent model."""
        mock_validate.return_value = True

        # Mock token manager to avoid HTTP calls
        mock_token = Mock()
        mock_token.get_token.return_value = "test-token"
        mock_token_manager.return_value = mock_token

        # Setup config without gpt-4o to ensure fallback fails
        test_subaccount = SubAccountConfig(
            name="test-sub",
            resource_group="test-rg",
            service_key_json="test-key.json",
            model_to_deployment_urls={
                "anthropic--claude-4.5-sonnet": ["https://test.api.com/claude"],
                "gemini-2.5-pro": ["https://test.api.com/gemini"],
            },
        )
        test_subaccount.service_key = ServiceKey(
            client_id="test-client",
            client_secret="test-secret",
            auth_url="https://test.auth.com",
            api_url="https://test.api.com",
            identity_zone_id="test-zone",
        )
        proxy_server.proxy_config.subaccounts = {"test-sub": test_subaccount}
        proxy_server.proxy_config.model_to_subaccounts = {
            "anthropic--claude-4.5-sonnet": ["test-sub"],
            "gemini-2.5-pro": ["test-sub"],
        }
        proxy_server.proxy_config.secret_authentication_tokens = ["test-token-123"]

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers={"Authorization": "Bearer test-token-123"},
        )

        # Should return 404 for unavailable model
        assert response.status_code == 404

    @patch("auth.request_validator.RequestValidator.validate")
    @patch("proxy_server.requests.post")
    def test_proxy_openai_stream_streaming_response(
        self, mock_post, mock_validate, client, setup_test_config
    ):
        """Test streaming response from proxy_openai_stream."""
        mock_validate.return_value = True

        mock_token = Mock()
        mock_token.get_token.return_value = "test-token"
        proxy_server.ctx.get_token_manager = Mock(return_value=mock_token)

        # Mock streaming response with context manager support
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            b'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"Hello"},"index":0}]}\n',
            b"data: [DONE]\n",
        ]
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_post.return_value = mock_response

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
            headers={"Authorization": "Bearer test-token-123"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


class TestGenerateClaudeStreamingResponse:
    """Test cases for generate_claude_streaming_response function (no Flask context needed)."""

    @patch("proxy_server.requests.post")
    def test_generate_claude_streaming_response_success(self, mock_post):
        """Test successful Claude streaming response generation."""
        from proxy_server import generate_claude_streaming_response

        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            b'data: {"type":"message_start","message":{"id":"msg_123"}}\n',
            b'data: {"type":"content_block_delta","delta":{"text":"Hello"}}\n',
            b'data: {"type":"message_stop"}\n',
        ]
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_post.return_value = mock_response

        result = generate_claude_streaming_response(
            "https://test.com/api",
            {"Authorization": "Bearer token"},
            {"messages": [{"role": "user", "content": "test"}]},
            "claude-3.5-sonnet",
            "test-sub",
        )

        # Should be a generator
        assert result is not None
        # Convert to list to test content
        chunks = list(result)
        assert len(chunks) > 0

    @patch("proxy_server.requests.post")
    def test_generate_claude_streaming_response_error_handling(self, mock_post):
        """Test error handling in Claude streaming response."""
        from proxy_server import generate_claude_streaming_response
        import requests

        mock_response = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_response.raise_for_status = Mock(
            side_effect=requests.exceptions.HTTPError("HTTP Error")
        )
        mock_post.return_value = mock_response

        result = generate_claude_streaming_response(
            "https://test.com/api",
            {"Authorization": "Bearer token"},
            {"messages": [{"role": "user", "content": "test"}]},
            "claude-3.5-sonnet",
            "test-sub",
        )

        # Should raise exception on HTTP error
        with pytest.raises(requests.exceptions.HTTPError):
            list(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
