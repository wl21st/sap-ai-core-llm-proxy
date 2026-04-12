## Context

The proxy has two handlers that read the `stream` parameter from incoming requests and default it to `True` when absent:

- `routers/messages.py:155` — handles `/v1/messages` (Anthropic Messages API)
- `handlers/model_handlers.py:38` — handles Claude model routing via `handle_claude_request()`

Both Anthropic and OpenAI define `stream` as an optional boolean defaulting to `false`. The wrong defaults cause clients that omit `stream` to receive SSE streaming responses instead of synchronous JSON — a spec violation and unexpected behavior.

The downstream branching logic (`if stream: ... else: ...`) in both files is correct; only the default value is wrong.

## Goals / Non-Goals

**Goals:**
- Align `stream` default to `false` in both affected files
- Ensure clients omitting `stream` receive synchronous JSON responses
- Add regression tests covering the omit-stream case

**Non-Goals:**
- Changing streaming behavior for clients that explicitly pass `stream=true`
- Modifying any other streaming logic, response format, or SSE handling
- Touching `routers/chat.py` (already uses `get("stream", False)` correctly)

## Decisions

**Fix both sites independently, same one-line change each.**
Both `routers/messages.py` and `handlers/model_handlers.py` read the `stream` flag from different request payloads in different contexts. There is no shared helper to centralize this — introducing one would be premature abstraction for a two-file, two-line fix.

**Do not change the downstream `if stream:` branching.**
The routing to `invoke_bedrock_streaming` vs `invoke_bedrock_non_streaming` is correct. Only the default value feeding into that branch is wrong.

**Default `False` matches both specs.**
Anthropic's Messages API and OpenAI's Chat Completions API both document `stream` as optional with an implicit default of `false`. Using `False` as the default is the spec-compliant choice.

## Risks / Trade-offs

- **Behavior change for existing clients omitting `stream`** — Any client currently relying on the proxy defaulting to streaming when `stream` is absent will now receive a synchronous response. This is a breaking change for such clients, but those clients were relying on non-spec behavior. → Mitigation: document in release notes; the fix is correct per spec.
- **No risk to clients explicitly passing `stream=true` or `stream=false`** — unaffected by this change.

## Migration Plan

1. Change two lines (one per file)
2. Run unit tests (`make test`) to confirm no regressions
3. Add targeted unit tests for the omit-stream case in both endpoints
4. Deploy — no database migrations, config changes, or rollback complexity needed
