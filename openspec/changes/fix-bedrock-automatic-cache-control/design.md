## Context

The proxy routes `/v1/messages` to Bedrock `invoke_model` / `invoke_model_with_response_stream`.
Bedrock accepts Anthropic's JSON body format including block-level `cache_control`, but does NOT
accept top-level `cache_control` (the Anthropic API's "automatic caching" feature) or the `ttl`
sub-field on `cache_control`.

The fix is entirely within `routers/messages.py`, in the body normalisation block between
line 208 (`body = request_body_json.copy()`) and line 261 (`body_json = json.dumps(body)`).

---

## Block eligibility rules

To replicate the Anthropic API's "last cacheable block" logic, a block is considered eligible
for `cache_control` injection if it meets all of the following:

1. Does **not** already have a `cache_control` key.
2. Is **not** a thinking block (`"type": "thinking"` or `"type": "redacted_thinking"`).
3. Is **not** an empty text block (`"type": "text"` with `"text"` being `""` or absent).

The search order for the last eligible block is:
```
messages[-1].content[-1]  ← last content block of last message (any role)
messages[-1]              ← message itself (if content is a string, treat it as one block)
...
messages[0].content[0]
system[-1]                ← last block in system array
...
system[0]
tools[-1]                 ← last tool definition
...
tools[0]
```
i.e. reverse traversal of `messages` (innermost content block first), then `system`, then `tools`.

---

## Transformation function design

```python
def _expand_top_level_cache_control(body: dict) -> dict:
    """
    Translate top-level automatic cache_control to an explicit block-level marker.

    Bedrock does not support top-level cache_control (Anthropic API automatic caching).
    This function finds the last cacheable block across tools → system → messages and
    injects cache_control on it, then removes the top-level field.

    Mutates and returns body.
    """
```

**Placement:** New private function in `routers/messages.py`, called from `proxy_claude_request`
after the `unsupported_fields` stripping block and before `body_json = json.dumps(body)`.

**Invocation guard:** Only called when `"cache_control" in body` — no-op for all existing requests
that already use block-level markers or no caching at all.

---

## Detailed algorithm

```
top_cc = body.pop("cache_control")           # extract and remove top-level marker
ttl = top_cc.get("ttl")                      # e.g. "1h"

if ttl:
    LOG WARNING: "top-level cache_control with ttl='{ttl}' — Bedrock supports only
                  5-minute TTL; proceeding with default ephemeral cache"

effective_cc = {"type": "ephemeral"}         # ttl stripped; Bedrock only knows ephemeral

# Build candidate list: last-to-first traversal of messages → system → tools
# Each candidate is (container_ref, index_or_key, is_content_block)
# We want the LAST eligible block overall, so we scan messages last→first, then system, then tools

last_eligible = None

# 1. Scan messages in reverse (last message first, last content block first)
for msg in reversed(body.get("messages", [])):
    content = msg.get("content")
    if isinstance(content, list):
        for block in reversed(content):
            if _is_eligible_for_cache(block):
                last_eligible = block
                break
    elif isinstance(content, str):
        # String content can't receive cache_control directly; convert to block first
        # (messages.py already normalises string content elsewhere, but guard here)
        pass
    if last_eligible:
        break

# 2. If not found in messages, scan system blocks in reverse
if last_eligible is None:
    for block in reversed(body.get("system", []) if isinstance(body.get("system"), list) else []):
        if _is_eligible_for_cache(block):
            last_eligible = block
            break

# 3. If not found in system, scan tools in reverse
if last_eligible is None:
    for tool in reversed(body.get("tools", [])):
        if _is_eligible_for_cache(tool):
            last_eligible = tool
            break

if last_eligible is not None:
    last_eligible["cache_control"] = effective_cc
    LOG INFO: "Expanded top-level cache_control to block-level on {block type/role summary}"
else:
    LOG WARNING: "top-level cache_control present but no eligible block found; caching skipped"
```

**`_is_eligible_for_cache(block)`:**
```python
def _is_eligible_for_cache(block: dict) -> bool:
    if not isinstance(block, dict):
        return False
    if "cache_control" in block:
        return False                              # already marked
    block_type = block.get("type", "")
    if block_type in ("thinking", "redacted_thinking"):
        return False                              # thinking blocks cannot be explicitly cached
    if block_type == "text" and not block.get("text", "").strip():
        return False                              # empty text blocks cannot be cached
    return True
```

---

## Edge cases and their handling

| Scenario | Handling |
|---|---|
| `cache_control` already on last block (same TTL) | `_is_eligible_for_cache` returns False for that block; search continues to second-to-last. This differs slightly from Anthropic API (which treats it as a no-op), but is safe — the net effect is the same caching, just the marker is on a slightly earlier block. |
| All blocks already have `cache_control` | No eligible block found; warn and skip injection. Request proceeds without top-level CC. |
| `messages` array is empty, `system` has blocks | Correctly falls through to system scan. |
| `messages` last message has string content | String content is not traversed for block-level injection (can't attach `cache_control` to a string). Falls through to system/tools. |
| `ttl: "1h"` present | Logged as warning; stripped from effective_cc. Proceeds with 5-minute ephemeral caching. |
| Top-level CC with `ttl: "1h"` AND existing block-level marker with `ttl: "1h"` | Top-level marker is expanded to 5-min; block-level marker with `ttl: "1h"` is kept as-is (will likely fail on Bedrock — that is a separate issue beyond scope). |
| No `cache_control` in body at all | `_expand_top_level_cache_control` is never called. Zero-cost no-op. |

---

## Placement in `proxy_claude_request`

```python
# After: body.pop("model", None) ... unsupported_fields stripping
# Before: body_json = json.dumps(body)

if "cache_control" in body:
    _expand_top_level_cache_control(body)
```

This placement is intentional: it runs after the `body = request_body_json.copy()` deep copy
so the original `request_body_json` is not mutated, and before `body_json = json.dumps(body)`
so the serialised payload sent to Bedrock contains the correct structure.

---

## Test design

### Unit tests — `tests/unit/routers/test_messages_router_cache.py`

Test the `_expand_top_level_cache_control` function in isolation (pure unit tests, no HTTP):

| Test | Input | Expected |
|---|---|---|
| `test_top_level_cc_injected_onto_last_message_block` | body with top-level CC, messages with two text blocks | CC on last text block of last message |
| `test_top_level_cc_injected_onto_last_system_block_when_messages_empty` | body with top-level CC, only system blocks, no messages | CC on last system block |
| `test_top_level_cc_injected_onto_tool_when_no_system_or_messages` | body with top-level CC, only tools array | CC on last tool |
| `test_top_level_cc_skips_thinking_blocks` | last content block is thinking; second-to-last is text | CC on text block, not thinking block |
| `test_top_level_cc_skips_empty_text_blocks` | last content block is empty text | CC on previous non-empty block |
| `test_top_level_cc_skips_already_marked_blocks` | last block already has CC | CC on second-to-last block |
| `test_top_level_cc_no_eligible_block_logs_warning` | all blocks already marked | top-level CC removed, no injection, warning logged |
| `test_top_level_cc_with_ttl_1h_degrades_to_5min` | top-level CC with `ttl: "1h"` | effective CC is `{"type":"ephemeral"}` (no ttl), warning logged |
| `test_top_level_cc_removed_from_body` | any valid body | `"cache_control"` not present in returned body |
| `test_no_top_level_cc_body_untouched` | body without top-level CC | body unchanged |
| `test_string_message_content_falls_through_to_system` | last message has string content, system has blocks | CC on last system block |
| `test_combined_top_level_and_existing_block_markers` | top-level CC + existing block CC on system | CC also injected on last message block |

### Integration tests — extend `tests/integration/test_cache_control.py`

Add a new test class `TestAutomaticCacheControlExpansion`:

| Test | Description |
|---|---|
| `test_automatic_cc_top_level_returns_200` | POST to `/v1/messages` with top-level `cache_control` (no block-level markers); expect 200 not 400 |
| `test_automatic_cc_top_level_cache_write_occurs` | Same as above; `usage.cache_creation_input_tokens > 0` (or cache_read if already warm) |
| `test_automatic_cc_top_level_cache_hit_on_second_request` | Two consecutive identical requests with top-level CC; second shows `cache_read_input_tokens > 0` |
| `test_automatic_cc_with_ttl_1h_returns_200` | Top-level `cache_control: {"type":"ephemeral","ttl":"1h"}`; expect 200 (graceful TTL degradation) |
| `test_automatic_cc_combined_with_block_level` | Both top-level CC and block CC in system; expect 200 and cache activity |
| `test_automatic_cc_streaming_returns_200_and_cache_fields` | Streaming request with top-level CC; `message_start` event has cache usage fields |
