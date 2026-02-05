import pytest
from flask import Flask
from unittest.mock import MagicMock, patch, Mock
from blueprints.messages import messages_bp, init_messages_blueprint


@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(messages_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@patch("blueprints.messages.validate_api_key")
@patch("blueprints.messages.load_balance_url")
def test_missing_model_returns_404(mock_load_balance, mock_validate, client):
    # Setup mocks
    mock_validate.return_value = (True, None)
    mock_load_balance.side_effect = ValueError("Model not found")

    # Init blueprint with mocks (needed because of global variables)
    mock_config = MagicMock()
    mock_ctx = MagicMock()
    # Mock secret_authentication_tokens for validate_api_key call inside blueprint
    mock_config.secret_authentication_tokens = []

    init_messages_blueprint(mock_config, mock_ctx)

    # Make request
    response = client.post("/v1/messages", json={"model": "missing-model"})

    # Assert
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"]["type"] == "not_found_error"
    assert "not available" in data["error"]["message"]


class TestReAuthenticationRetry:
    """Test re-authentication retry logic for 401/403 errors."""

    @pytest.fixture
    def mock_setup(self):
        """Setup common mocks for re-authentication tests."""
        mock_config = MagicMock()
        mock_ctx = MagicMock()
        mock_token_manager = MagicMock()
        mock_ctx.get_token_manager.return_value = mock_token_manager

        mock_subaccount = MagicMock()
        mock_subaccount.service_key = MagicMock()
        mock_subaccount.service_key.identity_zone_id = "test_zone"
        mock_config.subaccounts = {"test_subaccount": mock_subaccount}
        mock_config.secret_authentication_tokens = []

        return mock_config, mock_ctx, mock_token_manager

    @patch("blueprints.messages.validate_api_key")
    @patch("blueprints.messages.load_balance_url")
    @patch("blueprints.messages.make_backend_request")
    @patch("blueprints.messages.Detector")
    def test_proxy_claude_request_original_retries_on_401(
        self,
        mock_detector,
        mock_make_request,
        mock_load_balance,
        mock_validate,
        client,
        mock_setup,
    ):
        """Test that original proxy retries on 401 authentication error."""
        mock_config, mock_ctx, mock_token_manager = mock_setup

        # Setup mocks - use non-Claude model to trigger proxy_claude_request_original
        mock_validate.return_value = (True, None)
        mock_load_balance.return_value = (
            "https://test.url",
            "test_subaccount",
            "test_resource_group",
            "gpt-4-model",
        )
        # First call returns False (to trigger fallback), subsequent calls return True
        # Need enough values for: initial check + 2 checks after retry in proxy_claude_request_original
        mock_detector.is_claude_model.side_effect = [False, True, True, True, True]
        mock_detector.is_claude_37_or_4.return_value = False
        mock_detector.is_gemini_model.return_value = False
        mock_token_manager.get_token.return_value = "test_token"

        # First call returns 401, second call succeeds
        first_result = Mock()
        first_result.success = False
        first_result.status_code = 401
        first_result.error_message = "Unauthorized"
        first_result.response_data = None

        second_result = Mock()
        second_result.success = True
        second_result.status_code = 200
        second_result.response_data = {"content": "Hello"}
        second_result.is_sse_response = False
        second_result.headers = {}

        mock_make_request.side_effect = [first_result, second_result]

        init_messages_blueprint(mock_config, mock_ctx)

        # Make request
        response = client.post(
            "/v1/messages",
            json={
                "model": "gpt-4-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
        )

        # Assert
        assert response.status_code == 200
        assert mock_token_manager.invalidate_token.called
        assert mock_make_request.call_count == 2  # Initial + retry

    @patch("blueprints.messages.validate_api_key")
    @patch("blueprints.messages.load_balance_url")
    @patch("blueprints.messages.make_backend_request")
    @patch("blueprints.messages.Detector")
    def test_proxy_claude_request_original_retries_on_403(
        self,
        mock_detector,
        mock_make_request,
        mock_load_balance,
        mock_validate,
        client,
        mock_setup,
    ):
        """Test that original proxy retries on 403 authentication error."""
        mock_config, mock_ctx, mock_token_manager = mock_setup

        # Setup mocks - use non-Claude model to trigger proxy_claude_request_original
        mock_validate.return_value = (True, None)
        mock_load_balance.return_value = (
            "https://test.url",
            "test_subaccount",
            "test_resource_group",
            "gpt-4-model",
        )
        # First call returns False (to trigger fallback), subsequent calls return True
        # Need enough values for: initial check + 2 checks after retry in proxy_claude_request_original
        mock_detector.is_claude_model.side_effect = [False, True, True, True, True]
        mock_detector.is_claude_37_or_4.return_value = False
        mock_detector.is_gemini_model.return_value = False
        mock_token_manager.get_token.return_value = "test_token"

        # First call returns 403, second call succeeds
        first_result = Mock()
        first_result.success = False
        first_result.status_code = 403
        first_result.error_message = "Forbidden"
        first_result.response_data = None

        second_result = Mock()
        second_result.success = True
        second_result.status_code = 200
        second_result.response_data = {"content": "Hello"}
        second_result.is_sse_response = False
        second_result.headers = {}

        mock_make_request.side_effect = [first_result, second_result]

        init_messages_blueprint(mock_config, mock_ctx)

        # Make request
        response = client.post(
            "/v1/messages",
            json={
                "model": "gpt-4-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
        )

        # Assert
        assert response.status_code == 200
        assert mock_token_manager.invalidate_token.called
        assert mock_make_request.call_count == 2  # Initial + retry

    @patch("blueprints.messages.validate_api_key")
    @patch("blueprints.messages.load_balance_url")
    @patch("blueprints.messages.make_backend_request")
    @patch("blueprints.messages.Detector")
    def test_proxy_claude_request_original_no_retry_on_other_errors(
        self,
        mock_detector,
        mock_make_request,
        mock_load_balance,
        mock_validate,
        client,
        mock_setup,
    ):
        """Test that original proxy does not retry on non-auth errors."""
        mock_config, mock_ctx, mock_token_manager = mock_setup

        # Setup mocks - use non-Claude model to trigger proxy_claude_request_original
        mock_validate.return_value = (True, None)
        mock_load_balance.return_value = (
            "https://test.url",
            "test_subaccount",
            "test_resource_group",
            "gpt-4-model",
        )
        # First call returns False (to trigger fallback), subsequent calls return True
        # Need enough values for: initial check + checks in proxy_claude_request_original
        mock_detector.is_claude_model.side_effect = [False, True, True, True]
        mock_detector.is_claude_37_or_4.return_value = False
        mock_detector.is_gemini_model.return_value = False
        mock_token_manager.get_token.return_value = "test_token"

        # Returns 500 error (should not retry)
        error_result = Mock()
        error_result.success = False
        error_result.status_code = 500
        error_result.error_message = "Internal Server Error"
        error_result.response_data = {"error": "Server error"}

        mock_make_request.return_value = error_result

        init_messages_blueprint(mock_config, mock_ctx)

        # Make request
        response = client.post(
            "/v1/messages",
            json={
                "model": "gpt-4-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
        )

        # Assert
        assert response.status_code == 500
        assert not mock_token_manager.invalidate_token.called
        assert mock_make_request.call_count == 1  # No retry
