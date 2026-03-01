import json

from converters import chunks as chunk_converters


def test_claude_to_openai_chunk_content_block_delta():
    chunk = 'data: {"type": "content_block_delta", "delta": {"text": "Hi"}}'

    result = chunk_converters.claude_to_openai_chunk(chunk, "claude-3.5-sonnet")

    assert "data:" in result
    payload = json.loads(result.replace("data: ", "").strip())
    assert payload["choices"][0]["delta"]["content"] == "Hi"


def test_claude37_to_openai_chunk_message_stop():
    chunk = {"messageStop": {"stopReason": "max_tokens"}}

    result = chunk_converters.claude37_to_openai_chunk(
        chunk, "claude-3.7-sonnet", "stream123"
    )

    assert result is not None
    payload = json.loads(result.replace("data: ", "").strip())
    assert payload["choices"][0]["finish_reason"] == "length"


def test_gemini_to_openai_chunk_with_finish_reason():
    chunk = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": "Hello"}]},
            }
        ]
    }

    result = chunk_converters.gemini_to_openai_chunk(chunk, "gemini-pro")

    assert result is not None
    payload = json.loads(result.replace("data: ", "").strip())
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["choices"][0]["delta"]["content"] == "Hello"
