"""Unit tests for Gemini and OpenAI provider implementations.

Tests the GeminiProvider and OpenAIProvider classes.
"""

import pytest
from models.gemini_provider import GeminiProvider
from models.openai_provider import OpenAIProvider


class TestGeminiProvider:
    """Test cases for GeminiProvider class."""
    
    @pytest.fixture
    def provider(self):
        """Create a GeminiProvider instance."""
        return GeminiProvider()
    
    # Provider Name Tests
    def test_get_provider_name(self, provider):
        """Test provider name is 'gemini'."""
        assert provider.get_provider_name() == "gemini"
    
    # Model Support Tests
    def test_supports_gemini_25(self, provider):
        """Test support for Gemini 2.5 models."""
        assert provider.supports_model("gemini-2.5-pro") is True
        assert provider.supports_model("gemini-2.5-flash") is True
    
    def test_supports_gemini_15(self, provider):
        """Test support for Gemini 1.5 models."""
        assert provider.supports_model("gemini-1.5-pro") is True
        assert provider.supports_model("gemini-1.5-flash") is True
    
    def test_supports_gemini_short_names(self, provider):
        """Test support for short Gemini names."""
        assert provider.supports_model("gemini-pro") is True
        assert provider.supports_model("gemini-flash") is True
        assert provider.supports_model("gemini") is True
    
    def test_does_not_support_non_gemini(self, provider):
        """Test does not support non-Gemini models."""
        assert provider.supports_model("claude-4.5-sonnet") is False
        assert provider.supports_model("gpt-4o") is False
    
    # Endpoint URL Tests
    def test_endpoint_url_non_streaming(self, provider):
        """Test endpoint URL for non-streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "gemini-2.5-pro",
            stream=False
        )
        assert url == "https://api.example.com/models/gemini-2.5-pro:generateContent"
    
    def test_endpoint_url_streaming(self, provider):
        """Test endpoint URL for streaming."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "gemini-2.5-pro",
            stream=True
        )
        assert url == "https://api.example.com/models/gemini-2.5-pro:streamGenerateContent"
    
    def test_endpoint_url_with_version_suffix(self, provider):
        """Test endpoint URL strips version suffix after colon."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "gemini-2.5-pro:latest",
            stream=False
        )
        assert url == "https://api.example.com/models/gemini-2.5-pro:generateContent"
    
    def test_endpoint_url_strips_trailing_slash(self, provider):
        """Test endpoint URL strips trailing slash."""
        url = provider.get_endpoint_url(
            "https://api.example.com/",
            "gemini-2.5-pro",
            stream=False
        )
        assert url == "https://api.example.com/models/gemini-2.5-pro:generateContent"
    
    # Request Preparation Tests
    def test_prepare_request_unchanged(self, provider):
        """Test prepare_request returns payload unchanged."""
        payload = {
            "model": "gemini-2.5-pro",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7
        }
        result = provider.prepare_request(payload)
        assert result == payload
    
    # Streaming Support Tests
    def test_supports_streaming(self, provider):
        """Test Gemini supports streaming."""
        assert provider.supports_streaming() is True
    
    def test_get_streaming_endpoint(self, provider):
        """Test get_streaming_endpoint returns correct URL."""
        url = provider.get_streaming_endpoint(
            "https://api.example.com",
            "gemini-2.5-pro"
        )
        assert url == "https://api.example.com/models/gemini-2.5-pro:streamGenerateContent"
    
    # Helper Method Tests
    def test_get_model_variant_pro(self, provider):
        """Test get_model_variant for pro models."""
        assert provider.get_model_variant("gemini-2.5-pro") == "pro"
        assert provider.get_model_variant("gemini-pro") == "pro"
    
    def test_get_model_variant_flash(self, provider):
        """Test get_model_variant for flash models."""
        assert provider.get_model_variant("gemini-2.5-flash") == "flash"
        assert provider.get_model_variant("gemini-flash") == "flash"
    
    def test_get_model_variant_unknown(self, provider):
        """Test get_model_variant for unknown variants."""
        assert provider.get_model_variant("gemini") == "unknown"
    
    def test_get_model_version(self, provider):
        """Test get_model_version extraction."""
        assert provider.get_model_version("gemini-2.5-pro") == "2.5"
        assert provider.get_model_version("gemini-1.5-flash") == "1.5"
        assert provider.get_model_version("gemini-pro") == "unknown"


class TestOpenAIProvider:
    """Test cases for OpenAIProvider class."""
    
    @pytest.fixture
    def provider(self):
        """Create an OpenAIProvider instance."""
        return OpenAIProvider()
    
    # Provider Name Tests
    def test_get_provider_name(self, provider):
        """Test provider name is 'openai'."""
        assert provider.get_provider_name() == "openai"
    
    # Model Support Tests
    def test_supports_all_models(self, provider):
        """Test OpenAI provider supports all models (fallback)."""
        assert provider.supports_model("gpt-4o") is True
        assert provider.supports_model("gpt-5") is True
        assert provider.supports_model("o3-mini") is True
        assert provider.supports_model("random-model") is True
    
    # Endpoint URL Tests
    def test_endpoint_url_standard_model(self, provider):
        """Test endpoint URL for standard models."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "gpt-4o",
            stream=False
        )
        assert url == "https://api.example.com/chat/completions?api-version=2023-05-15"
    
    def test_endpoint_url_o3_model(self, provider):
        """Test endpoint URL for o3 models uses newer API version."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "o3-mini",
            stream=False
        )
        assert url == "https://api.example.com/chat/completions?api-version=2024-12-01-preview"
    
    def test_endpoint_url_o4_mini_model(self, provider):
        """Test endpoint URL for o4-mini uses newer API version."""
        url = provider.get_endpoint_url(
            "https://api.example.com",
            "o4-mini",
            stream=False
        )
        assert url == "https://api.example.com/chat/completions?api-version=2024-12-01-preview"
    
    def test_endpoint_url_streaming_same_as_non_streaming(self, provider):
        """Test streaming endpoint is same as non-streaming."""
        url_stream = provider.get_endpoint_url(
            "https://api.example.com",
            "gpt-4o",
            stream=True
        )
        url_non_stream = provider.get_endpoint_url(
            "https://api.example.com",
            "gpt-4o",
            stream=False
        )
        assert url_stream == url_non_stream
    
    # Request Preparation Tests
    def test_prepare_request_standard_model(self, provider):
        """Test prepare_request for standard models unchanged."""
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        result = provider.prepare_request(payload)
        assert result == payload
        assert "temperature" in result
    
    def test_prepare_request_o3_mini_removes_temperature(self, provider):
        """Test prepare_request removes temperature for o3-mini."""
        payload = {
            "model": "o3-mini",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        result = provider.prepare_request(payload)
        assert "temperature" not in result
        assert "max_tokens" in result
        assert result != payload  # Should be a copy
    
    def test_prepare_request_o3_mini_without_temperature(self, provider):
        """Test prepare_request for o3-mini without temperature."""
        payload = {
            "model": "o3-mini",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000
        }
        result = provider.prepare_request(payload)
        assert result == payload
    
    # Streaming Support Tests
    def test_supports_streaming(self, provider):
        """Test OpenAI supports streaming."""
        assert provider.supports_streaming() is True
    
    def test_get_streaming_endpoint(self, provider):
        """Test get_streaming_endpoint returns same as regular endpoint."""
        url = provider.get_streaming_endpoint(
            "https://api.example.com",
            "gpt-4o"
        )
        assert url == "https://api.example.com/chat/completions?api-version=2023-05-15"
    
    # Helper Method Tests
    def test_is_reasoning_model_o3(self, provider):
        """Test is_reasoning_model for o3 models."""
        assert provider.is_reasoning_model("o3") is True
        assert provider.is_reasoning_model("o3-mini") is True
    
    def test_is_reasoning_model_o4_mini(self, provider):
        """Test is_reasoning_model for o4-mini."""
        assert provider.is_reasoning_model("o4-mini") is True
    
    def test_is_reasoning_model_standard(self, provider):
        """Test is_reasoning_model for standard models."""
        assert provider.is_reasoning_model("gpt-4o") is False
        assert provider.is_reasoning_model("gpt-5") is False


class TestProviderEdgeCases:
    """Test edge cases for all providers."""
    
    def test_gemini_empty_base_url(self):
        """Test Gemini with empty base URL."""
        provider = GeminiProvider()
        url = provider.get_endpoint_url("", "gemini-2.5-pro", stream=False)
        assert url == "/models/gemini-2.5-pro:generateContent"
    
    def test_openai_empty_base_url(self):
        """Test OpenAI with empty base URL."""
        provider = OpenAIProvider()
        url = provider.get_endpoint_url("", "gpt-4o", stream=False)
        assert url == "/chat/completions?api-version=2023-05-15"
    
    def test_gemini_prepare_request_empty(self):
        """Test Gemini prepare_request with empty payload."""
        provider = GeminiProvider()
        result = provider.prepare_request({})
        assert result == {}
    
    def test_openai_prepare_request_empty(self):
        """Test OpenAI prepare_request with empty payload."""
        provider = OpenAIProvider()
        result = provider.prepare_request({})
        assert result == {}