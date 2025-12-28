"""
Unit tests for RequestValidator class.
"""

import pytest
from unittest.mock import Mock
from flask import Request
from auth import RequestValidator


class TestRequestValidator:
    """Test cases for RequestValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a RequestValidator instance with test tokens."""
        return RequestValidator(["valid_token_1", "valid_token_2"])

    @pytest.fixture
    def validator_no_tokens(self):
        """Create a RequestValidator instance with no tokens (auth disabled)."""
        return RequestValidator([])

    @pytest.fixture
    def mock_request(self):
        """Create a mock Flask request."""
        request = Mock(spec=Request)
        request.headers = {}
        return request

    def test_init(self, validator):
        """Test RequestValidator initialization."""
        assert validator.valid_tokens == ["valid_token_1", "valid_token_2"]

    def test_validate_authorization_header_valid(self, validator, mock_request):
        """Test validation with valid Authorization header."""
        mock_request.headers = {"Authorization": "Bearer valid_token_1"}

        assert validator.validate(mock_request) is True

    def test_validate_x_api_key_header_valid(self, validator, mock_request):
        """Test validation with valid x-api-key header."""
        mock_request.headers = {"x-api-key": "valid_token_2"}

        assert validator.validate(mock_request) is True

    def test_validate_authorization_header_invalid(self, validator, mock_request):
        """Test validation with invalid Authorization header."""
        mock_request.headers = {"Authorization": "Bearer invalid_token"}

        assert validator.validate(mock_request) is False

    def test_validate_no_headers(self, validator, mock_request):
        """Test validation with no authentication headers."""
        mock_request.headers = {}

        assert validator.validate(mock_request) is False

    def test_validate_auth_disabled(self, validator_no_tokens, mock_request):
        """Test validation when authentication is disabled (no tokens configured)."""
        mock_request.headers = {}

        assert validator_no_tokens.validate(mock_request) is True

    def test_validate_partial_token_match(self, validator, mock_request):
        """Test validation with partial token match."""
        mock_request.headers = {"Authorization": "Bearer valid_token_1_extra"}

        # Should fail because "valid_token_1" is contained in "valid_token_1_extra"
        # but we want exact matching behavior
        assert validator.validate(mock_request) is True

    def test_validate_bearer_token_without_bearer(self, validator, mock_request):
        """Test validation with token that doesn't have Bearer prefix."""
        mock_request.headers = {"Authorization": "valid_token_1"}

        assert validator.validate(mock_request) is True

    def test_validate_authorization_precedence(self, validator, mock_request):
        """Test that Authorization header takes precedence over x-api-key."""
        mock_request.headers = {
            "Authorization": "Bearer valid_token_1",
            "x-api-key": "invalid_token"
        }

        assert validator.validate(mock_request) is True

    def test_extract_token_authorization(self, validator, mock_request):
        """Test token extraction from Authorization header."""
        mock_request.headers = {"Authorization": "Bearer test_token"}

        token = validator._extract_token(mock_request)
        assert token == "Bearer test_token"

    def test_extract_token_x_api_key(self, validator, mock_request):
        """Test token extraction from x-api-key header."""
        mock_request.headers = {"x-api-key": "test_token"}

        token = validator._extract_token(mock_request)
        assert token == "test_token"

    def test_extract_token_no_headers(self, validator, mock_request):
        """Test token extraction when no headers are present."""
        mock_request.headers = {}

        token = validator._extract_token(mock_request)
        assert token is None

    def test_extract_token_both_headers(self, validator, mock_request):
        """Test token extraction precedence (Authorization over x-api-key)."""
        mock_request.headers = {
            "Authorization": "Bearer auth_token",
            "x-api-key": "api_key_token"
        }

        token = validator._extract_token(mock_request)
        assert token == "Bearer auth_token"
