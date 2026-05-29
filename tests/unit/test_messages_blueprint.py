"""Tests for the /v1/messages router (FastAPI)."""

import pytest
from unittest.mock import MagicMock, patch, Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from routers.messages import router


def _make_app(proxy_config=None, proxy_context=None):
    """Create a minimal FastAPI app with the messages router and injected state."""
    app = FastAPI()
    app.include_router(router)
    # Inject state required by the router
    if proxy_config is not None:
        app.state.proxy_config = proxy_config
    if proxy_context is not None:
        app.state.proxy_context = proxy_context
    return app


@pytest.fixture
def mock_proxy_state():
    """Return a (config, context) pair suitable for app state injection."""
    mock_config = MagicMock()
    mock_config.secret_authentication_tokens = []
    mock_ctx = MagicMock()
    return mock_config, mock_ctx


@pytest.fixture
def client(mock_proxy_state):
    mock_config, mock_ctx = mock_proxy_state
    app = _make_app(proxy_config=mock_config, proxy_context=mock_ctx)
    return TestClient(app, raise_server_exceptions=False)


@patch("routers.messages.verify_request_token", return_value=True)
@patch("routers.messages.load_balance_url", side_effect=ValueError("Model not found"))
def test_missing_model_returns_404(mock_load_balance, mock_validate, client):
    response = client.post("/v1/messages", json={"model": "missing-model"})

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["type"] == "not_found_error"
    assert "not available" in data["error"]["message"]


class TestSDKReAuthenticationRetry:
    """Test re-authentication retry logic for SDK path (proxy_claude_request)."""

    @pytest.fixture
    def mock_sdk_setup(self):
        mock_config = MagicMock()
        mock_ctx = MagicMock()

        mock_subaccount = MagicMock()
        mock_subaccount.service_key = MagicMock()
        mock_subaccount.service_key.identity_zone_id = "test_zone"
        mock_config.subaccounts = {"test_subaccount": mock_subaccount}
        mock_config.secret_authentication_tokens = []

        return mock_config, mock_ctx

    @pytest.fixture
    def sdk_client(self, mock_sdk_setup):
        mock_config, mock_ctx = mock_sdk_setup
        app = _make_app(proxy_config=mock_config, proxy_context=mock_ctx)
        return TestClient(app, raise_server_exceptions=False), mock_config, mock_ctx

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url")
    @patch("routers.messages.get_bedrock_client")
    @patch("routers.messages.invalidate_bedrock_client")
    @patch("routers.messages.Detector")
    @patch("routers.messages.extract_deployment_id")
    def test_proxy_claude_request_sdk_retries_on_401_non_streaming(
        self,
        mock_extract_id,
        mock_detector,
        mock_invalidate_client,
        mock_get_client,
        mock_load_balance,
        mock_validate,
        sdk_client,
    ):
        """Test that SDK path retries on 401 authentication error for non-streaming."""
        client, mock_config, mock_ctx = sdk_client

        mock_load_balance.return_value = (
            "https://test.url/deployment-id",
            "test_subaccount",
            "test_resource_group",
            "anthropic--claude-4.5-sonnet",
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deployment-id"

        mock_bedrock_client = MagicMock()
        mock_get_client.return_value = mock_bedrock_client

        first_response = Mock()
        first_response.get.return_value = {"HTTPStatusCode": 401, "body": MagicMock()}

        second_response = Mock()
        second_response.get.return_value = {"HTTPStatusCode": 200, "body": MagicMock()}

        with patch("routers.messages.invoke_bedrock_non_streaming") as mock_invoke:
            with patch(
                "routers.messages.read_response_body_stream",
                return_value='{"content": [{"text": "Hello"}], "type": "message"}',
            ):
                mock_invoke.side_effect = [first_response, second_response]

                response = client.post(
                    "/v1/messages",
                    json={
                        "model": "anthropic--claude-4.5-sonnet",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                assert response.status_code == 200
                assert mock_invalidate_client.called
                assert mock_invoke.call_count == 2

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url")
    @patch("routers.messages.get_bedrock_client")
    @patch("routers.messages.invalidate_bedrock_client")
    @patch("routers.messages.Detector")
    @patch("routers.messages.extract_deployment_id")
    def test_proxy_claude_request_sdk_retries_on_403_non_streaming(
        self,
        mock_extract_id,
        mock_detector,
        mock_invalidate_client,
        mock_get_client,
        mock_load_balance,
        mock_validate,
        sdk_client,
    ):
        """Test that SDK path retries on 403 authentication error for non-streaming."""
        client, mock_config, mock_ctx = sdk_client

        mock_load_balance.return_value = (
            "https://test.url/deployment-id",
            "test_subaccount",
            "test_resource_group",
            "anthropic--claude-4.5-sonnet",
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deployment-id"

        mock_bedrock_client = MagicMock()
        mock_get_client.return_value = mock_bedrock_client

        first_response = Mock()
        first_response.get.return_value = {"HTTPStatusCode": 403, "body": MagicMock()}

        second_response = Mock()
        second_response.get.return_value = {"HTTPStatusCode": 200, "body": MagicMock()}

        with patch("routers.messages.invoke_bedrock_non_streaming") as mock_invoke:
            with patch(
                "routers.messages.read_response_body_stream",
                return_value='{"content": [{"text": "Hello"}], "type": "message"}',
            ):
                mock_invoke.side_effect = [first_response, second_response]

                response = client.post(
                    "/v1/messages",
                    json={
                        "model": "anthropic--claude-4.5-sonnet",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False,
                    },
                )

                assert response.status_code == 200
                assert mock_invalidate_client.called
                assert mock_invoke.call_count == 2

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url")
    @patch("routers.messages.get_bedrock_client")
    @patch("routers.messages.invalidate_bedrock_client")
    @patch("routers.messages.Detector")
    @patch("routers.messages.extract_deployment_id")
    def test_proxy_claude_request_sdk_no_retry_on_other_errors(
        self,
        mock_extract_id,
        mock_detector,
        mock_invalidate_client,
        mock_get_client,
        mock_load_balance,
        mock_validate,
        sdk_client,
    ):
        """Test that SDK path does not retry on non-auth errors."""
        client, mock_config, mock_ctx = sdk_client

        mock_load_balance.return_value = (
            "https://test.url/deployment-id",
            "test_subaccount",
            "test_resource_group",
            "anthropic--claude-4.5-sonnet",
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deployment-id"

        mock_bedrock_client = MagicMock()
        mock_get_client.return_value = mock_bedrock_client

        error_response = Mock()
        error_response.get.return_value = {"HTTPStatusCode": 500, "body": MagicMock()}

        with patch("routers.messages.invoke_bedrock_non_streaming") as mock_invoke:
            mock_invoke.return_value = error_response

            response = client.post(
                "/v1/messages",
                json={
                    "model": "anthropic--claude-4.5-sonnet",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
            )

            assert response.status_code == 500
            assert not mock_invalidate_client.called
            assert mock_invoke.call_count == 1


class TestStreamingDefault:
    """Tests verifying that stream defaults to False per the Anthropic API spec."""

    @pytest.fixture
    def sdk_client(self, mock_proxy_state):
        mock_config, mock_ctx = mock_proxy_state
        app = _make_app(proxy_config=mock_config, proxy_context=mock_ctx)
        return TestClient(app, raise_server_exceptions=False), mock_config, mock_ctx

    def _make_non_streaming_response(self):
        response = Mock()
        response.get.side_effect = lambda key, default=None: {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "body": None,
        }.get(key, default)
        return response

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url")
    @patch("routers.messages.get_bedrock_client")
    @patch("routers.messages.invalidate_bedrock_client")
    @patch("routers.messages.Detector")
    @patch("routers.messages.extract_deployment_id")
    def test_omit_stream_defaults_to_non_streaming(
        self,
        mock_extract_id,
        mock_detector,
        mock_invalidate_client,
        mock_get_client,
        mock_load_balance,
        mock_validate,
        sdk_client,
    ):
        """Omitting stream should call non-streaming backend, not streaming."""
        client, mock_config, mock_ctx = sdk_client
        mock_load_balance.return_value = (
            "https://test.url/deployment-id",
            "test_subaccount",
            "test_resource_group",
            "anthropic--claude-4.5-sonnet",
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deployment-id"
        mock_get_client.return_value = MagicMock()

        ok_response = Mock()
        ok_response.get.side_effect = lambda key, default=None: {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "body": None,
        }.get(key, default)

        with patch("routers.messages.invoke_bedrock_non_streaming", return_value=ok_response) as mock_non_stream:
            with patch("routers.messages.invoke_bedrock_streaming") as mock_stream:
                with patch(
                    "routers.messages.read_response_body_stream",
                    return_value='{"content": [{"text": "Hi"}], "type": "message"}',
                ):
                    client.post(
                        "/v1/messages",
                        json={
                            "model": "anthropic--claude-4.5-sonnet",
                            "messages": [{"role": "user", "content": "Hello"}],
                            # stream intentionally omitted
                        },
                    )

        mock_non_stream.assert_called_once()
        mock_stream.assert_not_called()

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url")
    @patch("routers.messages.get_bedrock_client")
    @patch("routers.messages.invalidate_bedrock_client")
    @patch("routers.messages.Detector")
    @patch("routers.messages.extract_deployment_id")
    def test_explicit_stream_false_uses_non_streaming(
        self,
        mock_extract_id,
        mock_detector,
        mock_invalidate_client,
        mock_get_client,
        mock_load_balance,
        mock_validate,
        sdk_client,
    ):
        """Explicit stream=false must call non-streaming backend."""
        client, mock_config, mock_ctx = sdk_client
        mock_load_balance.return_value = (
            "https://test.url/deployment-id",
            "test_subaccount",
            "test_resource_group",
            "anthropic--claude-4.5-sonnet",
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deployment-id"
        mock_get_client.return_value = MagicMock()

        ok_response = Mock()
        ok_response.get.side_effect = lambda key, default=None: {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "body": None,
        }.get(key, default)

        with patch("routers.messages.invoke_bedrock_non_streaming", return_value=ok_response) as mock_non_stream:
            with patch("routers.messages.invoke_bedrock_streaming") as mock_stream:
                with patch(
                    "routers.messages.read_response_body_stream",
                    return_value='{"content": [{"text": "Hi"}], "type": "message"}',
                ):
                    client.post(
                        "/v1/messages",
                        json={
                            "model": "anthropic--claude-4.5-sonnet",
                            "messages": [{"role": "user", "content": "Hello"}],
                            "stream": False,
                        },
                    )

        mock_non_stream.assert_called_once()
        mock_stream.assert_not_called()

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url")
    @patch("routers.messages.get_bedrock_client")
    @patch("routers.messages.invalidate_bedrock_client")
    @patch("routers.messages.Detector")
    @patch("routers.messages.extract_deployment_id")
    def test_explicit_stream_true_uses_streaming(
        self,
        mock_extract_id,
        mock_detector,
        mock_invalidate_client,
        mock_get_client,
        mock_load_balance,
        mock_validate,
        sdk_client,
    ):
        """Regression: explicit stream=true must still call streaming backend."""
        client, mock_config, mock_ctx = sdk_client
        mock_load_balance.return_value = (
            "https://test.url/deployment-id",
            "test_subaccount",
            "test_resource_group",
            "anthropic--claude-4.5-sonnet",
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deployment-id"
        mock_get_client.return_value = MagicMock()

        ok_response = Mock()
        ok_response.get.side_effect = lambda key, default=None: {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "body": MagicMock(),
        }.get(key, default)

        with patch("routers.messages.invoke_bedrock_streaming", return_value=ok_response) as mock_stream:
            with patch("routers.messages.invoke_bedrock_non_streaming") as mock_non_stream:
                with patch("routers.messages.generate_bedrock_streaming_response", return_value=iter([])):
                    client.post(
                        "/v1/messages",
                        json={
                            "model": "anthropic--claude-4.5-sonnet",
                            "messages": [{"role": "user", "content": "Hello"}],
                            "stream": True,
                        },
                    )

        mock_stream.assert_called_once()
        mock_non_stream.assert_not_called()


class TestSystemMessageHandling:
    """Test system message extraction and removal from messages array."""

    @pytest.fixture
    def mock_sdk_setup(self):
        mock_config = MagicMock()
        mock_ctx = MagicMock()

        mock_subaccount = MagicMock()
        mock_subaccount.service_key = MagicMock()
        mock_subaccount.service_key.identity_zone_id = "test_zone"
        mock_config.subaccounts = {"test_subaccount": mock_subaccount}
        mock_config.secret_authentication_tokens = []

        return mock_config, mock_ctx

    @pytest.fixture
    def sdk_client(self, mock_sdk_setup):
        mock_config, mock_ctx = mock_sdk_setup
        app = _make_app(proxy_config=mock_config, proxy_context=mock_ctx)
        return TestClient(app, raise_server_exceptions=False), mock_config, mock_ctx

    @patch("routers.messages.verify_request_token", return_value=True)
    @patch("routers.messages.load_balance_url")
    @patch("routers.messages.get_bedrock_client")
    @patch("routers.messages.Detector")
    @patch("routers.messages.extract_deployment_id")
    def test_empty_system_message_is_removed_from_array(
        self,
        mock_extract_id,
        mock_detector,
        mock_get_client,
        mock_load_balance,
        mock_validate,
        sdk_client,
    ):
        """Test that empty system messages are removed from messages array.
        
        Regression test: empty system messages were not being removed,
        causing "Unexpected role 'system'" ValidationException from Bedrock.
        """
        client, mock_config, mock_ctx = sdk_client
        mock_load_balance.return_value = (
            "https://test.url/deployment-id",
            "test_subaccount",
            "test_resource_group",
            "anthropic--claude-4.5-sonnet",
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deployment-id"
        mock_bedrock_client = MagicMock()
        mock_get_client.return_value = mock_bedrock_client

        ok_response = Mock()
        ok_response.get.side_effect = lambda key, default=None: {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "body": MagicMock(),
        }.get(key, default)

        with patch("routers.messages.invoke_bedrock_non_streaming", return_value=ok_response) as mock_invoke:
            client.post(
                "/v1/messages",
                json={
                    "model": "anthropic--claude-4.5-sonnet",
                    "messages": [
                        {"role": "system", "content": ""},  # Empty system message
                        {"role": "user", "content": "Hello"},
                    ],
                },
            )

        # Verify that invoke_bedrock_non_streaming was called
        mock_invoke.assert_called_once()
        
        # Extract the body_json argument that was passed to invoke_bedrock_non_streaming
        call_args = mock_invoke.call_args
        body_json_str = call_args[0][1]  # Second positional argument
        
        import json
        body = json.loads(body_json_str)
        
        # Verify that no system role messages are in the messages array
        assert not any(m.get("role") == "system" for m in body["messages"]), \
            "System message should have been removed from messages array"
        
        # Verify that the messages array contains only the user message
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][0]["content"] == "Hello"

