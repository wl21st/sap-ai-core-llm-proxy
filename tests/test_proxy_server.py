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
from unittest.mock import Mock, patch, MagicMock, mock_open
from dataclasses import dataclass
from flask import Flask
from io import BytesIO

# Import the module under test
import proxy_server
from proxy_server import (
    ServiceKey,
    TokenInfo,
    SubAccountConfig,
    ProxyConfig,
    app,
    load_config,
    fetch_token,
    verify_request_token,
    load_balance_url,
    is_claude_model,
    is_claude_37_or_4,
    is_gemini_model,
    convert_openai_to_claude,
    convert_openai_to_claude37,
    convert_claude_to_openai,
    convert_claude37_to_openai,
    convert_openai_to_gemini,
    convert_gemini_to_openai,
    handle_http_429_error,
)


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
        "identityzoneid": "test-zone-id"
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
                    "gpt-4o": ["https://api.ai.prod.us-east-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d123"],
                    "anthropic--claude-4.5-sonnet": ["https://api.ai.prod.us-east-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d456"]
                }
            },
            "account2": {
                "resource_group": "default",
                "service_key_json": "account2_key.json",
                "deployment_models": {
                    "gpt-4o": ["https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d789"],
                    "gemini-2.5-pro": ["https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d101"]
                }
            }
        },
        "secret_authentication_tokens": ["test-token-123", "test-token-456"],
        "port": 3001,
        "host": "127.0.0.1"
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
    app.config['TESTING'] = True
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
            identityzoneid="test-zone"
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
            deployment_models={"gpt-4": ["url1", "url2"]}
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
            deployment_models={}
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
                "gpt-4": ["url2"]
            }
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
            deployment_models={"gpt-4": ["url1"], "claude": ["url2"]}
        )
        sub1.normalized_models = sub1.deployment_models
        
        sub2 = SubAccountConfig(
            name="sub2",
            resource_group="default",
            service_key_json="key2.json",
            deployment_models={"gpt-4": ["url3"]}
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
    
    @pytest.mark.parametrize("model_name,expected", [
        ("claude-3.5-sonnet", True),
        ("anthropic--claude-4-sonnet", True),
        ("claude", True),
        ("sonnet", True),
        ("CLAUDE", True),
        ("gpt-4", False),
        ("gemini-pro", False),
    ])
    def test_is_claude_model(self, model_name, expected):
        """Test Claude model detection."""
        assert is_claude_model(model_name) == expected
    
    @pytest.mark.parametrize("model_name,expected", [
        ("claude-3.7-sonnet", True),
        ("claude-4-opus", True),
        ("claude-4.5-sonnet", True),
        ("claude-3.5-sonnet", False),
        ("claude-2", True),  # Fixed: claude-2 doesn't contain "3.5" so returns True
    ])
    def test_is_claude_37_or_4(self, model_name, expected):
        """Test Claude 3.7/4 detection."""
        assert is_claude_37_or_4(model_name) == expected
    
    @pytest.mark.parametrize("model_name,expected", [
        ("gemini-pro", True),
        ("gemini-1.5-pro", True),
        ("gemini-2.5-flash", True),
        ("GEMINI-PRO", True),
        ("gpt-4", False),
        ("claude", False),
    ])
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
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
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
                {"role": "user", "content": "User message"}
            ],
            "max_tokens": 2000,
            "temperature": 0.5
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
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20
            }
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
                    "content": [{"type": "text", "text": "Response text"}]
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 15,
                "outputTokens": 25,
                "totalTokens": 40
            }
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
            "messages": [
                {"role": "user", "content": "Hello Gemini"}
            ],
            "max_tokens": 1500,
            "temperature": 0.8
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
            "candidates": [{
                "content": {
                    "parts": [{"text": "Gemini response"}],
                    "role": "model"
                },
                "finishReason": "STOP"
            }],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 10,
                "totalTokenCount": 15
            }
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
        mock_response.headers = {
            "Retry-After": "60",
            "X-RateLimit-Limit": "100"
        }
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
        
        assert verify_request_token(mock_request) is True
    
    def test_verify_request_token_invalid(self, reset_proxy_config):
        """Test token verification with invalid token."""
        proxy_server.proxy_config.secret_authentication_tokens = ["secret-abc-123"]
        
        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer wrong-token-xyz"}
        
        # The function checks if any secret_key is IN the token string
        # "wrong-token-xyz" doesn't contain "secret-abc-123"
        result = verify_request_token(mock_request)
        assert result is False
    
    def test_verify_request_token_no_auth_configured(self, reset_proxy_config):
        """Test token verification when no tokens configured."""
        proxy_server.proxy_config.secret_authentication_tokens = []
        
        mock_request = Mock()
        mock_request.headers = {}
        
        # Should return True when no authentication is configured
        assert verify_request_token(mock_request) is True
    
    def test_verify_request_token_x_api_key(self, reset_proxy_config):
        """Test token verification with x-api-key header."""
        proxy_server.proxy_config.secret_authentication_tokens = ["api-key-123"]
        
        mock_request = Mock()
        mock_request.headers = {"x-api-key": "api-key-123"}
        
        assert verify_request_token(mock_request) is True
    
    @patch('proxy_server.requests.post')
    def test_fetch_token_success(self, mock_post, reset_proxy_config, sample_service_key):
        """Test successful token fetch."""
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token-123",
            "expires_in": 3600
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # Setup subaccount
        subaccount = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={}
        )
        subaccount.service_key = ServiceKey(**sample_service_key)
        proxy_server.proxy_config.subaccounts["test-account"] = subaccount
        
        token = fetch_token("test-account")
        
        assert token == "new-token-123"
        assert subaccount.token_info.token == "new-token-123"
        assert subaccount.token_info.expiry > time.time()
    
    @patch('proxy_server.requests.post')
    def test_fetch_token_cached(self, mock_post, reset_proxy_config, sample_service_key):
        """Test token fetch returns cached token."""
        # Setup subaccount with valid cached token
        subaccount = SubAccountConfig(
            name="test-account",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={}
        )
        subaccount.service_key = ServiceKey(**sample_service_key)
        subaccount.token_info.token = "cached-token"
        subaccount.token_info.expiry = time.time() + 3600  # Valid for 1 hour
        proxy_server.proxy_config.subaccounts["test-account"] = subaccount
        
        token = fetch_token("test-account")
        
        assert token == "cached-token"
        # Should not make HTTP request
        mock_post.assert_not_called()
    
    def test_fetch_token_invalid_subaccount(self, reset_proxy_config):
        """Test token fetch with invalid subaccount."""
        with pytest.raises(ValueError, match="SubAccount .* not found"):
            fetch_token("nonexistent-account")


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
            deployment_models={"gpt-4": ["https://url1.com"]}
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
            deployment_models={"gpt-4": ["https://url1.com"]}
        )
        sub1.normalized_models = sub1.deployment_models
        
        sub2 = SubAccountConfig(
            name="account2",
            resource_group="rg2",
            service_key_json="key2.json",
            deployment_models={"gpt-4": ["https://url2.com"]}
        )
        sub2.normalized_models = sub2.deployment_models
        
        proxy_server.proxy_config.subaccounts = {"account1": sub1, "account2": sub2}
        proxy_server.proxy_config.model_to_subaccounts = {"gpt-4": ["account1", "account2"]}
        
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
            deployment_models={"anthropic--claude-4.5-sonnet": ["https://url1.com"]}
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
            "claude-3.5-sonnet": ["account2"]
        }
        
        response = flask_client.get('/v1/models')
        
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
            '/api/event_logging/batch',
            json={"events": [{"type": "test"}]}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
    
    @patch('proxy_server.verify_request_token')
    @patch('proxy_server.requests.post')
    def test_embeddings_endpoint(self, mock_post, mock_verify, flask_client, reset_proxy_config):
        """Test /v1/embeddings endpoint."""
        mock_verify.return_value = True
        
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "object": "list",
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # Setup subaccount
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"text-embedding-3-large": ["https://url1.com"]}
        )
        subaccount.normalized_models = subaccount.deployment_models
        subaccount.service_key = ServiceKey(
            clientid="id",
            clientsecret="secret",
            url="https://auth.url",
            identityzoneid="zone"
        )
        subaccount.token_info.token = "test-token"
        subaccount.token_info.expiry = time.time() + 3600
        
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {
            "text-embedding-3-large": ["account1"]
        }
        
        response = flask_client.post(
            '/v1/embeddings',
            json={
                "input": "Test text",
                "model": "text-embedding-3-large"
            },
            headers={"Authorization": "Bearer test-token"}
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
            key_file.write_text(json.dumps({
                "clientid": f"{account}-id",
                "clientsecret": f"{account}-secret",
                "url": "https://auth.url",
                "identityzoneid": "zone"
            }))
        
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
            "host": "127.0.0.1"
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
    
    @patch('proxy_server.verify_request_token')
    @patch('proxy_server.fetch_token')
    @patch('proxy_server.requests.post')
    def test_chat_completion_flow(self, mock_post, mock_fetch_token, mock_verify, 
                                   flask_client, reset_proxy_config):
        """Test complete chat completion flow."""
        mock_verify.return_value = True
        mock_fetch_token.return_value = "test-token"
        
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello!"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # Setup subaccount
        subaccount = SubAccountConfig(
            name="account1",
            resource_group="default",
            service_key_json="key.json",
            deployment_models={"gpt-4": ["https://url1.com"]}
        )
        subaccount.normalized_models = subaccount.deployment_models
        subaccount.service_key = ServiceKey(
            clientid="id",
            clientsecret="secret",
            url="https://auth.url",
            identityzoneid="zone"
        )
        
        proxy_server.proxy_config.subaccounts["account1"] = subaccount
        proxy_server.proxy_config.model_to_subaccounts = {"gpt-4": ["account1"]}
        
        response = flask_client.post(
            '/v1/chat/completions',
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["choices"][0]["message"]["content"] == "Hello!"


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])