# Anthropic to Bedrock Payload Conversion Examples

This document demonstrates incoming Anthropic `/v1/messages` payloads from clients (such as Claude Code) and how the proxy transforms them before forwarding to AWS Bedrock, including stripping unsupported fields.

---

## 1. Field Support Summary

| Field | Anthropic API | AWS Bedrock API | Proxy Action |
|---|---|---|---|
| `messages` | Supported | Supported | Preserved |
| `system` | Supported | Supported | Extracted & formatted to top-level |
| `cache_control` | Supported | Supported | Preserved on content blocks |
| `thinking` | Supported | Supported | Preserved (`type`, `budget_tokens`) |
| `metadata` | Supported | **Not Supported** | **Stripped** |
| `output_config` | Supported | **Not Supported** | **Stripped** |
| `context_management` | Supported | **Not Supported** | **Stripped** |

---

## 2. Real-World Conversion Examples

### Example: Stripping `metadata` and `output_config`

**Inbound Client Payload (Claude Code):**
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
    "session_id": "session-456"
  },
  "output_config": {
    "format": { "type": "json_schema" }
  }
}
```

**Outbound Payload Sent to Bedrock:**
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

---

### Example: Stripping Nested `context_management` in Thinking Blocks

**Inbound Client Payload:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [{"role": "user", "content": "Solve problem"}],
  "max_tokens": 4096,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 2048,
    "context_management": { "type": "auto" }
  }
}
```

**Outbound Payload Sent to Bedrock:**
```json
{
  "anthropic_version": "bedrock-2023-05-31",
  "messages": [{"role": "user", "content": [{"text": "Solve problem"}]}],
  "max_tokens": 4096,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 2048
  }
}
```
