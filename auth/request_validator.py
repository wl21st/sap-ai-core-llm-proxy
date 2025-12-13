"""
Request authentication and validation.

This module provides request validation against configured authentication tokens.
"""

import logging
from typing import List, Optional
from flask import Request


class RequestValidator:
    """Validates incoming requests against configured tokens.

    Features:
    - Token verification
    - Support for Authorization and x-api-key headers
    - Bearer token handling
    """

    def __init__(self, valid_tokens: List[str]):
        """Initialize validator with valid tokens.

        Args:
            valid_tokens: List of valid authentication tokens
        """
        self.valid_tokens = valid_tokens

    def validate(self, request: Request) -> bool:
        """Validate request authentication.

        Args:
            request: Flask request object

        Returns:
            True if request is authenticated, False otherwise
        """
        token = self._extract_token(request)

        if not self.valid_tokens:
            logging.warning("Authentication disabled - no tokens configured")
            return True

        if not token:
            logging.error("Missing authentication token")
            return False

        # Check if any valid token is in the request token
        # Handles both "Bearer <token>" and just "<token>"
        if not any(valid_token in token for valid_token in self.valid_tokens):
            logging.error("Invalid authentication token")
            return False

        logging.debug("Request authenticated successfully")
        return True

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract token from request headers.

        Args:
            request: Flask request object

        Returns:
            Token string or None if not found
        """
        token = request.headers.get("Authorization") or request.headers.get("x-api-key")

        if token:
            logging.debug(f"Token extracted: {token[:15]}...")

        return token


# Backward compatible function
def verify_request_token(request: Request, proxy_config) -> bool:
    """Backward compatible request validation function.

    Args:
        request: Flask request object
        proxy_config: Global ProxyConfig instance

    Returns:
        True if authenticated, False otherwise
    """
    import warnings
    warnings.warn("verify_request_token() is deprecated, use RequestValidator",
                  DeprecationWarning, stacklevel=2)

    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    return validator.validate(request)