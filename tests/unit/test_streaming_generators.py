"""Unit tests for async streaming generators."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi import Request
import httpx

from handlers.streaming_generators import generate_streaming_response


class TestGenerateStreamingResponseLifecycle:
    """Test async generator lifecycle and cleanup."""

    @pytest.mark.asyncio
    async def test_async_generator_cleanup_on_normal_completion(self):
        """Verify async generator cleanup after normal completion."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        # Mock httpx response
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.aiter_lines = AsyncMock(return_value=iter(["data: [DONE]"]))

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.__aexit__ = AsyncMock()
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Consume generator
            chunks = []
            async for chunk in generate_streaming_response(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "gpt-4"},
                model="gpt-4",
                subaccount_name="test",
                tid="test-123",
            ):
                chunks.append(chunk)

            # Verify cleanup was called
            mock_client.__aexit__.assert_called_once()
            mock_stream.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_generator_cleanup_on_early_break(self):
        """Verify cleanup when generator stopped early."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        async def mock_lines():
            for i in range(100):
                yield f'data: {{"chunk": {i}}}\n\n'

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.aiter_lines = Mock(return_value=mock_lines())

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.__aexit__ = AsyncMock()
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Consume only first 5 chunks then break
            chunk_count = 0
            async for chunk in generate_streaming_response(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "gpt-4"},
                model="gpt-4",
                subaccount_name="test",
                tid="test-123",
            ):
                chunk_count += 1
                if chunk_count == 5:
                    break

            # Give cleanup a chance to run
            await asyncio.sleep(0.1)

            # Verify cleanup was called even with early break
            mock_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_generator_cleanup_on_exception(self):
        """Verify cleanup when exception occurs in generator."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Error", request=Mock(), response=Mock(status_code=500, text="Error")
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.__aexit__ = AsyncMock()
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Consume generator (will get error)
            chunks = []
            async for chunk in generate_streaming_response(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "gpt-4"},
                model="gpt-4",
                subaccount_name="test",
                tid="test-123",
            ):
                chunks.append(chunk)

            # Verify cleanup was called even with exception
            mock_client.__aexit__.assert_called_once()
            mock_stream.__aexit__.assert_called_once()


class TestHttpxExceptionHandling:
    """Test httpx-specific exception handling."""

    @pytest.mark.asyncio
    async def test_timeout_exception_returns_504(self):
        """Verify TimeoutException returns 504 Gateway Timeout."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            mock_stream.__aexit__ = AsyncMock()
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Consume generator
            chunks = []
            async for chunk in generate_streaming_response(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "gpt-4"},
                model="gpt-4",
                subaccount_name="test",
                tid="test-123",
            ):
                chunks.append(chunk)

            # Verify error payload contains 504
            assert len(chunks) == 2  # Error + [DONE]
            error_data = json.loads(chunks[0].replace("data: ", ""))
            assert error_data["error"]["code"] == 504
            assert error_data["error"]["type"] == "timeout_error"
            assert "timed out" in error_data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_connect_error_returns_503(self):
        """Verify ConnectError returns 503 Service Unavailable."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_stream.__aexit__ = AsyncMock()
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in generate_streaming_response(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "gpt-4"},
                model="gpt-4",
                subaccount_name="test",
                tid="test-123",
            ):
                chunks.append(chunk)

            assert len(chunks) == 2
            error_data = json.loads(chunks[0].replace("data: ", ""))
            assert error_data["error"]["code"] == 503
            assert error_data["error"]["type"] == "connection_error"

    @pytest.mark.asyncio
    async def test_read_error_returns_502(self):
        """Verify ReadError returns 502 Bad Gateway."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()

        async def failing_lines():
            yield 'data: {"test": 1}\n\n'
            raise httpx.ReadError("Connection lost")

        def aiter_lines_impl():
            return failing_lines()

        mock_response.aiter_lines = Mock(side_effect=aiter_lines_impl)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.__aexit__ = AsyncMock(return_value=False)
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in generate_streaming_response(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={
                    "model": "claude-4"
                },  # Use Claude model that uses aiter_lines()
                model="claude-4",
                subaccount_name="test",
                tid="test-123",
            ):
                chunks.append(chunk)

            # Should get initial chunk, then error + [DONE]
            assert len(chunks) >= 2
            # Find error chunk
            error_chunk = next(c for c in chunks if "error" in c and "502" in c)
            error_data = json.loads(error_chunk.replace("data: ", ""))
            assert error_data["error"]["code"] == 502
            assert error_data["error"]["type"] == "connection_error"


class TestConcurrentStreaming:
    """Test concurrent streaming request isolation."""

    @pytest.mark.asyncio
    async def test_concurrent_streams_isolated(self):
        """Verify concurrent streaming requests don't interfere."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        async def create_stream(model_name: str, chunk_count: int):
            """Helper to create a mock stream."""

            async def mock_lines():
                for i in range(chunk_count):
                    yield f'data: {{"model": "{model_name}", "chunk": {i}}}\n\n'
                yield "data: [DONE]"

            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()

            def aiter_lines_impl():
                return mock_lines()

            mock_response.aiter_lines = Mock(side_effect=aiter_lines_impl)

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_stream = AsyncMock()
                mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
                mock_stream.__aexit__ = AsyncMock(return_value=False)
                mock_client.stream = Mock(return_value=mock_stream)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_class.return_value = mock_client

                chunks = []
                async for chunk in generate_streaming_response(
                    request=mock_request,
                    url="http://test.com",
                    headers={},
                    payload={"model": model_name},
                    model=model_name,
                    subaccount_name="test",
                    tid=f"test-{model_name}",
                ):
                    chunks.append(chunk)
                return chunks

        # Run 3 concurrent streams
        results = await asyncio.gather(
            create_stream("claude-4", 5),
            create_stream("claude-37", 7),
            create_stream("gemini", 3),
        )

        # Verify each stream got correct number of chunks
        assert len(results[0]) >= 5
        assert len(results[1]) >= 7
        assert len(results[2]) >= 3

        # Verify chunks aren't mixed between streams
        for chunks in results:
            # All non-[DONE] chunks should have same model
            data_chunks = [c for c in chunks if "[DONE]" not in c and c.strip()]
            if data_chunks:
                first_model = None
                for chunk in data_chunks:
                    if chunk.startswith("data: {"):
                        try:
                            data = json.loads(chunk.replace("data: ", ""))
                            if "model" in data:
                                if first_model is None:
                                    first_model = data["model"]
                                else:
                                    assert data["model"] == first_model
                        except json.JSONDecodeError:
                            pass  # Skip malformed chunks


class TestTokenUsageTracking:
    """Test token usage extraction across async boundaries."""

    @pytest.mark.asyncio
    async def test_claude_37_token_usage_extraction(self):
        """Verify token usage extracted from Claude 3.7/4 metadata."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        async def mock_lines():
            yield 'data: {"messageStart": {"message": {"id": "msg_123"}}}'
            yield 'data: {"contentBlockStart": {"index": 0}}'
            yield 'data: {"contentBlockDelta": {"delta": {"text": "Hello"}}}'
            yield 'data: {"messageStop": {"stopReason": "end_turn"}}'
            yield 'data: {"metadata": {"usage": {"totalTokens": 100, "inputTokens": 20, "outputTokens": 80}}}'

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.aiter_lines = Mock(return_value=mock_lines())

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.__aexit__ = AsyncMock()
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            chunks = []
            with patch(
                "handlers.streaming_generators.token_usage_logger"
            ) as mock_logger:
                async for chunk in generate_streaming_response(
                    request=mock_request,
                    url="http://test.com",
                    headers={},
                    payload={"model": "claude-4"},
                    model="claude-4",
                    subaccount_name="test",
                    tid="test-123",
                ):
                    chunks.append(chunk)

                # Verify token usage was logged
                mock_logger.info.assert_called()
                call_args = str(mock_logger.info.call_args)
                assert "100" in call_args  # total tokens
                assert "20" in call_args  # prompt tokens
                assert "80" in call_args  # completion tokens


class TestStreamingErrorNotification:
    """Test that errors during streaming notify the user."""

    @pytest.mark.asyncio
    async def test_chunk_parse_error_sends_error_event(self):
        """Verify chunk parsing errors send error event to user."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        async def mock_lines():
            yield 'data: {"messageStart": {"message": {"id": "msg_123"}}}'
            yield 'data: {"contentBlockStart": {"index": 0}}'
            # Invalid JSON will trigger error
            yield "data: {invalid json here"

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.aiter_lines = Mock(return_value=mock_lines())

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream.__aexit__ = AsyncMock()
            mock_client.stream = Mock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in generate_streaming_response(
                request=mock_request,
                url="http://test.com",
                headers={},
                payload={"model": "claude-4"},
                model="claude-4",
                subaccount_name="test",
                tid="test-123",
            ):
                chunks.append(chunk)

            # Should get error event before [DONE]
            error_events = [c for c in chunks if "PROXY ERROR" in c]
            assert len(error_events) > 0, "Expected error event for parse failure"
