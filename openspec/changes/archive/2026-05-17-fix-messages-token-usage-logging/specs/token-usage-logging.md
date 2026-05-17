# Spec: Token Usage Logging for /v1/messages

## Capability: messages-proxy

### Streaming path

`generate_bedrock_streaming_response(response_body, tid, request, model, subaccount_name)`

- Accepts `request: Request | None`, `model: str`, `subaccount_name: str` as new parameters (default to `None`/`""`)
- Accumulates usage by merging chunks into a single dict as they stream:
  - `message_start` chunk → `usage.update(message.usage)`
  - `message_delta` chunk → `usage.update(chunk.usage)` (overwrites `output_tokens` with final value)
- After yielding `message_stop`, before `data: [DONE]`: emit one `token_usage_logger.info(...)`:
  ```
  User: %s, IP: %s, Model: %s, SubAccount: %s, Usage: %s (Streaming)
  ```
  where `Usage` is `json.dumps(merged_usage_dict)` — the raw object as returned by Anthropic
- Chunks continue to yield unchanged (pass-through behavior preserved)
- When `request is None`, no log is emitted

### Non-streaming path (`proxy_claude_request`, non-streaming branch)

After `response_json = json.loads(chunk_data)`:

- Extract `usage = response_json.get("usage", {})`
- Emit `token_usage_logger.info(...)`:
  ```
  User: %s, IP: %s, Model: %s, SubAccount: %s, Usage: %s (Non-Streaming)
  ```
  where `Usage` is `json.dumps(usage)` — the raw object as returned by Anthropic

### Log format rationale

The raw usage dict is logged as-is so all present and future Anthropic usage fields
(`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`,
`cache_creation.ephemeral_5m_input_tokens`, `cache_creation.ephemeral_1h_input_tokens`,
`thinking_tokens`, `web_search_requests`, etc.) are captured without requiring proxy
code changes when Anthropic adds new fields.

### Call site update

`routers/messages.py` streaming branch:
```python
# Before
generate_bedrock_streaming_response(response_body, tid)
# After
generate_bedrock_streaming_response(response_body, tid, request, model, subaccount_name)
```

## Invariants

- No change to request or response content
- No new I/O or latency
- User ID truncated to 20 chars + "..." if longer
- All Anthropic usage fields preserved; none filtered or renamed
