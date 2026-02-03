import pytest
import threading
from unittest.mock import Mock, patch, MagicMock
import requests
from diskcache import Cache

from utils.sdk_utils import (
    fetch_all_deployments,
    fetch_deployment_url,
    extract_deployment_id,
    _clear_client_caches_for_testing,
)
from config.config_models import ServiceKey
from utils.exceptions import (
    DeploymentFetchError,
    CacheError,
    AuthenticationError,
    DeploymentResolutionError,
)
from utils.error_ids import ErrorIDs


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
def test_fetch_all_deployments_basic(mock_client_cls, mock_cache_cls, mock_service_key):
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


# ============ Priority 10: fetch_all_deployments() Error Handling Tests ============


def test_fetch_all_deployments_authentication_failure(mock_service_key):
    """Test that authentication failures are raised with proper error ID."""
    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_get_client.side_effect = AuthenticationError("Invalid credentials")

        with pytest.raises(DeploymentFetchError) as exc_info:
            fetch_all_deployments(
                service_key=mock_service_key, resource_group="default"
            )

        assert (
            "credentials" in str(exc_info.value).lower()
            or "authentication" in str(exc_info.value).lower()
        )


def test_fetch_all_deployments_authentication_failure_logging(mock_service_key, caplog):
    """Verify authentication failures are logged with error ID."""
    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_get_client.side_effect = AuthenticationError("Invalid credentials")

        with pytest.raises(DeploymentFetchError):
            fetch_all_deployments(
                service_key=mock_service_key, resource_group="default"
            )

    # Verify error message contains relevant information
    assert any(
        "credentials" in record.message.lower()
        or "authentication" in record.message.lower()
        for record in caplog.records
    )


def test_fetch_all_deployments_network_timeout(mock_service_key):
    """Test handling of network timeouts during deployment query."""
    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.side_effect = requests.exceptions.Timeout(
            "Connection timed out after 30s"
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(DeploymentFetchError) as exc_info:
            fetch_all_deployments(
                service_key=mock_service_key, resource_group="default"
            )

        assert "timed out" in str(exc_info.value).lower()


def test_fetch_all_deployments_connection_error(mock_service_key):
    """Test handling of network connection errors."""
    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.side_effect = requests.exceptions.ConnectionError(
            "Failed to establish connection"
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(DeploymentFetchError) as exc_info:
            fetch_all_deployments(
                service_key=mock_service_key, resource_group="default"
            )

        assert (
            "network" in str(exc_info.value).lower()
            or "connection" in str(exc_info.value).lower()
        )


def test_fetch_all_deployments_malformed_response(mock_service_key):
    """Test handling of unexpected deployment response structure."""
    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_client = Mock()
        # Return unexpected structure (e.g., dict instead of list)
        mock_query_response = Mock()
        mock_query_response.resources = {"error": "unexpected"}
        mock_client.deployment.query.return_value = mock_query_response
        mock_get_client.return_value = mock_client

        # This should either raise DeploymentFetchError or handle gracefully
        with pytest.raises((DeploymentFetchError, TypeError, AttributeError)):
            fetch_all_deployments(
                service_key=mock_service_key, resource_group="default"
            )


def test_fetch_all_deployments_cache_write_failure(mock_service_key):
    """Test behavior when cache.set() fails."""
    mock_deployment = MagicMock()
    mock_deployment.id = "d123"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d123"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"
    mock_deployment.details = {}

    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_client = Mock()
        mock_query_response = Mock()
        mock_query_response.resources = [mock_deployment]
        mock_client.deployment.query.return_value = mock_query_response
        mock_get_client.return_value = mock_client

        with patch("utils.sdk_utils.Cache") as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            mock_cache.get.return_value = None
            # Simulate cache write failure
            mock_cache.set.side_effect = OSError("Disk full")
            mock_cache_class.return_value = mock_cache

            # Should NOT raise - data should still be returned despite cache failure
            result = fetch_all_deployments(
                service_key=mock_service_key,
                resource_group="default",
                force_refresh=True,
            )

            # Verify data was still returned
            assert len(result) == 1
            assert result[0]["id"] == "d123"


# ============ Priority 9: Cache Behavior Tests ============


def test_fetch_all_deployments_cache_hit(mock_service_key):
    """Test that cached data is returned and API not called."""
    cached_data = [
        {
            "id": "d123",
            "url": "https://api.test.com/deployments/d123",
            "created_at": "2026-01-01T00:00:00Z",
            "model_name": "claude-4.5-sonnet",
        }
    ]

    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        with patch("utils.sdk_utils.Cache") as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            # Simulate cache hit
            mock_cache.get.return_value = cached_data
            mock_cache.expire.return_value = 604800  # 7 days in seconds
            mock_cache_class.return_value = mock_cache

            result = fetch_all_deployments(
                service_key=mock_service_key,
                resource_group="default",
            )

            # Verify API was NOT called
            mock_get_client.assert_not_called()

            # Verify cached data was returned
            assert result == cached_data
            assert len(result) == 1
            assert result[0]["id"] == "d123"


def test_fetch_all_deployments_cache_miss(mock_service_key):
    """Test that cache miss triggers fresh API fetch."""
    mock_deployment = MagicMock()
    mock_deployment.id = "d123"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d123"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"
    mock_deployment.details = {}

    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_client = Mock()
        mock_query_response = Mock()
        mock_query_response.resources = [mock_deployment]
        mock_client.deployment.query.return_value = mock_query_response
        mock_get_client.return_value = mock_client

        with patch("utils.sdk_utils.Cache") as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            # Simulate cache miss
            mock_cache.get.return_value = None
            mock_cache_class.return_value = mock_cache

            result = fetch_all_deployments(
                service_key=mock_service_key, resource_group="default"
            )

            # Verify API WAS called
            mock_get_client.assert_called_once()
            mock_client.deployment.query.assert_called_once()

            # Verify fresh data was cached
            mock_cache.set.assert_called_once()

            # Verify data was returned
            assert len(result) == 1
            assert result[0]["id"] == "d123"


def test_fetch_all_deployments_force_refresh(mock_service_key):
    """Test that force_refresh=True bypasses cache."""
    mock_deployment = MagicMock()
    mock_deployment.id = "d999"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d999"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"
    mock_deployment.details = {}

    cached_data = [{"id": "d123", "url": "https://old-url.com"}]

    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_client = Mock()
        mock_query_response = Mock()
        mock_query_response.resources = [mock_deployment]
        mock_client.deployment.query.return_value = mock_query_response
        mock_get_client.return_value = mock_client

        with patch("utils.sdk_utils.Cache") as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            mock_cache.get.return_value = cached_data
            mock_cache_class.return_value = mock_cache

            result = fetch_all_deployments(
                service_key=mock_service_key,
                resource_group="default",
                force_refresh=True,  # Force refresh
            )

            # Verify API WAS called despite cache hit
            mock_get_client.assert_called_once()

            # Verify fresh data was returned (not cached)
            assert len(result) == 1
            assert result[0]["id"] == "d999"
            assert result[0]["id"] != cached_data[0]["id"]


def test_fetch_all_deployments_cache_expiry(mock_service_key):
    """Test cache expiry timestamp is correctly calculated."""
    mock_deployment = MagicMock()
    mock_deployment.id = "d123"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d123"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"
    mock_deployment.details = {}

    with patch("utils.sdk_utils.AIAPIV2Client") as mock_get_client:
        mock_client = Mock()
        mock_query_response = Mock()
        mock_query_response.resources = [mock_deployment]
        mock_client.deployment.query.return_value = mock_query_response
        mock_get_client.return_value = mock_client

        with patch("utils.sdk_utils.Cache") as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            mock_cache.get.return_value = None
            mock_cache_class.return_value = mock_cache

            fetch_all_deployments(
                service_key=mock_service_key, resource_group="default"
            )

            # Verify cache.set was called with expiry
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args

            # Check expiry parameter (should be 7 days from now)
            if "expire" in call_args.kwargs:
                expire_seconds = call_args.kwargs["expire"]
                # Should be approximately 7 days (604800 seconds)
                assert 604700 <= expire_seconds <= 604900
            elif len(call_args.args) >= 3:
                # Positional argument
                expire_seconds = call_args.args[2]
                assert 604700 <= expire_seconds <= 604900


# ============ Priority 8: extract_deployment_id() Edge Cases ============


def test_extract_deployment_id_empty_string():
    """Test that empty string raises ValueError."""
    with pytest.raises(DeploymentResolutionError) as exc_info:
        extract_deployment_id("")

    assert (
        "empty" in str(exc_info.value).lower()
        or "invalid" in str(exc_info.value).lower()
    )


def test_extract_deployment_id_none():
    """Test that None input raises appropriate error."""
    with pytest.raises(
        (DeploymentResolutionError, TypeError, AttributeError)
    ) as exc_info:
        extract_deployment_id(None)  # type: ignore

    # Should clearly indicate invalid input
    assert exc_info.type in (DeploymentResolutionError, TypeError, AttributeError)


def test_extract_deployment_id_no_deployments_path():
    """Test URL without /deployments/ path."""
    url = "https://api.ai.com/v2/inference"

    with pytest.raises(ValueError) as exc_info:
        extract_deployment_id(url)

    assert "deployment" in str(exc_info.value).lower()


def test_extract_deployment_id_malformed_path():
    """Test URL with malformed path structure."""
    urls = [
        "https://api.ai.com/v2/deployments",  # No ID after deployments
        "https://api.ai.com/deployments/",  # Trailing slash, no ID
        "https://api.ai.com/v2/inference/deployments",  # deployments but no ID
    ]

    for url in urls:
        with pytest.raises(ValueError) as exc_info:
            extract_deployment_id(url)

        assert (
            "deployment" in str(exc_info.value).lower()
            or "invalid" in str(exc_info.value).lower()
        )


def test_extract_deployment_id_with_query_params():
    """Test URL with query parameters extracts correct ID."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc?version=1&format=json"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    # Verify query params are NOT included
    assert "?" not in deployment_id
    assert "version" not in deployment_id


def test_extract_deployment_id_with_fragment():
    """Test URL with fragment extracts correct ID."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc#metadata"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    # Verify fragment is NOT included
    assert "#" not in deployment_id
    assert "metadata" not in deployment_id


def test_extract_deployment_id_with_trailing_slash():
    """Test URL with trailing slash after ID."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc/"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    # Verify trailing slash is removed
    assert not deployment_id.endswith("/")


def test_extract_deployment_id_with_query_and_fragment():
    """Test URL with both query parameters and fragment."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc?v=1#section"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    assert "?" not in deployment_id
    assert "#" not in deployment_id


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
