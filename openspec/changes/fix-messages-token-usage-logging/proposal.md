## Why

The `/v1/messages` endpoint (Anthropic Messages API) has **no token usage logging** in
either the streaming or non-streaming path. This creates a complete observability gap for
the primary Claude API endpoint: operators cannot audit usage, detect cost anomalies, or
attribute traffic by user or subaccount.

Every streaming path in the chat router logs token usage at stream end. The messages router
does not:

| Path | `token_usage_logger` call |
|---|---|
| `generate_streaming_response` → Claude 3.7/4 (chat) | ✅ line 450 |
| `generate_streaming_response` → Gemini (chat) | ✅ line 621 |
| `generate_streaming_response` → older Claude / OpenAI (chat) | ✅ line 780 |
| `generate_bedrock_streaming_response` (messages streaming) | ❌ missing |
| `proxy_claude_request` non-streaming path (messages) | ❌ missing |

### What Bedrock returns

The real Bedrock Anthropic-format EventStream `message_start` chunk carries the full usage
object, including all cache fields (confirmed from `tests/integration/test_validators.py`):

```json
{
  "type": "message_start",
  "message": {
    "usage": {
      "input_tokens": 15,
      "output_tokens": 1,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 0,
      "cache_creation": {
        "ephemeral_5m_input_tokens": 0,
        "ephemeral_1h_input_tokens": 0
      }
    }
  }
}
```

The `message_delta` chunk carries final `output_tokens`:

```json
{
  "type": "message_delta",
  "usage": {"output_tokens": 4}
}
```

The non-streaming Bedrock response includes the same fields in `response.usage`
(`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`).

Since `generate_bedrock_streaming_response` passes chunks through **unchanged**, all these
fields already reach the client correctly. The only gap is that the proxy never extracts
them for the audit log.

## What Changes

### Change 1: `generate_bedrock_streaming_response` — extract and log at stream end

Extend the function signature to accept `request`, `model`, and `subaccount_name` alongside
the existing `response_body` and `tid` parameters.

As chunks are yielded, accumulate usage fields from the chunks before passing them through:

- From `message_start` chunk: extract `message.usage` → capture `input_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens`, and the nested
  `cache_creation.ephemeral_5m_input_tokens` / `cache_creation.ephemeral_1h_input_tokens`
  if present.
- From `message_delta` chunk: extract `usage.output_tokens` (the final output count).

After yielding the `message_stop` event, emit one `token_usage_logger.info(...)` call.
The log line format matches the existing pattern used by chat streaming paths, extended
with cache fields:

```
User: <auth_prefix>, IP: <ip>, Model: <model>, SubAccount: <sub>,
PromptTokens: <N>, CompletionTokens: <N>, TotalTokens: <N>,
CacheCreationTokens: <N>, CacheReadTokens: <N> (Streaming)
```

Cache fields are only appended when non-zero (same approach as `proxy_helpers.py`'s
`prompt_tokens_details` — only include if present).

The caller in `routers/messages.py` line 401 already has `request`, `model`, and
`subaccount_name` in scope and must be updated to pass them.

### Change 2: Non-streaming path in `routers/messages.py` — log after pass-through

After `response_json = json.loads(chunk_data)` (line 496), extract the `usage` field and
emit one `token_usage_logger.info(...)` call using the non-streaming format:

```
User: <auth_prefix>, IP: <ip>, Model: <model>, SubAccount: <sub>,
PromptTokens: <N>, CompletionTokens: <N>, TotalTokens: <N>,
CacheCreationTokens: <N>, CacheReadTokens: <N> (Non-Streaming)
```

Field names in the non-streaming Bedrock Anthropic-format response use snake_case
(`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`)
— confirmed by integration tests in `tests/integration/test_cache_control.py`.

## Capabilities

### Modified Capabilities

- `messages-proxy`: Token usage for `/v1/messages` — both streaming and non-streaming —
  is now recorded in the `token_usage_logger`, including all cache token fields.
  No change to request or response behaviour; this is purely observability.

## Impact

- **Files affected**: `handlers/streaming_generators.py`, `routers/messages.py`
- **New files**: none (extend existing unit and integration tests)
- **Breaking changes**: `generate_bedrock_streaming_response` signature changes — only
  called from one site (`routers/messages.py` line 401), updated in the same PR.
- **Side effects**: None. Token extraction reads fields from chunks that are already being
  yielded; no additional I/O or latency.
