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
        response_text = """data: {"contentBlockDelta": {"delta": {"text": "Hello"}}}
data: {"contentBlockDelta": {"delta": {"text": " World"}}}
data: [DONE]"""
        result = parse_sse_response_to_claude_json(response_text)
        assert result["content"][0]["text"] == "Hello World"
        assert result["type"] == "message"
        assert result["role"] == "assistant"

    def test_with_usage_metadata(self):
        """Test parsing includes usage information."""
        response_text = """data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: {"metadata": {"usage": {"inputTokens": 100, "outputTokens": 50}}}
data: [DONE]"""
        result = parse_sse_response_to_claude_json(response_text)
        assert result["usage"]["input_tokens"] == 100
        assert result["usage"]["output_tokens"] == 50

    def test_with_stop_reason(self):
        """Test parsing includes stop reason."""
        response_text = """data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: {"messageStop": {"stopReason": "max_tokens"}}
data: [DONE]"""
        result = parse_sse_response_to_claude_json(response_text)
        assert result["stop_reason"] == "max_tokens"

    def test_default_stop_reason(self):
        """Test that default stop reason is end_turn."""
        response_text = """data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: [DONE]"""
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
        response_text = """data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: 
data: [DONE]"""
        result = parse_sse_response_to_claude_json(response_text)
        assert result["content"][0]["text"] == "Test"

    def test_ignores_non_data_lines(self):
        """Test that non-data lines are ignored."""
        response_text = """event: message_start
id: msg_123
data: {"contentBlockDelta": {"delta": {"text": "Test"}}}
data: [DONE]"""
        result = parse_sse_response_to_claude_json(response_text)
        assert result["content"][0]["text"] == "Test"

    def test_handles_malformed_json_gracefully(self):
        """Test that malformed JSON is handled gracefully."""
        response_text = """data: {"contentBlockDelta": {"delta": {"text": "Before"}}}
data: not valid json
data: {"contentBlockDelta": {"delta": {"text": " After"}}}
data: [DONE]"""
        result = parse_sse_response_to_claude_json(response_text)
        # Should skip the malformed line and continue
        assert result["content"][0]["text"] == "Before After"


class TestBackendRequestResult:
    """Tests for the BackendRequestResult dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        from handlers.streaming_handler import BackendRequestResult

        result = BackendRequestResult(success=True, response_data={"key": "value"})
        assert result.success is True
        assert result.response_data == {"key": "value"}
        assert result.error_message is None
        assert result.status_code == 200
        assert result.is_sse_response is False

    def test_error_result(self):
        """Test creating an error result."""
        from handlers.streaming_handler import BackendRequestResult

        result = BackendRequestResult(
            success=False,
            response_data=None,
            error_message="Connection failed",
            status_code=500,
        )
        assert result.success is False
        assert result.response_data is None
        assert result.error_message == "Connection failed"
        assert result.status_code == 500

    def test_sse_response_flag(self):
        """Test SSE response flag."""
        from handlers.streaming_handler import BackendRequestResult

        result = BackendRequestResult(
            success=True,
            response_data={"content": "test"},
            is_sse_response=True,
        )
        assert result.is_sse_response is True


class TestMakeBackendRequest:
    """Tests for the make_backend_request function."""

    def test_successful_json_response(self, mocker):
        """Test successful JSON response handling."""
        from handlers.streaming_handler import make_backend_request

        mock_response = mocker.Mock()
        mock_response.text = '{"result": "success"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.status_code = 200
        mock_response.raise_for_status = mocker.Mock()
        mock_response.json.return_value = {"result": "success"}

        mock_post = mocker.patch("requests.post", return_value=mock_response)

        result = make_backend_request(
            url="https://api.example.com/v1/chat",
            headers={"Authorization": "Bearer token"},
            payload={"model": "gpt-4", "messages": []},
            model="gpt-4",
            tid="test-trace-id",
            is_claude_model_fn=lambda m: False,
        )

        assert result.success is True
        assert result.response_data == {"result": "success"}
        assert result.status_code == 200
        assert result.error_message is None
        mock_post.assert_called_once()

    def test_http_error_with_json_body(self, mocker):
        """Test HTTP error with JSON error body."""
        import requests
        from handlers.streaming_handler import make_backend_request

        mock_response = mocker.Mock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Bad request"}}'
        mock_response.headers = {"content-type": "application/json"}  # Proper dict
        mock_response.json.return_value = {"error": {"message": "Bad request"}}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )

        mocker.patch("requests.post", return_value=mock_response)

        result = make_backend_request(
            url="https://api.example.com/v1/chat",
            headers={},
            payload={},
            model="gpt-4",
            tid="test-trace-id",
            is_claude_model_fn=lambda m: False,
        )

        assert result.success is False
        assert result.status_code == 400
        assert result.response_data == {"error": {"message": "Bad request"}}
        # When JSON body is returned, error_message is None - error info is in response_data
        assert result.error_message is None

    def test_connection_timeout(self, mocker):
        """Test connection timeout handling."""
        import requests
        from handlers.streaming_handler import make_backend_request

        mocker.patch(
            "requests.post",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        )

        result = make_backend_request(
            url="https://api.example.com/v1/chat",
            headers={},
            payload={},
            model="gpt-4",
            tid="test-trace-id",
            is_claude_model_fn=lambda m: False,
            timeout=30,
        )

        assert result.success is False
        assert result.status_code == 500
        assert "timed out" in result.error_message.lower()

    def test_claude_model_sse_response(self, mocker):
        """Test Claude model SSE response parsing."""
        from handlers.streaming_handler import make_backend_request

        sse_response = """data: {"contentBlockDelta": {"delta": {"text": "Hello"}}}
data: {"contentBlockDelta": {"delta": {"text": " World"}}}
data: [DONE]"""

        mock_response = mocker.Mock()
        mock_response.text = sse_response
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = mocker.Mock()

        mocker.patch("requests.post", return_value=mock_response)

        result = make_backend_request(
            url="https://api.example.com/v1/chat",
            headers={},
            payload={"model": "anthropic--claude-3-sonnet"},
            model="anthropic--claude-3-sonnet",
            tid="test-trace-id",
            is_claude_model_fn=lambda m: "claude" in m.lower(),
        )

        assert result.success is True
        assert result.is_sse_response is True
        assert result.response_data["content"][0]["text"] == "Hello World"
        assert result.response_data["type"] == "message"

    def test_non_claude_model_returns_json(self, mocker):
        """Test non-Claude model returns parsed JSON."""
        from handlers.streaming_handler import make_backend_request

        mock_response = mocker.Mock()
        mock_response.text = '{"choices": [{"message": {"content": "Hello"}}]}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = mocker.Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello"}}]
        }

        mocker.patch("requests.post", return_value=mock_response)

        result = make_backend_request(
            url="https://api.example.com/v1/chat",
            headers={},
            payload={},
            model="gpt-4",
            tid="test-trace-id",
            is_claude_model_fn=lambda m: False,
        )

        assert result.success is True
        assert result.is_sse_response is False
        assert result.response_data["choices"][0]["message"]["content"] == "Hello"

    def test_custom_timeout(self, mocker):
        """Test that custom timeout is passed to requests."""
        from handlers.streaming_handler import make_backend_request

        mock_response = mocker.Mock()
        mock_response.text = '{"result": "ok"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = mocker.Mock()
        mock_response.json.return_value = {"result": "ok"}

        mock_post = mocker.patch("requests.post", return_value=mock_response)

        make_backend_request(
            url="https://api.example.com/v1/chat",
            headers={},
            payload={},
            model="gpt-4",
            tid="test-trace-id",
            is_claude_model_fn=lambda m: False,
            timeout=60,
        )

        # Verify timeout was passed
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["timeout"] == 60
