import pytest
import threading
from unittest.mock import Mock, patch, MagicMock
from utils.sdk_utils import (
    fetch_all_deployments,
    fetch_deployment_url,
    _clear_client_caches_for_testing,
)
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


@pytest.fixture(autouse=True)
def clear_client_caches():
    """Clear SDK client caches before and after each test."""
    _clear_client_caches_for_testing()
    yield
    _clear_client_caches_for_testing()


@patch("utils.sdk_utils.Cache")
@patch("utils.sdk_utils.AIAPIV2Client")
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
    mock_client.deployment.query.assert_called_once_with()


@patch("utils.sdk_utils.AIAPIV2Client")
def test_fetch_all_deployments_singleton(mock_client_cls, mock_service_key):
    """Test that AIAPIV2Client is reused across multiple calls."""
    mock_client = Mock()
    mock_client_cls.return_value = mock_client

    # Setup mock response
    mock_query_response = Mock()
    mock_query_response.resources = []
    mock_client.deployment.query.return_value = mock_query_response

    # Call function twice with same credentials
    with patch("utils.sdk_utils.Cache") as mock_cache_cls:
        mock_cache = MagicMock()
        mock_cache.__enter__.return_value.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        fetch_all_deployments(mock_service_key, force_refresh=True)
        fetch_all_deployments(mock_service_key, force_refresh=True)

    # Client should only be created once (singleton pattern)
    assert mock_client_cls.call_count == 1


@patch("utils.sdk_utils.AICoreV2Client")
def test_fetch_deployment_url_singleton(mock_client_cls, mock_service_key):
    """Test that AICoreV2Client is reused across multiple calls."""
    mock_client = Mock()
    mock_client_cls.return_value = mock_client

    # Setup mock response
    mock_deployment = Mock()
    mock_deployment.deployment_url = "https://test-deployment.com"
    mock_client.deployment.get.return_value = mock_deployment

    # Call function twice with same credentials
    fetch_deployment_url(mock_service_key, "dep-1")
    fetch_deployment_url(mock_service_key, "dep-2")

    # Client should only be created once (singleton pattern)
    assert mock_client_cls.call_count == 1


@patch("utils.sdk_utils.AIAPIV2Client")
def test_fetch_all_deployments_different_resource_groups(
    mock_client_cls, mock_service_key
):
    """Test that different resource groups create separate client instances."""
    mock_client = Mock()
    mock_client_cls.return_value = mock_client

    # Setup mock response
    mock_query_response = Mock()
    mock_query_response.resources = []
    mock_client.deployment.query.return_value = mock_query_response

    # Call function with different resource groups
    with patch("utils.sdk_utils.Cache") as mock_cache_cls:
        mock_cache = MagicMock()
        mock_cache.__enter__.return_value.get.return_value = None
        mock_cache_cls.return_value = mock_cache

        fetch_all_deployments(mock_service_key, resource_group="default", force_refresh=True)
        fetch_all_deployments(mock_service_key, resource_group="production", force_refresh=True)

    # Should create two separate clients (one per resource group)
    assert mock_client_cls.call_count == 2


@patch("utils.sdk_utils.AIAPIV2Client")
def test_fetch_all_deployments_thread_safety(mock_client_cls, mock_service_key):
    """Test that client caching is thread-safe."""
    mock_client = Mock()
    mock_client_cls.return_value = mock_client

    # Setup mock response
    mock_query_response = Mock()
    mock_query_response.resources = []
    mock_client.deployment.query.return_value = mock_query_response

    # Track how many times client was created
    call_count = []

    def track_calls(*args, **kwargs):
        call_count.append(1)
        return mock_client

    mock_client_cls.side_effect = track_calls

    # Run multiple threads calling the same function
    threads = []
    num_threads = 10

    def worker():
        with patch("utils.sdk_utils.Cache") as mock_cache_cls:
            mock_cache = MagicMock()
            mock_cache.__enter__.return_value.get.return_value = None
            mock_cache_cls.return_value = mock_cache
            fetch_all_deployments(mock_service_key, force_refresh=True)

    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Despite 10 threads, client should only be created once due to thread-safe singleton
    assert len(call_count) == 1


@patch("utils.sdk_utils.AICoreV2Client")
def test_fetch_deployment_url_thread_safety(mock_client_cls, mock_service_key):
    """Test that AICoreV2Client caching is thread-safe."""
    mock_client = Mock()
    mock_client_cls.return_value = mock_client

    # Setup mock response
    mock_deployment = Mock()
    mock_deployment.deployment_url = "https://test-deployment.com"
    mock_client.deployment.get.return_value = mock_deployment

    # Track how many times client was created
    call_count = []

    def track_calls(*args, **kwargs):
        call_count.append(1)
        return mock_client

    mock_client_cls.side_effect = track_calls

    # Run multiple threads calling the same function
    threads = []
    num_threads = 10

    def worker(dep_id):
        fetch_deployment_url(mock_service_key, dep_id)

    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(f"dep-{i}",))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Despite 10 threads, client should only be created once due to thread-safe singleton
    assert len(call_count) == 1
