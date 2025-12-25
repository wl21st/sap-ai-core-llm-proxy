"""
Helper functions for backward compatibility with old test API.

These functions wrap the new class-based auth system to maintain
compatibility with existing tests.
"""

from auth import TokenManager, RequestValidator
from config import ProxyConfig


def fetch_token(subaccount_name: str, proxy_config: ProxyConfig) -> str:
    """
    Fetch token for a subaccount (backward compatibility wrapper).

    Args:
        subaccount_name: Name of the subaccount
        proxy_config: ProxyConfig instance

    Returns:
        Authentication token

    Raises:
        ValueError: If subaccount not found
        ConnectionError: If token fetch fails
        TimeoutError: If connection times out
        RuntimeError: For other token processing errors
    """
    if subaccount_name not in proxy_config.subaccounts:
        raise ValueError(f"SubAccount {subaccount_name} not found in configuration")

    subaccount = proxy_config.subaccounts[subaccount_name]
    token_manager = TokenManager(subaccount)

    try:
        return token_manager.get_token()
    except Exception as e:
        # Re-raise with appropriate error type for backward compatibility
        error_msg = str(e).lower()
        if "timeout" in error_msg or "timed out" in error_msg:
            raise TimeoutError(f"Timeout connecting to token server: {e}") from e
        elif "http error" in error_msg or "httperror" in error_msg:
            raise ConnectionError(f"HTTP Error fetching token: {e}") from e
        elif "empty" in error_msg or "token is required" in error_msg:
            raise RuntimeError(
                f"Unexpected error processing token response: {e}"
            ) from e
        else:
            raise


def verify_request_token(request, proxy_config: ProxyConfig) -> bool:
    """
    Verify request token (backward compatibility wrapper).

    Args:
        request: Flask request object
        proxy_config: ProxyConfig instance

    Returns:
        True if token is valid or no auth configured, False otherwise
    """
    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    return validator.validate(request)
