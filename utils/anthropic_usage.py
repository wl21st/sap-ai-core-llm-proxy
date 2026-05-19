"""Anthropic token usage parsing and logging for the /v1/messages path."""

import logging
from dataclasses import dataclass

from utils.logging_utils import get_server_logger

token_usage_logger = get_server_logger("token_usage")
_logger = logging.getLogger(__name__)


@dataclass
class AnthropicUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    thinking_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        # Cache tokens are billed at different rates; excluded here and logged separately.
        return self.input_tokens + self.output_tokens + self.thinking_tokens


class AnthropicTokenUsageParser:
    """Parses Anthropic REST API usage fields and logs them via token_usage_logger.

    Usage (non-streaming):
        parser = AnthropicTokenUsageParser()
        parser.parse_response(response_json)
        parser.log(model, subaccount, user_id, ip_address)

    Usage (streaming):
        parser = AnthropicTokenUsageParser()
        for chunk in sse_events:
            parser.feed_chunk(chunk)
        parser.log(model, subaccount, user_id, ip_address)
    """

    def __init__(self) -> None:
        self._usage = AnthropicUsage()

    @property
    def usage(self) -> AnthropicUsage:
        return self._usage

    def parse_response(self, response: object) -> None:
        """Extract usage from a complete non-streaming Anthropic response dict."""
        try:
            if not isinstance(response, dict):
                _logger.warning(
                    "AnthropicTokenUsageParser.parse_response: expected dict, got %s",
                    type(response).__name__,
                )
                return
            usage = response.get("usage")
            if not isinstance(usage, dict):
                if usage is not None:
                    _logger.warning(
                        "AnthropicTokenUsageParser.parse_response: usage is not a dict: %s",
                        type(usage).__name__,
                    )
                return
            self._usage = self._extract_usage(usage)
        except Exception:
            _logger.warning(
                "AnthropicTokenUsageParser.parse_response failed", exc_info=True
            )

    def feed_chunk(self, chunk: object) -> None:
        """Update accumulator from an Anthropic SSE event chunk.

        message_start carries input tokens and cache fields (nested under chunk["message"]["usage"]).
        message_delta carries output tokens (under chunk["usage"]).
        All other chunk types are silently ignored.
        """
        try:
            if not isinstance(chunk, dict):
                _logger.warning(
                    "AnthropicTokenUsageParser.feed_chunk: expected dict, got %s",
                    type(chunk).__name__,
                )
                return
            chunk_type = chunk.get("type")
            if chunk_type == "message_start":
                usage = (chunk.get("message") or {}).get("usage") or {}
                if isinstance(usage, dict):
                    self._usage.input_tokens = usage.get("input_tokens", self._usage.input_tokens)
                    self._usage.cache_creation_input_tokens = (
                        self._resolve_cache_creation_tokens(usage)
                        or self._usage.cache_creation_input_tokens
                    )
                    self._usage.cache_read_input_tokens = usage.get(
                        "cache_read_input_tokens", self._usage.cache_read_input_tokens
                    )
                    self._usage.thinking_tokens = usage.get(
                        "thinking_tokens", self._usage.thinking_tokens
                    )
            elif chunk_type == "message_delta":
                usage = chunk.get("usage") or {}
                if isinstance(usage, dict):
                    self._usage.output_tokens = usage.get("output_tokens", self._usage.output_tokens)
        except Exception:
            _logger.warning(
                "AnthropicTokenUsageParser.feed_chunk failed", exc_info=True
            )

    def log(
        self,
        model: str,
        subaccount: str,
        user_id: str,
        ip_address: str,
        suffix: str = "",
    ) -> None:
        """Emit a token_usage_logger.info entry with the accumulated usage."""
        u = self._usage
        extra = ""
        if u.cache_creation_input_tokens or u.cache_read_input_tokens:
            extra += (
                f", CacheCreationTokens: {u.cache_creation_input_tokens}"
                f", CacheReadTokens: {u.cache_read_input_tokens}"
            )
        if u.thinking_tokens:
            extra += f", ThinkingTokens: {u.thinking_tokens}"
        if suffix:
            extra += f" ({suffix})"
        token_usage_logger.info(
            "User: %s, IP: %s, Model: %s, SubAccount: %s, PromptTokens: %s, CompletionTokens: %s, TotalTokens: %s%s",
            user_id,
            ip_address,
            model,
            subaccount,
            u.input_tokens,
            u.output_tokens,
            u.total_tokens,
            extra,
        )

    @staticmethod
    def normalize_usage_cache_fields(usage: dict) -> dict:
        """Normalize Bedrock's nested cache_creation format to the flat Anthropic API fields.

        Mutates and returns the usage dict so callers can pass the result directly
        to JSONResponse without an extra copy.
        """
        resolved = AnthropicTokenUsageParser._resolve_cache_creation_tokens(usage)
        if resolved and not int(usage.get("cache_creation_input_tokens") or 0):
            usage["cache_creation_input_tokens"] = resolved
        return usage

    @staticmethod
    def _resolve_cache_creation_tokens(usage: dict) -> int:
        """Return cache_creation_input_tokens, falling back to the nested cache_creation dict.

        Bedrock introduced a new format where cache_creation_input_tokens stays 0 and
        the actual counts live in usage["cache_creation"]["ephemeral_5m_input_tokens"]
        and usage["cache_creation"]["ephemeral_1h_input_tokens"].
        """
        flat = int(usage.get("cache_creation_input_tokens") or 0)
        if flat:
            return flat
        nested = usage.get("cache_creation")
        if isinstance(nested, dict):
            return sum(int(v or 0) for v in nested.values())
        return 0

    @staticmethod
    def _extract_usage(usage: dict) -> AnthropicUsage:
        return AnthropicUsage(
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            cache_creation_input_tokens=AnthropicTokenUsageParser._resolve_cache_creation_tokens(usage),
            cache_read_input_tokens=int(usage.get("cache_read_input_tokens") or 0),
            thinking_tokens=int(usage.get("thinking_tokens") or 0),
        )
