"""
Token management with caching and thread-safety.

This module provides authentication token management for SAP AI Core subaccounts.
Features:
- Thread-safe token caching
- Automatic token refresh
- Per-subaccount token management
"""

import logging
import time
import base64
import threading
from typing import Optional

import requests

from config import SubAccountConfig


class TokenManager:
    """Manages authentication tokens for SAP AI Core subaccounts.

    Features:
    - Thread-safe token caching
    - Automatic token refresh
    - Per-subaccount token management
    """

    def __init__(self, subaccount: SubAccountConfig):
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
                token = self.subaccount.token_info.token
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
        logging.info(f"Fetching new token for subaccount '{self.subaccount.name}'")

        service_key = self.subaccount.service_key
        if not service_key:
            raise ValueError(f"Service key not loaded for subaccount '{self.subaccount.name}'")

        auth_string = f"{service_key.clientid}:{service_key.clientsecret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        token_url = f"{service_key.url}/oauth/token?grant_type=client_credentials"
        headers = {"Authorization": f"Basic {encoded_auth}"}

        try:
            response = requests.post(token_url, headers=headers, timeout=15)
            response.raise_for_status()

            token_data = response.json()
            new_token = token_data.get('access_token')

            if not new_token:
                raise ValueError("Fetched token is empty")

            # Cache token with 5-minute buffer
            expires_in = int(token_data.get('expires_in', 14400))
            self.subaccount.token_info.token = new_token
            self.subaccount.token_info.expiry = time.time() + expires_in - 300

            logging.info(f"Token fetched successfully for '{self.subaccount.name}'")
            return new_token

        except requests.exceptions.Timeout as err:
            logging.error(f"Timeout fetching token: {err}")
            raise TimeoutError(f"Timeout connecting to token endpoint") from err

        except requests.exceptions.HTTPError as err:
            logging.error(f"HTTP error fetching token: {err.response.status_code}")
            raise ConnectionError(f"HTTP Error {err.response.status_code}") from err

        except ValueError as err:
            # Re-raise ValueError as-is (e.g., empty token)
            logging.error(f"Value error fetching token: {err}")
            raise
        except Exception as err:
            logging.error(f"Unexpected error fetching token: {err}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {err}") from err


# Backward compatible function
def fetch_token(subaccount_name: str, proxy_config) -> str:
    """Backward compatible token fetch function.

    Args:
        subaccount_name: Name of subaccount
        proxy_config: Global ProxyConfig instance

    Returns:
        Valid authentication token
        
    Raises:
        ValueError: If subaccount is not found or service key is missing
        ConnectionError: If there's a network issue during token fetch
        TimeoutError: If token fetch times out
        RuntimeError: For unexpected errors
    """
    import warnings
    warnings.warn("fetch_token() is deprecated, use TokenManager", DeprecationWarning, stacklevel=2)

    # Check if subaccount exists (backward compatibility with old error message)
    if subaccount_name not in proxy_config.subaccounts:
        raise ValueError(f"SubAccount '{subaccount_name}' not found in configuration")
    
    subaccount = proxy_config.subaccounts[subaccount_name]
    
    # Check if service key is loaded (backward compatibility)
    if not subaccount.service_key:
        raise ValueError(f"Service key not loaded for subAccount '{subaccount_name}'")
    
    manager = TokenManager(subaccount)
    
    try:
        return manager.get_token()
    except ValueError as err:
        # Wrap ValueError in RuntimeError for backward compatibility with old behavior
        # Old code: raise RuntimeError(f"Unexpected error processing token response...")
        raise RuntimeError(f"Unexpected error processing token response for '{subaccount_name}': {err}") from err