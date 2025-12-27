"""
Request authentication and validation.

This module provides request validation against configured authentication tokens.
"""

from logging import Logger

from flask import Request

from utils.logging_utils import get_client_logger

logger: Logger = get_client_logger(__name__)


class RequestValidator:
    """Validates incoming requests against configured tokens.

    Features:
    - Token verification
    - Support for Authorization and x-api-key headers
    - Bearer token handling
    """

    def __init__(self, valid_tokens: list[str]) -> None:
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
        token = RequestValidator._extract_token(request)

        if not self.valid_tokens:
            logger.info("Authentication disabled - no tokens configured")
            return True

        if not token:
            logger.error("Missing authentication token")
            return False

        # Check if any valid token is in the request token
        # Handles both "Bearer <token>" and just "<token>"
        if not any(valid_token in token for valid_token in self.valid_tokens):
            logger.error("Invalid authentication token")
            return False

        logger.debug("Request authenticated successfully")
        return True

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        """Extract token from request headers.

        Args:
            request: Flask request object

        Returns:
            Token string or None if not found
        """
        token = request.headers.get("Authorization") or request.headers.get("x-api-key")

        if token:
            logger.debug("Token extracted: %s...", token[:15])

        return token
