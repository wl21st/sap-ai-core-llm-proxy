"""Unit tests for the streaming_handler module.

Tests the helper functions for handling streaming responses.
"""

import pytest

from handlers.streaming_handler import (
    get_claude_stop_reason_from_gemini_chunk,
    get_claude_stop_reason_from_openai_chunk,
    parse_sse_response_to_claude_json,
)


class TestGetClaudeStopReasonFromGeminiChunk:
    """Tests for get_claude_stop_reason_from_gemini_chunk function."""

    def test_stop_reason(self):
        """Test mapping of STOP finish reason."""
        chunk = {"candidates": [{"finishReason": "STOP"}]}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result == "end_turn"

    def test_max_tokens_reason(self):
        """Test mapping of MAX_TOKENS finish reason."""
        chunk = {"candidates": [{"finishReason": "MAX_TOKENS"}]}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result == "max_tokens"

    def test_safety_reason(self):
        """Test mapping of SAFETY finish reason."""
        chunk = {"candidates": [{"finishReason": "SAFETY"}]}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result == "stop_sequence"

    def test_recitation_reason(self):
        """Test mapping of RECITATION finish reason."""
        chunk = {"candidates": [{"finishReason": "RECITATION"}]}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result == "stop_sequence"

    def test_other_reason(self):
        """Test mapping of OTHER finish reason."""
        chunk = {"candidates": [{"finishReason": "OTHER"}]}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result == "stop_sequence"

    def test_unknown_reason_falls_back_to_stop_sequence(self):
        """Test that unknown finish reasons fall back to stop_sequence."""
        chunk = {"candidates": [{"finishReason": "UNKNOWN_REASON"}]}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result == "stop_sequence"

    def test_no_finish_reason_returns_none(self):
        """Test that missing finish reason returns None."""
        chunk = {"candidates": [{}]}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result is None

    def test_empty_candidates_raises_index_error(self):
        """Test that empty candidates list raises IndexError (matches original behavior)."""
        chunk = {"candidates": []}
        # The original implementation doesn't handle empty lists
        with pytest.raises(IndexError):
            get_claude_stop_reason_from_gemini_chunk(chunk)

    def test_no_candidates_key_returns_none(self):
        """Test that missing candidates key returns None."""
        chunk = {}
        result = get_claude_stop_reason_from_gemini_chunk(chunk)
        assert result is None


class TestGetClaudeStopReasonFromOpenAIChunk:
    """Tests for get_claude_stop_reason_from_openai_chunk function."""

    def test_stop_reason(self):
        """Test mapping of 'stop' finish reason."""
        chunk = {"choices": [{"finish_reason": "stop"}]}
        result = get_claude_stop_reason_from_openai_chunk(chunk)
        assert result == "end_turn"

    def test_length_reason(self):
        """Test mapping of 'length' finish reason."""
        chunk = {"choices": [{"finish_reason": "length"}]}
        result = get_claude_stop_reason_from_openai_chunk(chunk)
        assert result == "max_tokens"

    def test_content_filter_reason(self):
        """Test mapping of 'content_filter' finish reason."""
        chunk = {"choices": [{"finish_reason": "content_filter"}]}
        result = get_claude_stop_reason_from_openai_chunk(chunk)
        assert result == "stop_sequence"

    def test_tool_calls_reason(self):
        """Test mapping of 'tool_calls' finish reason."""
        chunk = {"choices": [{"finish_reason": "tool_calls"}]}
        result = get_claude_stop_reason_from_openai_chunk(chunk)
        assert result == "tool_use"

    def test_unknown_reason_falls_back_to_stop_sequence(self):
        """Test that unknown finish reasons fall back to stop_sequence."""
        chunk = {"choices": [{"finish_reason": "unknown_reason"}]}
        result = get_claude_stop_reason_from_openai_chunk(chunk)
        assert result == "stop_sequence"

    def test_no_finish_reason_returns_none(self):
        """Test that missing finish reason returns None."""
        chunk = {"choices": [{}]}
        result = get_claude_stop_reason_from_openai_chunk(chunk)
        assert result is None

    def test_empty_choices_raises_index_error(self):
        """Test that empty choices list raises IndexError (matches original behavior)."""
        chunk = {"choices": []}
        # The original implementation doesn't handle empty lists
        with pytest.raises(IndexError):
            get_claude_stop_reason_from_openai_chunk(chunk)

    def test_no_choices_key_returns_none(self):
        """Test that missing choices key returns None."""
        chunk = {}
        result = get_claude_stop_reason_from_openai_chunk(chunk)
        assert result is None


class TestParseSSEResponseToClaudeJson:
    """Tests for parse_sse_response_to_claude_json function."""

    def test_basic_text_content(self):
        """Test parsing of basic text content."""
        response_text = '''data: {"contentBlockDelta": {"delta": {"text": "Hello"}}}
data: {"contentBlockDelta": {"delta": {"text": " World"}}}
data: [DONE]'''
        result = parse_sse_response_to_claude_json(response_text)
        assert result["content"][0]["text"] == "Hello World"
        assert result["type"] == "message"
        assert result["role"] == "assistant"

    def test_with_usage_metadata(self):
        """Test parsing includes usage information."""
        response_text = '''data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: {"metadata": {"usage": {"inputTokens": 100, "outputTokens": 50}}}
data: [DONE]'''
        result = parse_sse_response_to_claude_json(response_text)
        assert result["usage"]["input_tokens"] == 100
        assert result["usage"]["output_tokens"] == 50

    def test_with_stop_reason(self):
        """Test parsing includes stop reason."""
        response_text = '''data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: {"messageStop": {"stopReason": "max_tokens"}}
data: [DONE]'''
        result = parse_sse_response_to_claude_json(response_text)
        assert result["stop_reason"] == "max_tokens"

    def test_default_stop_reason(self):
        """Test that default stop reason is end_turn."""
        response_text = '''data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: [DONE]'''
        result = parse_sse_response_to_claude_json(response_text)
        assert result["stop_reason"] == "end_turn"

    def test_empty_response(self):
        """Test parsing of empty response."""
        response_text = """data: [DONE]"""
        result = parse_sse_response_to_claude_json(response_text)
        assert result["content"][0]["text"] == ""

    def test_response_has_correct_structure(self):
        """Test that response has the correct structure."""
        response_text = """data: {"contentBlockDelta": {"delta": {"text": "Test"}}}"""
        result = parse_sse_response_to_claude_json(response_text)
        assert "id" in result
        assert result["id"].startswith("msg_")
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert "content" in result
        assert result["model"] == "claude-3-5-sonnet-20241022"
        assert result["stop_sequence"] is None
        assert "usage" in result

    def test_ignores_empty_data_lines(self):
        """Test that empty data lines are ignored."""
        response_text = '''data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: 
data: [DONE]'''
        result = parse_sse_response_to_claude_json(response_text)
        assert result["content"][0]["text"] == "Test"

    def test_ignores_non_data_lines(self):
        """Test that non-data lines are ignored."""
        response_text = '''event: message_start
id: msg_123
data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: [DONE]'''
        result = parse_sse_response_to_claude_json(response_text)
        assert result["content"][0]["text"] == "Test"

    def test_handles_malformed_json_gracefully(self):
        """Test that malformed JSON is handled gracefully."""
        response_text = '''data: {"contentBlockDelta": {"delta": {"text": "Before"}}}
data: not valid json
data: {"contentBlockDelta": {"delta": {"text": " After"}}}
data: [DONE]'''
        result = parse_sse_response_to_claude_json(response_text)
        # Should skip the malformed line and continue
        assert result["content"][0]["text"] == "Before After"
