## Why

`generate_claude_streaming_response` (async) and `generate_claude_streaming_response_sync`
in `handlers/streaming_generators.py` are never called from any production code path.
The only call site is a backward-compatibility shim in `proxy_server.py` that exists
solely so that tests can import the function by its old name — making the tests the
only consumers of dead production code.

The `routers/messages.py` dead import was removed in change `fix-messages-dead-import`.
With that import gone, there are zero live call sites in production code. The async
function also contains a known correctness bug: it hardcodes `input_tokens: 0` in
the `message_start` event (tracked in `fix-generate-claude-streaming-input-tokens`).
Removing the function eliminates the bug entirely rather than requiring a separate fix.

## What Changes

1. Delete `generate_claude_streaming_response` (async, lines 974–1071) from
   `handlers/streaming_generators.py`.
2. Delete `generate_claude_streaming_response_sync` (lines 1342–1360) from
   `handlers/streaming_generators.py`.
3. Remove the backward-compat shim from `proxy_server.py` (lines 38–54):
   - The `from handlers.streaming_generators import generate_claude_streaming_response_sync`
     import
   - The `generate_claude_streaming_response` wrapper function
4. Delete the `TestGenerateClaudeStreamingResponse` test class
   (`tests/test_proxy_server_extended.py`, lines 501–557) — these tests cover only
   the deleted function and have no value once the function is gone.

No routing behavior changes. No API contract changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is dead-code removal only; no spec-level behavior changes.

## Impact

- **Files affected**: `handlers/streaming_generators.py`, `proxy_server.py`,
  `tests/test_proxy_server_extended.py`
- **New files**: none
- **Breaking changes**: None for callers — `generate_claude_streaming_response` has
  no live call sites in production code. The shim in `proxy_server.py` disappears,
  but nothing outside the deleted test class imports it.
- **Side effects**: Eliminates the `fix-generate-claude-streaming-input-tokens` bug
  without a separate fix — change `fix-generate-claude-streaming-input-tokens` can be
  closed or archived as superseded.

## Sequencing

Depends on `fix-messages-dead-import` being merged (removes the last import in a
router). Independent of `fix-generate-claude-streaming-input-tokens` — this supersedes
that change by deleting the buggy function entirely.
