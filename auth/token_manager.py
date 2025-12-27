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
    TODO: Create instance with the SubAccountConfig as it is 1-1 mapping relationship
    """

    def __init__(self, subaccount: SubAccountConfig) -> None:
        """Initialize token manager for a subaccount.

        Args:
            subaccount: SubAccountConfig instance
        """
        self.subaccount = subaccount
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

    def _fetch_new_token(self) -> str:
        """Fetch new token from SAP AI Core."""
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

        try:
            response = requests.post(token_url, headers=headers, timeout=15)
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
            logger.error(f"Timeout fetching token: {err}")
            raise TimeoutError(f"Timeout connecting to token endpoint") from err

        except requests.exceptions.HTTPError as err:
            logger.error(f"HTTP error fetching token: {err.response.status_code}")
            raise ConnectionError(f"HTTP Error {err.response.status_code}") from err

        except ValueError as err:
            # Re-raise ValueError as-is (e.g., empty token)
            logger.error(f"Value error fetching token: {err}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error fetching token: {err}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {err}") from err
