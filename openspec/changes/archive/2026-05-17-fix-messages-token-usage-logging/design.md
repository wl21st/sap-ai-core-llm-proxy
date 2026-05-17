# Design: fix-messages-token-usage-logging

## Overview

Add token usage logging to `/v1/messages` endpoint's streaming and non-streaming paths.
The messages router currently passes Bedrock's native Anthropic-format EventStream through
unchanged, which is correct for throughput, but never extracts usage fields for the audit log.

## Approach

### Streaming path

Extend `generate_bedrock_streaming_response` to accept three new parameters:
`request`, `model`, and `subaccount_name`. During the pass-through loop, extract usage
fields as they arrive in the stream:

- `message_start` chunk → `message.usage` → `input_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`, and nested `cache_creation.ephemeral_5m_input_tokens` /
  `cache_creation.ephemeral_1h_input_tokens`
- `message_delta` chunk → `usage.output_tokens` (final output count)

After yielding `message_stop`, emit one `token_usage_logger.info(...)` call and then
`data: [DONE]`. Chunks continue to be yielded unchanged — no format transformation.

The sync wrapper `generate_bedrock_streaming_response_sync` delegates to the async version
and must pass through the new parameters.

The single call site in `routers/messages.py` line 400 already has `request`, `model`, and
`subaccount_name` in scope and must be updated to pass them.

### Non-streaming path

After `response_json = json.loads(chunk_data)` (line 495), extract `response_json.get("usage", {})`
and emit one `token_usage_logger.info(...)` call before `return JSONResponse(...)`.

## Log Format

Match the existing chat streaming/non-streaming format:

```
User: <auth_prefix>, IP: <ip>, Model: <model>, SubAccount: <sub>,
PromptTokens: <N>, CompletionTokens: <N>, TotalTokens: <N> (Streaming)
```

Append cache fields only when non-zero:

```
..., CacheCreationTokens: <N>, CacheReadTokens: <N> (Streaming)
```

### Helper extraction

Both paths share the same extraction logic:

```python
def _extract_auth_info(request):
    auth = request.headers.get("Authorization", "")
    user_id = auth.split(" ")[-1][:20] + "..." if len(auth.split(" ")[-1]) > 20 else auth.split(" ")[-1]
    ip = request.client.host if request and request.client else "unknown_ip"
    return user_id, ip
```

Re-use the same inline pattern already used in `generate_streaming_response` (lines 438–448)
rather than introducing a new shared helper, since the messages path has a simpler structure.

## Files Changed

| File | Change |
|------|--------|
| `handlers/streaming_generators.py` | Extend `generate_bedrock_streaming_response` signature; accumulate and log usage |
| `routers/messages.py` | Pass `request`, `model`, `subaccount_name` to streaming generator; add non-streaming log |

## No New Files

All logging infrastructure already exists. `token_usage_logger` is already imported in
`handlers/streaming_generators.py` (line 30).

## Testing

- Unit test: streaming path logs correct values from mock chunks
- Unit test: non-streaming path logs correct values from mock response
- Unit test: cache fields omitted when zero, included when non-zero
- Existing tests must continue to pass (function signature change is backward-incompatible,
  so all call sites must be updated)
