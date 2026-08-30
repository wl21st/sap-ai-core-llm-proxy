# Token Accounting, Usage Tracking & Prompt Caching

This document outlines the token usage metrics, extended thinking token handling, and prompt caching mechanisms normalized across OpenAI, Anthropic, and Gemini models by the proxy.

---

## 1. Token Usage Metrics & Categories

The proxy standardizes heterogeneous token accounting fields from upstream backends into a unified schema:

| Category | Normalized Field | Description | Supported Providers |
|---|---|---|---|
| **Prompt Tokens** | `input_tokens` / `prompt_tokens` | Total input tokens processed in the prompt | OpenAI, Claude, Gemini |
| **Completion Tokens** | `output_tokens` / `completion_tokens` | Total output tokens generated in the response | OpenAI, Claude, Gemini |
| **Extended Thinking** | `thinking_tokens` | Reasoning / thought tokens generated during deliberation | Claude 3.7 Sonnet / Opus, o1/o3 |
| **Cache Write Tokens** | `cache_creation_input_tokens` | Tokens written to prompt cache checkpoints | Claude (Bedrock) |
| **Cache Read Tokens** | `cache_read_input_tokens` | Cached tokens read from prompt cache (~10% base cost) | Claude (Bedrock), OpenAI |
| **Total Aggregation** | `total_tokens` | Sum of prompt tokens, completion tokens, and cache creation tokens | All |

---

## 2. Standard Response Payloads

### OpenAI `/v1/chat/completions` Format
```json
{
  "id": "chatcmpl-abc123xyz",
  "object": "chat.completion",
  "created": 1750833737,
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 1024,
    "completion_tokens": 256,
    "total_tokens": 1280,
    "prompt_tokens_details": {
      "cached_tokens": 512
    },
    "completion_tokens_details": {
      "reasoning_tokens": 128
    }
  }
}
```

### Anthropic `/v1/messages` Format
```json
{
  "id": "msg_01XyZ...",
  "type": "message",
  "role": "assistant",
  "model": "anthropic--claude-3.7-sonnet",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I help you today?"
    }
  ],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 512,
    "output_tokens": 256,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 512
  }
}
```

---

## 3. Anthropic & Bedrock Prompt Caching Pass-Through

Claude Code and other Anthropic clients attach `cache_control: {"type": "ephemeral"}` to message content blocks to enable prompt caching.

### Request Flow
```
Client (/v1/messages)
      │  (includes cache_control on content blocks)
      ▼
FastAPI messages.py Router
      │  (preserves cache_control structures)
      ▼
SAP AI Core / Bedrock SDK
      │
      ▼
AWS Bedrock (cache hit: 10% cost / cache write / cache read)
```

The proxy preserves `cache_control` blocks in `/v1/messages` requests and forwards them transparently to AWS Bedrock.

---

## 4. Bedrock Cache Creation Wire Format Normalization

In May 2026, AWS Bedrock updated the `usage` object schema for cache creation tokens from a flat integer field to a nested dictionary:

### Previous Wire Format (Flat Field)
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

### New Wire Format (Nested Object)
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

### Normalization Logic
To maintain backward compatibility with Anthropic SDK clients expecting a flat `cache_creation_input_tokens`, the proxy extracts `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens` from `cache_creation` and populates the sum into `cache_creation_input_tokens`.
