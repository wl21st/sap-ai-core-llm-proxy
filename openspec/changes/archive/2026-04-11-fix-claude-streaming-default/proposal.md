## Why

The proxy defaults `stream` to `True` in two handlers, violating both the Anthropic Messages API and OpenAI Chat Completions API specifications — both define the `stream` parameter as optional with a default of `false`. Clients that omit `stream` receive SSE streaming responses when they expect a synchronous JSON response.

## What Changes

- Fix `routers/messages.py:155` — change `get("stream", True)` to `get("stream", False)`
- Fix `handlers/model_handlers.py:38` — change `get("stream", True)` to `get("stream", False)`
- Add/update unit tests to assert that omitting `stream` produces non-streaming behavior

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- None — this is a bug fix aligning implementation to already-specified API contracts (Anthropic and OpenAI both document `stream` default as `false`). No spec-level requirement is changing; the specs were always correct, the code was wrong.

## Impact

- **`routers/messages.py`** — `/v1/messages` endpoint: clients omitting `stream` will now receive synchronous JSON instead of SSE
- **`handlers/model_handlers.py`** — `handle_claude_request()`: Claude model routing will default to `/converse` (non-streaming) instead of `/converse-stream` when `stream` is absent
- **No breaking change for well-behaved clients** — clients already passing `stream=true` explicitly are unaffected
- **Behavior change for clients omitting `stream`** — they get synchronous responses (correct per spec) instead of streaming
