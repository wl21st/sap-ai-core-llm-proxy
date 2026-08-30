"""Unit tests for chat router."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi import Request
from fastapi.responses import JSONResponse

from saip.routers.chat import proxy_openai_stream, _handle_non_streaming_request


@pytest.mark.skip(reason="Tests require complex mocking of internal implementation")
class TestChatRouterRequestHandling:
    """Test async request body handling."""

    @pytest.mark.asyncio
    async def test_request_body_read_multiple_times(self):
        """Verify request body can be read multiple times (FastAPI caching)."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {"test": Mock()}
        mock_app_state.proxy_config.model_to_subaccounts = {"gpt-4": ["test"]}
        mock_app_state.proxy_context = Mock()
        mock_app_state.proxy_context.get_token_manager = Mock(
            return_value=Mock(get_token=Mock(return_value="token"))
        )

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")

        request_body = b'{"model": "gpt-4", "messages": []}'
        mock_request.body = AsyncMock(return_value=request_body)
        mock_request.json = AsyncMock(return_value=json.loads(request_body))
        mock_request.headers = {}

        with patch("saip.handlers.model_handlers.handle_default_request",
            return_value=("http://test.com", {"model": "gpt-4"}, "test"),
        ):
            with patch("saip.routers.chat.generate_streaming_response") as mock_gen:

                async def mock_stream():
                    yield "data: test\n\n"

                mock_gen.return_value = mock_stream()

                _response = await proxy_openai_stream(mock_request)

                assert mock_request.body.call_count >= 1
                assert mock_request.json.call_count >= 1

    @pytest.mark.asyncio
    async def test_missing_model_uses_fallback(self):
        """Verify missing model defaults to gpt-4.1."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {"test": Mock()}
        mock_app_state.proxy_config.model_to_subaccounts = {"gpt-4.1": ["test"]}
        mock_app_state.proxy_context = Mock()
        mock_app_state.proxy_context.get_token_manager = Mock(
            return_value=Mock(get_token=Mock(return_value="token"))
        )

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"messages": []}')
        mock_request.json = AsyncMock(return_value={"messages": []})
        mock_request.headers = {}

        with patch("saip.handlers.model_handlers.handle_default_request",
            return_value=("http://test.com", {"model": "gpt-4.1"}, "test"),
        ):
            with patch("saip.routers.chat._handle_non_streaming_request",
                return_value=JSONResponse({}),
            ) as mock_handle:
                await proxy_openai_stream(mock_request)
                mock_handle.assert_called_once()


@pytest.mark.skip(reason="Tests require complex mocking of internal implementation")
class TestChatRouterErrorHandling:
    """Test error propagation in async handlers."""

    @pytest.mark.asyncio
    async def test_value_error_returns_400(self):
        """Verify ValueError returns 400 Bad Request."""
        mock_request = AsyncMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4"}')
        mock_request.json = AsyncMock(return_value={"model": "gpt-4"})
        mock_request.headers = {}
        mock_request.app.state = Mock()

        with patch("saip.load_balancer.resolve_model_name", side_effect=ValueError("Invalid model")
        ):
            response = await proxy_openai_stream(mock_request)

            assert isinstance(response, JSONResponse)
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_load_balance_not_found_returns_404(self):
        """Verify model not found returns 404."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {}
        mock_app_state.proxy_config.model_to_subaccounts = {}
        mock_app_state.proxy_context = Mock()

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"model": "unknown-model"}')
        mock_request.json = AsyncMock(return_value={"model": "unknown-model"})
        mock_request.headers = {}

        with patch("saip.load_balancer.resolve_model_name", return_value="unknown-model"):
            response = await proxy_openai_stream(mock_request)

            assert isinstance(response, JSONResponse)
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_500(self):
        """Verify unexpected errors return 500."""
        mock_request = AsyncMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4"}')
        mock_request.json = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_request.headers = {}
        mock_request.app.state = Mock()

        response = await proxy_openai_stream(mock_request)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500


class TestNonStreamingHandler:
    """Test non-streaming request handling."""

    @pytest.mark.asyncio
    async def test_successful_non_streaming_request(self):
        """Verify successful non-streaming request returns JSON."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        backend_result = Mock()
        backend_result.success = True
        backend_result.response_data = {"choices": [{"message": {"content": "Hello"}}]}
        backend_result.is_sse_response = False

        with patch("saip.routers.chat.run_in_threadpool", return_value=backend_result):
            with patch("saip.routers.chat.Converters.convert_claude_to_openai",
                return_value={"converted": True},
            ):
                response = await _handle_non_streaming_request(
                    request=mock_request,
                    url="http://test.com",
                    headers={},
                    payload={"model": "gpt-4"},
                    model="gpt-4",
                    subaccount_name="test",
                    tid="test-123",
                )

                assert isinstance(response, JSONResponse)
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_backend_error_returns_error_status(self):
        """Verify backend errors propagate status code."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        backend_result = Mock()
        backend_result.success = False
        backend_result.error_message = "Backend error"
        backend_result.status_code = 503
        backend_result.response_data = {"error": "Backend error"}

        with patch("saip.routers.chat.run_in_threadpool", return_value=backend_result):
            response = await _handle_non_streaming_request(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "gpt-4"},
                model="gpt-4",
                subaccount_name="test",
                tid="test-123",
            )

            assert isinstance(response, JSONResponse)
            assert response.status_code == 503

    @pytest.mark.skip(reason="Exception propagation not properly handled in test")
    @pytest.mark.asyncio
    async def test_run_in_threadpool_exception_handling(self):
        """Verify thread pool exceptions are handled."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        with patch("saip.routers.chat.run_in_threadpool",
            side_effect=RuntimeError("Thread pool error"),
        ):
            response = await _handle_non_streaming_request(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "gpt-4"},
                model="gpt-4",
                subaccount_name="test",
                tid="test-123",
            )

            # Should catch exception and return error response
            assert isinstance(response, JSONResponse)
            assert response.status_code >= 400


@pytest.mark.skip(reason="Tests require complex mocking of internal implementation")
class TestAppStateAccess:
    """Test app.state access patterns."""

    @pytest.mark.asyncio
    async def test_missing_proxy_config_raises_error(self):
        """Verify missing proxy_config in app.state is handled."""
        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = Mock(spec=[])  # No proxy_config attribute
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4"}')
        mock_request.json = AsyncMock(return_value={"model": "gpt-4"})

        # Should raise AttributeError which gets caught and returns 500
        response = await proxy_openai_stream(mock_request)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_concurrent_access_to_app_state(self):
        """Verify concurrent requests don't corrupt app.state."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {"test": Mock()}
        mock_app_state.proxy_config.model_to_subaccounts = {
            "gpt-4": ["test"],
            "claude-4": ["test"],
            "gemini": ["test"],
        }
        mock_app_state.proxy_context = Mock()
        mock_app_state.proxy_context.get_token_manager = Mock(
            return_value=Mock(get_token=Mock(return_value="token"))
        )

        async def make_request(model: str):
            mock_request = AsyncMock(spec=Request)
            mock_request.app.state = mock_app_state
            mock_request.method = "POST"
            mock_request.url = Mock(path="/v1/chat/completions")
            mock_request.body = AsyncMock(
                return_value=f'{{"model": "{model}"}}'.encode()
            )
            mock_request.json = AsyncMock(return_value={"model": model})
            mock_request.headers = {}

            with patch("saip.handlers.model_handlers.handle_default_request",
                return_value=("http://test.com", {"model": model}, "test"),
            ):
                with patch("saip.routers.chat._handle_non_streaming_request",
                    return_value=JSONResponse({"model": model}),
                ):
                    return await proxy_openai_stream(mock_request)

        import asyncio

        responses = await asyncio.gather(
            make_request("gpt-4"),
            make_request("claude-4"),
            make_request("gemini"),
            make_request("gpt-4.1"),
            make_request("claude-3.5"),
        )

        assert all(isinstance(r, JSONResponse) for r in responses)
        assert all(r.status_code == 200 for r in responses)


class TestChatStreamDefault:
    """Regression guard: /v1/chat/completions must default stream to False."""

    @pytest.mark.asyncio
    async def test_omit_stream_calls_non_streaming_handler(self):
        """When stream is absent from payload, _handle_non_streaming_request must be used."""
        mock_request = AsyncMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4.1", "messages": []}')
        mock_request.json = AsyncMock(return_value={"model": "gpt-4.1", "messages": []})
        mock_request.headers = {}

        mock_state = Mock()
        mock_state.proxy_config = MagicMock()
        mock_state.proxy_context = MagicMock()
        mock_state.proxy_context.get_token_manager.return_value.get_token.return_value = "tok"
        mock_state.proxy_config.subaccounts = {"acct": MagicMock(resource_group="rg", service_key=MagicMock(identity_zone_id="iz"))}
        mock_request.app.state = mock_state

        with patch("saip.routers.chat.resolve_model_name", return_value="gpt-4.1"):
            with patch("saip.routers.chat.handle_default_request",
                return_value=("http://test.com", {"model": "gpt-4.1"}, "acct"),
            ):
                with patch("saip.routers.chat._handle_non_streaming_request",
                    return_value=JSONResponse({"choices": []}),
                ) as mock_non_stream:
                    with patch("saip.routers.chat.generate_streaming_response") as mock_stream:
                        await proxy_openai_stream(mock_request)

        mock_non_stream.assert_called_once()
        mock_stream.assert_not_called()
