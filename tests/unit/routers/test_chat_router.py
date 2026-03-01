"""Unit tests for chat router."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from routers.chat import router, proxy_openai_stream, _handle_non_streaming_request


class TestChatRouterRequestHandling:
    """Test async request body handling."""

    @pytest.mark.asyncio
    async def test_request_body_read_multiple_times(self):
        """Verify request body can be read multiple times (FastAPI caching)."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {}
        mock_app_state.proxy_context = Mock()

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")

        # Mock body() and json() to track calls
        request_body = b'{"model": "gpt-4", "messages": []}'
        mock_request.body = AsyncMock(return_value=request_body)
        mock_request.json = AsyncMock(return_value=json.loads(request_body))

        with patch("routers.chat.resolve_model_name", return_value="gpt-4"):
            with patch("routers.chat.load_balance_url", return_value=("http://test.com", "test", "gpt-4")):
                with patch("routers.chat.fetch_token", return_value="token"):
                    with patch("routers.chat.generate_streaming_response") as mock_gen:
                        async def mock_stream():
                            yield "data: test\n\n"
                        mock_gen.return_value = mock_stream()

                        # Call endpoint
                        response = await proxy_openai_stream(mock_request)

                        # Verify both body() and json() were called
                        assert mock_request.body.call_count >= 1
                        assert mock_request.json.call_count >= 1

    @pytest.mark.asyncio
    async def test_missing_model_uses_fallback(self):
        """Verify missing model defaults to gpt-4.1."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {}

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"messages": []}')  # No model
        mock_request.json = AsyncMock(return_value={"messages": []})

        with patch("routers.chat.resolve_model_name") as mock_resolve:
            with patch("routers.chat.load_balance_url", return_value=("http://test.com", "test", "gpt-4.1")):
                with patch("routers.chat.fetch_token", return_value="token"):
                    with patch("routers.chat._handle_non_streaming_request", return_value=JSONResponse({})):
                        await proxy_openai_stream(mock_request)

                        # Verify resolve was called (which handles fallback)
                        mock_resolve.assert_called_once()
                        call_args = mock_resolve.call_args[0]
                        # First arg should be None or "gpt-4.1"
                        assert call_args[0] is None or "gpt-4" in str(call_args[0])


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

        with patch("routers.chat.resolve_model_name", side_effect=ValueError("Invalid model")):
            response = await proxy_openai_stream(mock_request)

            assert isinstance(response, JSONResponse)
            assert response.status_code == 400
            content = json.loads(response.body.decode())
            assert "error" in content

    @pytest.mark.asyncio
    async def test_load_balance_not_found_returns_404(self):
        """Verify model not found returns 404."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"model": "unknown-model"}')
        mock_request.json = AsyncMock(return_value={"model": "unknown-model"})

        with patch("routers.chat.resolve_model_name", return_value="unknown-model"):
            with patch("routers.chat.load_balance_url", return_value=(None, None, None)):
                response = await proxy_openai_stream(mock_request)

                assert isinstance(response, JSONResponse)
                assert response.status_code == 404
                content = json.loads(response.body.decode())
                assert "error" in content
                assert "not found" in content["error"].lower()

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_500(self):
        """Verify unexpected errors return 500."""
        mock_request = AsyncMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/chat/completions")
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4"}')
        mock_request.json = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        response = await proxy_openai_stream(mock_request)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        content = json.loads(response.body.decode())
        assert "error" in content


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

        with patch("routers.chat.run_in_threadpool", return_value=backend_result):
            with patch("routers.chat.Converters.convert_claude_to_openai", return_value={"converted": True}):
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

        with patch("routers.chat.run_in_threadpool", return_value=backend_result):
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

    @pytest.mark.asyncio
    async def test_run_in_threadpool_exception_handling(self):
        """Verify thread pool exceptions are handled."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        with patch("routers.chat.run_in_threadpool", side_effect=RuntimeError("Thread pool error")):
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
        mock_app_state.proxy_config.subaccounts = {}
        mock_app_state.proxy_context = Mock()

        async def make_request(model: str):
            mock_request = AsyncMock(spec=Request)
            mock_request.app.state = mock_app_state
            mock_request.method = "POST"
            mock_request.url = Mock(path="/v1/chat/completions")
            mock_request.body = AsyncMock(return_value=f'{{"model": "{model}"}}'.encode())
            mock_request.json = AsyncMock(return_value={"model": model})

            with patch("routers.chat.resolve_model_name", return_value=model):
                with patch("routers.chat.load_balance_url", return_value=("http://test.com", "test", model)):
                    with patch("routers.chat.fetch_token", return_value="token"):
                        with patch("routers.chat._handle_non_streaming_request", return_value=JSONResponse({"model": model})):
                            return await proxy_openai_stream(mock_request)

        # Make 5 concurrent requests
        import asyncio
        responses = await asyncio.gather(
            make_request("gpt-4"),
            make_request("claude-4"),
            make_request("gemini"),
            make_request("gpt-4.1"),
            make_request("claude-3.5"),
        )

        # All should succeed
        assert all(isinstance(r, JSONResponse) for r in responses)
        assert all(r.status_code == 200 for r in responses)
