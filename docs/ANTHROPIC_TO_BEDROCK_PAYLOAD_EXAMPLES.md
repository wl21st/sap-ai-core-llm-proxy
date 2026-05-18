# Anthropic to Bedrock Payload Conversion

This document shows real Anthropic `/v1/messages` API payloads and how the proxy converts them to Bedrock format, including fields that get stripped because Bedrock doesn't support them.

## Overview

- **Anthropic Supports**: `metadata`, `output_config`, `context_management`, `cache_control`
- **Bedrock Supports**: Basic request/response with `inferenceConfig`, `messages`, `system`, `tools`
- **Proxy Action**: Strips unsupported fields before forwarding to Bedrock

## Real Anthropic Request Payloads

### Example 1: Basic Request with Metadata (UNSUPPORTED)

**What Claude Code sends:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {
      "role": "user",
      "content": "Hello, Claude"
    }
  ],
  "max_tokens": 1024,
  "metadata": {
    "user_id": "user-123-uuid",
    "session_id": "session-456",
    "request_id": "req-789"
  }
}
```

**Bedrock receives (after proxy strips `metadata`):**
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Hello, Claude"
        }
      ]
    }
  ],
  "max_tokens": 1024
}
```

**Why stripped:** Bedrock's Claude API doesn't accept a `metadata` field. It would return HTTP 400 Bad Request if included.

---

### Example 2: Request with Output Config (UNSUPPORTED)

**What Claude Code sends:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {
      "role": "user",
      "content": "Extract the name from this: John Smith is an engineer"
    }
  ],
  "max_tokens": 1024,
  "output_config": {
    "format": {
      "type": "json_schema",
      "schema": {
        "type": "object",
        "properties": {
          "name": { "type": "string" }
        },
        "required": ["name"]
      }
    },
    "effort": "high"
  }
}
```

**Bedrock receives (after proxy strips `output_config`):**
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Extract the name from this: John Smith is an engineer"
        }
      ]
    }
  ],
  "max_tokens": 1024
}
```

**Why stripped:** Bedrock's Claude API doesn't support structured output configuration at the request level. It would return HTTP 400 Bad Request if included.

---

### Example 3: Request with Context Management (UNSUPPORTED)

**What Claude Code sends:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {
      "role": "user",
      "content": "Summarize the document provided"
    }
  ],
  "max_tokens": 1024,
  "context_management": {
    "type": "auto"
  }
}
```

**Bedrock receives (after proxy strips `context_management`):**
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Summarize the document provided"
        }
      ]
    }
  ],
  "max_tokens": 1024
}
```

**Why stripped:** Bedrock's Claude API doesn't support context management settings. It would return HTTP 400 Bad Request if included.

---

### Example 4: Request with Extended Thinking + Context Management (NESTED UNSUPPORTED)

**What Claude Code sends:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {
      "role": "user",
      "content": "Solve this complex problem step by step"
    }
  ],
  "max_tokens": 4096,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 2048,
    "context_management": {
      "type": "auto"
    }
  }
}
```

**Bedrock receives (after proxy strips nested `context_management` from thinking):**
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Solve this complex problem step by step"
        }
      ]
    }
  ],
  "max_tokens": 4096,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 2048
  }
}
```

**Why stripped:** Bedrock's thinking config doesn't support `context_management`. The proxy removes it but keeps the thinking settings.

---

### Example 5: Request with All Unsupported Fields

**What Claude Code sends:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {
      "role": "user",
      "content": "Help me with this task"
    }
  ],
  "max_tokens": 2048,
  "metadata": {
    "user_id": "user-123",
    "source": "claude-code-ide"
  },
  "output_config": {
    "format": {
      "type": "json_schema",
      "schema": { "type": "object" }
    }
  },
  "context_management": {
    "type": "auto"
  },
  "thinking": {
    "type": "enabled",
    "budget_tokens": 1024,
    "context_management": {
      "type": "auto"
    }
  }
}
```

**Bedrock receives (after proxy strips ALL unsupported fields):**
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Help me with this task"
        }
      ]
    }
  ],
  "max_tokens": 2048,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 1024
  }
}
```

**Why stripped:** Multiple unsupported fields. The proxy removes all of them:
- `metadata` - Not supported by Bedrock
- `output_config` - Not supported by Bedrock
- `context_management` (top-level) - Not supported by Bedrock
- `context_management` (in thinking) - Not supported in Bedrock thinking config

---

## Real Anthropic Response Payloads

### Bedrock Response (as received):
```json
{
  "output": {
    "message": {
      "content": [
        {
          "text": "Hello! I'm Claude, an AI assistant created by Anthropic..."
        }
      ]
    }
  },
  "usage": {
    "inputTokens": 12,
    "outputTokens": 45
  },
  "stopReason": "end_turn"
}
```

### Converted to Anthropic Format (for proxy client):
```json
{
  "id": "msg_1234567890",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hello! I'm Claude, an AI assistant created by Anthropic..."
    }
  ],
  "model": "anthropic--claude-4.5-sonnet",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 12,
    "output_tokens": 45
  }
}
```

---

## Streaming Requests

### Anthropic Format (with unsupported fields):
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {
      "role": "user",
      "content": "Write a poem about AI"
    }
  ],
  "max_tokens": 1024,
  "stream": true,
  "metadata": {
    "request_type": "streaming_test"
  }
}
```

### Bedrock receives (stripped):
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "text": "Write a poem about AI"
        }
      ]
    }
  ],
  "max_tokens": 1024
}
```

Note: `stream` and `metadata` are removed before forwarding to Bedrock.

---

## Log Messages

When these payloads are processed, the proxy logs indicate field removal:

```
2026-05-18 07:11:14 [INFO] Removing unsupported top-level field 'metadata' from request body
2026-05-18 07:11:14 [INFO] Removing unsupported top-level field 'output_config' from request body
2026-05-18 07:11:14 [INFO] Removing unsupported top-level field 'context_management' from request body
2026-05-18 07:11:14 [INFO] Removing 'context_management' from thinking config
```

---

## Summary: What Gets Stripped

| Field | Anthropic Supports | Bedrock Supports | Proxy Action |
|-------|-------------------|-----------------|--------------|
| `metadata` | ✅ Yes | ❌ No | Stripped (logged) |
| `output_config` | ✅ Yes | ❌ No | Stripped (logged) |
| `context_management` (top-level) | ✅ Yes | ❌ No | Stripped (logged) |
| `context_management` (in thinking) | ✅ Yes | ❌ No | Stripped (logged) |
| `cache_control` | ✅ Yes | ❌ No | Stripped (not logged in current impl) |
| `stream` | ✅ Yes | ✅ Yes (via handler) | Removed from body |
| `model` | ✅ Yes | N/A | Removed from body |
| `thinking` | ✅ Yes (3.7+) | ✅ Yes | **Kept and forwarded** |
| `tools` | ✅ Yes | ✅ Yes | **Kept and forwarded** |
| `system` | ✅ Yes | ✅ Yes | **Kept and forwarded** |
| `messages` | ✅ Yes | ✅ Yes | **Kept and forwarded** |
| `max_tokens` | ✅ Yes | ✅ Yes | **Kept and forwarded** |

---

## Implementation Location

The field stripping happens in: `routers/messages.py:proxy_claude_request()`

```python
unsupported_fields = ["context_management", "metadata", "output_config"]
for field in unsupported_fields:
    if field in body:
        logger.info(
            "Removing unsupported top-level field '%s' from request body",
            field,
        )
        body.pop(field, None)
```

---

## Testing

Integration tests verify that these payloads are properly stripped:
- `tests/integration/test_unsupported_fields.py`

Each test sends a request with unsupported fields and verifies:
1. The proxy returns HTTP 200 (success)
2. The response is valid Anthropic format
3. If the fields were NOT stripped, Bedrock would reject with HTTP 400
