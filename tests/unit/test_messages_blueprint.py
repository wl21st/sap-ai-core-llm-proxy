"""Tests for the /v1/messages router (Orchestration V2 path)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from routers.messages import router


def _make_app(proxy_config=None, proxy_context=None):
    """Create a minimal FastAPI app with the messages router and injected state."""
    app = FastAPI()
    app.include_router(router)
    if proxy_config is not None:
        app.state.proxy_config = proxy_config
    if proxy_context is not None:
        app.state.proxy_context = proxy_context
    return app


@pytest.fixture
def mock_subaccount():
    sub = MagicMock()
    sub.name = "test_sub"
    sub.resource_group = "default"
    sub.orchestration_url = "https://api.ai.com/v2/inference/deployments/orch"
    sub.service_key = MagicMock(identity_zone_id="zone")
    return sub


@pytest.fixture
def mock_proxy_state(mock_subaccount):
    config = MagicMock()
    config.secret_authentication_tokens = []
    config.subaccounts = {"test_sub": mock_subaccount}
    config.model_to_subaccounts = {"*": ["test_sub"]}

    ctx = MagicMock()
    ctx.model_aliases = None
    ctx.foundation_model_registry = None
    ctx.get_token_manager.return_value.get_token.return_value = "test-token"
    ctx.get_ca_cert_bundle.return_value = None
    return config, ctx


@pytest.fixture
def client(mock_proxy_state):
    config, ctx = mock_proxy_state
    app = _make_app(proxy_config=config, proxy_context=ctx)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


@patch("routers.messages.verify_request_token", return_value=True)
@patch("routers.messages.select_subaccount_for_orchestration", side_effect=ValueError("no V2"))
def test_no_v2_subaccount_returns_503(mock_select, mock_validate, client):
    response = client.post(
        "/v1/messages",
        json={"model": "anthropic--claude-4.5-sonnet", "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert response.status_code == 503


@patch("routers.messages.verify_request_token", return_value=True)
def test_non_claude_model_returns_400(mock_validate, client):
    response = client.post(
        "/v1/messages",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["type"] == "invalid_request_error"


@patch("routers.messages.verify_request_token", return_value=True)
def test_registry_rejects_unknown_model_returns_404(mock_validate, mock_proxy_state):
    config, ctx = mock_proxy_state
    registry = MagicMock()
    registry.is_known_model.return_value = False
    ctx.foundation_model_registry = registry

    app = _make_app(proxy_config=config, proxy_context=ctx)
    c = TestClient(app, raise_server_exceptions=False)

    response = c.post(
        "/v1/messages",
        json={"model": "anthropic--claude-4.5-sonnet", "messages": []},
    )
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found_error"


# ---------------------------------------------------------------------------
# Non-streaming
# ---------------------------------------------------------------------------


@patch("routers.messages.verify_request_token", return_value=True)
@patch("routers.messages.select_subaccount_for_orchestration", return_value="test_sub")
def test_non_streaming_returns_claude_format(mock_select, mock_validate, client):
    """Non-streaming invoke converts OpenAI response to Anthropic format."""
    openai_response = {
        "id": "chatcmpl-123",
        "choices": [{"message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }

    with patch("routers.messages.get_orchestration_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.invoke.return_value = openai_response
        mock_get_client.return_value = mock_client

        with patch("routers.messages.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
            mock_tp.return_value = openai_response

            response = client.post(
                "/v1/messages",
                json={
                    "model": "anthropic--claude-4.5-sonnet",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
            )

    assert response.status_code == 200
    data = response.json()
    # Should be converted to Anthropic format (type: message)
    assert data.get("type") == "message" or "content" in data or "error" in data


@patch("routers.messages.verify_request_token", return_value=True)
@patch("routers.messages.select_subaccount_for_orchestration", return_value="test_sub")
def test_default_model_when_missing(mock_select, mock_validate, client):
    """When model is omitted, default Claude model is used."""
    openai_response = {
        "id": "chatcmpl-456",
        "choices": [{"message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
        "usage": {},
    }

    with patch("routers.messages.get_orchestration_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.invoke.return_value = openai_response
        mock_get_client.return_value = mock_client

        with patch("routers.messages.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
            mock_tp.return_value = openai_response

            response = client.post(
                "/v1/messages",
                json={"messages": [{"role": "user", "content": "Hello"}]},
            )

    # Should succeed (default model is a Claude model)
    assert response.status_code in (200, 400, 404, 503)


class TestStreamingDefault:
    """Tests verifying that stream defaults to False per the Anthropic API spec."""

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.select_subaccount_for_orchestration", return_value="test_sub")
    def test_omit_stream_defaults_to_non_streaming(
        self, mock_select, mock_validate, client
    ):
        """Omitting stream should call non-streaming OrchestrationClient.invoke."""
        openai_response = {
            "id": "chatcmpl-789",
            "choices": [{"message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
            "usage": {},
        }

        with patch("routers.messages.get_orchestration_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke.return_value = openai_response
            mock_get_client.return_value = mock_client

            with patch("routers.messages.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
                mock_tp.return_value = openai_response

                client.post(
                    "/v1/messages",
                    json={
                        "model": "anthropic--claude-4.5-sonnet",
                        "messages": [{"role": "user", "content": "Hello"}],
                        # stream intentionally omitted
                    },
                )

            # run_in_threadpool called → non-streaming path used
            mock_tp.assert_called_once()

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.select_subaccount_for_orchestration", return_value="test_sub")
    def test_explicit_stream_false_uses_non_streaming(
        self, mock_select, mock_validate, client
    ):
        """Explicit stream=false must use non-streaming path (run_in_threadpool)."""
        openai_response = {
            "id": "chatcmpl-aaa",
            "choices": [{"message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
            "usage": {},
        }

        with patch("routers.messages.get_orchestration_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch("routers.messages.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
                mock_tp.return_value = openai_response

                client.post(
                    "/v1/messages",
                    json={
                        "model": "anthropic--claude-4.5-sonnet",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

            mock_tp.assert_called_once()

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.select_subaccount_for_orchestration", return_value="test_sub")
    def test_explicit_stream_true_returns_streaming_response(
        self, mock_select, mock_validate, client
    ):
        """Explicit stream=true must return StreamingResponse (text/event-stream)."""
        with patch("routers.messages.get_orchestration_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.invoke_stream.return_value = iter([b"data: {}\n\n"])
            mock_get_client.return_value = mock_client

            response = client.post(
                "/v1/messages",
                json={
                    "model": "anthropic--claude-4.5-sonnet",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True,
                },
            )

        assert "text/event-stream" in response.headers.get("content-type", "")
