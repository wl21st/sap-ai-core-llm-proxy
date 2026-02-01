import pytest
from unittest.mock import Mock, patch, MagicMock
from utils.sdk_utils import fetch_all_deployments
from config import ServiceKey


@pytest.fixture
def mock_service_key():
    return ServiceKey(
        client_id="test-client",
        client_secret="test-secret",
        auth_url="https://auth.test",
        api_url="https://api.test",
        identity_zone_id="test-zone",
    )


@patch("utils.sdk_utils.Cache")
@patch("utils.sdk_utils.AICoreV2Client")
def test_fetch_all_deployments(mock_client_cls, mock_cache_cls, mock_service_key):
    # Setup mock cache to simulate cache miss
    mock_cache = MagicMock()
    mock_cache.__enter__.return_value.get.return_value = None
    mock_cache_cls.return_value = mock_cache

    # Setup mock client
    mock_client = Mock()
    mock_client_cls.return_value = mock_client

    # Setup mock deployments response
    # Use MagicMock for deployments to allow attribute access
    mock_dep1 = MagicMock()
    mock_dep1.id = "dep-1"
    mock_dep1.deployment_url = "https://dep-1.com"
    mock_dep1.created_at = "2023-01-01"
    mock_dep1.details = {"resources": {"backend_details": {"model": {"name": "gpt-4"}}}}

    mock_dep2 = MagicMock()
    mock_dep2.id = "dep-2"
    mock_dep2.deployment_url = "https://dep-2.com"
    mock_dep2.created_at = "2023-01-02"
    # dep-2 has missing backend details
    mock_dep2.details = {}

    # Configure query return value
    mock_query_response = Mock()
    mock_query_response.resources = [mock_dep1, mock_dep2]
    mock_client.deployment.query.return_value = mock_query_response

    # Run function
    results = fetch_all_deployments(mock_service_key)

    # Verify
    assert len(results) == 2

    assert results[0]["id"] == "dep-1"
    assert results[0]["model_name"] == "gpt-4"
    assert results[0]["url"] == "https://dep-1.com"

    assert results[1]["id"] == "dep-2"
    assert results[1]["model_name"] is None

    # Verify calls
    mock_client_cls.assert_called_once()
    mock_client.deployment.query.assert_called_once_with(resource_group="default")
