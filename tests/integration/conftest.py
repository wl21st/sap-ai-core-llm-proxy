"""
Pytest configuration and fixtures for real integration tests.

Provides:
- Test configuration loading from file or environment
- HTTP client configured for proxy server
- Server availability checking
- Test prompts and utilities
"""

import json
import logging
import os
import pytest
import requests
from pathlib import Path
from typing import Dict, Any

# Get logger for integration tests
logger = logging.getLogger(__name__)


def load_test_config() -> Dict[str, Any]:
    """
    Load test configuration from file or environment variables.

    Priority:
    1. tests/integration/test_config.json (if exists)
    2. tests/integration/test_config.json.example (fallback)
    3. Environment variables

    Returns:
        Test configuration dictionary
    """
    config_path = Path(__file__).parent / "test_config.json"
    example_path = Path(__file__).parent / "test_config.json.example"

    # Try to load from test_config.json first
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    elif example_path.exists():
        with open(example_path) as f:
            config = json.load(f)
    else:
        # Default configuration
        config = {
            "proxy_url": "http://127.0.0.1:3001",
            "auth_token": "",
            "models_to_test": [
                "anthropic--claude-4.5-sonnet",
                "sonnet-4.5",
                "gpt-4.1",
                "gpt-5",
                "gemini-2.5-pro",
            ],
            "test_prompts": {
                "simple": "Hello, how are you?",
                "math": "What is 2+2?",
                "creative": "Tell me a joke.",
                "technical": "Explain Python in one sentence.",
            },
            "timeout": 30,
            "max_tokens": 100,
            "skip_if_server_not_running": True,
        }

    # Override with environment variables
    if os.getenv("PROXY_URL"):
        config["proxy_url"] = os.getenv("PROXY_URL")

    if os.getenv("PROXY_AUTH_TOKEN"):
        config["auth_token"] = os.getenv("PROXY_AUTH_TOKEN")
    elif config["auth_token"].startswith("${") and config["auth_token"].endswith("}"):
        # Try to expand environment variable reference
        env_var = config["auth_token"][2:-1]
        config["auth_token"] = os.getenv(env_var, "")

    skip_env = os.getenv("SKIP_INTEGRATION_TESTS")
    if skip_env:
        config["skip_if_server_not_running"] = skip_env.lower() == "true"

    return config


@pytest.fixture(scope="session")
def test_config():
    """Load and provide test configuration."""
    return load_test_config()


@pytest.fixture(scope="session")
def proxy_url(test_config):
    """Get proxy server URL."""
    return test_config["proxy_url"]


@pytest.fixture(scope="session")
def auth_token(test_config):
    """Get authentication token."""
    return test_config["auth_token"]


@pytest.fixture(scope="session")
def check_server_running(test_config, proxy_url):
    """
    Check if proxy server is running.

    Raises:
        pytest.skip: If server is not running and skip_if_server_not_running is True
    """
    try:
        response = requests.get(f"{proxy_url}/v1/models", timeout=5)
        if response.status_code not in [200, 401]:
            if test_config["skip_if_server_not_running"]:
                pytest.skip(f"Proxy server not responding correctly at {proxy_url}")
            else:
                pytest.fail(f"Proxy server not responding correctly at {proxy_url}")
    except requests.exceptions.RequestException as e:
        if test_config["skip_if_server_not_running"]:
            pytest.skip(f"Proxy server not running at {proxy_url}: {e}")
        else:
            pytest.fail(f"Proxy server not running at {proxy_url}: {e}")


class LoggingSession(requests.Session):
    """Session that logs requests and responses with enhanced visibility."""
    
    def request(self, method, url, *args, **kwargs):
        """Override request to add enhanced logging."""
        # Prepare headers with masking
        headers_dict = dict(self.headers)
        masked_headers = {}
        for key, value in headers_dict.items():
            if isinstance(key, str) and isinstance(value, str) and key.lower() in ['authorization', 'x-api-key']:
                masked_headers[key] = f"{value[:10]}...[REDACTED]" if len(value) > 10 else "***"
            else:
                masked_headers[key] = value
        
        # Enhanced request logging with prominent formatting
        logger.info(f"\n🔵🔵🔵 HTTP REQUEST START 🔵🔵🔵")
        logger.info(f"📡 METHOD: {method}")
        logger.info(f"🌐 URL: {url}")
        logger.info(f"📋 HEADERS:")
        for key, value in masked_headers.items():
            logger.info(f"   {key}: {value}")
        
        if 'json' in kwargs:
            logger.info(f"📦 JSON BODY:\n{json.dumps(kwargs['json'], indent=2)}")
        elif 'data' in kwargs:
            logger.info(f"📦 DATA BODY: {kwargs['data']}")
        if 'params' in kwargs:
            logger.info(f"🔤 PARAMS: {kwargs['params']}")
        
        logger.info(f"🔵🔵🔵 HTTP REQUEST END 🔵🔵🔵\n")
        
        # Make request
        response = super().request(method, url, *args, **kwargs)
        
        # Enhanced response logging
        response_headers = dict(response.headers)
        
        logger.info(f"\n🟢🟢🟢 HTTP RESPONSE START 🟢🟢🟢")
        logger.info(f"📊 STATUS: {response.status_code} {response.reason}")
        logger.info(f"⏱️  RESPONSE TIME: {response.elapsed.total_seconds():.3f}s")
        logger.info(f"📋 RESPONSE HEADERS:")
        for key, value in response_headers.items():
            logger.info(f"   {key}: {value}")
        
        # Log response body (handle streaming vs non-streaming)
        if kwargs.get('stream'):
            logger.info(f"📡 STREAMING: [Streaming response - chunks will be logged below]")
        else:
            logger.info(f"📦 RESPONSE BODY:")
            try:
                response_json = response.json()
                logger.info(f"{json.dumps(response_json, indent=2)}")
            except Exception:
                response_text = response.text
                if len(response_text) > 1000:
                    logger.info(f"{response_text[:1000]}...[TRUNCATED]")
                else:
                    logger.info(response_text)
        
        logger.info(f"🟢🟢🟢 HTTP RESPONSE END 🟢🟢🟢\n")
        
        return response


@pytest.fixture(scope="session")
def proxy_client(test_config, proxy_url, auth_token, check_server_running):
    """
    Create HTTP client configured for proxy server with request/response logging.

    Returns:
        Configured LoggingSession
    """
    session = LoggingSession()
    session.headers.update({"Content-Type": "application/json"})

    if auth_token:
        session.headers.update({"Authorization": f"Bearer {auth_token}"})

    return session


@pytest.fixture
def simple_prompts(test_config):
    """Get simple test prompts."""
    return test_config["test_prompts"]


@pytest.fixture
def models_to_test(test_config):
    """Get list of models to test."""
    return test_config["models_to_test"]


@pytest.fixture
def max_tokens(test_config):
    """Get max tokens for test requests."""
    return test_config.get("max_tokens", 100)


@pytest.fixture
def claude_models(models_to_test):
    """Get Claude models from test configuration."""
    return [m for m in models_to_test if "claude" in m.lower() or "sonnet" in m.lower()]


@pytest.fixture
def gpt_models(models_to_test):
    """Get GPT models from test configuration."""
    return [m for m in models_to_test if "gpt" in m.lower()]


@pytest.fixture
def gemini_models(models_to_test):
    """Get Gemini models from test configuration."""
    return [m for m in models_to_test if "gemini" in m.lower()]


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "real: Real integration tests against localhost")
    config.addinivalue_line("markers", "smoke: Quick smoke tests")
    config.addinivalue_line("markers", "streaming: Streaming response tests")
    config.addinivalue_line("markers", "claude: Claude-specific tests")
    config.addinivalue_line("markers", "openai: OpenAI-compatible tests")
    config.addinivalue_line("markers", "gemini: Gemini-specific tests")