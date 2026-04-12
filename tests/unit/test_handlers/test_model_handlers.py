"""Tests for handlers/model_handlers.py — stream parameter default behaviour."""

from unittest.mock import MagicMock, patch

import pytest

from handlers.model_handlers import handle_claude_request


def _make_proxy_config(model: str = "claude-haiku", url: str = "https://test.url/dep-id"):
    cfg = MagicMock()
    cfg.subaccounts = {"acct": MagicMock()}
    return cfg


class TestHandleClaudeRequestStreamDefault:
    """Verify handle_claude_request() defaults stream to False (non-streaming)."""

    @patch("handlers.model_handlers.load_balance_url")
    @patch("handlers.model_handlers.Detector")
    @patch("handlers.model_handlers.Converters")
    def test_omit_stream_routes_to_non_streaming_endpoint(
        self, mock_converters, mock_detector, mock_load_balance
    ):
        """When stream is absent from payload, endpoint must be /converse (not /converse-stream)."""
        mock_load_balance.return_value = (
            "https://test.url/dep-id",
            "acct",
            "default",
            "claude-4-sonnet",
        )
        mock_detector.is_claude_37_or_4.return_value = True
        mock_converters.convert_openai_to_claude37.return_value = {}

        payload = {
            "model": "claude-4-sonnet",
            "messages": [{"role": "user", "content": "hi"}],
            # stream intentionally omitted
        }

        endpoint_url, _, _ = handle_claude_request(payload, "claude-4-sonnet", _make_proxy_config())

        assert endpoint_url.endswith("/converse"), (
            f"Expected non-streaming /converse endpoint, got: {endpoint_url}"
        )

    @patch("handlers.model_handlers.load_balance_url")
    @patch("handlers.model_handlers.Detector")
    @patch("handlers.model_handlers.Converters")
    def test_explicit_stream_false_routes_to_non_streaming_endpoint(
        self, mock_converters, mock_detector, mock_load_balance
    ):
        """Explicit stream=False must also route to /converse."""
        mock_load_balance.return_value = (
            "https://test.url/dep-id",
            "acct",
            "default",
            "claude-4-sonnet",
        )
        mock_detector.is_claude_37_or_4.return_value = True
        mock_converters.convert_openai_to_claude37.return_value = {}

        payload = {
            "model": "claude-4-sonnet",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        }

        endpoint_url, _, _ = handle_claude_request(payload, "claude-4-sonnet", _make_proxy_config())

        assert endpoint_url.endswith("/converse"), (
            f"Expected non-streaming /converse endpoint, got: {endpoint_url}"
        )

    @patch("handlers.model_handlers.load_balance_url")
    @patch("handlers.model_handlers.Detector")
    @patch("handlers.model_handlers.Converters")
    def test_explicit_stream_true_routes_to_streaming_endpoint(
        self, mock_converters, mock_detector, mock_load_balance
    ):
        """Regression: stream=True must still route to /converse-stream."""
        mock_load_balance.return_value = (
            "https://test.url/dep-id",
            "acct",
            "default",
            "claude-4-sonnet",
        )
        mock_detector.is_claude_37_or_4.return_value = True
        mock_converters.convert_openai_to_claude37.return_value = {}

        payload = {
            "model": "claude-4-sonnet",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }

        endpoint_url, _, _ = handle_claude_request(payload, "claude-4-sonnet", _make_proxy_config())

        assert endpoint_url.endswith("/converse-stream"), (
            f"Expected streaming /converse-stream endpoint, got: {endpoint_url}"
        )

    @patch("handlers.model_handlers.load_balance_url")
    @patch("handlers.model_handlers.Detector")
    @patch("handlers.model_handlers.Converters")
    def test_omit_stream_older_claude_routes_to_invoke(
        self, mock_converters, mock_detector, mock_load_balance
    ):
        """Older Claude models (not 3.7/4): omit stream → /invoke, not /invoke-with-response-stream."""
        mock_load_balance.return_value = (
            "https://test.url/dep-id",
            "acct",
            "default",
            "claude-3-5-sonnet",
        )
        mock_detector.is_claude_37_or_4.return_value = False
        mock_converters.convert_openai_to_claude.return_value = {}

        payload = {
            "model": "claude-3-5-sonnet",
            "messages": [{"role": "user", "content": "hi"}],
            # stream intentionally omitted
        }

        endpoint_url, _, _ = handle_claude_request(payload, "claude-3-5-sonnet", _make_proxy_config())

        assert endpoint_url.endswith("/invoke"), (
            f"Expected non-streaming /invoke endpoint, got: {endpoint_url}"
        )
