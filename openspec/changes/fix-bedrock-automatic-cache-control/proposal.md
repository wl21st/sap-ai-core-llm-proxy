## Why

The `/v1/messages` endpoint (Anthropic Messages API passthrough) does not correctly handle
**top-level automatic `cache_control`** — the simplified caching syntax introduced in the
Anthropic API where a single `cache_control` field is placed at the request root rather than
on individual content blocks.

Bedrock's `InvokeModel` API does **not** support top-level `cache_control`. When a client
sends this field, the proxy currently passes it through verbatim to Bedrock, which rejects
the request or silently ignores it — either way, caching does not occur.

Additionally, the `ttl` sub-field (`{"type": "ephemeral", "ttl": "1h"}`) used for the
1-hour cache duration on block-level markers needs verification: Bedrock supports 1-hour TTL
only on select models (Sonnet 4.5, Haiku 4.5, Opus 4.5). For unsupported models the field
may cause a 400 error. This is currently passed through unmodified with no guard.

**Reference:** `docs/reference/claude_caching_reference.md` §Automatic caching, §1-hour
cache duration, and the Bedrock note:
> "Automatic caching is available on the Claude API … Bedrock and Vertex AI do not support
> automatic caching."

### Verification: Does Claude Code use top-level cache_control?

**No.** Claude Code v2.1.143 was inspected and uses **block-level** `cache_control` on
individual system blocks and tool definitions — not top-level automatic caching:

```json
{
  "system": [
    {"type": "text", "text": "...", "cache_control": {"type": "ephemeral"}}
  ],
  "messages": [...]
}
```

Claude Code's internal model uses a `cacheScope` field (`"org"`, `"global"`, `null`) on
system blocks that is converted to block-level `cache_control` before the API call. The
top-level `cache_control` field is never sent.

**This means the proxy already works correctly for Claude Code today** — block-level
`cache_control` passes through the `/v1/messages` handler unchanged, as confirmed by the
prior exploration in `docs/history/2026-05-16-cache-control-exploration.md`.

### Who is affected by the top-level gap?

Any third-party client that uses the newer Anthropic API automatic caching syntax — e.g.,
direct users of the `anthropic` Python/TypeScript SDK with `cache_control` at the request
root, or clients that follow the reference doc examples for automatic caching. This is a
correctness gap for forward-compatibility as the automatic caching pattern becomes more
common in the ecosystem.

## What Changes

Implement a **top-level `cache_control` expansion** step in `routers/messages.py`, executed
before `body_json = json.dumps(body)`, that transforms the automatic caching syntax into
the equivalent explicit block-level breakpoints that Bedrock supports.

### Transformation logic

The Anthropic API's automatic caching rule: apply `cache_control` to the **last cacheable
block** in the request, scanning in order `tools → system → messages`.

The proxy replicates this by:

1. Detect `cache_control` at the top level of the request body.
2. Extract `ttl` from it if present; strip `ttl` from the Bedrock-bound body regardless
   (Bedrock uses only `{"type": "ephemeral"}`; `ttl` is a Claude API-only field).
3. Walk `tools → system → messages` in reverse, find the last block that:
   - Does not already have a `cache_control` marker, and
   - Is a cacheable type (not a thinking block, not an empty text block).
4. Inject `cache_control: {"type": "ephemeral"}` on that block.
5. Remove the top-level `cache_control` from the body.
6. Log the transformation at INFO level (which block received the marker).

If no eligible block is found (edge case — e.g., all blocks already have markers, or the
only blocks are thinking blocks), log a warning and remove the top-level `cache_control`
without injecting anything. This degrades gracefully to no caching rather than a 400 error.

### The `ttl: "1h"` case

Bedrock does not support the 1-hour cache TTL. When `cache_control` contains `"ttl": "1h"`:
- Log a WARNING that 1-hour TTL is not supported on Bedrock; the request will use the
  default 5-minute TTL instead.
- Proceed with the same block-level injection using `{"type": "ephemeral"}` (no `ttl`).
- Do NOT return an error — degrade gracefully to 5-minute caching.

### Combination case: top-level + explicit block-level breakpoints

When a request contains **both** top-level `cache_control` and existing explicit
`cache_control` on individual blocks (the "combining" pattern from the reference docs),
the transformation should still find the last block without a marker and inject there —
exactly matching the Anthropic API's behaviour where the automatic breakpoint takes one
of the 4 available slots.

## Capabilities

### Modified Capabilities

- `messages-proxy`: The `/v1/messages` handler gains a pre-send normalisation step that
  translates automatic caching syntax to explicit block-level syntax compatible with Bedrock.

### New Capabilities (none)

No new user-visible capabilities. This is a compatibility fix: clients using the Anthropic
API's automatic caching syntax now get the same caching behaviour from the proxy as they
would from the Claude API directly, at Bedrock prices.

## Impact

- **Files affected**: `routers/messages.py`
- **New files**: `tests/unit/routers/test_messages_router_cache.py`,
  `tests/integration/test_cache_control.py` (extend existing)
- **Breaking changes**: None. Clients using explicit block-level `cache_control` are
  unaffected. Clients using top-level `cache_control` currently get errors or no caching;
  after this fix they get correct caching.
- **Side effects**: None. The transformation only touches the local `body` dict before
  serialisation; no persistent state is modified.
- **Bedrock API compatibility**: Bedrock `invoke_model` and `invoke_model_with_response_stream`
  both accept `cache_control` on content blocks — confirmed by the existing integration tests
  in `tests/integration/test_cache_control.py`.
