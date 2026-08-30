# Streaming Server-Sent Events (SSE) Analysis & Specification

This document details Server-Sent Events (SSE) streaming protocols for OpenAI Chat Completions, Anthropic Messages API, and how the proxy transforms between them in real-time.

---

## 1. OpenAI Chat Completion SSE Format

OpenAI's streaming protocol sends sequential JSON chunks prefixed by `data: ` ending with `\n\n`. The stream is terminated with `data: [DONE]\n\n`.

### Stream Chunk Lifecycle

| Phase | Event / Payload Structure | Description |
|---|---|---|
| **1. Stream Init** | `data: {"id":"chatcmpl-...","choices":[{"index":0,"delta":{"role":"assistant","content":""}}]}` | Initial chunk establishing ID, model, and role |
| **2. Content Deltas** | `data: {"id":"chatcmpl-...","choices":[{"index":0,"delta":{"content":"Hello"}}]}` | Sequential token deltas |
| **3. Stream Final** | `data: {"id":"chatcmpl-...","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}` | Empty delta with finish reason |
| **4. Stream End** | `data: [DONE]` | Connection termination signal |

---

## 2. Anthropic Messages API SSE Format

Anthropic's streaming format uses named SSE events (`event: <type>\ndata: {...}\n\n`):

| Event Name | Purpose | Key Payload Fields |
|---|---|---|
| `message_start` | Initializes message metadata | `message.id`, `message.model`, `message.usage` |
| `content_block_start` | Signals a new content block | `index`, `content_block.type` (`text` or `thinking`) |
| `content_block_delta` | Delivers incremental text / thinking | `index`, `delta.type` (`text_delta`, `thinking_delta`), `delta.text` |
| `content_block_stop` | Signals completion of content block | `index` |
| `message_delta` | Reports stop reason & token delta | `delta.stop_reason`, `usage.output_tokens` |
| `message_stop` | Final stream completion marker | `{}` |

---

## 3. Real-Time Protocol Conversion

When transforming Anthropic / Bedrock event streams into OpenAI Chat Completion chunks:
1. **Initial Chunk**: On `message_start`, emit initial OpenAI chunk with `role: "assistant"`.
2. **Text Accumulation**: On `content_block_delta` (`text_delta`), map `delta.text` to `choices[0].delta.content`.
3. **Thinking Deltas**: Extended thinking deltas (`thinking_delta`) are handled or mapped based on client compatibility.
4. **Completion**: On `message_delta` or `message_stop`, emit the final chunk containing `finish_reason: "stop"` (or `"length"`), followed by `data: [DONE]\n\n`.
