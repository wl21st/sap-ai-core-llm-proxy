"""
Tests for status endpoints (/health, /stats, /info).
"""

import pytest
from fastapi.testclient import TestClient
from saip.main import create_app
import tempfile
import json


@pytest.fixture
def temp_config():
    """Create a temporary config file for testing."""
    # Create a temporary service key file with required fields
    service_key = {
        "clientid": "test-client",
        "clientsecret": "test-secret",
        "url": "https://test.example.com",
        "serviceurls": {
            "AI_API_URL": "https://api.test.example.com"
        }
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as key_file:
        json.dump(service_key, key_file)
        key_file_path = key_file.name

    config = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": key_file_path,
                "deploymentModels": {
                    "gpt-4.1": ["https://api.example.com/gpt"],
                    "claude-4.5": ["https://api.example.com/claude"],
                },
            }
        },
        "secret_authentication_tokens": ["test-token"],
        "host": "127.0.0.1",
        "port": 3001,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(config, f)
        return f.name


@pytest.fixture
def client(temp_config):
    """Create a test client with temporary config."""
    from saip.config import ProxyConfig, SubAccountConfig, ProxyGlobalContext
    from saip.utils.metrics import MetricsCollector
    from unittest.mock import MagicMock

    app = create_app(temp_config)

    # Manually initialize app state with mocked config to avoid real API calls
    mock_sub_config = SubAccountConfig(
        name="test-account",
        resource_group="default",
        service_key_json=None,
        model_to_deployment_urls={
            "gpt-4.1": ["https://api.example.com/gpt"],
            "claude-4.5": ["https://api.example.com/claude"],
        },
    )

    config = MagicMock(spec=ProxyConfig)
    config.host = "127.0.0.1"
    config.port = 3001
    config.subaccounts = {"test-account": mock_sub_config}

    context = ProxyGlobalContext()
    context.config = config
    context.token_managers = {}

    app.state.proxy_config = config
    app.state.proxy_context = context
    app.state.metrics = MetricsCollector()

    return TestClient(app)


def test_health_endpoint(client):
    """Test /health endpoint returns OK status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_stats_endpoint(client):
    """Test /stats endpoint returns metrics."""
    # Make a request first to increment counters
    client.get("/health")

    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "metrics"
    assert "request_count" in data
    assert "uptime_seconds" in data
    assert "requests_by_model" in data
    assert "requests_by_endpoint" in data
    assert isinstance(data["request_count"], int)
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0


def test_info_endpoint(client):
    """Test /info endpoint returns configuration details."""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "details"
    assert "subaccounts" in data
    assert "subaccount_count" in data
    assert "available_models" in data
    assert "host" in data
    assert "port" in data
    assert data["subaccount_count"] == 1
    assert "test-account" in data["subaccounts"]
    assert "gpt-4.1" in data["available_models"]
    assert "claude-4.5" in data["available_models"]


def test_metrics_tracking_multiple_requests(client):
    """Test that metrics are tracked across multiple requests."""
    # Make multiple requests
    client.get("/health")
    client.get("/health")
    client.get("/stats")
    client.get("/info")

    response = client.get("/stats")
    data = response.json()
    # Should have at least 5 requests (3 /health + 1 /stats + 1 /info + 1 final /stats)
    assert data["request_count"] >= 5
    assert "/health" in data["requests_by_endpoint"]
    assert "/stats" in data["requests_by_endpoint"]
    assert "/info" in data["requests_by_endpoint"]
