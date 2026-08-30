# Declarative Model Manifest & Neutral Adapter Plan

This document outlines the architectural plan for introducing a declarative model manifest (`config/model_manifest.yaml`) and neutral provider adapters across the proxy.

---

## 1. Objectives & Motivation

- **Declarative Capabilities**: Centralize model token limits, context windows, and streaming semantics in YAML rather than hardcoded Python conditionals.
- **Neutral Adapter Layer**: Standardize incoming requests to an intermediate representation (`CanonicalChatRequest`) before translating into provider-specific schemas.
- **Accurate Clamping & Validation**: Automatically clamp `max_output_tokens` and validate parameter compatibility before dispatching to SAP AI Core backends.

---

## 2. Manifest Schema (`config/model_manifest.yaml`)

```yaml
models:
  gpt-4o:
    provider: openai
    context_window: 128000
    max_output_tokens: 16384
    supports:
      streaming: true
      function_calling: true
      vision: true
    token_accounting:
      reasoning_tokens: false

  anthropic--claude-3.7-sonnet:
    provider: bedrock_converse
    context_window: 200000
    max_output_tokens: 64000
    supports:
      streaming: true
      thinking: true
      cache_control: true
    token_accounting:
      cache_read: true
      cache_write: true

  anthropic--claude-3.5-sonnet:
    provider: bedrock_invoke
    context_window: 200000
    max_output_tokens: 8192
    supports:
      streaming: true
      cache_control: true

  gemini-2.5-pro:
    provider: vertex_gemini
    context_window: 1000000
    max_output_tokens: 65536
    supports:
      streaming: true
      thinking: true
```

---

## 3. Neutral Adapter Pipeline

```
Inbound Request (OpenAI / Anthropic Format)
      │
      ▼
Inbound Codec (OpenAICodec / AnthropicCodec)
      │
      ▼
Canonical AST (CanonicalChatRequest)
      │  (Validate & clamp against model_manifest.yaml)
      ▼
Outbound Adapter (BedrockConverseAdapter / GeminiAdapter)
      │
      ▼
SAP AI Core Backend Dispatch
```

---

## 4. Implementation Steps

1. **Manifest Loader (`config/manifest_loader.py`)**: Parse and validate `model_manifest.yaml` using Pydantic models.
2. **Canonical Models (`core/models/canonical.py`)**: Define neutral request and response data structures.
3. **Provider Adapters (`adapters/`)**: Implement adapters that translate canonical messages into vendor payloads.
4. **Integration**: Wire the adapter registry into `routers/chat.py` and `routers/messages.py`.
