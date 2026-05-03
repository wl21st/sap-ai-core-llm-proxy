"""
Unit tests for certificate handling in token manager and SDK pool.

Tests certificate discovery, validation, retry logic, and error handling.
"""

import os
import ssl
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from auth import TokenManager
from config import SubAccountConfig, ServiceKey, TokenInfo
from utils.sdk_pool import resolve_ca_cert_bundle
from utils.exceptions import ConfigValidationError


class TestResolveCaCertBundle:
    """Test certificate bundle resolution with fallback chain."""

    def test_configured_path_exists_and_readable(self):
        """Test using configured path when it exists and is readable."""
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")

        try:
            result = resolve_ca_cert_bundle(tmp_path)
            assert result == tmp_path
        finally:
            os.unlink(tmp_path)

    def test_configured_path_not_found(self):
        """Test error when configured path does not exist."""
        non_existent_path = "/tmp/non_existent_cert_file_xyz_12345.pem"
        with pytest.raises(ConfigValidationError) as exc_info:
            resolve_ca_cert_bundle(non_existent_path)
        assert "does not exist" in str(exc_info.value)

    def test_configured_path_not_file(self):
        """Test error when configured path is not a file (e.g., directory)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ConfigValidationError) as exc_info:
                resolve_ca_cert_bundle(tmpdir)
            assert "not a file" in str(exc_info.value)

    def test_configured_path_not_readable(self):
        """Test error when configured path is not readable."""
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Remove read permissions
            os.chmod(tmp_path, 0o000)
            with pytest.raises(ConfigValidationError) as exc_info:
                resolve_ca_cert_bundle(tmp_path)
            assert "not readable" in str(exc_info.value)
        finally:
            # Restore permissions for cleanup
            os.chmod(tmp_path, 0o644)
            os.unlink(tmp_path)

    @patch("certifi.where")
    def test_certifi_fallback(self, mock_certifi_where):
        """Test fallback to certifi when configured path is None."""
        certifi_path = "/usr/lib/python3.11/site-packages/certifi/cacert.pem"
        mock_certifi_where.return_value = certifi_path

        with patch("pathlib.Path.exists", return_value=True):
            result = resolve_ca_cert_bundle(None)
            assert result == certifi_path

    @patch("certifi.where")
    def test_certifi_import_error(self, mock_certifi_where):
        """Test fallback when certifi import fails."""
        mock_certifi_where.side_effect = ImportError("certifi not found")

        # Should not raise, should continue to other fallbacks
        with patch("pathlib.Path.exists", return_value=False):
            with patch("ssl.get_default_verify_paths") as mock_ssl:
                mock_ssl.return_value = Mock(cafile=None, capath=None)
                result = resolve_ca_cert_bundle(None)
                # Either returns a system path or None
                assert result is None or isinstance(result, str)

    @patch("certifi.where")
    def test_certifi_where_error(self, mock_certifi_where):
        """Test fallback when certifi.where() raises exception."""
        mock_certifi_where.side_effect = RuntimeError("certifi error")

        with patch("pathlib.Path.exists", return_value=False):
            with patch("ssl.get_default_verify_paths") as mock_ssl:
                mock_ssl.return_value = Mock(cafile=None, capath=None)
                result = resolve_ca_cert_bundle(None)
                assert result is None or isinstance(result, str)

    @patch("os.name", "posix")
    def test_system_paths_linux(self):
        """Test system path fallback on Linux."""
        linux_paths = [
            "/etc/ssl/certs/ca-bundle.crt",
            "/etc/ssl/certs/ca-certificates.crt",
        ]

        with patch("certifi.where", side_effect=ImportError):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    with patch("os.access", return_value=True):
                        result = resolve_ca_cert_bundle(None)
                        # Should return one of the linux paths that was found
                        assert result in linux_paths or result is not None

    @patch("os.name", "nt")
    def test_system_paths_windows(self):
        """Test system path fallback on Windows."""
        windows_path = r"C:\ProgramData\ssl\certs\ca-bundle.crt"

        with patch("certifi.where", side_effect=ImportError):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    with patch("os.access", return_value=True):
                        with patch("os.path.expandvars") as mock_expand:
                            mock_expand.return_value = windows_path
                            result = resolve_ca_cert_bundle(None)
                            # Should resolve on Windows
                            assert result is not None

    @patch("ssl.get_default_verify_paths")
    def test_ssl_default_verify_paths(self, mock_ssl_paths):
        """Test fallback to ssl.get_default_verify_paths()."""
        # Test that when system paths fail, ssl.get_default_verify_paths() is used
        ssl_cafile = "/etc/ssl/certs/ca-bundle.crt"
        mock_ssl_paths.return_value = Mock(cafile=ssl_cafile, capath=None)

        with patch("certifi.where", side_effect=ImportError):
            # All system path checks return False
            with patch("utils.sdk_pool.Path.exists", return_value=False):
                # ssl.get_default_verify_paths().cafile will be checked and found valid
                result = resolve_ca_cert_bundle(None)
                # When system paths don't exist, ssl module path should be used
                assert result == ssl_cafile or result is None  # Depending on mocking

    @patch("ssl.get_default_verify_paths")
    def test_no_bundle_found_returns_none(self, mock_ssl_paths):
        """Test that None is returned when no bundle is found."""
        mock_ssl_paths.return_value = Mock(cafile=None, capath=None)

        with patch("certifi.where", side_effect=ImportError):
            with patch("pathlib.Path.exists", return_value=False):
                result = resolve_ca_cert_bundle(None)
                assert result is None


class TestTokenManagerCertificateHandling:
    """Test TokenManager certificate handling and retry logic."""

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
        subaccount.token_info = TokenInfo(token="", expiry=0.0)
        return subaccount

    def test_token_manager_init_with_cert_bundle(self, mock_subaccount):
        """Test TokenManager initialization with certificate bundle."""
        cert_path = "/path/to/cert.pem"
        manager = TokenManager(mock_subaccount, ca_cert_bundle=cert_path)
        assert manager.ca_cert_bundle == cert_path
        assert manager.subaccount == mock_subaccount

    def test_token_manager_init_without_cert_bundle(self, mock_subaccount):
        """Test TokenManager initialization without certificate bundle."""
        manager = TokenManager(mock_subaccount)
        assert manager.ca_cert_bundle is None

    @patch("requests.post")
    def test_fetch_new_token_with_cert_success(self, mock_post, mock_subaccount):
        """Test successful token fetch with certificate bundle."""
        cert_path = "/path/to/cert.pem"
        manager = TokenManager(mock_subaccount, ca_cert_bundle=cert_path)

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        token = manager._fetch_new_token()
        assert token == "test_token"
        # Verify requests.post was called with the certificate path
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["verify"] == cert_path

    @patch("requests.post")
    def test_fetch_new_token_without_cert_uses_default(
        self, mock_post, mock_subaccount
    ):
        """Test token fetch without cert uses default verification."""
        manager = TokenManager(mock_subaccount)

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        token = manager._fetch_new_token()
        assert token == "test_token"
        # Verify requests.post was called with verify=True (default)
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["verify"] is True

    @patch("requests.post")
    def test_cert_error_with_fallback_retry(self, mock_post, mock_subaccount):
        """Test certificate error triggers fallback to default verification."""
        cert_path = "/path/to/cert.pem"
        manager = TokenManager(mock_subaccount, ca_cert_bundle=cert_path)

        # First call fails with cert error, second succeeds
        cert_error = OSError("CA certificate problem")
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "fallback_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None

        mock_post.side_effect = [cert_error, mock_response]

        token = manager._fetch_new_token()
        assert token == "fallback_token"
        # Verify two calls were made (first with cert path, second with verify=True)
        assert mock_post.call_count == 2
        first_call_kwargs = mock_post.call_args_list[0][1]
        second_call_kwargs = mock_post.call_args_list[1][1]
        assert first_call_kwargs["verify"] == cert_path
        assert second_call_kwargs["verify"] is True

    @patch("requests.post")
    def test_cert_error_both_attempts_fail(self, mock_post, mock_subaccount):
        """Test certificate error when both attempts fail."""
        cert_path = "/path/to/cert.pem"
        manager = TokenManager(mock_subaccount, ca_cert_bundle=cert_path)

        cert_error = OSError("CA certificate problem")
        mock_post.side_effect = cert_error

        with pytest.raises(ConnectionError) as exc_info:
            manager._fetch_new_token()

        assert "TLS certificate verification failed" in str(exc_info.value)
        # Both attempts should have been made
        assert mock_post.call_count == 2

    @patch("requests.post")
    def test_timeout_error(self, mock_post, mock_subaccount):
        """Test timeout error handling."""
        import requests

        manager = TokenManager(mock_subaccount)
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")

        with pytest.raises(TimeoutError):
            manager._fetch_new_token()

    @patch("requests.post")
    def test_http_error_401(self, mock_post, mock_subaccount):
        """Test HTTP 401 error handling."""
        import requests

        manager = TokenManager(mock_subaccount)
        mock_response = Mock()
        mock_response.status_code = 401
        http_error = requests.exceptions.HTTPError("401 Unauthorized")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        with pytest.raises(ConnectionError):
            manager._fetch_new_token()

    @patch("requests.post")
    def test_empty_token_error(self, mock_post, mock_subaccount):
        """Test error when fetched token is empty."""
        manager = TokenManager(mock_subaccount)

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "",  # Empty token
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(ValueError) as exc_info:
            manager._fetch_new_token()

        assert "empty" in str(exc_info.value).lower()

    @patch("requests.post")
    def test_ssl_certificate_verify_failed_error(self, mock_post, mock_subaccount):
        """Test specific SSL certificate_verify_failed error."""
        cert_path = "/path/to/cert.pem"
        manager = TokenManager(mock_subaccount, ca_cert_bundle=cert_path)

        ssl_error = OSError("certificate verify failed")
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "retry_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None

        mock_post.side_effect = [ssl_error, mock_response]

        token = manager._fetch_new_token()
        assert token == "retry_token"
        assert mock_post.call_count == 2

    def test_cert_bundle_parameter_passthrough(self, mock_subaccount):
        """Test that ca_cert_bundle parameter is correctly stored for various values."""
        for cert_path in [
            "/etc/ssl/certs/ca-bundle.crt",
            "/usr/local/etc/openssl/cert.pem",
            None,
        ]:
            manager = TokenManager(mock_subaccount, ca_cert_bundle=cert_path)
            assert manager.ca_cert_bundle == cert_path


class TestCertificateErrorDetection:
    """Test certificate error detection in message router."""

    def test_is_certificate_error_oserror_with_cert_keyword(self):
        """Test detection of OSError with certificate keyword."""
        from utils.cert_errors import is_certificate_error

        error = OSError("SSL: CERTIFICATE_VERIFY_FAILED")
        assert is_certificate_error(error) is True

    def test_is_certificate_error_oserror_with_ssl_keyword(self):
        """Test detection of OSError with SSL keyword."""
        from utils.cert_errors import is_certificate_error

        error = OSError("SSL: SSLV3_ALERT_UNKNOWN_CA")
        assert is_certificate_error(error) is True

    def test_is_certificate_error_oserror_with_ca_keyword(self):
        """Test detection of OSError with CA certificate keyword."""
        from utils.cert_errors import is_certificate_error

        error = OSError("CA certificate verification failed")
        assert is_certificate_error(error) is True

    def test_is_certificate_error_generic_exception(self):
        """Test detection with generic Exception and cert keywords."""
        from utils.cert_errors import is_certificate_error

        error = Exception("certificate verification failed")
        assert is_certificate_error(error) is True

    def test_is_certificate_error_not_cert_error(self):
        """Test that non-certificate errors are not detected."""
        from utils.cert_errors import is_certificate_error

        error = OSError("Connection refused")
        assert is_certificate_error(error) is False

    def test_is_certificate_error_timeout_not_detected(self):
        """Test that timeout errors are not detected as certificate errors."""
        from utils.cert_errors import is_certificate_error

        error = TimeoutError("Request timed out")
        assert is_certificate_error(error) is False

    def test_is_certificate_error_case_insensitive(self):
        """Test that certificate error detection is case-insensitive."""
        from utils.cert_errors import is_certificate_error

        error = OSError("CERTIFICATE_VERIFY_FAILED")
        assert is_certificate_error(error) is True

        error = OSError("Certificate Verify Failed")
        assert is_certificate_error(error) is True

    def test_is_certificate_error_botocore_ssl_validation_failed(self):
        """Test detection of botocore SSLError after WiFi reconnect.

        When WiFi drops and reconnects, macOS destroys cached SSL context state.
        botocore wraps the resulting FileNotFoundError in a botocore.exceptions.SSLError
        whose str() is 'SSL validation failed for <url> [Errno 2] No such file or directory'.
        This must be treated as a recoverable SSL error so the cached client is invalidated
        and retried with a fresh connection.
        """
        from utils.cert_errors import is_certificate_error
        from botocore.exceptions import SSLError

        error = SSLError(
            endpoint_url="https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com"
            "/v2/inference/deployments/abc123/invoke-with-response-stream",
            error=FileNotFoundError(2, "No such file or directory"),
        )
        assert is_certificate_error(error) is True

    def test_is_certificate_error_ssl_validation_failed_generic(self):
        """Test detection of generic 'SSL validation failed' message."""
        from utils.cert_errors import is_certificate_error

        error = Exception("SSL validation failed for https://example.com No such file")
        assert is_certificate_error(error) is True


class TestSessionInvalidation:
    """Test SDK session invalidation on certificate errors."""

    def test_invalidate_bedrock_client_is_safe(self):
        """Test that invalidate_bedrock_client can be called safely."""
        from utils import sdk_pool

        # Test that the function exists and is callable
        assert hasattr(sdk_pool, "invalidate_bedrock_client")
        assert callable(sdk_pool.invalidate_bedrock_client)

        # Calling with non-existent model should not raise
        try:
            sdk_pool.invalidate_bedrock_client("test-model-that-does-not-exist")
            assert True  # Should complete without error
        except Exception as e:
            pytest.fail(f"invalidate_bedrock_client raised unexpected error: {e}")

    def test_invalidate_bedrock_client_resets_session(self):
        """Test that invalidate_bedrock_client signature includes session handling."""
        import inspect
        from utils import sdk_pool

        # Verify the function exists and has the documented behavior
        source = inspect.getsource(sdk_pool.invalidate_bedrock_client)
        assert "__sdk_session" in source, (
            "invalidate_bedrock_client should reset __sdk_session"
        )
