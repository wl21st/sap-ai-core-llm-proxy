# Bug Report: Sonnet 4.5 Token Usage Regression in v1.2.5

## Summary
Since v1.2.5 (git tag), Claude 3.7/4 models (including sonnet-4.5) streaming responses via `/v1/chat/completions` endpoint have:
1. **Missing token usage** in the final chunk
2. **Extra empty chunks** being emitted

## Affected Versions
- **Broken**: v1.2.5 (current)
- **Working**: v1.2.4

## Reproduction
```bash
curl -X POST http://localhost:3001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "model": "sonnet-4.5",
    "messages": [{"role": "user", "content": "Say hello in one word"}],
    "max_completion_tokens": 100,
    "stream": true
  }'
```

## Current (Broken) Output
```
data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "msg_bdrk_01QrCa66TQHCbB766KPw9zop", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: {"choices": [{"delta": {}, "finish_reason": null, "index": 0}], "created": 1767102743, "id": "chatcmpl-unknown", "model": "claude-v1", "object": "chat.completion.chunk", "system_fingerprint": "fp_36b0c83da2"}
data: [DONE]
```

**Issues**:
- Chunk with `finish_reason: "stop"` has NO usage data
- Extra empty chunks with `finish_reason: null`

## Expected (v1.2.4) Output
```
data: {"id": "chatcmpl-claude37-67505", "object": "chat.completion.chunk", "created": 1767102420, "model": "sonnet-4.5", "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": null}]}
data: {"id": "chatcmpl-claude37-19040", "object": "chat.completion.chunk", "created": 1767102420, "model": "sonnet-4.5", "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": null}]}
data: {"id": "chatcmpl-claude37-28255", "object": "chat.completion.chunk", "created": 1767102420, "model": "sonnet-4.5", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 15, "completion_tokens": 4, "total_tokens": 19}}
data: [DONE]
```

**Correct behavior**:
- Token usage is in the SAME chunk as `finish_reason: "stop"`
- No extra empty chunks

## Root Cause Analysis

### Regression Introduced By
Commit `a171ef7` - "fix: prevent duplicate [DONE] signals in streaming responses"

### The Bug

In [`proxy_server.py:1726-1836`](../proxy_server.py:1726), the Claude 3.7/4 streaming logic has two issues:

#### Issue 1: messageStop Chunk Sent Separately
**File**: `proxy_server.py`
**Lines**: 1765-1779

The code converts ALL Claude chunks (including `messageStop`) to OpenAI format via `convert_claude37_chunk_to_openai()`.

In [`proxy_helpers.py:789-814`](../proxy_helpers.py:789), when a `messageStop` chunk is received:
```python
elif chunk_type == "messageStop":
    # Extract stop reason
    stop_reason = claude_dict_chunk.get("messageStop", {}).get("stopReason")
    # Map Claude stopReason to OpenAI finish_reason
    stop_reason_map = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    finish_reason = stop_reason_map.get(stop_reason)
    if finish_reason:
        openai_chunk_payload["choices"][0]["finish_reason"] = finish_reason
        openai_chunk_payload["choices"][0]["delta"] = {}  # Empty delta
        logger.debug(f"Converted messageStop chunk: {openai_chunk_payload}")
```

This creates a chunk with `finish_reason: "stop"` but **NO usage data**.

#### Issue 2: Usage Chunk Sent Without finish_reason
**File**: `proxy_server.py`
**Lines**: 1802-1823

After the loop, the code sends a separate final chunk:
```python
final_usage_chunk = {
    "id": f"chatcmpl-claude37-{random.randint(10000, 99999)}",
    "object": "chat.completion.chunk",
    "created": int(time.time()),
    "model": model,
    "choices": [{"index": 0, "delta": {}, "finish_reason": None}],  # ❌ None!
    "usage": {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    },
}
```

This violates OpenAI's streaming spec, which requires usage to be in the SAME chunk as `finish_reason`.

#### Issue 3: metadata Chunk Handling
**Lines**: 1742-1763

When a `metadata` chunk is received, it extracts token counts but **continues** (doesn't yield). This is correct, but the tokens are then used to create a separate chunk later.

## The Fix

### Solution Overview
Combine the `messageStop` chunk and usage data into a SINGLE final chunk with both `finish_reason: "stop"` AND `usage`.

### Required Changes

**File**: `proxy_server.py`
**Location**: Lines 1730-1823

1. **Add variable to track stop reason** (after line 1730):
```python
stop_reason_received = None  # Track the stop reason from messageStop
```

2. **Intercept messageStop chunk** (after line 1740, before checking metadata):
```python
# Check if this is a messageStop chunk - capture stop reason but don't send yet
if "messageStop" in claude_dict_chunk:
    stop_reason_received = claude_dict_chunk.get("messageStop", {}).get("stopReason", "end_turn")
    logger.info(f"Received messageStop with stopReason: {stop_reason_received}")
    # Don't send this chunk yet - wait for metadata to combine with usage
    continue
```

3. **Update final chunk generation** (lines 1802-1823):
```python
# Send final chunk with BOTH finish_reason and usage information
if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
    # Map Claude stop reason to OpenAI finish_reason
    stop_reason_map = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    finish_reason = stop_reason_map.get(stop_reason_received, "stop")
    
    final_usage_chunk = {
        "id": f"chatcmpl-claude37-{random.randint(10000, 99999)}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],  # ✅ Add finish_reason
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }
    final_usage_chunk_str = f"data: {json.dumps(final_usage_chunk)}\n\n"
    logger.info(
        f"Sending final chunk with finish_reason={finish_reason} and usage: {final_usage_chunk_str[:200]}..."
    )
    yield final_usage_chunk_str
    logger.info(
        f"Sent final chunk: finish_reason={finish_reason}, prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
    )
```

### Alternative: Update convert_claude37_chunk_to_openai()

**File**: `proxy_helpers.py`
**Location**: Lines 816-824

Modify to NOT send messageStop chunks:
```python
elif chunk_type in ["contentBlockStart", "contentBlockStop", "metadata", "messageStop"]:  # Add messageStop
    # These Claude events don't have a direct OpenAI chunk equivalent
    logger.debug(
        f"Ignoring Claude chunk type for OpenAI stream: {chunk_type}"
    )
    return None
```

This prevents the messageStop chunk from being converted at all, relying entirely on the final chunk generation logic.

## Testing

### Manual Test
```bash
# Test streaming with token usage
curl -N -X POST http://localhost:3001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "model": "sonnet-4.5",
    "messages": [{"role": "user", "content": "Say hello in one word"}],
    "max_completion_tokens": 100,
    "stream": true
  }' | grep -E '(finish_reason|usage)'
```

**Expected**:
- Should see ONE line with both `"finish_reason": "stop"` AND `"usage": {`
- Should NOT see multiple lines with empty deltas

### Unit Test
Add test to verify single final chunk with both finish_reason and usage:
```python
def test_claude37_streaming_final_chunk_has_usage_and_finish_reason():
    """Verify final chunk has both finish_reason and usage in one chunk."""
    # Test implementation
    pass
```

## Impact

### Affected Components
- Claude 3.7/4/4.5 models (sonnet-4.5, etc.)
- `/v1/chat/completions` endpoint with `stream: true`
- Any clients relying on accurate token counting

### Not Affected
- Non-streaming requests
- Claude 3.5 and older models
- Gemini models
- GPT models
- `/v1/messages` endpoint

## References

- OpenAI Streaming Spec: https://platform.openai.com/docs/api-reference/streaming
- Regression commit: `a171ef7`
- Related file: [`proxy_server.py:1726-1836`](../proxy_server.py:1726)
- Related file: [`proxy_helpers.py:717-859`](../proxy_helpers.py:717)

## Status
🔴 **CRITICAL** - Affects token usage tracking and billing