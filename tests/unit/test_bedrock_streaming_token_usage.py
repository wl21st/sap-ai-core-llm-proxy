"""Unit tests for token usage logging in the /v1/messages endpoint."""

import json
import logging
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from saip.handlers.streaming_generators import generate_bedrock_streaming_response
from saip.routers.messages import router


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

def _make_event(chunk: dict) -> dict:
    return {"chunk": {"bytes": json.dumps(chunk).encode()}}


def _make_stream(chunks: list[dict]) -> list[dict]:
    return [_make_event(c) for c in chunks]


# ---------------------------------------------------------------------------
# Fixture chunk sequences
# ---------------------------------------------------------------------------

BASIC_CHUNKS = [
    {"type": "message_start", "message": {"usage": {
        "input_tokens": 15, "output_tokens": 1,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
    }}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 4}},
    {"type": "message_stop"},
]

CACHE_CHUNKS = [
    {"type": "message_start", "message": {"usage": {
        "input_tokens": 100, "output_tokens": 1,
        "cache_creation_input_tokens": 500, "cache_read_input_tokens": 200,
    }}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hi"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 8}},
    {"type": "message_stop"},
]

EXTENDED_CHUNKS = [
    {"type": "message_start", "message": {"usage": {
        "input_tokens": 50, "output_tokens": 0,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
        "thinking_tokens": 120,
    }}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Answer"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 20}},
    {"type": "message_stop"},
]


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

async def _collect(
    chunks,
    user_id: str = "testtoken123",
    ip_address: str = "10.0.0.1",
    model: str = "claude-4.5",
    subaccount: str = "acct1",
) -> list[str]:
    results = []
    async for chunk in generate_bedrock_streaming_response(
        chunks, "tid-test", model=model, subaccount_name=subaccount,
        user_id=user_id, ip_address=ip_address,
    ):
        results.append(chunk)
    return results


def _get_streaming_log(caplog) -> str:
    return next(r.message for r in caplog.records if "PromptTokens:" in r.message)


# ---------------------------------------------------------------------------
# Streaming path tests
# ---------------------------------------------------------------------------

class TestBedrockStreamingTokenLogging:

    @pytest.mark.asyncio
    async def test_usage_logged(self, caplog):
        """Token usage is logged after message_stop."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS))

        assert any("PromptTokens:" in r.message for r in caplog.records)
        assert any("(Streaming)" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_prompt_and_completion_tokens(self, caplog):
        """input_tokens maps to PromptTokens, output_tokens to CompletionTokens."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS))

        msg = _get_streaming_log(caplog)
        assert "PromptTokens: 15" in msg
        assert "CompletionTokens: 4" in msg  # from message_delta, overrides message_start

    @pytest.mark.asyncio
    async def test_cache_fields_logged(self, caplog):
        """Cache creation and read tokens are included when non-zero."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(CACHE_CHUNKS))

        msg = _get_streaming_log(caplog)
        assert "CacheCreationTokens: 500" in msg
        assert "CacheReadTokens: 200" in msg

    @pytest.mark.asyncio
    async def test_thinking_tokens_logged(self, caplog):
        """thinking_tokens is included when non-zero."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(EXTENDED_CHUNKS))

        msg = _get_streaming_log(caplog)
        assert "ThinkingTokens: 120" in msg

    @pytest.mark.asyncio
    async def test_model_and_subaccount_in_log(self, caplog):
        """Model and subaccount appear in the log line."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS), model="claude-4.5-sonnet", subaccount="prod-acct")

        msg = _get_streaming_log(caplog)
        assert "Model: claude-4.5-sonnet" in msg
        assert "SubAccount: prod-acct" in msg

    @pytest.mark.asyncio
    async def test_user_id_in_log(self, caplog):
        """User ID appears in the log line."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS), user_id="myuser")

        msg = _get_streaming_log(caplog)
        assert "User: myuser" in msg

    @pytest.mark.asyncio
    async def test_ip_address_logged(self, caplog):
        """Client IP is included in the log."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS), ip_address="192.168.1.1")

        msg = _get_streaming_log(caplog)
        assert "IP: 192.168.1.1" in msg

    @pytest.mark.asyncio
    async def test_chunks_pass_through_unchanged(self):
        """All SSE chunks are yielded normally regardless of logging."""
        results = await _collect(_make_stream(BASIC_CHUNKS))
        chunk_types = [r for r in results if r.startswith("event:")]
        assert any("message_start" in c for c in chunk_types)
        assert any("message_stop" in c for c in chunk_types)
        assert "data: [DONE]\n\n" in results


# ---------------------------------------------------------------------------
# Non-streaming path tests (router level)
# ---------------------------------------------------------------------------

def _make_router_client():
    mock_config = MagicMock()
    mock_config.secret_authentication_tokens = []
    mock_subaccount = MagicMock()
    mock_config.subaccounts = {"test_subaccount": mock_subaccount}
    app = FastAPI()
    app.include_router(router)
    app.state.proxy_config = mock_config
    app.state.proxy_context = MagicMock()
    return TestClient(app, raise_server_exceptions=False), mock_config


@patch("saip.routers.messages.verify_request_token", return_value=True)
@patch("saip.routers.messages.load_balance_url")
@patch("saip.routers.messages.get_bedrock_client")
@patch("saip.routers.messages.invalidate_bedrock_client")
@patch("saip.routers.messages.Detector")
@patch("saip.routers.messages.extract_deployment_id")
class TestNonStreamingTokenLogging:

    def _setup_mocks(self, mock_extract_id, mock_detector, mock_invalidate, mock_get_client, mock_load_balance, response_body_json: dict):
        mock_load_balance.return_value = (
            "https://test.url/deploy-id", "test_subaccount", "rg", "anthropic--claude-4.5-sonnet"
        )
        mock_detector.is_claude_model.return_value = True
        mock_extract_id.return_value = "deploy-id"
        mock_get_client.return_value = MagicMock()
        return json.dumps(response_body_json)

    def test_non_streaming_logs_usage(
        self, mock_extract_id, mock_detector, mock_invalidate, mock_get_client, mock_load_balance, mock_validate, caplog
    ):
        """Non-streaming path logs token counts to token_usage logger."""
        client, _ = _make_router_client()
        response_json = {
            "type": "message", "role": "assistant",
            "content": [{"type": "text", "text": "Hi"}],
            "usage": {"input_tokens": 20, "output_tokens": 10,
                      "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        }
        body_str = self._setup_mocks(mock_extract_id, mock_detector, mock_invalidate, mock_get_client, mock_load_balance, response_json)

        with patch("saip.routers.messages.invoke_bedrock_non_streaming") as mock_invoke, \
             patch("saip.routers.messages.read_response_body_stream", return_value=body_str), \
             caplog.at_level(logging.INFO, logger="token_usage"):
            mock_invoke.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}, "body": MagicMock()}
            client.post("/v1/messages", json={
                "model": "anthropic--claude-4.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            })

        log_msg = next((r.message for r in caplog.records if "PromptTokens:" in r.message), None)
        assert log_msg is not None, "Expected a token usage log entry"
        assert "PromptTokens: 20" in log_msg
        assert "CompletionTokens: 10" in log_msg

    def test_non_streaming_logs_cache_fields(
        self, mock_extract_id, mock_detector, mock_invalidate, mock_get_client, mock_load_balance, mock_validate, caplog
    ):
        """Non-streaming path includes cache token fields when non-zero."""
        client, _ = _make_router_client()
        response_json = {
            "type": "message", "role": "assistant",
            "content": [{"type": "text", "text": "Hi"}],
            "usage": {
                "input_tokens": 50, "output_tokens": 15,
                "cache_creation_input_tokens": 300, "cache_read_input_tokens": 100,
            },
        }
        body_str = self._setup_mocks(mock_extract_id, mock_detector, mock_invalidate, mock_get_client, mock_load_balance, response_json)

        with patch("saip.routers.messages.invoke_bedrock_non_streaming") as mock_invoke, \
             patch("saip.routers.messages.read_response_body_stream", return_value=body_str), \
             caplog.at_level(logging.INFO, logger="token_usage"):
            mock_invoke.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}, "body": MagicMock()}
            client.post("/v1/messages", json={
                "model": "anthropic--claude-4.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            })

        log_msg = next((r.message for r in caplog.records if "PromptTokens:" in r.message), None)
        assert log_msg is not None
        assert "CacheCreationTokens: 300" in log_msg
        assert "CacheReadTokens: 100" in log_msg

    def test_non_streaming_missing_usage_no_crash(
        self, mock_extract_id, mock_detector, mock_invalidate, mock_get_client, mock_load_balance, mock_validate, caplog
    ):
        """Non-streaming path does not crash when usage is absent from response."""
        client, _ = _make_router_client()
        response_json = {
            "type": "message", "role": "assistant",
            "content": [{"type": "text", "text": "Hi"}],
            # no "usage" key
        }
        body_str = self._setup_mocks(mock_extract_id, mock_detector, mock_invalidate, mock_get_client, mock_load_balance, response_json)

        with patch("saip.routers.messages.invoke_bedrock_non_streaming") as mock_invoke, \
             patch("saip.routers.messages.read_response_body_stream", return_value=body_str), \
             caplog.at_level(logging.INFO, logger="token_usage"):
            mock_invoke.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}, "body": MagicMock()}
            resp = client.post("/v1/messages", json={
                "model": "anthropic--claude-4.5-sonnet",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            })

        assert resp.status_code == 200
