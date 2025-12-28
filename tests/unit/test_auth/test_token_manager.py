"""
Unit tests for TokenManager class.
"""

import pytest
import time
from unittest.mock import Mock, patch
from config import SubAccountConfig, ServiceKey
from auth import TokenManager


class TestTokenManager:
    """Test cases for TokenManager class."""

    @pytest.fixture
    def mock_service_key(self):
        """Create a mock service key."""
        return ServiceKey(
            client_id="test_client_id",
            client_secret="test_client_secret",
            auth_url="https://test.auth.com",
            api_url="https://test.api.com",
            identity_zone_id="test_zone",
        )

    @pytest.fixture
    def mock_subaccount(self, mock_service_key):
        """Create a mock subaccount configuration."""
        subaccount = SubAccountConfig(
            name="test_subaccount",
            resource_group="test_resource_group",
            service_key_json="/path/to/service_key.json",
            model_to_deployment_urls={"model1": ["url1"], "model2": ["url2"]},
        )
        subaccount.service_key = mock_service_key
        return subaccount

    @pytest.fixture
    def token_manager(self, mock_subaccount):
        """Create a TokenManager instance."""
        return TokenManager(mock_subaccount)

    def test_init(self, token_manager, mock_subaccount):
        """Test TokenManager initialization."""
        assert token_manager.subaccount == mock_subaccount
        assert hasattr(token_manager, "_lock")

    def test_get_token_cached_valid(self, token_manager, mock_subaccount):
        """Test getting cached valid token."""
        # Set up cached token
        mock_subaccount.token_info.token = "cached_token"
        mock_subaccount.token_info.expiry = time.time() + 3600  # Valid for 1 hour

        token = token_manager.get_token()
        assert token == "cached_token"

    def test_get_token_cached_expired(self, token_manager, mock_subaccount):
        """Test getting new token when cached token is expired."""
        # Set up expired cached token
        mock_subaccount.token_info.token = "expired_token"
        mock_subaccount.token_info.expiry = time.time() - 3600  # Expired 1 hour ago

        with patch.object(
            token_manager, "_fetch_new_token", return_value="new_token"
        ) as mock_fetch:
            token = token_manager.get_token()
            assert token == "new_token"
            mock_fetch.assert_called_once()

    def test_get_token_no_cached_token(self, token_manager, mock_subaccount):
        """Test getting new token when no cached token exists."""
        # No cached token
        mock_subaccount.token_info.token = None
        mock_subaccount.token_info.expiry = 0

        with patch.object(
            token_manager, "_fetch_new_token", return_value="new_token"
        ) as mock_fetch:
            token = token_manager.get_token()
            assert token == "new_token"
            mock_fetch.assert_called_once()

    @patch("requests.post")
    def test_fetch_new_token_success(self, mock_post, token_manager, mock_subaccount):
        """Test successful token fetching."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        token = token_manager._fetch_new_token()

        assert token == "new_access_token"
        assert mock_subaccount.token_info.token == "new_access_token"
        assert mock_subaccount.token_info.expiry > time.time()

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert (
            call_args[0][0]
            == "https://test.auth.com/oauth/token?grant_type=client_credentials"
        )
        assert "Authorization" in call_args[1]["headers"]

    @patch("requests.post")
    def test_fetch_new_token_empty_token(self, mock_post, token_manager):
        """Test handling of empty token in response."""
        mock_response = Mock()
        mock_response.json.return_value = {"access_token": ""}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(ValueError, match="Fetched token is empty"):
            token_manager._fetch_new_token()

    @patch("requests.post")
    def test_fetch_new_token_timeout(self, mock_post, token_manager):
        """Test handling of timeout errors."""
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout("Connection timed out")

        with pytest.raises(TimeoutError, match="Timeout connecting to token endpoint"):
            token_manager._fetch_new_token()

    @patch("requests.post")
    def test_fetch_new_token_http_error(self, mock_post, token_manager):
        """Test handling of HTTP errors."""
        from requests.exceptions import HTTPError

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        http_error = HTTPError("400 Bad Request")
        http_error.response = mock_response
        mock_post.side_effect = http_error

        with pytest.raises(ConnectionError, match="HTTP Error 400"):
            token_manager._fetch_new_token()

    def test_fetch_new_token_no_service_key(self, token_manager, mock_subaccount):
        """Test handling when service key is not loaded."""
        mock_subaccount.service_key = None

        with pytest.raises(ValueError, match="Service key not loaded"):
            token_manager._fetch_new_token()

    def test_is_token_valid_true(self, token_manager, mock_subaccount):
        """Test token validity check when token is valid."""
        mock_subaccount.token_info.token = "valid_token"
        mock_subaccount.token_info.expiry = time.time() + 3600

        assert token_manager._is_token_valid() is True

    def test_is_token_valid_no_token(self, token_manager, mock_subaccount):
        """Test token validity check when no token exists."""
        mock_subaccount.token_info.token = None
        mock_subaccount.token_info.expiry = time.time() + 3600

        assert token_manager._is_token_valid() is False

    def test_is_token_valid_expired(self, token_manager, mock_subaccount):
        """Test token validity check when token is expired."""
        mock_subaccount.token_info.token = "expired_token"
        mock_subaccount.token_info.expiry = time.time() - 3600

        assert token_manager._is_token_valid() is False


class TestBackwardCompatibility:
    """Test backward compatibility functions."""

    @pytest.fixture
    def mock_service_key(self):
        """Create a mock service key."""
        return ServiceKey(
            client_id="test_client_id",
            client_secret="test_client_secret",
            auth_url="https://test.auth.com",
            api_url="https://test.api.com",
            identity_zone_id="test_zone",
        )

    @pytest.fixture
    def mock_subaccount(self, mock_service_key):
        """Create a mock subaccount configuration."""
        subaccount = SubAccountConfig(
            name="test_subaccount",
            resource_group="test_resource_group",
            service_key_json="/path/to/service_key.json",
            model_to_deployment_urls={"model1": ["url1"], "model2": ["url2"]},
        )
        subaccount.service_key = mock_service_key
        return subaccount
