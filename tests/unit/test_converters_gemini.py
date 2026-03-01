from converters import gemini as gemini_converters


def test_from_openai_single_message():
    payload = {
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
    }

    result = gemini_converters.from_openai(payload)

    assert result["contents"]["parts"]["text"] == "Hello"
    assert result["generation_config"]["maxOutputTokens"] == 10


def test_from_claude_basic():
    payload = {
        "system": "Sys",
        "messages": [{"role": "user", "content": "Hi"}],
        "temperature": 0.3,
    }

    result = gemini_converters.from_claude(payload)

    assert result["contents"][0]["role"] == "user"
    assert "Sys" in result["contents"][0]["parts"]["text"]
    assert result["generation_config"]["temperature"] == 0.3
