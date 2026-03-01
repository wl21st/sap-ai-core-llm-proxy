"""Shared constants for converter modules."""

from typing import Final

API_VERSION_BEDROCK_2023_05_31: Final[str] = "bedrock-2023-05-31"
API_VERSION_2024_12_01_PREVIEW: Final[str] = "2024-12-01-preview"
API_VERSION_2023_05_15: Final[str] = "2023-05-15"

STOP_REASON_MAP: Final[dict[str, dict[str, str]]] = {
    "claude_to_openai": {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    },
    "openai_to_claude": {
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "stop_sequence",
        "tool_calls": "tool_use",
    },
    "gemini_to_openai": {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "OTHER": "stop",
    },
    "gemini_to_claude": {
        "STOP": "end_turn",
        "MAX_TOKENS": "max_tokens",
        "SAFETY": "stop_sequence",
        "RECITATION": "stop_sequence",
        "OTHER": "stop_sequence",
    },
}
