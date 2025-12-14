"""Unit tests for models.claude_provider module.

Tests the ClaudeProvider class implementation.
"""

import pytest
from models.claude_provider import ClaudeProvider


class TestClaudeProvider:
    """Test cases for ClaudeProvider class."""
    
    @pytest.fixture
    def provider(self):
        """Create a ClaudeProvider instance."""
        return ClaudeProvider()
    
    # Provider Name Tests
    def test_get_provider_name(self, provider):
        """Test provider name is 'claude'."""
        assert provider.get_provider_name() == "claude"
    
    # Model Support Tests
    def test_supports_claude_35(self, provider):
        """Test support for Claude 3.5 models."""
        assert provider.supports_model("claude-3.5-sonnet") is True
        assert provider.supports_model("anthropic--claude-3.5-sonnet") is True
    
    def test_supports_claude_37(self, provider):
        """Test support for Claude 3.7 models."""
        assert provider.supports_model("claude-3.7-sonnet") is True
        assert provider.supports_model("anthropic--claude-3.7-sonnet") is True
    
    def test_supports_claude_4(self, provider):
        """Test support for Claude 4 models."""
        assert provider.supports_model("claude-4-sonnet") is True
        assert provider.supports_model("claude-4-opus") is True
        assert provider.supports_model("anthropic--claude-4-opus") is True
    
    def test_supports_claude_45(self, provider):
        """Test support for Claude 4.5 models."""
        assert provider.supports_model("claude-4.5-sonnet") is True
        assert provider.supports_model("anthropic--claude-4.5-sonnet") is True
    
    def test_supports_partial_names(self, provider):
        """Test support for partial Claude names."""
        assert provider.supports_model("clau") is True
        assert provider.supports_model("sonnet") is True
        assert provider.supports_model("sonne") is True
    
    def test_does_not_support_non_claude(self, provider):
        """Test does not support non-Claude models."""
        assert provider.supports_model("gpt-4o") is False
        assert provider.supports_model("gemini-2.5-pro") is False
        assert provider.supports_model("random-model") is False
    
    # Endpoint URL Tests - Claude 3.5
    def test_endpoint_url_claude_35_non_streaming(self, provider):
        """Test endpoint URL for Claude 3.5 non-streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-3.5-sonnet",
            stream=False
        )
        assert url == "https://api.example.com/invoke"
    
    def test_endpoint_url_claude_35_streaming(self, provider):
        """Test endpoint URL for Claude 3.5 streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-3.5-sonnet",
            stream=True
        )
        assert url == "https://api.example.com/invoke-with-response-stream"
    
    # Endpoint URL Tests - Claude 3.7
    def test_endpoint_url_claude_37_non_streaming(self, provider):
        """Test endpoint URL for Claude 3.7 non-streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-3.7-sonnet",
            stream=False
        )
        assert url == "https://api.example.com/converse"
    
    def test_endpoint_url_claude_37_streaming(self, provider):
        """Test endpoint URL for Claude 3.7 streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-3.7-sonnet",
            stream=True
        )
        assert url == "https://api.example.com/converse-stream"
    
    # Endpoint URL Tests - Claude 4
    def test_endpoint_url_claude_4_non_streaming(self, provider):
        """Test endpoint URL for Claude 4 non-streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-4-opus",
            stream=False
        )
        assert url == "https://api.example.com/converse"
    
    def test_endpoint_url_claude_4_streaming(self, provider):
        """Test endpoint URL for Claude 4 streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-4-sonnet",
            stream=True
        )
        assert url == "https://api.example.com/converse-stream"
    
    # Endpoint URL Tests - Claude 4.5
    def test_endpoint_url_claude_45_non_streaming(self, provider):
        """Test endpoint URL for Claude 4.5 non-streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-4.5-sonnet",
            stream=False
        )
        assert url == "https://api.example.com/converse"
    
    def test_endpoint_url_claude_45_streaming(self, provider):
        """Test endpoint URL for Claude 4.5 streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "claude-4.5-sonnet",
            stream=True
        )
        assert url == "https://api.example.com/converse-stream"
    
    # URL Handling Tests
    def test_endpoint_url_strips_trailing_slash(self, provider):
        """Test endpoint URL strips trailing slash from base URL."""
        url = provider.get_endpoint_url(
            "https://api.example.com/",
            "claude-4.5-sonnet",
            stream=False
        )
        assert url == "https://api.example.com/converse"
    
    def test_endpoint_url_with_anthropic_prefix(self, provider):
        """Test endpoint URL with anthropic-- prefix."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "anthropic--claude-4.5-sonnet",
            stream=False
        )
        assert url == "https://api.example.com/converse"
    
    # Request Preparation Tests
    def test_prepare_request_unchanged(self, provider):
        """Test prepare_request returns payload unchanged."""
        payload = {
            "model": "claude-4.5-sonnet",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        result = provider.prepare_request(payload)
        assert result == payload
        assert result is payload  # Should be same object
    
    # Streaming Support Tests
    def test_supports_streaming(self, provider):
        """Test Claude supports streaming."""
        assert provider.supports_streaming() is True
    
    def test_get_streaming_endpoint(self, provider):
        """Test get_streaming_endpoint returns correct URL."""
        url = provider.get_streaming_endpoint(
            "https://api.example.com",
            "claude-4.5-sonnet"
        )
        assert url == "https://api.example.com/converse-stream"
    
    # Model Name Normalization Tests
    def test_normalize_model_name_with_prefix(self, provider):
        """Test normalize_model_name removes anthropic-- prefix."""
        assert provider.normalize_model_name("anthropic--claude-4.5-sonnet") == "claude-4.5-sonnet"
        assert provider.normalize_model_name("anthropic--claude-4-opus") == "claude-4-opus"
    
    def test_normalize_model_name_without_prefix(self, provider):
        """Test normalize_model_name returns unchanged if no prefix."""
        assert provider.normalize_model_name("claude-4.5-sonnet") == "claude-4.5-sonnet"
        assert provider.normalize_model_name("claude-3.5-sonnet") == "claude-3.5-sonnet"
    
    # Version Detection Tests
    def test_get_model_version_35(self, provider):
        """Test get_model_version for Claude 3.5."""
        assert provider.get_model_version("claude-3.5-sonnet") == "3.5"
    
    def test_get_model_version_37(self, provider):
        """Test get_model_version for Claude 3.7."""
        assert provider.get_model_version("claude-3.7-sonnet") == "3.7"
    
    def test_get_model_version_4(self, provider):
        """Test get_model_version for Claude 4."""
        assert provider.get_model_version("claude-4-opus") == "4"
    
    def test_get_model_version_45(self, provider):
        """Test get_model_version for Claude 4.5."""
        assert provider.get_model_version("claude-4.5-sonnet") == "4.5"
    
    def test_get_model_version_unknown(self, provider):
        """Test get_model_version returns 'unknown' for models without version."""
        assert provider.get_model_version("claude-sonnet") == "unknown"
        assert provider.get_model_version("sonnet") == "unknown"


class TestClaudeProviderEdgeCases:
    """Test edge cases for ClaudeProvider."""
    
    @pytest.fixture
    def provider(self):
        """Create a ClaudeProvider instance."""
        return ClaudeProvider()
    
    def test_empty_base_url(self, provider):
        """Test endpoint URL with empty base URL."""
        url = provider.get_endpoint_url("", "claude-4.5-sonnet", stream=False)
        assert url == "/converse"
    
    def test_base_url_with_path(self, provider):
        """Test endpoint URL with base URL containing path."""
        url = provider.get_endpoint_url(
            "https://api.example.com/v1/models",
            "claude-4.5-sonnet",
            stream=False
        )
        assert url == "https://api.example.com/v1/models/converse"
    
    def test_prepare_request_empty_payload(self, provider):
        """Test prepare_request with empty payload."""
        result = provider.prepare_request({})
        assert result == {}
    
    def test_prepare_request_with_extra_fields(self, provider):
        """Test prepare_request preserves extra fields."""
        payload = {
            "model": "claude-4.5-sonnet",
            "messages": [],
            "custom_field": "value",
            "another_field": 123
        }
        result = provider.prepare_request(payload)
        assert result == payload
        assert "custom_field" in result
        assert "another_field" in result