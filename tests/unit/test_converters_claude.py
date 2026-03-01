from converters import claude as claude_converters


def test_from_openai_basic():
    payload = {
        "messages": [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
        ],
        "max_tokens": 100,
        "temperature": 0.2,
    }

    result = claude_converters.from_openai(payload)

    assert result["system"] == "System prompt"
    assert result["messages"][0]["role"] == "user"
    assert result["system"] == "System prompt"
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"] == "Hello"
    assert result["max_tokens"] == 100
    assert result["temperature"] == 0.2


def test_from_openai_messages_stop_sequences():
    payload = {
        "messages": [
            {"role": "user", "content": "Hi"},
        ],
        "stop": ["END"],
        "max_tokens": 50,
    }

    result = claude_converters.from_openai_messages(payload)

    assert result["messages"][0]["content"][0]["text"] == "Hi"
    assert result["inferenceConfig"]["stopSequences"] == ["END"]
    assert result["inferenceConfig"]["maxTokens"] == 50


def test_to_bedrock_removes_cache_control():
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Hello", "cache_control": "no"}],
            }
        ]
    }

    result = claude_converters.to_bedrock(payload)

    content_item = result["messages"][0]["content"][0]
    assert "cache_control" not in content_item
