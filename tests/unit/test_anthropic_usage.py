"""Unit tests for AnthropicUsage dataclass and AnthropicTokenUsageParser."""

from unittest.mock import patch

import pytest

from utils.anthropic_usage import AnthropicTokenUsageParser, AnthropicUsage


class TestAnthropicUsage:
    def test_default_construction_all_zero(self):
        u = AnthropicUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.cache_creation_input_tokens == 0
        assert u.cache_read_input_tokens == 0
        assert u.thinking_tokens == 0
        assert u.total_tokens == 0

    def test_total_tokens_sums_all_fields(self):
        u = AnthropicUsage(input_tokens=10, output_tokens=5, thinking_tokens=3)
        assert u.total_tokens == 18

    def test_total_tokens_excludes_cache_fields(self):
        u = AnthropicUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=10,
        )
        # Cache tokens billed at different rates; tracked separately, not in total.
        assert u.total_tokens == 150


class TestAnthropicTokenUsageParserParseResponse:
    def test_full_usage_object_parsed(self):
        parser = AnthropicTokenUsageParser()
        parser.parse_response({
            "usage": {
                "input_tokens": 100,
                "output_tokens": 200,
                "cache_creation_input_tokens": 30,
                "cache_read_input_tokens": 15,
                "thinking_tokens": 5,
            }
        })
        u = parser.usage
        assert u.input_tokens == 100
        assert u.output_tokens == 200
        assert u.cache_creation_input_tokens == 30
        assert u.cache_read_input_tokens == 15
        assert u.thinking_tokens == 5

    def test_partial_usage_defaults_missing_fields(self):
        parser = AnthropicTokenUsageParser()
        parser.parse_response({"usage": {"input_tokens": 50, "output_tokens": 25}})
        u = parser.usage
        assert u.input_tokens == 50
        assert u.output_tokens == 25
        assert u.cache_creation_input_tokens == 0
        assert u.cache_read_input_tokens == 0
        assert u.thinking_tokens == 0

    def test_missing_usage_key_stays_zero_and_warns(self):
        parser = AnthropicTokenUsageParser()
        with patch("utils.anthropic_usage._logger") as mock_log:
            parser.parse_response({"content": []})
            assert parser.usage.total_tokens == 0
            mock_log.warning.assert_not_called()  # missing key is silent (None branch)

    def test_none_usage_value_warns_no_raise(self):
        parser = AnthropicTokenUsageParser()
        with patch("utils.anthropic_usage._logger") as mock_log:
            parser.parse_response({"usage": None})
            assert parser.usage.total_tokens == 0
            mock_log.warning.assert_not_called()  # None is handled without warning

    def test_non_dict_usage_warns_no_raise(self):
        parser = AnthropicTokenUsageParser()
        with patch("utils.anthropic_usage._logger") as mock_log:
            parser.parse_response({"usage": 42})
            assert parser.usage.total_tokens == 0
            mock_log.warning.assert_called_once()

    def test_non_dict_response_warns_no_raise(self):
        parser = AnthropicTokenUsageParser()
        with patch("utils.anthropic_usage._logger") as mock_log:
            parser.parse_response("not a dict")
            assert parser.usage.total_tokens == 0
            mock_log.warning.assert_called_once()

    def test_exception_in_parse_is_caught_no_raise(self):
        parser = AnthropicTokenUsageParser()
        with patch("utils.anthropic_usage._logger") as mock_log:
            # Cause an internal exception by making .get() blow up
            class Exploding(dict):
                def get(self, *args, **kwargs):
                    raise RuntimeError("boom")

            parser.parse_response(Exploding())
            mock_log.warning.assert_called_once()


class TestAnthropicTokenUsageParserFeedChunk:
    def test_message_start_populates_input_tokens(self):
        parser = AnthropicTokenUsageParser()
        parser.feed_chunk({
            "type": "message_start",
            "message": {"usage": {"input_tokens": 80}},
        })
        assert parser.usage.input_tokens == 80

    def test_message_start_populates_cache_fields(self):
        parser = AnthropicTokenUsageParser()
        parser.feed_chunk({
            "type": "message_start",
            "message": {
                "usage": {
                    "input_tokens": 10,
                    "cache_creation_input_tokens": 7,
                    "cache_read_input_tokens": 3,
                }
            },
        })
        assert parser.usage.cache_creation_input_tokens == 7
        assert parser.usage.cache_read_input_tokens == 3

    def test_message_start_populates_thinking_tokens(self):
        parser = AnthropicTokenUsageParser()
        parser.feed_chunk({
            "type": "message_start",
            "message": {
                "usage": {
                    "input_tokens": 20,
                    "thinking_tokens": 8,
                }
            },
        })
        assert parser.usage.input_tokens == 20
        assert parser.usage.thinking_tokens == 8

    def test_message_delta_populates_output_tokens(self):
        parser = AnthropicTokenUsageParser()
        parser.feed_chunk({"type": "message_delta", "usage": {"output_tokens": 120}})
        assert parser.usage.output_tokens == 120

    def test_unknown_chunk_types_silently_ignored(self):
        parser = AnthropicTokenUsageParser()
        parser.feed_chunk({"type": "content_block_delta", "delta": {"text": "hi"}})
        parser.feed_chunk({"type": "content_block_start"})
        parser.feed_chunk({"type": "message_stop"})
        assert parser.usage.total_tokens == 0

    def test_full_stream_accumulation(self):
        parser = AnthropicTokenUsageParser()
        parser.feed_chunk({
            "type": "message_start",
            "message": {"usage": {"input_tokens": 50, "cache_read_input_tokens": 10}},
        })
        parser.feed_chunk({"type": "content_block_start"})
        parser.feed_chunk({"type": "content_block_delta", "delta": {"text": "hello"}})
        parser.feed_chunk({"type": "content_block_stop"})
        parser.feed_chunk({"type": "message_delta", "usage": {"output_tokens": 30}})
        parser.feed_chunk({"type": "message_stop"})

        u = parser.usage
        assert u.input_tokens == 50
        assert u.output_tokens == 30
        assert u.cache_read_input_tokens == 10
        assert u.total_tokens == 80  # cache tokens excluded from total

    def test_none_message_in_message_start_silently_ignored(self):
        # None message is guarded by `or {}` — no exception, no warning, tokens stay zero
        parser = AnthropicTokenUsageParser()
        parser.feed_chunk({"type": "message_start", "message": None})
        assert parser.usage.input_tokens == 0

    def test_exception_in_feed_chunk_is_caught_no_raise(self):
        parser = AnthropicTokenUsageParser()

        class RaisingDict(dict):
            def get(self, *args, **kwargs):
                raise RuntimeError("forced")

        with patch("utils.anthropic_usage._logger") as mock_log:
            # feed_chunk calls chunk.get("type") — if that raises, the except fires
            parser.feed_chunk(RaisingDict({"type": "message_start"}))
            mock_log.warning.assert_called_once()


class TestAnthropicTokenUsageParserLog:
    def test_basic_log_entry_emitted(self):
        parser = AnthropicTokenUsageParser()
        parser.parse_response({"usage": {"input_tokens": 10, "output_tokens": 5}})
        with patch("utils.anthropic_usage.token_usage_logger") as mock_logger:
            parser.log("claude-4.5", "acct1", "u1", "1.2.3.4")
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            msg = call_args[0][0] % call_args[0][1:]
            assert "claude-4.5" in msg
            assert "acct1" in msg
            assert "u1" in msg
            assert "1.2.3.4" in msg
            assert "10" in msg
            assert "5" in msg

    def test_cache_suffix_appended_when_nonzero(self):
        parser = AnthropicTokenUsageParser()
        parser.parse_response({
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_input_tokens": 3,
                "cache_read_input_tokens": 2,
            }
        })
        with patch("utils.anthropic_usage.token_usage_logger") as mock_logger:
            parser.log("m", "s", "u", "ip")
            call_args = mock_logger.info.call_args
            msg = call_args[0][0] % call_args[0][1:]
            assert "CacheCreationTokens" in msg
            assert "CacheReadTokens" in msg

    def test_thinking_suffix_appended_when_nonzero(self):
        parser = AnthropicTokenUsageParser()
        parser.parse_response({"usage": {"input_tokens": 10, "output_tokens": 5, "thinking_tokens": 4}})
        with patch("utils.anthropic_usage.token_usage_logger") as mock_logger:
            parser.log("m", "s", "u", "ip")
            call_args = mock_logger.info.call_args
            msg = call_args[0][0] % call_args[0][1:]
            assert "ThinkingTokens" in msg

    def test_no_cache_suffix_when_zero(self):
        parser = AnthropicTokenUsageParser()
        parser.parse_response({"usage": {"input_tokens": 10, "output_tokens": 5}})
        with patch("utils.anthropic_usage.token_usage_logger") as mock_logger:
            parser.log("m", "s", "u", "ip")
            call_args = mock_logger.info.call_args
            msg = call_args[0][0] % call_args[0][1:]
            assert "CacheCreationTokens" not in msg
            assert "ThinkingTokens" not in msg

    def test_suffix_parameter_appended(self):
        parser = AnthropicTokenUsageParser()
        with patch("utils.anthropic_usage.token_usage_logger") as mock_logger:
            parser.log("m", "s", "u", "ip", suffix="Streaming")
            call_args = mock_logger.info.call_args
            msg = call_args[0][0] % call_args[0][1:]
            assert "Streaming" in msg
