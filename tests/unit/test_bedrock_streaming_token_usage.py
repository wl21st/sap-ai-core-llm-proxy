"""Unit tests for token usage logging in generate_bedrock_streaming_response."""

import json
import logging
import pytest

from handlers.streaming_generators import generate_bedrock_streaming_response


def _make_event(chunk: dict) -> dict:
    return {"chunk": {"bytes": json.dumps(chunk).encode()}}


def _make_stream(chunks: list[dict]) -> list[dict]:
    return [_make_event(c) for c in chunks]


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


def _get_usage_log(caplog) -> str:
    return next(r.message for r in caplog.records if "PromptTokens:" in r.message)


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

        msg = _get_usage_log(caplog)
        assert "PromptTokens: 15" in msg
        assert "CompletionTokens: 4" in msg  # from message_delta, overrides message_start

    @pytest.mark.asyncio
    async def test_cache_fields_logged(self, caplog):
        """Cache creation and read tokens are included when non-zero."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(CACHE_CHUNKS))

        msg = _get_usage_log(caplog)
        assert "CacheCreationTokens: 500" in msg
        assert "CacheReadTokens: 200" in msg

    @pytest.mark.asyncio
    async def test_thinking_tokens_logged(self, caplog):
        """thinking_tokens is included when non-zero."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(EXTENDED_CHUNKS))

        msg = _get_usage_log(caplog)
        assert "ThinkingTokens: 120" in msg

    @pytest.mark.asyncio
    async def test_model_and_subaccount_in_log(self, caplog):
        """Model and subaccount appear in the log line."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS), model="claude-4.5-sonnet", subaccount="prod-acct")

        msg = _get_usage_log(caplog)
        assert "Model: claude-4.5-sonnet" in msg
        assert "SubAccount: prod-acct" in msg

    @pytest.mark.asyncio
    async def test_user_id_in_log(self, caplog):
        """User ID appears in the log line."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS), user_id="myuser")

        msg = _get_usage_log(caplog)
        assert "User: myuser" in msg

    @pytest.mark.asyncio
    async def test_ip_address_logged(self, caplog):
        """Client IP is included in the log."""
        with caplog.at_level(logging.INFO, logger="token_usage"):
            await _collect(_make_stream(BASIC_CHUNKS), ip_address="192.168.1.1")

        msg = _get_usage_log(caplog)
        assert "IP: 192.168.1.1" in msg

    @pytest.mark.asyncio
    async def test_chunks_pass_through_unchanged(self):
        """All SSE chunks are yielded normally regardless of logging."""
        results = await _collect(_make_stream(BASIC_CHUNKS))
        chunk_types = [r for r in results if r.startswith("event:")]
        assert any("message_start" in c for c in chunk_types)
        assert any("message_stop" in c for c in chunk_types)
        assert "data: [DONE]\n\n" in results
