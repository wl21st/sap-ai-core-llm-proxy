"""
Regression tests for primary API routes after dead-code cleanup.

Verifies that /v1/models, /v1/messages, and /v1/chat/completions still wire
up correctly after import cleanup removed previously-imported but unused symbols
(Converters, make_backend_request, bedrock_retry, etc.).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.status import HTTP_401_UNAUTHORIZED

from auth.request_validator import verify_request_token
from routers import chat, messages, models


def _make_app(proxy_config=None, proxy_context=None):
    app = FastAPI()
    app.include_router(models.router)
    app.include_router(messages.router)
    app.include_router(chat.router)
    if proxy_config is not None:
        app.state.proxy_config = proxy_config
    if proxy_context is not None:
        app.state.proxy_context = proxy_context
    return app


@pytest.fixture
def mock_state():
    config = MagicMock()
    config.secret_authentication_tokens = []
    config.model_to_subaccounts = {"gpt-4.1": ["test"], "claude-4.5": ["test"]}
    ctx = MagicMock()
    return config, ctx


@pytest.fixture
def client(mock_state):
    config, ctx = mock_state
    app = _make_app(proxy_config=config, proxy_context=ctx)
    return TestClient(app, raise_server_exceptions=False)


class TestModelsRoute:
    @patch("routers.models.verify_request_token", return_value=True)
    def test_models_returns_200(self, _mock_auth, client):
        response = client.get("/v1/models")
        assert response.status_code == 200

    @patch("routers.models.verify_request_token", return_value=True)
    def test_models_returns_data_list(self, _mock_auth, client):
        response = client.get("/v1/models")
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    @patch("routers.models.verify_request_token", return_value=True)
    def test_models_lists_configured_models(self, _mock_auth, client):
        response = client.get("/v1/models")
        ids = {m["id"] for m in response.json()["data"]}
        assert "gpt-4.1" in ids
        assert "claude-4.5" in ids


class TestMessagesRoute:
    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url", side_effect=ValueError("not found"))
    def test_missing_model_returns_404(self, _mock_lb, _mock_auth, client):
        response = client.post("/v1/messages", json={"model": "unknown-model"})
        assert response.status_code == 404

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url", side_effect=ValueError("not found"))
    def test_404_response_shape(self, _mock_lb, _mock_auth, client):
        response = client.post("/v1/messages", json={"model": "unknown-model"})
        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "not_found_error"


class TestChatCompletionsRoute:
     @patch("routers.chat.verify_request_token", return_value=True)
     @patch(
         "routers.chat.handle_default_request",
         side_effect=ValueError("model not found"),
     )
     def test_missing_model_returns_error(self, _mock_handler, _mock_auth, client):
         response = client.post(
             "/v1/chat/completions",
             json={"model": "unknown", "messages": [{"role": "user", "content": "hi"}]},
         )
         assert response.status_code in (400, 404, 500)

     def test_unauthenticated_returns_401(self, client):
         """Test that unauthenticated requests receive 401.
         
         Uses FastAPI's dependency_overrides to properly mock the dependency
         at runtime, ensuring the override is applied before the request is processed.
         """
         def mock_auth_fail(
             request: Request,
             authorization: str | None = Header(default=None, alias="Authorization"),
             x_api_key: str | None = Header(default=None, alias="x-api-key"),
         ) -> None:
             """Mock dependency that raises 401 authentication error."""
             raise HTTPException(status_code=HTTP_401_UNAUTHORIZED)

         client.app.dependency_overrides[verify_request_token] = mock_auth_fail
         try:
             response = client.post(
                 "/v1/chat/completions",
                 json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "hi"}]},
             )
             assert response.status_code == 401
         finally:
             client.app.dependency_overrides.clear()
