## Context

The `/v1/messages` endpoint uses `routers/messages.py` to proxy Anthropic Claude REST API calls through AWS Bedrock. Responses pass through in their original Anthropic format (unlike `/v1/chat/completions` which converts to OpenAI format). The existing `token_usage_logger` (Python logger named `"token_usage"`) is already in use in `handlers/streaming_generators.py` for OpenAI-compatible streaming, but the Anthropic-native path — both `generate_bedrock_streaming_response` and the non-streaming branch in `routers/messages.py` — never logs token counts.

The Anthropic REST response `usage` object contains fields documented in `docs/reference/AnthropicTokenUsageDetailItems.md`: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, and `thinking_tokens` (where extended thinking is enabled). In the Bedrock SSE event stream these fields are split across: `message_start` → input usage, `message_delta` → output usage.

**Constraint**: All existing token processing and logging code (`generate_openai_compatible_streaming_response`, `routers/chat.py`, etc.) is left entirely unchanged. This change is purely additive.

## Goals / Non-Goals

**Goals:**
- Introduce an extensible `AnthropicTokenUsageParser` class that parses all known Anthropic `usage` fields and emits a `token_usage_logger` entry
- Call the parser as an additional, independent step after the existing response-handling logic in `routers/messages.py`
- Support both non-streaming (single response dict) and streaming (accumulate across SSE events) via the same class
- Resilient by design: any failure in the parser class is caught internally and logged as a warning; it never affects the response
- Extensible: adding a new usage field or a new logging backend requires only a subclass or a small change to the parser class, not edits to routing code

**Non-Goals:**
- Modifying any existing token processing, logging, or streaming code
- Changing the response body returned to the caller
- Persisting usage to a database or external metrics system
- Changing logging for the `/v1/chat/completions` path

## Decisions

### D1: Encapsulate all parsing logic in a class, not a standalone function

**Decision**: Create `utils/anthropic_usage.py` containing:
- `AnthropicUsage` dataclass — typed, all-zero defaults
- `AnthropicTokenUsageParser` class — holds an `AnthropicUsage` accumulator, exposes `feed_chunk(chunk: dict)` for streaming and `parse_response(response: dict)` for non-streaming, and `log(...)` to emit the `token_usage_logger` entry

**Rationale**: A class (vs. a standalone function) enables:
1. **Streaming accumulation** — state (`_usage`, seen-event flags) lives naturally on the instance across `feed_chunk` calls
2. **Extensibility** — a subclass can override `log()` to write to a metrics sink, or override `_extract_from_chunk()` to handle new event types, without touching call sites
3. **Testability** — the parser can be instantiated and driven in isolation without mocking routers or generators

Alternatives considered:
- Module-level functions with a mutable dict passed around: stateful but not encapsulated
- Inheriting from an ABC: over-engineered for current scope; a concrete class with clear extension points is sufficient

### D2: `feed_chunk` / `parse_response` are the only public entry points; `log` is called explicitly by the caller

**Decision**: The caller (router or generator) constructs a `AnthropicTokenUsageParser`, feeds it data, then calls `.log(model, subaccount, user_id, ip_address)` when ready. The parser does not auto-log on `message_stop`.

**Rationale**: Keeps the parser's responsibilities clean — it knows *what* to parse, not *when* to log. The router/generator owns the decision of when a response is complete. Separating `feed_chunk` from `log` also makes testing straightforward (verify accumulator state before triggering the log).

### D3: Log format stays consistent with existing token_usage_logger pattern

**Decision**: `log()` emits the same `"User: %s, IP: %s, Model: %s, SubAccount: %s, PromptTokens: %s, CompletionTokens: %s, TotalTokens: %s"` format already used for OpenAI-compatible streaming, appending cache and thinking counts as a suffix when non-zero.

**Rationale**: Consistency across API paths makes log aggregation and alerting work without new patterns. A structured JSON format was considered but deferred — that would be a global observability change, not scoped here.

### D4: `AnthropicUsage` dataclass fields

Fields: `input_tokens: int = 0`, `output_tokens: int = 0`, `cache_creation_input_tokens: int = 0`, `cache_read_input_tokens: int = 0`, `thinking_tokens: int = 0`. A `total_tokens` property computes the sum. `thinking_tokens` is included in the total as it represents billed tokens.

### D5: Streaming integration — call site in `generate_bedrock_streaming_response` only

**Decision**: Instantiate `AnthropicTokenUsageParser` at the top of `generate_bedrock_streaming_response`, call `feed_chunk(chunk)` inside the existing event loop (after the chunk is already processed and yielded), and call `.log(...)` after the `message_stop` branch. The existing `yield` and `transport_logger` calls in that function are not moved or modified.

**Rationale**: Adding calls *after* the existing logic in each branch means zero risk of breaking the SSE output. The parser is a side-effect observer, not part of the event dispatch path.

## Risks / Trade-offs

- [Missing `usage` key in response] → `feed_chunk` and `parse_response` guard with `or {}` and all fields default to 0; warning logged internally
- [Streaming error before `message_stop`] → caller's `except` block calls `.log(...)` with whatever was accumulated; partial log is better than no log
- [Thinking tokens field name changes] → field is read via `.get("thinking_tokens", 0)` — silently 0 if renamed; update `AnthropicUsage` to fix
- [Future Anthropic usage fields] → add a field to `AnthropicUsage` and a line to `_extract_usage`; no call-site changes needed

## Migration Plan

1. Create `utils/anthropic_usage.py` — `AnthropicUsage` dataclass + `AnthropicTokenUsageParser` class
2. In `routers/messages.py`: after `response_json = json.loads(chunk_data)`, construct parser, call `parse_response(response_json)`, then `.log(...)` — all in a try/except that only warns on failure
3. In `handlers/streaming_generators.py:generate_bedrock_streaming_response`: construct parser at top, call `feed_chunk(chunk)` after each existing event branch, call `.log(...)` at `message_stop` and in the `except` handler
4. Add unit tests in `tests/unit/test_anthropic_usage.py`
5. No rollback needed — entirely additive; removing the three call sites restores prior behavior exactly

## Open Questions

- Should `generate_bedrock_streaming_response` accept a `request` parameter to enable user/IP extraction? Currently it only takes `response_body` and `tid`. Passing `None` for both is safe (parser will use `"unknown"`), so this can be added later without changing the parser class.
