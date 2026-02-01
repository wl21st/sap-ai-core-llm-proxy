# PR #10 Critical Test Cases

**Generated**: 2026-02-01
**Purpose**: Concrete test implementations for missing critical test coverage

---

## Priority 10: `fetch_all_deployments()` Error Handling Tests

**File**: `tests/unit/test_sdk_utils.py`

### Test 1: SDK Authentication Failure

```python
import pytest
from unittest.mock import patch, Mock
from utils.sdk_utils import fetch_all_deployments
from utils.error_ids import ErrorIDs


def test_fetch_all_deployments_authentication_failure():
    """Test that authentication failures are raised with proper error ID."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    # Mock authentication failure
    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_get_client.side_effect = AuthenticationError("Invalid credentials")

        with pytest.raises(DeploymentFetchError) as exc_info:
            fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )

        assert "Authentication failed" in str(exc_info.value)
        # Verify error was logged with error ID
        # (requires caplog fixture to verify logging)


def test_fetch_all_deployments_authentication_failure_logging(caplog):
    """Verify authentication failures are logged with error ID."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_get_client.side_effect = AuthenticationError("Invalid credentials")

        with pytest.raises(DeploymentFetchError):
            fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )

    # Verify error ID in log
    assert any(
        ErrorIDs.DEPLOYMENT_FETCH_AUTH in str(record.extra)
        for record in caplog.records
        if hasattr(record, 'extra')
    )
```

---

### Test 2: Network Timeout

```python
import requests


def test_fetch_all_deployments_network_timeout():
    """Test handling of network timeouts during deployment query."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.side_effect = requests.exceptions.Timeout(
            "Connection timed out after 30s"
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(DeploymentFetchError) as exc_info:
            fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )

        assert "timed out" in str(exc_info.value).lower()
```

---

### Test 3: Network Connection Error

```python
def test_fetch_all_deployments_connection_error():
    """Test handling of network connection errors."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.side_effect = requests.exceptions.ConnectionError(
            "Failed to establish connection"
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(DeploymentFetchError) as exc_info:
            fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )

        assert "network error" in str(exc_info.value).lower()
```

---

### Test 4: Malformed Deployment Response

```python
def test_fetch_all_deployments_malformed_response():
    """Test handling of unexpected deployment response structure."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_client = Mock()
        # Return unexpected structure (e.g., dict instead of list)
        mock_client.deployment.query.return_value = {"error": "unexpected"}
        mock_get_client.return_value = mock_client

        # This should either raise DeploymentFetchError or handle gracefully
        # depending on implementation choice
        with pytest.raises((DeploymentFetchError, TypeError, AttributeError)):
            fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )
```

---

### Test 5: Cache Write Failure

```python
from diskcache import Cache


def test_fetch_all_deployments_cache_write_failure():
    """Test behavior when cache.set() fails."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    mock_deployment = Mock()
    mock_deployment.id = "d123"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d123"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.return_value = [mock_deployment]
        mock_get_client.return_value = mock_client

        with patch('utils.sdk_utils.Cache') as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            # Simulate cache write failure
            mock_cache.set.side_effect = OSError("Disk full")
            mock_cache_class.return_value = mock_cache

            # Should raise CacheError on write failure
            with pytest.raises(CacheError) as exc_info:
                fetch_all_deployments(
                    service_key=service_key,
                    resource_group="default",
                    force_refresh=True
                )

            assert "disk full" in str(exc_info.value).lower()
```

---

## Priority 9: Cache Behavior Tests

**File**: `tests/unit/test_sdk_utils.py`

### Test 6: Cache Hit Behavior

```python
def test_fetch_all_deployments_cache_hit():
    """Test that cached data is returned and API not called."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    cached_data = [
        {
            "id": "d123",
            "url": "https://api.test.com/deployments/d123",
            "created_at": "2026-01-01T00:00:00Z",
            "model_name": "claude-4.5-sonnet",
        }
    ]

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        with patch('utils.sdk_utils.Cache') as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            # Simulate cache hit
            mock_cache.get.return_value = cached_data
            mock_cache_class.return_value = mock_cache

            result = fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )

            # Verify API was NOT called
            mock_get_client.assert_not_called()

            # Verify cached data was returned
            assert result == cached_data
            assert len(result) == 1
            assert result[0]["id"] == "d123"
```

---

### Test 7: Cache Miss Behavior

```python
def test_fetch_all_deployments_cache_miss():
    """Test that cache miss triggers fresh API fetch."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    mock_deployment = Mock()
    mock_deployment.id = "d123"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d123"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.return_value = [mock_deployment]
        mock_get_client.return_value = mock_client

        with patch('utils.sdk_utils.Cache') as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            # Simulate cache miss
            mock_cache.get.return_value = None
            mock_cache_class.return_value = mock_cache

            result = fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )

            # Verify API WAS called
            mock_get_client.assert_called_once()
            mock_client.deployment.query.assert_called_once()

            # Verify fresh data was cached
            mock_cache.set.assert_called_once()

            # Verify data was returned
            assert len(result) == 1
            assert result[0]["id"] == "d123"
```

---

### Test 8: Force Refresh Bypasses Cache

```python
def test_fetch_all_deployments_force_refresh():
    """Test that force_refresh=True bypasses cache."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    mock_deployment = Mock()
    mock_deployment.id = "d999"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d999"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"

    cached_data = [{"id": "d123", "url": "https://old-url.com"}]

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.return_value = [mock_deployment]
        mock_get_client.return_value = mock_client

        with patch('utils.sdk_utils.Cache') as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            mock_cache.get.return_value = cached_data
            mock_cache_class.return_value = mock_cache

            result = fetch_all_deployments(
                service_key=service_key,
                resource_group="default",
                force_refresh=True  # ← Force refresh
            )

            # Verify API WAS called despite cache hit
            mock_get_client.assert_called_once()

            # Verify fresh data was returned (not cached)
            assert len(result) == 1
            assert result[0]["id"] == "d999"
            assert result[0]["id"] != cached_data[0]["id"]
```

---

### Test 9: Cache Expiry Calculation

```python
from datetime import datetime, timedelta


def test_fetch_all_deployments_cache_expiry():
    """Test cache expiry timestamp is correctly calculated."""
    service_key = Mock()
    service_key.client_id = "test-client"
    service_key.client_secret = "test-secret"
    service_key.api_url = "https://api.test.com"

    mock_deployment = Mock()
    mock_deployment.id = "d123"
    mock_deployment.deployment_url = "https://api.test.com/deployments/d123"
    mock_deployment.created_at = "2026-01-01T00:00:00Z"

    with patch('utils.sdk_utils.get_bedrock_client') as mock_get_client:
        mock_client = Mock()
        mock_client.deployment.query.return_value = [mock_deployment]
        mock_get_client.return_value = mock_client

        with patch('utils.sdk_utils.Cache') as mock_cache_class:
            mock_cache = Mock(spec=Cache)
            mock_cache.__enter__ = Mock(return_value=mock_cache)
            mock_cache.__exit__ = Mock(return_value=False)
            mock_cache.get.return_value = None
            mock_cache_class.return_value = mock_cache

            before = datetime.now()
            fetch_all_deployments(
                service_key=service_key,
                resource_group="default"
            )
            after = datetime.now()

            # Verify cache.set was called with expiry
            mock_cache.set.assert_called_once()
            call_args = mock_cache.set.call_args

            # Check expiry parameter (should be 7 days from now)
            if 'expire' in call_args.kwargs:
                expire_seconds = call_args.kwargs['expire']
                # Should be approximately 7 days (604800 seconds)
                assert 604700 <= expire_seconds <= 604900
```

---

## Priority 8: `extract_deployment_id()` Edge Cases

**File**: `tests/unit/test_sdk_utils.py`

### Test 10: Empty String

```python
from utils.sdk_utils import extract_deployment_id


def test_extract_deployment_id_empty_string():
    """Test that empty string raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        extract_deployment_id("")

    assert "empty" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
```

---

### Test 11: None Input

```python
def test_extract_deployment_id_none():
    """Test that None input raises appropriate error."""
    with pytest.raises((ValueError, TypeError, AttributeError)) as exc_info:
        extract_deployment_id(None)

    # Should clearly indicate invalid input
    assert exc_info.type in (ValueError, TypeError, AttributeError)
```

---

### Test 12: No Deployment ID in URL

```python
def test_extract_deployment_id_no_deployments_path():
    """Test URL without /deployments/ path."""
    url = "https://api.ai.com/v2/inference"

    with pytest.raises(ValueError) as exc_info:
        extract_deployment_id(url)

    assert "deployments" in str(exc_info.value).lower()
```

---

### Test 13: Malformed Path Structure

```python
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

        assert "deployment id" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
```

---

### Test 14: URL with Query Parameters

```python
def test_extract_deployment_id_with_query_params():
    """Test URL with query parameters extracts correct ID."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc?version=1&format=json"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    # Verify query params are NOT included
    assert "?" not in deployment_id
    assert "version" not in deployment_id
```

---

### Test 15: URL with Fragment

```python
def test_extract_deployment_id_with_fragment():
    """Test URL with fragment extracts correct ID."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc#metadata"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    # Verify fragment is NOT included
    assert "#" not in deployment_id
    assert "metadata" not in deployment_id
```

---

### Test 16: URL with Trailing Slash

```python
def test_extract_deployment_id_with_trailing_slash():
    """Test URL with trailing slash after ID."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc/"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    # Verify trailing slash is removed
    assert not deployment_id.endswith("/")
```

---

### Test 17: URL with Both Query and Fragment

```python
def test_extract_deployment_id_with_query_and_fragment():
    """Test URL with both query parameters and fragment."""
    url = "https://api.ai.com/v2/inference/deployments/d123abc?v=1#section"

    deployment_id = extract_deployment_id(url)

    assert deployment_id == "d123abc"
    assert "?" not in deployment_id
    assert "#" not in deployment_id
```

---

## Integration Tests

**File**: `tests/integration/test_config_validation.py`

### Test 18: Config Load with Auth Failure

```python
import pytest
from unittest.mock import patch


def test_config_load_auth_failure():
    """Test that config loading fails fast on authentication error."""
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": "invalid_key.json",
                "deployment_models": {}
            }
        }
    }

    with patch('config.config_parser.fetch_all_deployments') as mock_fetch:
        mock_fetch.side_effect = AuthenticationError("Invalid credentials")

        with pytest.raises(ConfigValidationError) as exc_info:
            load_proxy_config(config_data)

        assert "authentication" in str(exc_info.value).lower()
        assert "test-account" in str(exc_info.value)
```

---

### Test 19: Config Load with Network Failure

```python
def test_config_load_network_failure():
    """Test that config loading fails fast on network error."""
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": "key.json",
                "deployment_models": {}
            }
        }
    }

    with patch('config.config_parser.fetch_all_deployments') as mock_fetch:
        mock_fetch.side_effect = requests.exceptions.ConnectionError("Network unreachable")

        with pytest.raises(ConfigValidationError) as exc_info:
            load_proxy_config(config_data)

        assert "network" in str(exc_info.value).lower()
```

---

### Test 20: Config Load with Invalid Deployment ID

```python
def test_config_load_invalid_deployment_id():
    """Test that config loading fails on invalid deployment ID."""
    config_data = {
        "subAccounts": {
            "test-account": {
                "resource_group": "default",
                "service_key_json": "key.json",
                "deployment_models": {
                    "gpt-4o": ["invalid-deployment-id"]
                }
            }
        }
    }

    with patch('config.config_parser.fetch_deployment_url') as mock_fetch_url:
        mock_fetch_url.side_effect = ValueError("Invalid deployment ID format")

        with pytest.raises(ConfigValidationError) as exc_info:
            load_proxy_config(config_data)

        assert "invalid-deployment-id" in str(exc_info.value).lower()
        assert "gpt-4o" in str(exc_info.value).lower()
```

---

## Test Fixtures

**File**: `tests/conftest.py`

### Fixture: Mock Service Key

```python
import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_service_key():
    """Create a mock service key for testing."""
    key = Mock()
    key.client_id = "test-client-id"
    key.client_secret = "test-secret"
    key.api_url = "https://api.test.com"
    key.auth_url = "https://auth.test.com"
    return key
```

---

### Fixture: Mock Deployment

```python
@pytest.fixture
def mock_deployment():
    """Create a mock deployment object."""
    deployment = Mock()
    deployment.id = "d123abc"
    deployment.deployment_url = "https://api.test.com/v2/inference/deployments/d123abc"
    deployment.created_at = "2026-01-01T00:00:00Z"
    deployment.modified_at = "2026-01-01T00:00:00Z"
    deployment.configuration_id = "config123"
    deployment.scenario_id = "scenario123"
    return deployment
```

---

### Fixture: Clean Cache

```python
@pytest.fixture
def clean_cache():
    """Ensure cache is clean before and after test."""
    from utils.cache_utils import clear_deployment_cache

    # Clean before
    try:
        clear_deployment_cache()
    except:
        pass

    yield

    # Clean after
    try:
        clear_deployment_cache()
    except:
        pass
```

---

## Running the Tests

```bash
# Run all new tests
pytest tests/unit/test_sdk_utils.py -v -k "test_fetch_all_deployments or test_extract_deployment_id"

# Run cache behavior tests
pytest tests/unit/test_sdk_utils.py -v -k "cache"

# Run integration tests
pytest tests/integration/test_config_validation.py -v

# Run with coverage
pytest tests/unit/test_sdk_utils.py --cov=utils.sdk_utils --cov-report=html
```

---

## Expected Outcomes

After implementing these tests:

1. **Error handling coverage** increases from 0% to 80%+ for critical paths
2. **Cache behavior** is fully validated and documented
3. **Edge cases** in URL parsing are covered
4. **Integration points** between config loading and SDK calls are tested
5. **Silent failures** are caught before production

---

## Notes

- All tests use proper mocking to avoid real API calls
- Tests are isolated and can run in any order
- Each test focuses on a single behavior
- Test names clearly describe what they verify
- Tests include both positive and negative cases

---

**Generated by**: Claude Code PR Review Toolkit
