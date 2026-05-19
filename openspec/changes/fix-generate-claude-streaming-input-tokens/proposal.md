## Why

`generate_claude_streaming_response` in `handlers/streaming_generators.py` constructs
Anthropic Messages API SSE events from a backend HTTP stream. It has two token reporting
bugs that cause clients to always receive zero for prompt/input token counts.

### Bug A — `message_start` hardcodes `input_tokens: 0`

The `message_start` event is emitted immediately before streaming begins, before any
backend data has arrived, so real token counts are not yet known:

```python
# line 1045 — Claude model branch
# line 1181 — non-Claude model branch (GPT/Gemini proxied to Claude format)
"usage": {"input_tokens": 0, "output_tokens": 0},
```

Per the Anthropic Messages API spec, `message_start.message.usage.input_tokens` is the
canonical field for prompt token counts in a streaming response. Clients that read this
field — including the `anthropic` Python SDK's streaming helper, LangChain's token
tracking, and billing/observability tools — will always see `0` for prompt tokens.

### Bug B — `metadata` handler drops `inputTokens`

When the backend sends a `metadata` chunk (which arrives after all content, before
`messageStop`), the handler maps `outputTokens` to `output_tokens` in `message_delta`
but silently drops `inputTokens`:

```python
# lines 1119-1131
"usage": {
    "output_tokens": usage_info.get("outputTokens", 0)
    # inputTokens is present in usage_info but never read
},
```

The `message_delta.usage` containing only `output_tokens` is actually spec-correct. But
because `message_start` already emitted `input_tokens: 0`, the only chance to deliver the
real value has been missed.

### Root cause

The function emits `message_start` eagerly, before the backend response is read, because
it needs to open the SSE stream. The correct fix is to **buffer `message_start`** and emit
it only after `inputTokens` is available from the `metadata` chunk.

This is exactly what the Bedrock SDK path (`generate_bedrock_streaming_response`) does
implicitly — the SDK's own `message_start` EventStream event already carries real
`input_tokens` because the SDK buffers internally before surfacing events.

### Current exposure

`generate_claude_streaming_response` is not called by any live router today — the
`/v1/messages` router uses `generate_bedrock_streaming_response` exclusively (see change
`fix-messages-dead-import`). However:

- It is tested via `tests/test_proxy_server_extended.py` (lines 502–560).
- It is the intended HTTP-based fallback for future routing (non-SDK subaccounts).
- Fixing it before it is activated prevents shipping a silent bug.

## What Changes

In `generate_claude_streaming_response` (`handlers/streaming_generators.py`):

### Claude model branch (lines 1035–1166, `Detector.is_claude_model(model) == True`)

1. **Declare** `input_tokens = 0` and `output_tokens = 0` before the line loop.
2. **Buffer** the `message_start` construction into `_pending_message_start` — do not
   yield it yet.
3. **Emit** `content_block_start` immediately (unchanged — no token data needed here).
4. **Continue** yielding `content_block_delta` and `content_block_stop` as they arrive
   (unchanged).
5. When the `metadata` chunk arrives:
   - Extract `inputTokens` → `input_tokens` and `outputTokens` → `output_tokens`.
   - Patch `_pending_message_start["message"]["usage"]` with real values.
   - **Yield the patched `_pending_message_start`** now (before `message_delta`).
6. Yield `message_delta` with `output_tokens` (already correct, no change).
7. Yield `message_stop` (unchanged).

The Anthropic streaming spec requires `message_start` to arrive before `message_stop`; it
does not constrain its position relative to content deltas. Emitting it after content is
spec-compliant.

### Non-Claude model branch (lines 1169–1318, GPT/Gemini proxied to Claude format)

Apply the same buffering pattern. Token sources differ by model:

- **OpenAI backend** (GPT models): usage arrives in the final `data:` line as
  `{"usage": {"prompt_tokens": N, "completion_tokens": N}}`. Buffer `message_start`,
  extract on the final chunk, patch and yield before `message_delta`.
- **Gemini backend**: usage arrives in a chunk containing `usageMetadata` with
  `promptTokenCount` and `candidatesTokenCount`. Same buffering pattern.

### `message_start` ordering note

In the current implementation `message_start` is the very first event. After this fix it
will be emitted after `content_block_start` and all content deltas, immediately before
`message_delta`. This is a valid SSE ordering per the Anthropic spec. Client SDKs that
parse the full stream before processing (e.g., `anthropic.messages.stream()`) are
unaffected. Clients that process events incrementally and rely on `message_start` arriving
first would need to handle reordering — this is explicitly noted in the implementation
comments.

## Capabilities

### Modified Capabilities

- `generate_claude_streaming_response`: Streaming `message_start` events now carry real
  `input_tokens` instead of hardcoded `0`. `message_delta.usage` continues to carry only
  `output_tokens` (spec-correct, unchanged).

## Impact

- **Files affected**: `handlers/streaming_generators.py`
- **New files**: none (update existing tests in `tests/test_proxy_server_extended.py` to
  assert `input_tokens > 0` in `message_start`)
- **Breaking changes**: None for clients following the Anthropic spec. The change makes
  the output more correct; no spec-compliant client depends on `input_tokens: 0`.
- **Side effects**: `message_start` is now emitted later in the stream. See ordering note
  above.

## Sequencing

Independent of `fix-messages-dead-import`. If merged after that change, the now-correct
function will no longer be reachable from `messages.py` — but it will still be correct
when an HTTP-based route is wired up in the future.
