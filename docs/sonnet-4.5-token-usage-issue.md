# Sonnet 4.5 Token Usage Issue

- [Sonnet 4.5 Token Usage Issue](#sonnet-45-token-usage-issue)
  - [Current Missing Token Usage](#current-missing-token-usage)
    - [Sonnet-4.5 in Anthropic Format](#sonnet-45-in-anthropic-format)
    - [Sonnet 4.5 in OpenAI Format without Token Usage](#sonnet-45-in-openai-format-without-token-usage)
  - [Expect Baseline](#expect-baseline)
    - [Sonnet in Anthropic Format](#sonnet-in-anthropic-format)
    - [Sonnet 4.5 Stream Response in OpenAI Format](#sonnet-45-stream-response-in-openai-format)

## Current Missing Token Usage

### Sonnet-4.5 in Anthropic Format

```bash
Testing Anthropic format (Stream): sonnet-4.5
Request JSON: {
      "model": "sonnet-4.5",
      "messages": [
        {
          "role": "user",
          "content": "Say 'hello' in one word"
        }
      ],
      "max_tokens": 100,
      "stream": true
    }

✓ Success: sonnet-4.5 (Stream) (2090ms)
event: message_start
data: {"type": "message_start", "message": {"model": "claude-sonnet-4-5-20250929", "id": "msg_bdrk_01TW6wbPiQ3e5dwnDWoiVQrX", "type": "message", "role": "assistant", "content": []

event: content_block_start
data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}

event: content_block_stop
data: {"type": "content_block_stop", "index": 0}

event: message_delta
data: {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": null}, "usage": {"output_tokens": 4}}

event: message_stop
data: {"type": "message_stop", "amazon-bedrock-invocationMetrics": {"inputTokenCount": 15, "outputTokenCount": 4, "invocationLatency": 1655, "firstByteLatency": 1610}}
```

data: [DONE]

### Sonnet 4.5 in OpenAI Format without Token Usage

```bash
--- OpenAI API Format ---
Testing OpenAI format (Stream): sonnet-4.5

Request JSON: {
      "model": "sonnet-4.5",
      "messages": [
        {
          "role": "user",
          "content": "Say 'hello' in one word"
        }
      ],
      "max_completion_tokens": 100,
      "stream": true
    }

✓ Success: sonnet-4.5 (Stream) (3100ms)

data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "msg_bdrk_01QrCa66TQHCbB766KPw9zop", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: [DONE]
```

## Expect Baseline

### Sonnet in Anthropic Format

```bash
Testing Anthropic format (Stream): sonnet-4.5
Request JSON: {
      "model": "sonnet-4.5",
      "messages": [
        {
          "role": "user",
          "content": "Say 'hello' in one word"
        }
      ],
      "max_tokens": 100,
      "stream": true
    }

✓ Success: sonnet-4.5 (Stream) (2750ms)
event: message_start
data: {"type": "message_start", "message": {"model": "claude-sonnet-4-5-20250929", "id": "msg_bdrk_01TYPiR41HegjBJjXpRy62rF", "type": "message", "role": "assistant", "content": [], "stop_reason": null, "stop_sequence": null, "usage": {"input_tokens": 15, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0}, "output_tokens": 1}}}

event: content_block_start
data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}

event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}

event: content_block_stop
data: {"type": "content_block_stop", "index": 0}

event: message_delta
data: {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": null}, "usage": {"output_tokens": 4}}

event: message_stop
data: {"type": "message_stop", "amazon-bedrock-invocationMetrics": {"inputTokenCount": 15, "outputTokenCount": 4, "invocationLatency": 2270, "firstByteLatency": 2183}}

data: [DONE]

```

### Sonnet 4.5 Stream Response in OpenAI Format

```json
--- OpenAI API Format ---
Testing OpenAI format: sonnet-4.5
Request JSON: {
      "model": "sonnet-4.5",
      "messages": [
        {
          "role": "user",
          "content": "Say 'hello' in one word"
        }
      ],
      "max_completion_tokens": 100,
      "stream": false
    }

✓ Success: sonnet-4.5 (3125ms)
Hello

Testing OpenAI format (Stream): sonnet-4.5
Request JSON: {
      "model": "sonnet-4.5",
      "messages": [
        {
          "role": "user",
          "content": "Say 'hello' in one word"
        }
      ],
      "max_completion_tokens": 100,
      "stream": true
    }

✓ Success: sonnet-4.5 (Stream) (2516ms)
data: {"id": "chatcmpl-claude37-67505", "object": "chat.completion.chunk", "created": 1767102420, "model": "sonnet-4.5", "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": null}]}
data: {"id": "chatcmpl-claude37-19040", "object": "chat.completion.chunk", "created": 1767102420, "model": "sonnet-4.5", "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": null}]}
data: {"id": "chatcmpl-claude37-28255", "object": "chat.completion.chunk", "created": 1767102420, "model": "sonnet-4.5", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 15, "completion_tokens": 4, "total_tokens": 19}}
data: [DONE]
```

