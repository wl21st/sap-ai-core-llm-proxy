"""Unit tests for embeddings router."""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import Request
from fastapi.responses import JSONResponse

from routers.embeddings import handle_embedding_request


class TestEmbeddingsRouterRequestHandling:
    """Test embeddings request handling."""

    @pytest.mark.asyncio
    async def test_successful_embedding_request(self):
        """Verify successful embedding request returns JSON."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {}

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/embeddings")
        mock_request.json = AsyncMock(return_value={
            "input": "test text",
            "model": "text-embedding-3-small"
        })

        backend_result = Mock()
        backend_result.success = True
        backend_result.response_data = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
            "model": "text-embedding-3-small"
        }

        with patch("routers.embeddings.resolve_model_name", return_value="text-embedding-3-small"):
            with patch("routers.embeddings.load_balance_url", return_value=("http://test.com", "test", "text-embedding-3-small")):
                with patch("routers.embeddings.fetch_token", return_value="token"):
                    with patch("routers.embeddings.run_in_threadpool", return_value=backend_result):
                        response = await handle_embedding_request(mock_request)

                        assert isinstance(response, JSONResponse)
                        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_input_returns_400(self):
        """Verify missing input text returns 400."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/embeddings")
        mock_request.json = AsyncMock(return_value={"model": "text-embedding-3-small"})  # No input

        response = await handle_embedding_request(mock_request)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        content = json.loads(response.body.decode())
        assert "error" in content

    @pytest.mark.asyncio
    async def test_rate_limit_error_returns_429(self):
        """Verify rate limit errors return 429."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {}

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/embeddings")
        mock_request.json = AsyncMock(return_value={
            "input": "test",
            "model": "text-embedding-3-small"
        })

        backend_result = Mock()
        backend_result.success = False
        backend_result.status_code = 429
        backend_result.error_message = "Rate limit exceeded"

        with patch("routers.embeddings.resolve_model_name", return_value="text-embedding-3-small"):
            with patch("routers.embeddings.load_balance_url", return_value=("http://test.com", "test", "text-embedding-3-small")):
                with patch("routers.embeddings.fetch_token", return_value="token"):
                    with patch("routers.embeddings.run_in_threadpool", return_value=backend_result):
                        response = await handle_embedding_request(mock_request)

                        assert isinstance(response, JSONResponse)
                        assert response.status_code == 429


class TestThreadPoolHandling:
    """Test thread pool offloading for embeddings."""

    @pytest.mark.asyncio
    async def test_run_in_threadpool_called(self):
        """Verify synchronous backend call offloaded to thread pool."""
        mock_app_state = Mock()
        mock_app_state.proxy_config = Mock()
        mock_app_state.proxy_config.subaccounts = {}

        mock_request = AsyncMock(spec=Request)
        mock_request.app.state = mock_app_state
        mock_request.method = "POST"
        mock_request.url = Mock(path="/v1/embeddings")
        mock_request.json = AsyncMock(return_value={
            "input": "test",
            "model": "text-embedding-3-small"
        })

        backend_result = Mock()
        backend_result.success = True
        backend_result.response_data = {"data": []}

        with patch("routers.embeddings.resolve_model_name", return_value="text-embedding-3-small"):
            with patch("routers.embeddings.load_balance_url", return_value=("http://test.com", "test", "text-embedding-3-small")):
                with patch("routers.embeddings.fetch_token", return_value="token"):
                    with patch("routers.embeddings.run_in_threadpool", return_value=backend_result) as mock_threadpool:
                        await handle_embedding_request(mock_request)

                        # Verify run_in_threadpool was called
                        mock_threadpool.assert_called_once()
                        # First argument should be the function to run
                        assert callable(mock_threadpool.call_args[0][0])
