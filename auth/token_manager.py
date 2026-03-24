"""
Token management with caching and thread-safety.

This module provides authentication token management for SAP AI Core subaccounts.
Features:
- Thread-safe token caching
- Automatic token refresh
- Per-subaccount token management
"""

import base64
import threading
import time
from logging import Logger

import requests

from config import SubAccountConfig
from utils.logging_utils import get_server_logger

logger: Logger = get_server_logger(__name__)


class TokenManager:
    """Manages authentication tokens for SAP AI Core subaccounts.

    Features:
    - Thread-safe token caching
    - Automatic token refresh
    - Per-subaccount token management
    - TLS certificate bundle support for HTTPS requests
    """

    def __init__(
        self, subaccount: SubAccountConfig, ca_cert_bundle: str | None = None
    ) -> None:
        """Initialize token manager for a subaccount.

        Args:
            subaccount: SubAccountConfig instance
            ca_cert_bundle: Optional path to CA certificate bundle for TLS verification.
                If None, requests will use its default verification.
        """
        self.subaccount = subaccount
        self.ca_cert_bundle = ca_cert_bundle
        self._lock = threading.Lock()

    def get_token(self) -> str:
        """Get valid token, refreshing if necessary.

        Returns:
            Valid authentication token

        Raises:
            ConnectionError: If token fetch fails
            ValueError: If token is empty
        """
        with self._lock:
            if self._is_token_valid():
                token: str | None = self.subaccount.token_info.token

                if token is not None:
                    return token

            return self._fetch_new_token()

    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid."""
        if not self.subaccount.token_info.token:
            return False

        now = time.time()
        return now < self.subaccount.token_info.expiry

    def invalidate_token(self) -> None:
        """Invalidate the cached token for this subaccount.

        This clears the cached token, forcing a fresh token fetch on the next call.
        Should be called when the backend returns 401 or 403 errors.
        """
        with self._lock:
            logger.info(
                f"Invalidating cached token for subaccount '{self.subaccount.name}'"
            )
            self.subaccount.token_info.token = ""
            self.subaccount.token_info.expiry = 0.0

    def _fetch_new_token(self) -> str:
        """Fetch new token from SAP AI Core with certificate validation and fallback."""
        logger.info(f"Fetching new token for subaccount '{self.subaccount.name}'")

        service_key = self.subaccount.service_key
        if not service_key:
            raise ValueError(
                f"Service key not loaded for subaccount '{self.subaccount.name}'"
            )

        auth_string = f"{service_key.client_id}:{service_key.client_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        token_url = f"{service_key.auth_url}/oauth/token?grant_type=client_credentials"
        headers = {"Authorization": f"Basic {encoded_auth}"}

        # First attempt: use configured/resolved certificate bundle
        verify = self.ca_cert_bundle if self.ca_cert_bundle else True
        return self._attempt_token_fetch(token_url, headers, verify, first_attempt=True)

    def _attempt_token_fetch(
        self, token_url: str, headers: dict, verify, first_attempt: bool = True
    ) -> str:
        """Attempt to fetch token with given verify parameter.

        Args:
            token_url: Token endpoint URL
            headers: Authorization headers
            verify: Certificate verification setting (True, False, or path)
            first_attempt: Whether this is the first attempt (used for logging)

        Returns:
            Access token

        Raises:
            ConnectionError: On authentication/connection failure
            TimeoutError: On timeout
            RuntimeError: On unexpected errors
        """
        try:
            response = requests.post(
                token_url, headers=headers, timeout=15, verify=verify
            )
            # Check HTTP status
            response.raise_for_status()

            # Populate access tokens
            token_response = response.json()
            access_token = token_response.get("access_token")

            if not access_token:
                raise ValueError("Fetched token is empty")

            # Cache token with 5-minute buffer
            expires_in = int(token_response.get("expires_in", 14400))
            self.subaccount.token_info.token = access_token
            self.subaccount.token_info.expiry = time.time() + expires_in - 300

            logger.info(f"Token fetched successfully for '{self.subaccount.name}'")
            return access_token

        except requests.exceptions.Timeout as err:
            logger.error(f"Timeout fetching token from {token_url}: {err}")
            raise TimeoutError(f"Timeout connecting to token endpoint") from err

        except requests.exceptions.HTTPError as err:
            logger.error(f"HTTP error fetching token: {err.response.status_code}")
            raise ConnectionError(f"HTTP Error {err.response.status_code}") from err

        except OSError as err:
            # Catch TLS/SSL certificate errors
            error_str = str(err).lower()
            is_cert_error = (
                "ca certificate" in error_str
                or "ssl" in error_str
                or "certificate verify failed" in error_str
            )

            if is_cert_error:
                if first_attempt and verify is not True:
                    # If first attempt with custom cert failed, retry with verify=True
                    # (allows SSL errors but may accept self-signed certs)
                    logger.warning(
                        f"Certificate validation failed with configured bundle for '{self.subaccount.name}'. "
                        f"Retrying with default verification. Error: {err}"
                    )
                    try:
                        return self._attempt_token_fetch(
                            token_url, headers, True, first_attempt=False
                        )
                    except Exception as retry_err:
                        # If retry also fails, report original error
                        logger.error(
                            f"Retry with default verification also failed for '{self.subaccount.name}': {retry_err}"
                        )
                        raise ConnectionError(
                            f"TLS certificate verification failed. "
                            f"Check ca_cert_bundle configuration or network connectivity. "
                            f"Original error: {err}"
                        ) from err
                else:
                    # Second attempt or already using default verification
                    logger.error(
                        f"TLS certificate error fetching token for '{self.subaccount.name}': {err}\n"
                        "Troubleshooting: Verify SAP AI Core auth URL is accessible and certificate is valid. "
                        "Run: python -c 'import certifi; print(certifi.where())'"
                    )
                    raise ConnectionError(
                        f"TLS certificate verification failed. "
                        f"Check ca_cert_bundle configuration or network connectivity. {err}"
                    ) from err

            logger.error(f"OS error fetching token: {err}")
            raise

        except ValueError as err:
            # Re-raise ValueError as-is (e.g., empty token)
            logger.error(f"Value error fetching token: {err}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error fetching token: {err}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {err}") from err
