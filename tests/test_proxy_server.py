"""
Comprehensive test suite for proxy_server.py

Tests cover:
- Dataclasses (ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig)
- Utility functions (model detection, conversion functions)
- Token management (fetch_token, verify_request_token)
- Load balancing (load_balance_url)
- Flask endpoints (chat completions, messages, models, embeddings)
- Streaming response handlers
"""

import json
import pytest
import threading
import time
import requests.exceptions
from unittest.mock import Mock, patch, MagicMock, mock_open
from dataclasses import dataclass
from flask import Flask
from io import BytesIO

import proxy_helpers

# Import the module under test
import proxy_server
from proxy_server import (
    app,
    load_balance_url,
    retry_on_rate_limit,
    invoke_bedrock_streaming,
    invoke_bedrock_non_streaming,
    read_response_body_stream,
    get_sapaicore_sdk_client,
    RETRY_MAX_ATTEMPTS,
    RETRY_MULTIPLIER,
    RETRY_MIN_WAIT,
    RETRY_MAX_WAIT,
)
from proxy_helpers import Detector, Converters

# Create convenience aliases for the test functions
is_claude_model = Detector.is_claude_model
is_claude_37_or_4 = Detector.is_claude_37_or_4
is_gemini_model = Detector.is_gemini_model
convert_openai_to_claude = Converters.convert_openai_to_claude
convert_openai_to_claude37 = Converters.convert_openai_to_claude37
convert_claude_to_openai = Converters.convert_claude_to_openai
convert_claude37_to_openai = Converters.convert_claude37_to_openai
convert_openai_to_gemini = Converters.convert_openai_to_gemini
convert_gemini_to_openai = Converters.convert_gemini_to_openai

# Import from modular structure
from config import ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig, load_config
from auth import TokenManager, fetch_token, verify_request_token
from utils import handle_http_429_error


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_service_key():
    """Sample service key data for testing."""
    return {
        "clientid": "test-client-id",
        "clientsecret": "test-client-secret",
        "url": "https://test.authentication.sap.hana.ondemand.com",
        "identityzoneid": "test-zone-id",
    }


@pytest.fixture
def sample_config():
    """Sample proxy configuration for testing."""
    return {
        "subAccounts": {
            "account1": {
                "resource_group": "default",
                "service_key_json": "account1_key.json",
                "deployment_models": {
                    "gpt-4o": [
                        "https://api.ai.prod.us-east-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d123"
                    ],
                    "anthropic--claude-4.5-sonnet": [
                        "https://api.ai.prod.us-east-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d456"
                    ],
                },
            },
            "account2": {
                "resource_group": "default",
                "service_key_json": "account2_key.json",
                "deployment_models": {
                    "gpt-4o": [
                        "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d789"
                    ],
                    "gemini-2.5-pro": [
                        "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d101"
                    ],
                },
            },
        },
        "secret_authentication_tokens": ["test-token-123", "test-token-456"],
        "port": 3001,
        "host": "127.0.0.1",
    }


@pytest.fixture
def mock_service_key_file(sample_service_key, tmp_path):
    """Create a temporary service key file."""
    key_file = tmp_path / "test_key.json"
    key_file.write_text(json.dumps(sample_service_key))
    return str(key_file)


@pytest.fixture
def flask_client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def reset_proxy_config():
    """Reset global proxy_config before each test."""
    # Store original state
    original_config = proxy_server.proxy_config

    # Reset to clean state
    proxy_server.proxy_config = ProxyConfig()

    yield

    # Restore original state
    proxy_server.proxy_config = original_config


# ============================================================================
# DATACLASS TESTS
# ============================================================================


class TestServiceKey:
    """Tests for ServiceKey dataclass."""

    def test_service_key_creation(self):
        """Test ServiceKey can be created with all fields."""
        key = ServiceKey(
            clientid="test-id",
            clientsecret="test-secret",
            url="https://test.url",
            identityzoneid="test-zone",
        )
        assert key.clientid == "test-id"
        assert key.clientsecret == "test-secret"
        assert key.url == "https://test.url"
        assert key.identityzoneid == "test-zone"


class TestTokenInfo:
    """Tests for TokenInfo dataclass."""

    def test_token_info_default_values(self):
        """Test TokenInfo has correct default values."""
        token_info = TokenInfo()
        assert token_info.token is None
        assert token_info.expiry == 0
        assert isinstance(token_info.lock, threading.Lock)

    def test_token_info_with_values(self):
        """Test TokenInfo can be created with custom values."""
        token_info = TokenInfo(token="test-token", expiry=12345.0)
        assert token_info.token == "test-token"
        assert token_info.expiry == 12345.0


class TestSubAccountConfig:
    """Tests for SubAccountConfig dataclass."""

    def test_subaccount_creation(self):
        """Test SubAccountConfig can be created."""
        config = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gpt-4": ["url1", "url2"]},
        )
        assert config.name == "test-account"
        assert config.resource_group == "default"
        assert config.service_key_json == "key.json"
        assert "gpt-4" in config.deployment_models

    def test_load_service_key(self, sample_service_key, tmp_path):
        """Test loading service key from file."""
        # Create temp key file
        key_file = tmp_path / "test_key.json"
        key_file.write_text(json.dumps(sample_service_key))

        config = SubAccountConfig(
            name="test",
            resource_group="default",
            service_key_json=str(key_file),
            deployment_models={},
        )

        config.load_service_key()

        assert config.service_key is not None
        assert config.service_key.clientid == sample_service_key["clientid"]
        assert config.service_key.clientsecret == sample_service_key["clientsecret"]

    def test_normalize_model_names(self):
        """Test model name normalization."""
        config = SubAccountConfig(
            name="test",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={
                "anthropic--claude-3.5-sonnet": ["url1"],
                "gpt-4": ["url2"],
            },
        )

        config.normalize_model_names()

        # Current implementation doesn't strip prefixes (False branch)
        assert "anthropic--claude-3.5-sonnet" in config.normalized_models
        assert "gpt-4" in config.normalized_models


class TestProxyConfig:
    """Tests for ProxyConfig dataclass."""

    def test_proxy_config_defaults(self):
        """Test ProxyConfig has correct default values."""
        config = ProxyConfig()
        assert config.subaccounts == {}
        assert config.secret_authentication_tokens == []
        assert config.port == 3001
        assert config.host == "127.0.0.1"
        assert config.model_to_subaccounts == {}

    def test_build_model_mapping(self):
        """Test building model to subaccounts mapping."""
        config = ProxyConfig()

        # Add subaccounts with models
        sub1 = SubAccountConfig(
            name="sub1",
            resource_group="default",
            service_key_json="key1.json",
            deployment_models={"gpt-4": ["url1"], "claude": ["url2"]},
        )
        sub1.normalized_models = sub1.deployment_models

        sub2 = SubAccountConfig(
            name="sub2",
            resource_group="default",
            service_key_json="key2.json",
            deployment_models={"gpt-4": ["url3"]},
        )
        sub2.normalized_models = sub2.deployment_models

        config.subaccounts = {"sub1": sub1, "sub2": sub2}
        config.build_model_mapping()

        # gpt-4 should be in both subaccounts
        assert "gpt-4" in config.model_to_subaccounts
        assert set(config.model_to_subaccounts["gpt-4"]) == {"sub1", "sub2"}

        # claude should only be in sub1
        assert "claude" in config.model_to_subaccounts
        assert config.model_to_subaccounts["claude"] == ["sub1"]


# ============================================================================
# UTILITY FUNCTION TESTS
# ============================================================================


class TestModelDetection:
    """Tests for model detection functions."""

    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("claude-3.5-sonnet", True),
            ("anthropic--claude-4-sonnet", True),
            ("claude", True),
            ("sonnet", True),
            ("CLAUDE", True),
            ("gpt-4", False),
            ("gemini-pro", False),
        ],
    )
    def test_is_claude_model(self, model_name, expected):
        """Test Claude model detection."""
        assert is_claude_model(model_name) == expected

    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("claude-3.7-sonnet", True),
            ("claude-4-opus", True),
            ("claude-4.5-sonnet", True),
            ("claude-3.5-sonnet", False),
            ("claude-2", True),  # Fixed: claude-2 doesn't contain "3.5" so returns True
        ],
    )
    def test_is_claude_37_or_4(self, model_name, expected):
        """Test Claude 3.7/4 detection."""
        assert is_claude_37_or_4(model_name) == expected

    @pytest.mark.parametrize(
        "model_name,expected",
        [
            ("gemini-pro", True),
            ("gemini-1.5-pro", True),
            ("gemini-2.5-flash", True),
            ("GEMINI-PRO", True),
            ("gpt-4", False),
            ("claude", False),
        ],
    )
    def test_is_gemini_model(self, model_name, expected):
        """Test Gemini model detection."""
        assert is_gemini_model(model_name) == expected


class TestConversionFunctions:
    """Tests for payload conversion functions."""

    def test_convert_openai_to_claude(self):
        """Test OpenAI to Claude conversion."""
        openai_payload = {
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ],
            "max_tokens": 1000,
            "temperature": 0.7,
        }

        result = convert_openai_to_claude(openai_payload)

        assert result["anthropic_version"] == "bedrock-2023-05-31"
        assert result["max_tokens"] == 1000
        assert result["temperature"] == 0.7
        assert result["system"] == "You are helpful"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_convert_openai_to_claude37(self):
        """Test OpenAI to Claude 3.7 conversion."""
        openai_payload = {
            "messages": [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User message"},
            ],
            "max_tokens": 2000,
            "temperature": 0.5,
        }

        result = convert_openai_to_claude37(openai_payload)

        assert "messages" in result
        assert "inferenceConfig" in result
        assert result["inferenceConfig"]["maxTokens"] == 2000
        assert result["inferenceConfig"]["temperature"] == 0.5
        # System message is inserted as first user message, then original user message
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"][0]["text"] == "System prompt"
        assert result["messages"][1]["role"] == "user"
        assert result["messages"][1]["content"][0]["text"] == "User message"

    def test_convert_claude_to_openai(self):
        """Test Claude to OpenAI conversion."""
        claude_response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-3.5-sonnet",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        result = convert_claude_to_openai(claude_response, "claude-3.5-sonnet")

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["message"]["content"] == "Hello!"
        assert result["choices"][0]["message"]["role"] == "assistant"
        # Claude 3.5 uses standard conversion, which maps end_turn to end_turn (not stop)
        assert result["choices"][0]["finish_reason"] == "end_turn"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 20
        assert result["usage"]["total_tokens"] == 30

    def test_convert_claude37_to_openai(self):
        """Test Claude 3.7 to OpenAI conversion."""
        claude37_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Response text"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 15, "outputTokens": 25, "totalTokens": 40},
        }

        result = convert_claude37_to_openai(claude37_response, "claude-3.7-sonnet")

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["message"]["content"] == "Response text"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 15
        assert result["usage"]["completion_tokens"] == 25
        assert result["usage"]["total_tokens"] == 40

    def test_convert_openai_to_gemini(self):
        """Test OpenAI to Gemini conversion."""
        openai_payload = {
            "messages": [{"role": "user", "content": "Hello Gemini"}],
            "max_tokens": 1500,
            "temperature": 0.8,
        }

        result = convert_openai_to_gemini(openai_payload)

        assert "contents" in result
        assert result["contents"]["role"] == "user"
        assert result["contents"]["parts"]["text"] == "Hello Gemini"
        assert result["generation_config"]["maxOutputTokens"] == 1500
        assert result["generation_config"]["temperature"] == 0.8

    def test_convert_gemini_to_openai(self):
        """Test Gemini to OpenAI conversion."""
        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Gemini response"}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 10,
                "totalTokenCount": 15,
            },
        }

        result = convert_gemini_to_openai(gemini_response, "gemini-pro")

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["message"]["content"] == "Gemini response"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 5
        assert result["usage"]["completion_tokens"] == 10
        assert result["usage"]["total_tokens"] == 15


class TestHTTP429Handler:
    """Tests for HTTP 429 error handling."""

    def test_handle_http_429_error(self, flask_client):
        """Test HTTP 429 error handler."""
        # Create mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60", "X-RateLimit-Limit": "100"}
        mock_response.text = "Rate limit exceeded"

        mock_error = Mock()
        mock_error.response = mock_response

        # Need Flask app context for jsonify
        with app.app_context():
            result = handle_http_429_error(mock_error, "test request")

            assert result.status_code == 429
            assert "Retry-After" in result.headers


# ============================================================================
# TOKEN MANAGEMENT TESTS
# ============================================================================


class TestTokenManagement:
    """Tests for token fetching and verification."""

    def test_verify_request_token_valid(self, reset_proxy_config):
        """Test token verification with valid token."""
        proxy_server.proxy_config.secret_authentication_tokens = ["valid-token"]

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer valid-token"}

        assert verify_request_token(mock_request, proxy_server.proxy_config) is True

    def test_verify_request_token_invalid(self, reset_proxy_config):
        """Test token verification with invalid token."""
        proxy_server.proxy_config.secret_authentication_tokens = ["secret-abc-123"]

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer wrong-token-xyz"}

        # The function checks if any secret_key is IN the token string
        # "wrong-token-xyz" doesn't contain "secret-abc-123"
        result = verify_request_token(mock_request, proxy_server.proxy_config)
        assert result is False

    def test_verify_request_token_no_auth_configured(self, reset_proxy_config):
        """Test token verification when no tokens configured."""
        proxy_server.proxy_config.secret_authentication_tokens = []

        mock_request = Mock()
        mock_request.headers = {}

        # Should return True when no authentication is configured
        assert verify_request_token(mock_request, proxy_server.proxy_config) is True

    def test_verify_request_token_x_api_key(self, reset_proxy_config):
        """Test token verification with x-api-key header."""
        proxy_server.proxy_config.secret_authentication_tokens = ["api-key-123"]

        mock_request = Mock()
        mock_request.headers = {"x-api-key": "api-key-123"}

        assert verify_request_token(mock_request, proxy_server.proxy_config) is True

    @patch("proxy_server.requests.post")
    def test_fetch_token_success(
        self, mock_post, reset_proxy_config, sample_service_key
    ):
        """Test successful token fetch."""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token-123",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Setup subaccount
        subaccount = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={},
        )
        subaccount.service_key = ServiceKey(**sample_service_key)
        proxy_server.proxy_config.subaccounts["test-account"] = subaccount

        token = fetch_token("test-account", proxy_server.proxy_config)

        assert token == "new-token-123"
        assert subaccount.token_info.token == "new-token-123"
        assert subaccount.token_info.expiry > time.time()

    @patch("proxy_server.requests.post")
    def test_fetch_token_cached(
        self, mock_post, reset_proxy_config, sample_service_key
    ):
        """Test token fetch returns cached token."""
        # Setup subaccount with valid cached token
        subaccount = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={},
        )
        subaccount.service_key = ServiceKey(**sample_service_key)
        subaccount.token_info.token = "cached-token"
        subaccount.token_info.expiry = time.time() + 3600  # Valid for 1 hour
        proxy_server.proxy_config.subaccounts["test-account"] = subaccount

        token = fetch_token("test-account", proxy_server.proxy_config)

        assert token == "cached-token"
        # Should not make HTTP request
        mock_post.assert_not_called()

    def test_fetch_token_invalid_subaccount(self, reset_proxy_config):
        """Test token fetch with invalid subaccount."""
        with pytest.raises(ValueError, match="SubAccount .* not found"):
            fetch_token("nonexistent-account", proxy_server.proxy_config)


# ============================================================================
# LOAD BALANCING TESTS
# ============================================================================


class TestLoadBalancing:
    """Tests for load balancing functionality."""

    def test_load_balance_url_single_subaccount(self, reset_proxy_config):
        """Test load balancing with single subaccount."""
        # Setup
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gpt-4": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}

        url, subaccount_name, resource_group, model = load_balance_url("gpt-4")

        assert url == "https://url1.com"
        assert subaccount_name == "account1"
        assert resource_group == "default"
        assert model == "gpt-4"

    def test_load_balance_url_multiple_subaccounts(self, reset_proxy_config):
        """Test load balancing across multiple subaccounts."""
        # Setup two subaccounts with same model
        sub1 = SubAccountConfig(
            name="account1",
            resource_group="rg1",
            service_key_json="key1.json",
            deployment_models={"gpt-4": ["https://url1.com"]},
        )
        sub1.normalized_models = sub1.deployment_models

        sub2 = SubAccountConfig(
            name="account2",
            resource_group="rg2",
            service_key_json="key2.json",
            deployment_models={"gpt-4": ["https://url2.com"]},
        )
        sub2.normalized_models = sub2.deployment_models

        proxy_server.proxy_config.subaccounts = {"account1": sub1, "account2": sub2}
        proxy_server.proxy_config.model_to_subaccounts = {
            "gpt-4": ["account1", "account2"]
        }

        # Reset counters
        if hasattr(load_balance_url, "counters"):
            load_balance_url.counters.clear()

        # First call should use account1
        url1, sub1_name, _, _ = load_balance_url("gpt-4")
        assert sub1_name == "account1"

        # Second call should use account2 (round-robin)
        url2, sub2_name, _, _ = load_balance_url("gpt-4")
        assert sub2_name == "account2"

        # Third call should cycle back to account1
        url3, sub3_name, _, _ = load_balance_url("gpt-4")
        assert sub3_name == "account1"

    def test_load_balance_url_model_not_found(self, reset_proxy_config):
        """Test load balancing with non-existent model."""
        proxy_server.proxy_config.model_to_subaccounts = {}

        with pytest.raises(ValueError, match="not available in any subAccount"):
            load_balance_url("nonexistent-model")

    def test_load_balance_url_claude_fallback(self, reset_proxy_config):
        """Test Claude model fallback."""
        # Setup with fallback model
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"anthropic--claude-4.5-sonnet": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "anthropic--claude-4.5-sonnet": ["account1"]
        }

        # Request non-existent Claude model, should fallback
        url, subaccount_name, _, model = load_balance_url("claude-3-opus")

        assert model == "anthropic--claude-4.5-sonnet"
        assert subaccount_name == "account1"


# ============================================================================
# FLASK ENDPOINT TESTS
# ============================================================================


class TestFlaskEndpoints:
    """Tests for Flask API endpoints."""

    def test_list_models_endpoint(self, flask_client, reset_proxy_config):
        """Test /v1/models endpoint."""
        # Setup models
        proxy_server.proxy_config.model_to_subaccounts = {
            "gpt-4": ["account1"],
            "claude-3.5-sonnet": ["account2"],
        }

        response = flask_client.get("/v1/models")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        model_ids = [m["id"] for m in data["data"]]
        assert "gpt-4" in model_ids
        assert "claude-3.5-sonnet" in model_ids

    def test_event_logging_endpoint(self, flask_client):
        """Test /api/event_logging/batch endpoint."""
        response = flask_client.post(
            "/api/event_logging/batch", json={"events": [{"type": "test"}]}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"

    @patch("auth.request_validator.RequestValidator.validate")
    @patch("proxy_server.requests.post")
    def test_embeddings_endpoint(
        self, mock_post, mock_validate, flask_client, reset_proxy_config
    ):
        """Test /v1/embeddings endpoint."""
        mock_validate.return_value = True

        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Setup subaccount
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"text-embedding-3-large": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        subaccount.service_key = ServiceKey(
            clientid="id",
            clientsecret="secret",
            url="https://auth.url",
            identityzoneid="zone",
        )
        subaccount.token_info.token = "test-token"
        subaccount.token_info.expiry = time.time() + 3600

        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "text-embedding-3-large": ["account1"]
        }

        response = flask_client.post(
            "/v1/embeddings",
            json={"input": "Test text", "model": "text-embedding-3-large"},
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200


# ============================================================================
# CONFIGURATION LOADING TESTS
# ============================================================================


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_config_new_format(self, sample_config, tmp_path):
        """Test loading new multi-subaccount config format."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(sample_config))

        # Create service key files
        for account in sample_config["subAccounts"].keys():
            key_file = tmp_path / f"{account}_key.json"
            key_file.write_text(
                json.dumps(
                    {
                        "clientid": f"{account}-id",
                        "clientsecret": f"{account}-secret",
                        "url": "https://auth.url",
                        "identityzoneid": "zone",
                    }
                )
            )

        # Update paths in config
        for account, config in sample_config["subAccounts"].items():
            config["service_key_json"] = str(tmp_path / f"{account}_key.json")

        config_file.write_text(json.dumps(sample_config))

        result = load_config(str(config_file))

        assert isinstance(result, ProxyConfig)
        assert len(result.subaccounts) == 2
        assert "account1" in result.subaccounts
        assert "account2" in result.subaccounts
        assert result.port == 3001
        assert result.host == "127.0.0.1"

    def test_load_config_legacy_format(self, tmp_path, sample_service_key):
        """Test loading legacy single-account config format."""
        legacy_config = {
            "service_key_json": "key.json",
            "deployment_models": {"gpt-4": ["https://url1.com"]},
            "secret_authentication_tokens": ["token1"],
            "resource_group": "default",
            "port": 3001,
            "host": "127.0.0.1",
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(legacy_config))

        result = load_config(str(config_file))

        # Legacy format returns raw dict
        assert isinstance(result, dict)
        assert result["resource_group"] == "default"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    @patch("auth.request_validator.RequestValidator.validate")
    @patch("proxy_server.requests.post")
    def test_chat_completion_flow(
        self, mock_post, mock_validate, flask_client, reset_proxy_config
    ):
        """Test complete chat completion flow."""
        mock_validate.return_value = True

        def mock_post_side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "oauth/token" in url:
                # Token response
                mock_response = Mock()
                mock_response.json.return_value = {
                    "access_token": "test-token",
                    "expires_in": 3600,
                }
                mock_response.raise_for_status = Mock()
                return mock_response
            else:
                # Chat completion response
                mock_response = Mock()
                mock_response.json.return_value = {
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "gpt-4",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Hello!"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                }
                mock_response.raise_for_status = Mock()
                return mock_response

        mock_post.side_effect = mock_post_side_effect

        # Setup subaccount
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gpt-4": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        subaccount.service_key = ServiceKey(
            clientid="id",
            clientsecret="secret",
            url="https://auth.url",
            identityzoneid="zone",
        )

        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}

        response = flask_client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["choices"][0]["message"]["content"] == "Hello!"


# ============================================================================
# ADDITIONAL EDGE CASE TESTS
# ============================================================================


class TestConversionEdgeCases:
    """Tests for edge cases in conversion functions."""

    def test_convert_openai_to_claude_with_tools(self):
        """Test OpenAI to Claude conversion with tools."""
        openai_payload = {
            "messages": [{"role": "user", "content": "Use a tool"}],
            "max_tokens": 1000,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        }

        result = convert_openai_to_claude(openai_payload)
        assert "messages" in result
        assert result["max_tokens"] == 1000

    def test_convert_claude37_with_stop_sequences(self):
        """Test Claude 3.7 conversion with stop sequences."""
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "stop": ["STOP", "END"],
        }

        result = convert_openai_to_claude37(payload)
        assert "inferenceConfig" in result
        assert result["inferenceConfig"]["stopSequences"] == ["STOP", "END"]

    def test_convert_claude37_with_single_stop_string(self):
        """Test Claude 3.7 conversion with single stop string."""
        payload = {"messages": [{"role": "user", "content": "Hello"}], "stop": "STOP"}

        result = convert_openai_to_claude37(payload)
        assert result["inferenceConfig"]["stopSequences"] == ["STOP"]

    def test_convert_openai_to_gemini_multiple_messages(self):
        """Test Gemini conversion with multiple messages."""
        payload = {
            "messages": [
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "Response"},
                {"role": "user", "content": "Second message"},
            ],
            "temperature": 0.5,
        }

        result = convert_openai_to_gemini(payload)
        assert isinstance(result["contents"], list)
        assert len(result["contents"]) == 3
        assert result["contents"][0]["role"] == "user"
        assert result["contents"][1]["role"] == "model"

    def test_convert_gemini_to_openai_max_tokens_stop(self):
        """Test Gemini to OpenAI conversion with max_tokens stop."""
        gemini_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Response"}], "role": "model"},
                    "finishReason": "MAX_TOKENS",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 50,
                "totalTokenCount": 150,
            },
        }

        result = convert_gemini_to_openai(gemini_response)
        assert result["choices"][0]["finish_reason"] == "length"
        assert result["usage"]["total_tokens"] == 150


class TestTokenManagementEdgeCases:
    """Additional token management tests."""

    @patch("proxy_server.requests.post")
    def test_fetch_token_http_error(
        self, mock_post, reset_proxy_config, sample_service_key
    ):
        """Test token fetch with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_error = requests.exceptions.HTTPError(response=mock_response)
        mock_post.side_effect = mock_error

        subaccount = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={},
        )
        subaccount.service_key = ServiceKey(**sample_service_key)
        proxy_server.proxy_config.subaccounts["test-account"] = subaccount

        with pytest.raises(ConnectionError, match="HTTP Error"):
            fetch_token("test-account", proxy_server.proxy_config)

    @patch("proxy_server.requests.post")
    def test_fetch_token_timeout(
        self, mock_post, reset_proxy_config, sample_service_key
    ):
        """Test token fetch with timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")

        subaccount = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={},
        )
        subaccount.service_key = ServiceKey(**sample_service_key)
        proxy_server.proxy_config.subaccounts["test-account"] = subaccount

        with pytest.raises(TimeoutError, match="Timeout connecting"):
            fetch_token("test-account", proxy_server.proxy_config)

    @patch("proxy_server.requests.post")
    def test_fetch_token_empty_token(
        self, mock_post, reset_proxy_config, sample_service_key
    ):
        """Test token fetch with empty token response."""
        mock_response = Mock()
        mock_response.json.return_value = {"access_token": ""}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        subaccount = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={},
        )
        subaccount.service_key = ServiceKey(**sample_service_key)
        proxy_server.proxy_config.subaccounts["test-account"] = subaccount

        # The function wraps ValueError in RuntimeError
        with pytest.raises(
            RuntimeError, match="Unexpected error processing token response"
        ):
            fetch_token("test-account", proxy_server.proxy_config)

    def test_verify_request_token_bearer_format(self, reset_proxy_config):
        """Test token verification with Bearer format."""
        proxy_server.proxy_config.secret_authentication_tokens = ["my-secret-token"]

        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer my-secret-token"}

        assert verify_request_token(mock_request, proxy_server.proxy_config) is True


class TestLoadBalancingEdgeCases:
    """Additional load balancing tests."""

    def test_load_balance_url_multiple_urls_per_subaccount(self, reset_proxy_config):
        """Test load balancing with multiple URLs per subaccount."""
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={
                "gpt-4": ["https://url1.com", "https://url2.com", "https://url3.com"]
            },
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}

        if hasattr(load_balance_url, "counters"):
            load_balance_url.counters.clear()

        url1, _, _, _ = load_balance_url("gpt-4")
        assert url1 == "https://url1.com"

        url2, _, _, _ = load_balance_url("gpt-4")
        assert url2 == "https://url2.com"

        url3, _, _, _ = load_balance_url("gpt-4")
        assert url3 == "https://url3.com"

        url4, _, _, _ = load_balance_url("gpt-4")
        assert url4 == "https://url1.com"

    def test_load_balance_url_gemini_fallback(self, reset_proxy_config):
        """Test Gemini model fallback."""
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gemini-2.5-pro": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "gemini-2.5-pro": ["account1"]
        }

        url, subaccount_name, _, model = load_balance_url("gemini-1.5-flash")

        assert model == "gemini-2.5-pro"
        assert subaccount_name == "account1"

    def test_load_balance_url_no_urls_configured(self, reset_proxy_config):
        """Test load balancing when model has no URLs."""
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gpt-4": []},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}

        with pytest.raises(ValueError, match="No URLs for model"):
            load_balance_url("gpt-4")


class TestFlaskEndpointsEdgeCases:
    """Additional Flask endpoint tests."""

    def test_list_models_empty(self, flask_client, reset_proxy_config):
        """Test /v1/models with no models configured."""
        proxy_server.proxy_config.model_to_subaccounts = {}

        response = flask_client.get("/v1/models")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["object"] == "list"
        assert len(data["data"]) == 0

    @patch("auth.request_validator.RequestValidator.validate")
    def test_embeddings_missing_input(self, mock_validate, flask_client):
        """Test embeddings endpoint with missing input."""
        mock_validate.return_value = True

        response = flask_client.post(
            "/v1/embeddings",
            json={"model": "text-embedding-3-large"},
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    @patch("auth.request_validator.RequestValidator.validate")
    def test_embeddings_unauthorized(self, mock_validate, flask_client):
        """Test embeddings endpoint without authorization."""
        mock_validate.return_value = False

        response = flask_client.post(
            "/v1/embeddings", json={"input": "test", "model": "text-embedding-3-large"}
        )

        assert response.status_code == 401

    def test_options_request(self, flask_client):
        """Test OPTIONS request to chat completions."""
        response = flask_client.options("/v1/chat/completions")

        assert response.status_code == 204


class TestStreamingHelpersExtended:
    """Additional tests for streaming helper functions."""

    def test_convert_gemini_chunk_to_claude_delta(self):
        """Test Gemini chunk to Claude delta conversion."""
        gemini_chunk = {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}

        result = Converters.convert_gemini_chunk_to_claude_delta(gemini_chunk)

        assert result is not None
        assert result["type"] == "content_block_delta"
        assert result["delta"]["text"] == "Hello"

    def test_convert_openai_chunk_to_claude_delta(self):
        """Test OpenAI chunk to Claude delta conversion."""
        openai_chunk = {"choices": [{"delta": {"content": "World"}}]}

        result = Converters.convert_openai_chunk_to_claude_delta(openai_chunk)

        assert result is not None
        assert result["type"] == "content_block_delta"
        assert result["delta"]["text"] == "World"

    def test_get_claude_stop_reason_from_gemini_chunk(self):
        """Test extracting stop reason from Gemini chunk."""
        gemini_chunk = {"candidates": [{"finishReason": "STOP"}]}

        result = proxy_server.get_claude_stop_reason_from_gemini_chunk(gemini_chunk)
        assert result == "end_turn"

    def test_get_claude_stop_reason_from_openai_chunk(self):
        """Test extracting stop reason from OpenAI chunk."""
        openai_chunk = {"choices": [{"finish_reason": "length"}]}

        result = proxy_server.get_claude_stop_reason_from_openai_chunk(openai_chunk)
        assert result == "max_tokens"


class TestRequestHandlers:
    """Tests for request handler functions."""

    def test_handle_claude_request_streaming(self, reset_proxy_config):
        """Test Claude request handler with streaming."""
        from proxy_server import handle_claude_request

        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"anthropic--claude-4.5-sonnet": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "anthropic--claude-4.5-sonnet": ["account1"]
        }

        payload = {"messages": [{"role": "user", "content": "Hello"}], "stream": True}

        url, modified_payload, subaccount_name = handle_claude_request(
            payload, "anthropic--claude-4.5-sonnet"
        )

        assert "/converse-stream" in url
        assert subaccount_name == "account1"
        assert "messages" in modified_payload

    def test_handle_gemini_request_non_streaming(self, reset_proxy_config):
        """Test Gemini request handler without streaming."""
        from proxy_server import handle_gemini_request

        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gemini-2.5-pro": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "gemini-2.5-pro": ["account1"]
        }

        payload = {"messages": [{"role": "user", "content": "Hello"}], "stream": False}

        url, modified_payload, subaccount_name = handle_gemini_request(
            payload, "gemini-2.5-pro"
        )

        assert ":generateContent" in url
        assert ":streamGenerateContent" not in url
        assert subaccount_name == "account1"

    def test_handle_default_request_o3_model(self, reset_proxy_config):
        """Test default request handler with o3 model."""
        from proxy_server import handle_default_request

        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"o3-mini": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {"o3-mini": ["account1"]}

        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }

        url, modified_payload, subaccount_name = handle_default_request(
            payload, "o3-mini"
        )

        assert "2024-12-01-preview" in url
        assert "temperature" not in modified_payload


class TestResponseConversionEdgeCases:
    """Tests for response conversion edge cases."""

    def test_convert_claude37_to_openai_with_cache_tokens(self):
        """Test Claude 3.7 to OpenAI with cache tokens."""
        claude37_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Cached response"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 100,
                "outputTokens": 50,
                "totalTokens": 150,
                "cacheReadInputTokens": 80,
                "cacheCreationInputTokens": 20,
            },
        }

        result = convert_claude37_to_openai(claude37_response, "claude-3.7-sonnet")

        assert "prompt_tokens_details" in result["usage"]
        assert result["usage"]["prompt_tokens_details"]["cached_tokens"] == 80
        assert result["usage"]["prompt_tokens_details"]["cache_creation_tokens"] == 20

    def test_convert_gemini_to_openai_safety_stop(self):
        """Test Gemini conversion with safety stop reason."""
        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Filtered content"}],
                        "role": "model",
                    },
                    "finishReason": "SAFETY",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }

        result = convert_gemini_to_openai(gemini_response)
        assert result["choices"][0]["finish_reason"] == "content_filter"


# ============================================================================
# SDK SESSION AND CLIENT TESTS
# ============================================================================


class TestSDKSessionManagement:
    """Tests for SAP AI Core SDK session and client management."""

    @patch("proxy_server.Session")
    def test_get_sapaicore_sdk_session_creates_new_session(self, mock_session_class):
        """Test that get_sapaicore_sdk_session creates a new session when none exists."""
        # Reset global state
        proxy_server._sdk_session = None

        mock_session = Mock()
        mock_session_class.return_value = mock_session

        result = proxy_server.get_sapaicore_sdk_session()

        assert result == mock_session
        mock_session_class.assert_called_once()
        assert proxy_server._sdk_session == mock_session

    @patch("proxy_server.Session")
    def test_get_sapaicore_sdk_session_returns_cached_session(self, mock_session_class):
        """Test that get_sapaicore_sdk_session returns cached session."""
        mock_session = Mock()
        proxy_server._sdk_session = mock_session

        result = proxy_server.get_sapaicore_sdk_session()

        assert result == mock_session
        mock_session_class.assert_not_called()

    @patch("proxy_server.get_sapaicore_sdk_session")
    @patch("proxy_server.Config")
    def test_get_sapaicore_sdk_client_creates_new_client(
        self, mock_config, mock_get_session
    ):
        """Test that get_sapaicore_sdk_client creates a new client when none exists."""
        # Reset global state
        proxy_server._bedrock_clients.clear()

        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_get_session.return_value = mock_session

        # Mock Config to return the expected dict
        expected_config = {
            "retries": {
                "max_attempts": 1,
                "mode": "standard",
            }
        }
        mock_config.return_value = expected_config

        result = proxy_server.get_sapaicore_sdk_client("gpt-4")

        assert result == mock_client
        mock_session.client.assert_called_once_with(
            model_name="gpt-4", config=expected_config
        )
        assert proxy_server._bedrock_clients["gpt-4"] == mock_client

    @patch("proxy_server.get_sapaicore_sdk_session")
    def test_get_sapaicore_sdk_client_returns_cached_client(self, mock_get_session):
        """Test that get_sapaicore_sdk_client returns cached client."""
        mock_client = Mock()
        proxy_server._bedrock_clients["gpt-4"] = mock_client

        result = proxy_server.get_sapaicore_sdk_client("gpt-4")

        assert result == mock_client
        mock_get_session.assert_not_called()


# ============================================================================
# EMBEDDING TESTS
# ============================================================================


class TestEmbeddingFunctions:
    """Tests for embedding-related functions."""

    def test_format_embedding_response(self):
        """Test format_embedding_response function."""
        response = {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}

        result = proxy_server.format_embedding_response(
            response, "text-embedding-3-large"
        )

        assert result["object"] == "list"
        assert result["data"][0]["object"] == "embedding"
        assert result["data"][0]["embedding"] == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert result["data"][0]["index"] == 0
        assert result["model"] == "text-embedding-3-large"
        assert result["usage"]["prompt_tokens"] == 5
        assert result["usage"]["total_tokens"] == 5


# ============================================================================
# CLAUDE CONVERSION TESTS
# ============================================================================


class TestClaudeRequestConversions:
    """Tests for Claude request conversion functions."""

    def test_convert_claude_request_to_openai(self):
        """Test convert_claude_request_to_openai function."""
        claude_payload = {
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000,
            "temperature": 0.7,
            "stream": True,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather info",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
        }

        result = Converters.convert_claude_request_to_openai(claude_payload)

        assert result["model"] is None  # Not set in input
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "You are helpful"
        assert result["messages"][1]["role"] == "user"
        assert result["messages"][1]["content"] == "Hello"
        assert result["max_completion_tokens"] == 1000
        assert result["temperature"] == 0.7
        assert result["stream"] is True
        assert len(result["tools"]) == 1
        assert result["tools"][0]["function"]["name"] == "get_weather"

    def test_convert_claude_request_to_gemini(self):
        """Test convert_claude_request_to_gemini function."""
        claude_payload = {
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000,
            "temperature": 0.7,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather info",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
        }

        result = Converters.convert_claude_request_to_gemini(claude_payload)

        # The function returns contents as a list for multiple messages
        assert isinstance(result["contents"], list)
        assert (
            len(result["contents"]) == 1
        )  # System message is prepended to first user message
        assert result["contents"][0]["role"] == "user"
        assert "You are helpful" in result["contents"][0]["parts"]["text"]
        assert "Hello" in result["contents"][0]["parts"]["text"]
        assert result["generation_config"]["maxOutputTokens"] == 1000
        assert result["generation_config"]["temperature"] == 0.7
        assert len(result["tools"]) == 1

    def test_convert_claude_request_for_bedrock(self):
        """Test convert_claude_request_for_bedrock function."""
        claude_payload = {
            "model": "claude-3.5-sonnet",
            "max_tokens": 1000,
            "temperature": 0.7,
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {},
                }
            ],
        }

        result = Converters.convert_claude_request_for_bedrock(claude_payload)

        assert result["model"] == "claude-3.5-sonnet"
        assert result["max_tokens"] == 1000
        assert result["temperature"] == 0.7
        assert result["system"] == "You are helpful"
        assert len(result["messages"]) == 1
        assert result["anthropic_version"] == "bedrock-2023-05-31"
        assert "tools" in result


# ============================================================================
# RESPONSE CONVERSION TESTS
# ============================================================================


class TestResponseConversions:
    """Tests for response conversion functions."""

    def test_convert_claude_to_openai_standard(self):
        """Test convert_claude_to_openai for standard Claude models."""
        claude_response = {
            "id": "msg_123",
            "content": [{"text": "Hello world"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

        result = Converters.convert_claude_to_openai(
            claude_response, "claude-3.5-sonnet"
        )

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["message"]["content"] == "Hello world"
        assert result["choices"][0]["finish_reason"] == "end_turn"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 20
        assert result["usage"]["total_tokens"] == 30

    def test_convert_claude37_to_openai(self):
        """Test convert_claude37_to_openai function."""
        claude37_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello from Claude 3.7"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 15, "outputTokens": 25, "totalTokens": 40},
        }

        result = Converters.convert_claude37_to_openai(
            claude37_response, "claude-3.7-sonnet"
        )

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["message"]["content"] == "Hello from Claude 3.7"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 15
        assert result["usage"]["completion_tokens"] == 25
        assert result["usage"]["total_tokens"] == 40

    def test_convert_gemini_to_openai(self):
        """Test convert_gemini_to_openai function."""
        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Hello from Gemini"}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 10,
                "totalTokenCount": 15,
            },
        }

        result = Converters.convert_gemini_to_openai(gemini_response, "gemini-pro")

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["message"]["content"] == "Hello from Gemini"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] == 5
        assert result["usage"]["completion_tokens"] == 10
        assert result["usage"]["total_tokens"] == 15

    def test_convert_gemini_response_to_claude(self):
        """Test convert_gemini_response_to_claude function."""
        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Hello from Gemini"}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 10},
        }

        result = Converters.convert_gemini_response_to_claude(
            gemini_response, "gemini-pro"
        )

        assert result["id"].startswith("msg_gemini_")
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["content"][0]["text"] == "Hello from Gemini"
        assert result["stop_reason"] == "end_turn"
        assert result["usage"]["input_tokens"] == 5
        assert result["usage"]["output_tokens"] == 10

    def test_convert_openai_response_to_claude(self):
        """Test convert_openai_response_to_claude function."""
        openai_response = {
            "choices": [
                {
                    "message": {
                        "content": "Hello from OpenAI",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "NYC"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

        result = Converters.convert_openai_response_to_claude(openai_response)

        assert result["id"].startswith("msg_openai_")
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["content"][0]["text"] == "Hello from OpenAI"
        assert result["content"][1]["type"] == "tool_use"
        assert result["content"][1]["name"] == "get_weather"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 20


# ============================================================================
# STREAMING HELPER TESTS
# ============================================================================


class TestStreamingHelpers:
    """Tests for streaming helper functions."""

    def test_convert_gemini_chunk_to_claude_delta(self):
        """Test convert_gemini_chunk_to_claude_delta function."""
        gemini_chunk = {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}

        result = Converters.convert_gemini_chunk_to_claude_delta(gemini_chunk)

        assert result is not None
        assert result["type"] == "content_block_delta"
        assert result["delta"]["text"] == "Hello"

    def test_convert_openai_chunk_to_claude_delta(self):
        """Test convert_openai_chunk_to_claude_delta function."""
        openai_chunk = {"choices": [{"delta": {"content": "World"}}]}

        result = Converters.convert_openai_chunk_to_claude_delta(openai_chunk)

        assert result is not None
        assert result["type"] == "content_block_delta"
        assert result["delta"]["text"] == "World"

    def test_get_claude_stop_reason_from_gemini_chunk(self):
        """Test get_claude_stop_reason_from_gemini_chunk function."""
        gemini_chunk = {"candidates": [{"finishReason": "STOP"}]}

        result = proxy_server.get_claude_stop_reason_from_gemini_chunk(gemini_chunk)
        assert result == "end_turn"

    def test_get_claude_stop_reason_from_openai_chunk(self):
        """Test get_claude_stop_reason_from_openai_chunk function."""
        openai_chunk = {"choices": [{"finish_reason": "stop"}]}

        result = proxy_server.get_claude_stop_reason_from_openai_chunk(openai_chunk)
        assert result == "end_turn"


# ============================================================================
# REQUEST HANDLER TESTS
# ============================================================================


class TestRequestHandlers:
    """Tests for request handler functions."""

    def test_handle_claude_request_streaming(self, reset_proxy_config):
        """Test handle_claude_request with streaming."""
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"anthropic--claude-4.5-sonnet": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "anthropic--claude-4.5-sonnet": ["account1"]
        }

        payload = {"messages": [{"role": "user", "content": "Hello"}], "stream": True}

        url, modified_payload, subaccount_name = proxy_server.handle_claude_request(
            payload, "anthropic--claude-4.5-sonnet"
        )

        assert "/converse-stream" in url
        assert subaccount_name == "account1"
        assert "messages" in modified_payload

    def test_handle_gemini_request_streaming(self, reset_proxy_config):
        """Test handle_gemini_request with streaming."""
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gemini-2.5-pro": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "gemini-2.5-pro": ["account1"]
        }

        payload = {"messages": [{"role": "user", "content": "Hello"}], "stream": True}

        url, modified_payload, subaccount_name = proxy_server.handle_gemini_request(
            payload, "gemini-2.5-pro"
        )

        assert ":streamGenerateContent" in url
        assert subaccount_name == "account1"
        assert "contents" in modified_payload

    def test_handle_default_request_o3_model(self, reset_proxy_config):
        """Test handle_default_request with o3 model."""
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"o3-mini": ["https://url1.com"]},
        )
        subaccount.normalized_models = subaccount.deployment_models
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {"o3-mini": ["account1"]}

        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }

        url, modified_payload, subaccount_name = proxy_server.handle_default_request(
            payload, "o3-mini"
        )

        assert "2024-12-01-preview" in url
        assert "temperature" not in modified_payload
        assert subaccount_name == "account1"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
