import pytest
from flask import Flask
from unittest.mock import MagicMock, patch
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
