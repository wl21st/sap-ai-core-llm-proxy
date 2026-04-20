"""Unit tests for chat router (Orchestration V2 path)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from routers.chat import router, proxy_openai_stream, _handle_orchestration_v2


# ---------------------------------------------------------------------------
# V2 availability helper
# ---------------------------------------------------------------------------

class TestOrchestrationV2Availability:
    def test_v2_available_when_wildcard_present(self):
        from routers.chat import _is_orchestration_v2_available
        config = Mock()
        config.model_to_subaccounts = {"*": ["sub1"]}
        assert _is_orchestration_v2_available(config) is True

    def test_v2_not_available_without_wildcard(self):
        from routers.chat import _is_orchestration_v2_available
        config = Mock()
        config.model_to_subaccounts = {"gpt-4o": ["sub1"]}
        assert _is_orchestration_v2_available(config) is False


# ---------------------------------------------------------------------------
# proxy_openai_stream — top-level handler
# ---------------------------------------------------------------------------

class TestProxyOpenaiStream:
    @pytest.mark.asyncio
    async def test_returns_json_on_success(self):
        """proxy_openai_stream delegates to V2 handler and returns JSON."""
        mock_request = AsyncMock(spec=Request)
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4o", "messages": []}')
        mock_request.json = AsyncMock(return_value={"model": "gpt-4o", "messages": []})
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")
        mock_request.url = Mock()

        mock_state = Mock()
        mock_state.proxy_config.model_to_subaccounts = {"*": ["sub1"]}
        mock_state.proxy_context.model_aliases = None
        mock_state.proxy_context.foundation_model_registry = None
        mock_state.proxy_config.subaccounts = {"sub1": Mock(
            resource_group="default",
            orchestration_url="https://api.ai.com/completion",
            service_key=Mock(identity_zone_id="z"),
        )}
        mock_state.proxy_context.get_token_manager.return_value.get_token.return_value = "tok"
        mock_request.app.state = mock_state

        expected = {"id": "chatcmpl-1", "choices": []}

        with patch("routers.chat.select_subaccount_for_orchestration", return_value="sub1"):
            with patch("routers.chat.get_orchestration_client") as mock_client_fn:
                mock_client = Mock()
                mock_client.invoke.return_value = expected
                mock_client_fn.return_value = mock_client

                with patch("routers.chat.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
                    mock_tp.return_value = expected
                    result = await proxy_openai_stream(mock_request)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_no_v2_subaccount_returns_503(self):
        """Returns 503 when no V2 subaccounts configured."""
        mock_request = AsyncMock(spec=Request)
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4o"}')
        mock_request.json = AsyncMock(return_value={"model": "gpt-4o"})
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")
        mock_request.url = Mock()

        mock_state = Mock()
        mock_state.proxy_config.model_to_subaccounts = {}
        mock_state.proxy_context.model_aliases = None
        mock_state.proxy_context.foundation_model_registry = None
        mock_request.app.state = mock_state

        with patch("routers.chat.select_subaccount_for_orchestration", side_effect=ValueError("no sub")):
            result = await proxy_openai_stream(mock_request)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 503


# ---------------------------------------------------------------------------
# _handle_orchestration_v2
# ---------------------------------------------------------------------------

class TestOrchestrationV2Path:
    @pytest.mark.asyncio
    async def test_unknown_model_returns_404_when_registry_present(self):
        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        mock_config = Mock()
        mock_config.model_to_subaccounts = {"*": ["sub1"]}

        mock_registry = Mock()
        mock_registry.is_known_model.return_value = False

        mock_context = Mock()
        mock_context.model_aliases = None
        mock_context.foundation_model_registry = mock_registry

        result = await _handle_orchestration_v2(
            request=mock_request,
            payload={"model": "unknown-model", "messages": []},
            original_model="unknown-model",
            effective_model="unknown-model",
            proxy_config=mock_config,
            proxy_context=mock_context,
            tid="test-tid",
            transport_logger=Mock(),
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_non_streaming_returns_json(self):
        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        mock_sub = Mock()
        mock_sub.orchestration_url = "https://api.ai.com/v2/deployment/orch"
        mock_sub.resource_group = "default"
        mock_sub.service_key = Mock(identity_zone_id="zone")

        mock_config = Mock()
        mock_config.subaccounts = {"sub1": mock_sub}

        mock_context = Mock()
        mock_context.model_aliases = None
        mock_context.foundation_model_registry = None
        mock_context.get_token_manager.return_value.get_token.return_value = "tok"

        expected_response = {
            "id": "chatcmpl-123",
            "choices": [{"message": {"role": "assistant", "content": "Hi"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }

        with patch("routers.chat.select_subaccount_for_orchestration", return_value="sub1"):
            with patch("routers.chat.get_orchestration_client") as mock_get_client:
                mock_client = Mock()
                mock_get_client.return_value = mock_client

                with patch("routers.chat.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
                    mock_tp.return_value = expected_response

                    result = await _handle_orchestration_v2(
                        request=mock_request,
                        payload={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
                        original_model="gpt-4o",
                        effective_model="gpt-4o",
                        proxy_config=mock_config,
                        proxy_context=mock_context,
                        tid="test-tid",
                        transport_logger=Mock(),
                    )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_streaming_returns_streaming_response(self):
        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        mock_sub = Mock()
        mock_sub.orchestration_url = "https://api.ai.com/v2/deployment/orch"
        mock_sub.resource_group = "default"
        mock_sub.service_key = Mock(identity_zone_id="zone")

        mock_config = Mock()
        mock_config.subaccounts = {"sub1": mock_sub}

        mock_context = Mock()
        mock_context.model_aliases = None
        mock_context.foundation_model_registry = None
        mock_context.get_token_manager.return_value.get_token.return_value = "tok"

        with patch("routers.chat.select_subaccount_for_orchestration", return_value="sub1"):
            with patch("routers.chat.get_orchestration_client") as mock_get_client:
                mock_client = Mock()
                mock_client.invoke_stream.return_value = iter([b"data: {}\n\n"])
                mock_get_client.return_value = mock_client

                result = await _handle_orchestration_v2(
                    request=mock_request,
                    payload={
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": "Hi"}],
                        "stream": True,
                    },
                    original_model="gpt-4o",
                    effective_model="gpt-4o",
                    proxy_config=mock_config,
                    proxy_context=mock_context,
                    tid="test-tid",
                    transport_logger=Mock(),
                )

        assert isinstance(result, StreamingResponse)

    @pytest.mark.asyncio
    async def test_alias_resolved_before_dispatch(self):
        """Model alias is resolved before calling OrchestrationClient."""
        mock_request = AsyncMock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")

        mock_sub = Mock()
        mock_sub.orchestration_url = "https://api.ai.com/orch"
        mock_sub.resource_group = "default"
        mock_sub.service_key = Mock(identity_zone_id="zone")

        mock_config = Mock()
        mock_config.subaccounts = {"sub1": mock_sub}
        mock_context = Mock()
        mock_context.model_aliases = {"claude-sonnet": "anthropic--claude-4.5-sonnet"}
        mock_context.foundation_model_registry = None
        mock_context.get_token_manager.return_value.get_token.return_value = "tok"

        captured = {}

        with patch("routers.chat.select_subaccount_for_orchestration", return_value="sub1"):
            with patch("routers.chat.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
                mock_tp.return_value = {"id": "r1", "choices": [], "usage": {}}

                await _handle_orchestration_v2(
                    request=mock_request,
                    payload={"model": "claude-sonnet", "messages": []},
                    original_model="claude-sonnet",
                    effective_model="claude-sonnet",
                    proxy_config=mock_config,
                    proxy_context=mock_context,
                    tid="tid",
                    transport_logger=Mock(),
                )
                # Capture what model was passed to run_in_threadpool
                if mock_tp.called:
                    call_kwargs = mock_tp.call_args[1]
                    captured["model"] = call_kwargs.get("model")

        # The alias should have been resolved before dispatch
        assert captured.get("model") == "anthropic--claude-4.5-sonnet"


# ---------------------------------------------------------------------------
# Streaming default (regression guard)
# ---------------------------------------------------------------------------

class TestStreamDefault:
    @pytest.mark.asyncio
    async def test_omit_stream_calls_non_streaming(self):
        """When stream is absent, non-streaming path (run_in_threadpool) is used."""
        mock_request = AsyncMock(spec=Request)
        mock_request.body = AsyncMock(return_value=b'{"model": "gpt-4o", "messages": []}')
        mock_request.json = AsyncMock(return_value={"model": "gpt-4o", "messages": []})
        mock_request.headers = {}
        mock_request.client = Mock(host="127.0.0.1")
        mock_request.url = Mock()

        mock_state = Mock()
        mock_state.proxy_config.model_to_subaccounts = {"*": ["sub1"]}
        mock_state.proxy_config.subaccounts = {"sub1": Mock(
            orchestration_url="https://api.ai.com/orch",
            resource_group="default",
            service_key=Mock(identity_zone_id="z"),
        )}
        mock_state.proxy_context.model_aliases = None
        mock_state.proxy_context.foundation_model_registry = None
        mock_state.proxy_context.get_token_manager.return_value.get_token.return_value = "tok"
        mock_request.app.state = mock_state

        with patch("routers.chat.select_subaccount_for_orchestration", return_value="sub1"):
            with patch("routers.chat.get_orchestration_client"):
                with patch("routers.chat.run_in_threadpool", new_callable=AsyncMock) as mock_tp:
                    mock_tp.return_value = {"id": "r", "choices": [], "usage": {}}
                    await proxy_openai_stream(mock_request)

        mock_tp.assert_called_once()
