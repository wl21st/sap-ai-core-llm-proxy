# Bedrock `cache_creation_input_tokens` Wire Format Change

## Background

AWS Bedrock Anthropic models support prompt caching via the `cache_control: {"type": "ephemeral"}`
field on content blocks. When a cache entry is written, Bedrock reports how many tokens were cached
in the `usage` object of the response.

In **May 2026**, Bedrock changed how it reports cache-write token counts, introducing a new nested
object alongside the existing flat field. This change affects the `/v1/messages` endpoint of this
proxy (the Anthropic Messages API path).

---

## Wire Format: Before and After

### Before (original flat format)

```json
{
  "usage": {
    "input_tokens": 42,
    "output_tokens": 100,
    "cache_creation_input_tokens": 1071,
    "cache_read_input_tokens": 0
  }
}
```

`cache_creation_input_tokens` carried the total number of tokens written to cache in a single
integer. Clients read this field directly.

---

### After (new nested format, introduced May 2026)

```json
{
  "usage": {
    "input_tokens": 42,
    "output_tokens": 100,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "cache_creation": {
      "ephemeral_5m_input_tokens": 1071,
      "ephemeral_1h_input_tokens": 0
    }
  }
}
```

Key differences:

| Field | Before | After |
|---|---|---|
| `cache_creation_input_tokens` | Total tokens written to cache | **Always 0** |
| `cache_creation` | Not present | New nested object with per-TTL-tier counts |
| `cache_creation.ephemeral_5m_input_tokens` | — | Tokens written to the 5-minute cache tier |
| `cache_creation.ephemeral_1h_input_tokens` | — | Tokens written to the 1-hour cache tier |
| `cache_read_input_tokens` | Unchanged | Unchanged |
| `input_tokens` | Unchanged | Unchanged |

The nested object breaks down cache writes by TTL tier (`ephemeral_5m` = 5-minute TTL,
`ephemeral_1h` = 1-hour TTL). The flat field is kept in the response for backward compatibility
but is set to 0 even when caching occurs.

The same change applies to streaming responses: the `message_start` SSE event contains a `usage`
object with the same structure.

---

## Impact

### Clients reading `cache_creation_input_tokens` directly

Any client that checks `usage.cache_creation_input_tokens > 0` to detect cache activity will
always see 0 after this change, even when tokens were actually cached. Affected clients include:

- **Claude Code** — sends `cache_control: ephemeral` on system prompts by default and reads
  `cache_creation_input_tokens` to verify caching is working. Without the fix it would appear
  that caching never activates, making cost estimates incorrect.
- **This proxy's token usage logger** — would log `CacheCreationTokens: 0` for every request,
  making the logs misleading.
- Any other client or monitoring tool that relies on the flat field.

### Models affected

The new format is returned by all Claude models on Bedrock that support prompt caching:

- `anthropic--claude-4.5-haiku`
- `haiku-4.5`
- `opus-4.7`
- `sonnet-4.6`
- (and future models)

### Minimum token thresholds (unchanged)

The minimum number of tokens required to activate caching is unchanged:

| Model | Minimum cacheable tokens |
|---|---|
| Claude Sonnet 4.6 | 1,024 |
| Claude Haiku 4.5 | 4,096 |
| Claude Opus 4.7 | 4,096 |
| Claude Haiku / Sonnet 4.5 (older) | 4,096 |

---

## Fix: Proxy-Side Normalization

The proxy normalizes the new nested format back to the flat field before forwarding the response
to clients. This ensures all callers receive a consistent, backward-compatible response regardless
of which Bedrock format is active.

### Helper: `_resolve_cache_creation_tokens` (`utils/anthropic_usage.py`)

```python
@staticmethod
def _resolve_cache_creation_tokens(usage: dict) -> int:
    flat = int(usage.get("cache_creation_input_tokens") or 0)
    if flat:
        return flat                         # old format: use flat field directly
    nested = usage.get("cache_creation")
    if isinstance(nested, dict):
        return sum(int(v or 0) for v in nested.values())  # new format: sum all tiers
    return 0
```

Priority rules:

1. If `cache_creation_input_tokens` is non-zero, use it (old format, no change).
2. Otherwise, sum all values in the `cache_creation` nested dict (new format, both TTL tiers).
3. If neither is present, return 0.

This avoids double-counting if Bedrock ever populates both fields simultaneously.

### Normalization of response body: `normalize_usage_cache_fields` (`utils/anthropic_usage.py`)

```python
@staticmethod
def normalize_usage_cache_fields(usage: dict) -> dict:
    resolved = AnthropicTokenUsageParser._resolve_cache_creation_tokens(usage)
    if resolved and not int(usage.get("cache_creation_input_tokens") or 0):
        usage["cache_creation_input_tokens"] = resolved
    return usage
```

Mutates `usage` in-place: writes the resolved count into `cache_creation_input_tokens` only when
the flat field is currently 0. The nested `cache_creation` object is preserved so clients that
understand the new format can still read it.

### Where normalization is applied

| Location | Path | What is normalized |
|---|---|---|
| `routers/messages.py` | Non-streaming (`/v1/messages`) | `response_json["usage"]` before `JSONResponse` |
| `handlers/streaming_generators.py` | Streaming (`/v1/messages?stream=true`) | `message_start` chunk's `message.usage` before the SSE event is yielded |
| `AnthropicTokenUsageParser._extract_usage` | Internal token logging (non-streaming) | `AnthropicUsage.cache_creation_input_tokens` field |
| `AnthropicTokenUsageParser.feed_chunk` | Internal token logging (streaming) | `_usage.cache_creation_input_tokens` accumulator |

### Backward compatibility

| Scenario | Behavior |
|---|---|
| Old format (flat non-zero, no nested dict) | Flat field used as-is; no mutation |
| New format (flat = 0, nested dict present) | Flat field populated from nested sum |
| Both fields present and flat non-zero | Flat field wins; nested ignored |
| Neither field present | Zero returned; no mutation |

The proxy response always includes `cache_creation_input_tokens` with the correct count.
The `cache_creation` nested object is passed through unchanged for forward compatibility.
