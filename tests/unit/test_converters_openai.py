import pytest

from converters import openai as openai_converters


def test_from_claude_standard_model():
    response = {
        "id": "msg_123",
        "model": "claude-3-5-sonnet",
        "role": "assistant",
        "content": [{"type": "text", "text": "Hello"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 2, "output_tokens": 3},
    }

    result = openai_converters.from_claude(response, "claude-3-5-sonnet")

    assert result["choices"][0]["message"]["content"] == "Hello"
    assert result["choices"][0]["finish_reason"] == "end_turn"
    assert result["usage"]["prompt_tokens"] == 2
    assert result["usage"]["completion_tokens"] == 3


def test_from_claude37_basic():
    response = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hi"}],
            }
        },
        "usage": {"inputTokens": 4, "outputTokens": 5, "totalTokens": 9},
        "stopReason": "max_tokens",
    }

    result = openai_converters.from_claude37(response, "claude-3-7-sonnet")

    assert result["choices"][0]["message"]["content"] == "Hi"
    assert result["choices"][0]["finish_reason"] == "length"
    assert result["usage"]["prompt_tokens"] == 4
    assert result["usage"]["completion_tokens"] == 5
    assert result["usage"]["total_tokens"] == 9


def test_from_gemini_basic():
    response = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Gemini hello"}]},
                "finishReason": "MAX_TOKENS",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 3,
            "candidatesTokenCount": 7,
            "totalTokenCount": 10,
        },
    }

    result = openai_converters.from_gemini(response, "gemini-pro")

    assert result["choices"][0]["message"]["content"] == "Gemini hello"
    assert result["choices"][0]["finish_reason"] == "length"
    assert result["usage"]["prompt_tokens"] == 3
    assert result["usage"]["completion_tokens"] == 7
    assert result["usage"]["total_tokens"] == 10
