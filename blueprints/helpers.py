"""Shared utilities for Flask blueprints."""

from typing import Tuple, Dict, Any, Optional
from flask import jsonify, request
from auth import RequestValidator


class MockResponse:
    """Mock HTTP response object for testing and error handling.

    This class mimics the interface of requests.Response to allow
    consistent error handling across different response sources.
    """

    def __init__(
        self,
        status_code: int,
        text: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize mock response.

        Args:
            status_code: HTTP status code
            text: Response text
            data: Response data dictionary
            headers: Response headers dictionary
        """
        self.status_code = status_code
        self.text = text
        self._data = data
        self.headers = headers if headers else {}

    def json(self) -> Dict[str, Any]:
        """Return response data as JSON.

        Returns:
            Response data dictionary or empty dict if no data
        """
        return self._data if self._data else {}


def validate_api_key(secret_tokens: list) -> Tuple[bool, Optional[Tuple[Any, int]]]:
    """Validate API key from request headers.

    Checks both X-Api-Key and Authorization headers for valid tokens.

    Args:
        secret_tokens: List of valid authentication tokens

    Returns:
        Tuple of (is_valid, error_response)
        - If valid: (True, None)
        - If invalid: (False, (jsonify(error), status_code))
    """
    validator = RequestValidator(secret_tokens)
    if not validator.validate(request):
        error_response = jsonify(
            {
                "type": "error",
                "error": {
                    "type": "authentication_error",
                    "message": "Invalid API Key provided.",
                },
            }
        )
        return False, (error_response, 401)
    return True, None


def create_error_response(
    error_type: str,
    message: str,
    status_code: int = 500,
) -> Tuple[Any, int]:
    """Create standardized error response.

    Args:
        error_type: Type of error (e.g., 'api_error', 'invalid_request_error')
        message: Error message
        status_code: HTTP status code (default: 500)

    Returns:
        Tuple of (jsonify(error), status_code)
    """
    error_response = jsonify(
        {
            "type": "error",
            "error": {
                "type": error_type,
                "message": message,
            },
        }
    )
    return error_response, status_code


def create_authentication_error() -> Tuple[Any, int]:
    """Create authentication error response.

    Returns:
        Tuple of (jsonify(error), 401)
    """
    return create_error_response(
        "authentication_error",
        "Invalid API Key provided.",
        401,
    )


def create_invalid_request_error(message: str) -> Tuple[Any, int]:
    """Create invalid request error response.

    Args:
        message: Error message

    Returns:
        Tuple of (jsonify(error), 400)
    """
    return create_error_response(
        "invalid_request_error",
        message,
        400,
    )


def create_api_error(message: str, status_code: int = 500) -> Tuple[Any, int]:
    """Create API error response.

    Args:
        message: Error message
        status_code: HTTP status code (default: 500)

    Returns:
        Tuple of (jsonify(error), status_code)
    """
    return create_error_response(
        "api_error",
        message,
        status_code,
    )


def create_rate_limit_error() -> Tuple[Any, int]:
    """Create rate limit error response.

    Returns:
        Tuple of (jsonify(error), 429)
    """
    return create_error_response(
        "rate_limit_error",
        "Rate limit exceeded. Please try again later.",
        429,
    )
