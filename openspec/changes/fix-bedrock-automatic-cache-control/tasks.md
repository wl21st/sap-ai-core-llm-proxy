## Tasks

### 1. Implement `_is_eligible_for_cache` helper in `routers/messages.py`

Add private function `_is_eligible_for_cache(block: dict) -> bool` that returns True iff
the block can receive a `cache_control` marker:
- Is a dict
- Does not already have `cache_control`
- Is not a thinking/redacted_thinking block
- Is not an empty text block

### 2. Implement `_expand_top_level_cache_control` in `routers/messages.py`

Add private function `_expand_top_level_cache_control(body: dict) -> None` that:
- Pops top-level `cache_control` from body
- Warns if `ttl` is present (strips it)
- Scans messages (reverse) → system (reverse) → tools (reverse) for last eligible block
- Injects `{"type": "ephemeral"}` on that block
- Logs INFO on success, WARNING if no eligible block found

### 3. Wire into `proxy_claude_request` in `routers/messages.py`

Add guard after the unsupported_fields stripping block:
```python
if "cache_control" in body:
    _expand_top_level_cache_control(body)
```

### 4. Write unit tests in `tests/unit/routers/test_messages_router_cache.py`

Cover all 12 cases from the design spec:
- block injection onto last message/system/tool
- thinking block skipping
- empty text block skipping
- already-marked block skipping
- no eligible block (warning path)
- ttl:"1h" degradation
- top-level CC removed from body
- no-op when no top-level CC
- string content fallthrough
- combined top-level + block-level markers

### 5. Write integration tests extending `tests/integration/test_cache_control.py`

Add class `TestAutomaticCacheControlExpansion` with 6 tests covering:
- 200 response (not 400) with top-level CC
- cache write occurs
- cache hit on second request
- ttl:"1h" graceful degradation
- combined top-level + block-level
- streaming with top-level CC
