# Fix for Sonnet-4.5 Token Usage Regression

## Issue Summary
Since git tag v1.2.5, there was a regression affecting Claude 3.7/4 models (specifically sonnet-4.5) when serviced via `/v1/chat/completions` endpoint:
- Missing token usage data in streaming responses
- Additional empty data chunks being emitted
- Wrong IDs (`msg_bdrk_01...` and `chatcmpl-unknown`) instead of proper IDs
- Wrong model name (`claude-v1` instead of actual model name)

## Root Cause Analysis

### Problem
The model detection logic in [`proxy_helpers.py:is_claude_37_or_4()`](../proxy_helpers.py:13-39) was checking for:
- `"claude-3.7"` in model name
- `"claude-4"` in model name  
- `"claude-4.5"` in model name
- OR `"claude"` in model name (with exclusions for 3.5)

**But the model name "sonnet-4.5" does NOT contain "claude"!**

### Consequence
When `is_claude_37_or_4("sonnet-4.5")` returned `False`:
1. The code incorrectly identified it as an OLD Claude 3.5 model
2. Used the wrong streaming path (lines 1984-2026 in `proxy_server.py`)
3. Called the wrong converter: [`convert_claude_chunk_to_openai()`](../proxy_helpers.py:684-714) instead of [`convert_claude37_chunk_to_openai()`](../proxy_helpers.py:717-860)
4. The old converter has hardcoded:
   - `"id": "chatcmpl-unknown"` (line 693)
   - `"model": "claude-v1"` (line 694)
5. The old converter doesn't handle `messageStop` and `metadata` chunks properly
6. Token usage never gets extracted or sent

## The Fix

Updated [`proxy_helpers.py:is_claude_37_or_4()`](../proxy_helpers.py:13-39) to detect model names like "sonnet-4.x" and "haiku-4.x":

```python
@staticmethod
def is_claude_37_or_4(model):
    model_lower = model.lower()
    return (
        "claude-3.7" in model_lower
        or "claude-4" in model_lower
        or "claude-4.5" in model_lower
        or "sonnet-4" in model_lower  # NEW: Detect sonnet-4.x models
        or "haiku-4" in model_lower    # NEW: Detect haiku-4.x models
        or (
            "claude" in model_lower
            and not any(v in model_lower for v in ["3-5", "3.5", "3-opus"])
        )
    )
```

## Expected Behavior After Fix

For model "sonnet-4.5", the code will now:
1. ✅ Correctly detect it as Claude 3.7/4 model
2. ✅ Use the correct streaming path (lines 1726-1854 in `proxy_server.py`)
3. ✅ Call the correct converter: [`convert_claude37_chunk_to_openai()`](../proxy_helpers.py:717-860)
4. ✅ Generate proper IDs: `chatcmpl-claude37-{random}`
5. ✅ Use correct model name: `sonnet-4.5`
6. ✅ Extract token usage from `metadata` chunk
7. ✅ Combine `finish_reason` from `messageStop` with `usage` in final chunk
8. ✅ Send single final chunk with BOTH `finish_reason: "stop"` AND `usage: {...}`

## Files Modified
- [`proxy_helpers.py`](../proxy_helpers.py) - Added detection for "sonnet-4" and "haiku-4" model name patterns

## Testing
To verify the fix:
```bash
# Start the proxy server
python proxy_server.py --config config.json

# Test with sonnet-4.5 model
curl -X POST http://localhost:3001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model": "sonnet-4.5",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

Expected final chunk should look like:
```json
data: {"id": "chatcmpl-claude37-28255", "object": "chat.completion.chunk", "created": 1767102420, "model": "sonnet-4.5", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 15, "completion_tokens": 4, "total_tokens": 19}}
data: [DONE]
```

## Related Issues
- Git tag v1.2.5 introduced this regression
- Git tag v1.2.4 was working correctly
- Affects all models with names like "sonnet-4.x", "haiku-4.x" that don't contain "claude" prefix