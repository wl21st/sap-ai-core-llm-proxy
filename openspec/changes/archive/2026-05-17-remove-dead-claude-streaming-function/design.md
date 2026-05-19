# Design: remove-dead-claude-streaming-function

## Summary

Pure dead-code removal. No behavior changes, no API contract changes, no new abstractions.

## Deletion Targets

### 1. `handlers/streaming_generators.py`

- **Lines 974–1071**: `async def generate_claude_streaming_response(...)` — async generator,
  never called from production code. Contains known bug: hardcodes `input_tokens: 0` in
  `message_start` event.
- **Lines 1342–1360**: `def generate_claude_streaming_response_sync(...)` — sync wrapper,
  only reference is the backward-compat shim below.

### 2. `proxy_server.py` (lines 38–54)

Remove:
```python
from handlers.streaming_generators import (
    generate_claude_streaming_response_sync,
)

# Backward-compatible alias for tests
def generate_claude_streaming_response(...):
    return generate_claude_streaming_response_sync(...)
```

The import block on lines 35–41 covers several imports; only the
`generate_claude_streaming_response_sync` line is removed, not the entire block.

### 3. `tests/test_proxy_server_extended.py` (lines 501–557)

Delete `class TestGenerateClaudeStreamingResponse` entirely — both test methods import
`generate_claude_streaming_response` from `proxy_server`, which will no longer exist after
the shim is removed.

## Verification

After deletion, confirm:
- `grep -rn generate_claude_streaming_response` returns zero results
- `make test` passes with no regressions
