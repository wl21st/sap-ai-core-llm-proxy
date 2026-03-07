# SAP AI Core LLM Proxy: Deep-Dive Technical Documentation

**Version:** 1.0  
**Last Updated:** 2026-01-19  
**Based on Commit:** f358537  
**Branch:** main

> **Audience:** Software engineers working on the SAP AI Core LLM Proxy project who need comprehensive understanding of architecture, streaming implementation, token caching, converters, and error handling.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Request Processing Pipeline](#request-processing-pipeline)
4. [Streaming Responses: SSE Implementation](#streaming-responses-sse-implementation)
5. [Token Caching Mechanism](#token-caching-mechanism)
6. [Format Converters: OpenAI ↔ Claude ↔ Gemini](#format-converters-openai--claude--gemini)
7. [Transform Pipeline: Request to Response](#transform-pipeline-request-to-response)
8. [Error Handling & Retry Logic](#error-handling--retry-logic)
9. [Load Balancing Strategy](#load-balancing-strategy)
10. [Performance Considerations](#performance-considerations)
11. [Best Practices & Common Patterns](#best-practices--common-patterns)
12. [Appendices](#appendices)

---

## Executive Summary

The SAP AI Core LLM Proxy is a Flask-based API gateway that transforms SAP AI Core APIs (Bedrock) into OpenAI/Anthropic-compatible endpoints. It handles:

- **Multi-model support**: Claude (3.5, 3.7, 4, 4.5), GPT-4, Gemini
- **Format translation**: Bidirectional conversion between OpenAI, Claude, and Gemini request/response formats
- **Streaming responses**: Server-sent events (SSE) with per-chunk format conversion
- **Token caching**: Thread-safe OAuth token management with 5-minute expiry buffer
- **Load balancing**: Round-robin across subaccounts and deployments
- **Robust error handling**: Conservative retry strategy for rate limits, auth error recovery

**Key Architecture Decision:** Centralized format conversion at gateway boundaries (request ingress, response egress) keeps converters isolated and testable.

---

## Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                         │
│  POST /v1/chat/completions (OpenAI format)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────▼──────────────┐
                │   Flask Route Handler     │
                │  (routers/chat.py)        │
                └────────────┬──────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
  ┌──────────┐      ┌──────────────┐      ┌────────────┐
  │ Verify   │      │ Model        │      │ Load       │
  │ Token    │      │ Detection    │      │ Balance   │
  │ (auth/)  │      │ (helpers)    │      │ (helpers) │
  └────┬─────┘      └──────┬───────┘      └─────┬──────┘
       │                   │                     │
       └───────────────────┼─────────────────────┘
                           │
              ┌────────────▼──────────────┐
              │ Transform 1: Request      │
              │ OpenAI → Model Format     │
              │ (proxy_helpers.py)        │
              └────────────┬──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   NON-STREAMING       STREAMING         ERROR
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐    ┌──────────┐
   │ Single  │      │ SSE Stream  │    │ Error    │
   │ Request │      │ Generator   │    │ Handler  │
   │ (Direct)│      │ (handlers/) │    │ (utils/) │
   └────┬────┘      └──────┬──────┘    └────┬─────┘
        │                  │                │
        └──────────────────┼────────────────┘
                           │
              ┌────────────▼──────────────┐
              │ SAP AI Core / Bedrock SDK │
              │ (Actual Model Inference)  │
              └────────────┬──────────────┘
                           │
              ┌────────────▼──────────────┐
              │ Transform 2: Response     │
              │ Model Format → OpenAI     │
              │ (proxy_helpers.py)        │
              └────────────┬──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   NON-STREAMING       STREAMING         ERROR
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐    ┌──────────┐
   │ JSON    │      │ SSE Chunks  │    │ SSE Data │
   │ Response│      │ (per-chunk) │    │ Chunks   │
   │ (200)   │      │ (SSE format)│    │ (errors) │
   └─────────┘      └─────────────┘    └──────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                ┌──────────▼────────────┐
                │  CLIENT RESPONSE      │
                │  OpenAI Format        │
                └───────────────────────┘
```

### File Structure

```
sap-ai-core-llm-proxy/
├── main.py (144 lines)
│   └─ FastAPI app factory, startup hooks
│
├── proxy_server.py (2563 lines) ⭐ PRIMARY
│   └─ Flask app, endpoints, orchestration
│
├── proxy_helpers.py (1786 lines) ⭐ CRITICAL
│   ├─ Detector class (model detection)
│   ├─ Converters (OpenAI ↔ Claude ↔ Gemini)
│   └─ Sanitization logic
│
├── auth/
│   ├─ token_manager.py (132 lines) ⭐ CRITICAL
│   │  └─ OAuth token caching + thread safety
│   └─ request_validator.py
│      └─ API token verification
│
├── handlers/
│   ├─ streaming_generators.py (1355 lines) ⭐ CRITICAL
│   │  └─ SSE chunk generation, per-chunk conversion
│   ├─ streaming_handler.py (274 lines)
│   │  └─ Backend request + streaming setup
│   ├─ model_handlers.py
│   │  └─ Model-specific response parsing
│   └─ bedrock_handler.py
│      └─ Bedrock SDK integration
│
├── routers/
│   ├─ chat.py (207 lines) ⭐ CRITICAL
│   │  └─ POST /v1/chat/completions endpoint
│   ├─ messages.py
│   │  └─ POST /v1/messages endpoint (Claude)
│   ├─ embeddings.py
│   │  └─ POST /v1/embeddings endpoint
│   └─ models.py
│      └─ GET /v1/models endpoint
│
├── utils/
│   ├─ retry.py (89 lines) ⭐ CRITICAL
│   │  └─ Retry logic (rate limits, exponential backoff)
│   ├─ auth_retry.py (23 lines)
│   │  └─ Auth retry configuration
│   ├─ error_handlers.py (57 lines)
│   │  └─ Error response formatting
│   ├─ logging_utils.py
│   │  └─ Structured logging setup
│   └─ sdk_pool.py
│      └─ SDK client caching + pooling
│
├── config/
│   └─ config_parser.py
│      └─ Pydantic models (ServiceKey, SubAccountConfig, ProxyConfig)
│
└── docs/
   ├─ PROXY_DEEP_DIVE.md (this file)
   ├─ ARCHITECTURE.md (high-level overview)
   ├─ TESTING.md (test patterns)
   └─ ... (other documentation)
```

**⭐ = Critical files for understanding this deep-dive**

---

## Request Processing Pipeline

### High-Level Flow

Every request follows this 8-stage pipeline:

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: Request Parsing & Validation                          │
│          - Extract headers, body, API token                     │
│          - Verify authorization token (verify_request_token)    │
└─────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Model Detection                                        │
│          - is_claude_37_or_4(model) → /converse endpoint        │
│          - is_claude_model(model) → /invoke endpoint            │
│          - is_gemini_model(model) → /generateContent endpoint   │
│          - Default: OpenAI GPT backend                          │
└─────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 3: Load Balancing                                         │
│          - Select subaccount (round-robin)                      │
│          - Select deployment URL (round-robin per subaccount)   │
│          - Fallback: normalized model name if exact match fails │
└─────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 4: Token Management                                       │
│          - Get cached token for subaccount (5-min buffer)       │
│          - If expired/invalid, fetch fresh OAuth token          │
│          - On 401/403, invalidate cache + retry once           │
└─────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 5: Request Transform (OpenAI → Model Format)             │
│          - Sanitize (remove cache_control, thinking, etc)      │
│          - Extract system message (if present)                  │
│          - Map parameters (max_tokens, temperature, etc)        │
│          - Convert message format                               │
└─────────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 6: Backend Request Execution                              │
│          - Send to SAP AI Core Bedrock SDK                      │
│          - Timeout: 10 minutes max                              │
│          - Retry on 429 (exponential backoff: 1s→16s)          │
└─────────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        ▼ STREAMING                           ▼ NON-STREAMING
┌──────────────────────┐          ┌────────────────────────────┐
│ STAGE 7a: SSE Stream │          │ STAGE 7b: Single Response  │
│ - Chunk generator    │          │ - Parse complete body      │
│ - Per-chunk convert  │          │ - Single transform         │
│ - Error as SSE data  │          │ - Error handling           │
└──────────────────────┘          └────────────────────────────┘
        │                                     │
        └──────────────────┬──────────────────┘
                           │
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 8: Response Transform (Model Format → OpenAI)            │
│          - Parse backend response                               │
│          - Extract text/content                                 │
│          - Extract tokens (prompt_tokens, completion_tokens)   │
│          - Map stop reasons                                     │
│          - Build OpenAI response structure                      │
└─────────────────────────────────────────────────────────────────┘
                           │
                    CLIENT RESPONSE
```

### Code Example: Request Entry Point

From `routers/chat.py` (207 lines):

```python
@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Union[StreamingResponse, JSONResponse]:
    """Main chat completions endpoint - OpenAI compatible."""
    logging.info("POST /v1/chat/completions")
    
    # STAGE 1: Validate request
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    verify_request_token(token)  # raises 401 if invalid
    
    # Parse body
    data = await request.json()
    model = data.get("model")
    stream = data.get("stream", False)
    
    # STAGE 2: Model detection
    if is_claude_37_or_4(model):
        endpoint = "/converse"
    elif is_claude_model(model):
        endpoint = "/invoke"
    elif is_gemini_model(model):
        endpoint = "/generateContent"
    else:
        endpoint = "/chat/completions"
    
    # STAGE 3: Load balancing
    subaccount, deployment_url = load_balance_url(model)
    
    # STAGE 4: Token management
    token_info = get_token(subaccount)  # cached, 5-min buffer
    
    # STAGE 5: Transform request
    backend_request = convert_openai_to_model_format(
        openai_request=data,
        model_type=endpoint,
        deployment_url=deployment_url
    )
    
    # STAGE 6: Backend request
    if stream:
        # STAGE 7a: SSE streaming
        return StreamingResponse(
            streaming_generator(backend_request, token_info, ...),
            media_type="text/event-stream"
        )
    else:
        # STAGE 7b: Single response
        response = await bedrock_sdk.invoke(
            deployment_url=deployment_url,
            request=backend_request,
            token=token_info.token,
            timeout=600  # 10 minutes
        )
        
        # STAGE 8: Transform response
        openai_response = convert_model_to_openai(response, model)
        return JSONResponse(openai_response, status_code=200)
```

---

## Streaming Responses: SSE Implementation

### Why SSE (Server-Sent Events)?

The proxy uses Server-Sent Events to:
1. **Enable real-time token streaming** - Client receives tokens as they arrive from Bedrock
2. **Support client cancellation** - Client can close connection mid-stream
3. **Allow per-chunk format conversion** - Each SSE chunk is converted independently
4. **Emit errors safely** - Once HTTP 200 is sent, errors must be sent as SSE data chunks (can't change status code)

### SSE Frame Format

Each chunk sent to the client follows this exact format:

```
event: chat.completion.chunk
data: {"choices":[{"delta":{"content":"token"},...}]}

event: chat.completion.chunk
data: {"choices":[{"delta":{"finish_reason":"stop"},...}]}

event: [DONE]
data: {"model":"claude-3-7-sonnet","usage":{"prompt_tokens":150,"completion_tokens":45}}
```

**Format Requirements:**
- `event: chat.completion.chunk` - Event type (OpenAI standard)
- `data: {...}` - JSON payload
- Blank line between chunks (important: `\n\n`)
- Final frame: `event: [DONE]` with full metadata
- No other headers after first `event: chat.completion.chunk`

### Complete Streaming Flow

From `handlers/streaming_generators.py` (1355 lines):

```python
async def streaming_generator(
    backend_request: dict,
    token_info: TokenInfo,
    deployment_url: str,
    model: str,
    stream: bool,
    request_id: str,
    logger: logging.Logger
) -> AsyncGenerator[str, None]:
    """
    SSE generator that:
    1. Sends request to Bedrock
    2. Streams response chunks
    3. Converts each chunk from model format to OpenAI format
    4. Emits as SSE frames
    5. Handles errors as SSE data chunks
    """
    
    request_id = str(uuid.uuid4())
    created_timestamp = int(time.time())
    
    try:
        # Get SDK client
        client = get_or_create_bedrock_client(deployment_url)
        
        # Determine endpoint based on model
        if is_claude_37_or_4(model):
            response_stream = await client.converse_stream(
                **backend_request,
                authorization=token_info.token
            )
        elif is_claude_model(model):
            response_stream = await client.invoke_with_response_stream(
                **backend_request,
                authorization=token_info.token
            )
        else:  # Gemini
            response_stream = await client.generate_content_stream(
                **backend_request,
                authorization=token_info.token
            )
        
        # Initialize state for streaming
        finish_reason = None
        prompt_tokens = 0
        completion_tokens = 0
        full_text = ""
        
        # STREAM CHUNKS FROM BACKEND
        async for chunk in response_stream:
            
            # PARSE CHUNK (model-specific parsing)
            if is_claude_37_or_4(model):
                parsed = parse_claude37_stream_chunk(chunk)
            elif is_claude_model(model):
                parsed = parse_claude_stream_chunk(chunk)
            else:  # Gemini
                parsed = parse_gemini_stream_chunk(chunk)
            
            # Extract content
            if parsed.get("type") == "content_block_delta":
                delta_text = parsed.get("delta", {}).get("text", "")
                full_text += delta_text
                completion_tokens += len(delta_text.split())
                
                # CONVERT TO OPENAI FORMAT
                sse_chunk = {
                    "id": f"chatcmpl-{request_id}",
                    "object": "chat.completion.chunk",
                    "created": created_timestamp,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "role": "assistant",
                                "content": delta_text
                            },
                            "finish_reason": None
                        }
                    ]
                }
                
                # EMIT SSE FRAME
                yield f"event: chat.completion.chunk\n"
                yield f"data: {json.dumps(sse_chunk)}\n\n"
            
            # EXTRACT FINISH REASON
            elif parsed.get("type") == "message_stop":
                finish_reason = map_stop_reason(
                    parsed.get("message", {}).get("stop_reason")
                )
            
            # EXTRACT TOKENS (if in metadata chunk)
            elif parsed.get("type") == "message_start":
                usage = parsed.get("message", {}).get("usage", {})
                prompt_tokens = usage.get("input_tokens", 0)
        
        # FINAL FRAME WITH METADATA
        final_chunk = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": created_timestamp,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": finish_reason
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }
        
        # Emit final chunk
        yield f"event: [DONE]\n"
        yield f"data: {json.dumps(final_chunk)}\n\n"
        
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        
        # EMIT ERROR AS SSE DATA CHUNK (status already sent, can't use 500)
        error_chunk = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [],
            "error": {
                "type": "server_error",
                "message": str(e)
            }
        }
        
        yield f"event: chat.completion.chunk\n"
        yield f"data: {json.dumps(error_chunk)}\n\n"
```

### Chunk Parsing by Model Type

#### Claude 3.7/4 Stream Chunks

Claude 3.7 sends chunks with this structure:

```python
# Content chunk
{
    "type": "content_block_delta",
    "index": 0,
    "delta": {
        "type": "text_delta",
        "text": "The answer is "
    }
}

# Message start (includes token info)
{
    "type": "message_start",
    "message": {
        "id": "msg_...",
        "type": "message",
        "role": "assistant",
        "content": [...],
        "usage": {
            "input_tokens": 150,
            "output_tokens": 0
        }
    }
}

# Message stop
{
    "type": "message_stop",
    "message": {
        "id": "msg_...",
        "type": "message",
        "role": "assistant",
        "content": [...],
        "stop_reason": "end_turn",
        "stop_sequence": null,
        "usage": {
            "input_tokens": 150,
            "output_tokens": 45
        }
    }
}
```

**Parsing Code** (`handlers/streaming_generators.py`):

```python
def parse_claude37_stream_chunk(chunk: dict) -> dict:
    """Parse Claude 3.7 stream chunk."""
    chunk_type = chunk.get("type")
    
    if chunk_type == "content_block_delta":
        return {
            "type": "content_block_delta",
            "delta": {
                "text": chunk.get("delta", {}).get("text", "")
            }
        }
    
    elif chunk_type == "message_start":
        return {
            "type": "message_start",
            "message": chunk.get("message", {}),
            "usage": chunk.get("message", {}).get("usage", {})
        }
    
    elif chunk_type == "message_stop":
        return {
            "type": "message_stop",
            "message": chunk.get("message", {}),
            "stop_reason": chunk.get("message", {}).get("stop_reason")
        }
    
    return chunk
```

#### Gemini Stream Chunks

Gemini sends chunks with different structure:

```python
{
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": "The answer is "
                    }
                ],
                "role": "model"
            },
            "finishReason": "STOP",
            "index": 0
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 150,
        "candidatesTokenCount": 45
    }
}
```

**Parsing Code**:

```python
def parse_gemini_stream_chunk(chunk: dict) -> dict:
    """Parse Gemini stream chunk."""
    
    # Extract text from parts
    candidates = chunk.get("candidates", [])
    if candidates:
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        
        return {
            "type": "content_block_delta",
            "delta": {"text": text},
            "finish_reason": candidate.get("finishReason")
        }
    
    # Extract token counts from metadata
    usage = chunk.get("usageMetadata", {})
    return {
        "type": "usage_metadata",
        "prompt_tokens": usage.get("promptTokenCount", 0),
        "completion_tokens": usage.get("candidatesTokenCount", 0)
    }
```

#### Claude 3.5 and Earlier Stream Chunks

Older Claude models use different streaming format:

```python
{
    "type": "content_block_start",
    "index": 0,
    "content_block": {
        "type": "text"
    }
}

{
    "type": "content_block_delta",
    "index": 0,
    "delta": {
        "type": "text_delta",
        "text": "The answer is "
    }
}

{
    "type": "message_stop",
    "message": {
        "id": "msg_...",
        "type": "message",
        "role": "assistant",
        "content": [...],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 150,
            "output_tokens": 45
        }
    }
}
```

**Parsing Code**:

```python
def parse_claude_stream_chunk(chunk: dict) -> dict:
    """Parse Claude 3.5 and earlier stream chunk."""
    chunk_type = chunk.get("type")
    
    if chunk_type == "content_block_delta":
        return {
            "type": "content_block_delta",
            "delta": {
                "text": chunk.get("delta", {}).get("text", "")
            }
        }
    
    elif chunk_type == "message_stop":
        message = chunk.get("message", {})
        return {
            "type": "message_stop",
            "stop_reason": message.get("stop_reason"),
            "usage": message.get("usage", {})
        }
    
    return chunk
```

### Stop Reason Mapping

Different models use different stop reason values. The proxy maps them all to OpenAI format:

```python
def map_stop_reason(backend_stop_reason: str) -> str:
    """Map backend stop reason to OpenAI format."""
    mapping = {
        # Claude
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        
        # Gemini
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "FINISH_REASON_UNSPECIFIED": "stop",
        
        # OpenAI (already correct)
        "stop": "stop",
        "length": "length",
        "function_call": "function_call",
        "tool_calls": "tool_calls",
        "content_filter": "content_filter",
    }
    
    return mapping.get(backend_stop_reason, "stop")
```

**Reference Table:**

| Backend | Stop Reason | OpenAI Equivalent | Meaning |
|---------|-------------|-------------------|---------|
| Claude | `end_turn` | `stop` | Natural response end |
| Claude | `max_tokens` | `length` | Hit token limit |
| Claude | `stop_sequence` | `stop` | Hit custom stop sequence |
| Gemini | `STOP` | `stop` | Natural response end |
| Gemini | `MAX_TOKENS` | `length` | Hit token limit |
| OpenAI | `stop` | `stop` | Natural response end |
| OpenAI | `length` | `length` | Hit token limit |

---

## Token Caching Mechanism

### Problem: Why Cache Tokens?

OAuth tokens from SAP AI Core have:
- **Typical lifespan**: 3600 seconds (1 hour)
- **Risk**: Without caching, every request would require fetching a fresh token (network overhead + latency)
- **Token expiry in flight**: If a request is in-flight when token expires, it fails mid-stream

### Solution: 5-Minute Buffer Strategy

The proxy caches tokens but **invalidates them 5 minutes before actual expiry**:

```
Token Lifecycle Example:
┌────────────────────────────────────────────────────────┐
│                                                        │
│ 12:00:00 - Token fetched (expires at 13:00:00)       │
│           Cache: valid, expires at 13:00:00          │
│                                                        │
│ 12:10:00 - Request 1: use cached token (valid)       │
│           Cache: still valid, expires at 13:00:00    │
│                                                        │
│ 12:50:00 - Request 2: use cached token (valid)       │
│           Cache: still valid, expires at 13:00:00    │
│                                                        │
│ 12:55:00 - Request 3: cache expires ⚠️               │
│           5-min buffer: fetch fresh token NOW        │
│           New token: expires at 14:00:00             │
│           Cache: valid, expires at 14:00:00          │
│                                                        │
│ 12:55:30 - Request 4: use fresh cached token        │
│           Cache: valid, expires at 14:00:00         │
│                                                        │
│ 13:00:00 - Old token would have expired (not used)   │
│           But we fetched fresh at 12:55:00           │
│           No mid-flight expiry! ✓                     │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Key insight**: By refreshing at `12:55:00` (5 minutes early), we guarantee that:
1. If request 3 completes by `13:00:00`, it uses the fresh token
2. If a long-running request started at `12:57:00` completes at `13:05:00`, it still uses fresh token
3. No race condition where token expires mid-request

### Implementation: TokenManager

From `auth/token_manager.py` (132 lines):

```python
from threading import Lock
from datetime import datetime, timedelta
from pydantic import BaseModel

class TokenInfo(BaseModel):
    """Cached token information."""
    token: str
    expires_at: datetime  # Absolute expiry timestamp from OAuth provider
    
    def is_expired(self) -> bool:
        """Check if token expired (without 5-min buffer)."""
        return datetime.now() >= self.expires_at
    
    def needs_refresh(self, buffer_seconds: int = 300) -> bool:
        """Check if token needs refresh (with 5-min buffer)."""
        refresh_at = self.expires_at - timedelta(seconds=buffer_seconds)
        return datetime.now() >= refresh_at


class TokenManager:
    """Thread-safe OAuth token cache per subaccount."""
    
    def __init__(self):
        self._tokens: dict[str, TokenInfo] = {}  # key: subaccount_name
        self._lock = Lock()  # Protects _tokens dict
    
    def get_token(self, subaccount_name: str, fetch_fn) -> TokenInfo:
        """
        Get cached token or fetch fresh one.
        
        Args:
            subaccount_name: Name of subaccount (e.g., "prod", "dev")
            fetch_fn: Callable that fetches fresh token from OAuth endpoint
        
        Returns:
            TokenInfo with valid token
        
        Thread-safe: Uses lock to prevent race conditions
        """
        
        # CRITICAL SECTION 1: Check cache without blocking
        with self._lock:
            cached = self._tokens.get(subaccount_name)
            
            # Token exists and not expired (with 5-min buffer)
            if cached and not cached.needs_refresh():
                logging.info(
                    f"Using cached token for {subaccount_name}",
                    extra={"expires_in_seconds": (cached.expires_at - datetime.now()).total_seconds()}
                )
                return cached
            
            # Token missing or needs refresh - must fetch
            if cached:
                logging.info(
                    f"Token refresh needed for {subaccount_name} "
                    f"(expires in {(cached.expires_at - datetime.now()).total_seconds()}s)"
                )
        
        # FETCH NEW TOKEN (outside lock to avoid blocking)
        logging.info(f"Fetching fresh token for {subaccount_name}")
        try:
            fresh_token = fetch_fn(subaccount_name)
        except Exception as e:
            logging.error(f"Token fetch failed for {subaccount_name}: {e}")
            raise
        
        # CRITICAL SECTION 2: Update cache
        with self._lock:
            self._tokens[subaccount_name] = fresh_token
            logging.info(
                f"Cached fresh token for {subaccount_name}",
                extra={"expires_in_seconds": (fresh_token.expires_at - datetime.now()).total_seconds()}
            )
            return fresh_token
    
    def invalidate_token(self, subaccount_name: str):
        """
        Invalidate cached token (on 401/403 error).
        Forces fresh fetch on next request.
        """
        with self._lock:
            if subaccount_name in self._tokens:
                del self._tokens[subaccount_name]
                logging.warning(f"Invalidated token for {subaccount_name}")


# Global instance
_token_manager = TokenManager()


def get_token(subaccount_name: str) -> TokenInfo:
    """
    Get token for subaccount with 5-minute refresh buffer.
    
    Usage:
        token_info = get_token("prod")
        print(token_info.token)  # "Bearer eyJ0eX..."
    """
    
    def fetch_oauth_token(account: str) -> TokenInfo:
        """Fetch fresh token from SAP AI Core OAuth endpoint."""
        config = load_proxy_config()
        subaccount_config = config.subaccounts[account]
        
        # Call SAP AI Core OAuth endpoint
        oauth_response = requests.post(
            url=subaccount_config.oauth_url,
            data={
                "client_id": subaccount_config.client_id,
                "client_secret": subaccount_config.client_secret,
                "grant_type": "client_credentials"
            },
            timeout=10
        )
        
        if oauth_response.status_code != 200:
            raise Exception(f"OAuth fetch failed: {oauth_response.status_code}")
        
        data = oauth_response.json()
        
        # Calculate absolute expiry time
        expires_in = data.get("expires_in", 3600)  # seconds
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        return TokenInfo(
            token=data["access_token"],
            expires_at=expires_at
        )
    
    return _token_manager.get_token(subaccount_name, fetch_oauth_token)


def invalidate_token(subaccount_name: str):
    """
    Invalidate token cache (on auth errors).
    Called when request returns 401 or 403.
    """
    _token_manager.invalidate_token(subaccount_name)
```

### Thread Safety Analysis

#### Race Condition Scenario (WITHOUT proper locking)

```
Time    Thread 1                          Thread 2
────────────────────────────────────────────────────
12:50   Check cache for "prod"            
        Cache: Valid, expires 13:00
        Return cached token
                                          Check cache for "prod"
                                          Cache: Still valid!
12:51                                     Return cached token
12:55   Check cache for "prod"
        Cache: needs_refresh = True
        Fetch new token (takes 1s)
        <Token fetch in progress>
                                          Check cache for "prod"
                                          Cache still has old token!
                                          Return old token
12:56   Update cache with new token
        Set cache["prod"] = fresh_token
                                          <Old token reaches expiry>
                                          Request fails with 401!
```

**Problem**: Thread 2 sees the cache decision before Thread 1 updates it.

#### Solution: Locking at Critical Sections

```python
def get_token(subaccount_name: str) -> TokenInfo:
    
    # CRITICAL SECTION 1: Atomic read + decide
    with self._lock:  # ← Lock ACQUIRED
        cached = self._tokens.get(subaccount_name)
        if cached and not cached.needs_refresh():
            return cached  # Both threads CANNOT reach here simultaneously
    # Lock RELEASED here ← Fetch can happen concurrently
    
    # Fetch token (may take 1 second, but lock is released)
    fresh_token = fetch_oauth_token(subaccount_name)
    
    # CRITICAL SECTION 2: Atomic update
    with self._lock:  # ← Lock ACQUIRED again
        self._tokens[subaccount_name] = fresh_token
    # Lock RELEASED
    
    return fresh_token
```

**Why this works:**
- **Mutual exclusion**: Only one thread can read cache at a time
- **Double-check pattern**: Second thread sees updated cache after first thread fetches
- **Non-blocking fetch**: Fetch happens outside lock (prevents thread starvation)

#### Verification: Same scenario WITH locking

```
Time    Thread 1                          Thread 2
────────────────────────────────────────────────────
12:50   [LOCK] get_token("prod")         
        Cache: valid
        [RELEASE]
        Return token A
                                          [LOCK] get_token("prod")
                                          Cache: valid
                                          [RELEASE]
                                          Return token A
12:55   [LOCK] get_token("prod")
        Cache: needs_refresh = True
        [RELEASE]
        Fetch new token (1s)
                                          [WAIT] get_token("prod")
                                          [Thread 2 blocks on lock]
12:56   [LOCK] Update cache
        cache["prod"] = token B
        [RELEASE]
        Return token B
                                          [LOCK ACQUIRED finally]
                                          Cache: UPDATED! needs_refresh = False
                                          [RELEASE]
                                          Return token B (fresh!)
        
Result: Both threads get token B ✓
```

---

## Format Converters: OpenAI ↔ Claude ↔ Gemini

### Converter Architecture

```
OpenAI Format (canonical)
        ↓
    Sanitize
        ↓
    Model Converters
        ├─ OpenAI → Claude 3.7/4 (/converse)
        ├─ OpenAI → Claude 3.5 (/invoke)
        └─ OpenAI → Gemini (/generateContent)
        ↓
    Backend Request (model-specific)
        ↓
    Response Parsing
        ├─ Claude 3.7/4 → OpenAI
        ├─ Claude 3.5 → OpenAI
        └─ Gemini → OpenAI
        ↓
    OpenAI Format (canonical)
```

### OpenAI Request Format (Input)

All client requests come in OpenAI format:

```python
{
    "model": "claude-3-7-sonnet",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "What is 2+2?"
        }
    ],
    "temperature": 0.7,
    "max_tokens": 1000,
    "top_p": 0.9,
    "stop": ["END"],
    "stream": False
}
```

### Step 1: Sanitization

**Why**: Claude-specific fields must be removed before sending to SAP AI Core.

**What to remove**:
- `cache_control` - Anthropic prompt caching (not supported in SAP AI)
- `thinking` - Claude's extended thinking (not universally supported)
- `budget_tokens` - Thinking budget (not supported)
- `betas` - Anthropic beta features
- Any other Anthropic-native extensions

**Code** (`proxy_helpers.py`):

```python
def sanitize_request_for_backend(openai_request: dict) -> dict:
    """
    Remove Anthropic-specific fields that SAP AI Core won't understand.
    Creates a copy; original unchanged.
    """
    # Shallow copy
    sanitized = openai_request.copy()
    
    # Remove Anthropic-specific top-level fields
    anthropic_fields = [
        "cache_control",
        "thinking",
        "budget_tokens",
        "betas",
        "metadata"  # Anthropic metadata extension
    ]
    for field in anthropic_fields:
        sanitized.pop(field, None)
    
    # Remove system prompt fields from messages
    # (Claude uses separate system parameter, not role=system)
    if "messages" in sanitized:
        messages = sanitized["messages"]
        sanitized["messages"] = [
            {k: v for k, v in msg.items() 
             if k not in ["cache_control", "thinking"]}
            for msg in messages
        ]
    
    return sanitized
```

### Step 2: OpenAI → Claude 3.7/4 Converter

Claude 3.7 and 4 use the `/converse` endpoint with a different message format.

#### Key Differences

| Aspect | OpenAI | Claude 3.7+ |
|--------|--------|------------|
| System prompt | Role `"system"` in messages | Top-level `"system"` parameter |
| User message | Role `"user"` | Role `"user"` |
| Assistant message | Role `"assistant"` | Role `"assistant"` |
| Content type | `"content"` (string) | `"content"` (list of blocks) |
| Content blocks | N/A | `[{"type": "text", "text": "..."}]` |
| Stop sequences | `"stop"` (string or list) | `"stopSequences"` (list only) |
| Max tokens | `"max_tokens"` (int) | `"maxTokens"` (int) |
| Temperature | `"temperature"` (float, 0-1) | `"temperature"` (float, 0-1) |
| Top P | `"top_p"` (float) | `"topP"` (float) |

#### Conversion Process

From `proxy_helpers.py`:

```python
def convert_openai_to_claude37(openai_request: dict) -> dict:
    """
    Convert OpenAI format to Claude 3.7 /converse format.
    
    Example:
        Input (OpenAI):
            {
                "model": "claude-3-7-sonnet",
                "messages": [
                    {"role": "system", "content": "Be helpful"},
                    {"role": "user", "content": "Hello"}
                ],
                "max_tokens": 1000,
                "temperature": 0.7,
                "stop": ["END"]
            }
        
        Output (Claude 3.7):
            {
                "modelId": "claude-3-7-sonnet",
                "system": "Be helpful",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Hello"}]
                    }
                ],
                "maxTokens": 1000,
                "temperature": 0.7,
                "stopSequences": ["END"]
            }
    """
    
    # STEP 1: Extract system message from messages array
    messages = openai_request.get("messages", [])
    system_message = None
    user_messages = []
    
    for msg in messages:
        if msg.get("role") == "system":
            # Extract system content
            system_message = msg.get("content", "")
        else:
            # Keep non-system messages
            user_messages.append(msg)
    
    # STEP 2: Convert message format (string → list of text blocks)
    converted_messages = []
    for msg in user_messages:
        role = msg.get("role")
        content = msg.get("content", "")
        
        # Convert string content to text blocks
        if isinstance(content, str):
            text_blocks = [{"type": "text", "text": content}]
        else:
            # Already list of blocks (tool results, etc)
            text_blocks = content
        
        converted_messages.append({
            "role": role,
            "content": text_blocks
        })
    
    # STEP 3: Build Claude request
    claude_request = {
        "modelId": openai_request.get("model"),
        "messages": converted_messages,
    }
    
    # STEP 4: Add system message (top-level, not in messages)
    if system_message:
        claude_request["system"] = system_message
    
    # STEP 5: Map parameters
    if "max_tokens" in openai_request:
        claude_request["maxTokens"] = openai_request["max_tokens"]
    
    if "temperature" in openai_request:
        claude_request["temperature"] = openai_request["temperature"]
    
    if "top_p" in openai_request:
        claude_request["topP"] = openai_request["top_p"]
    
    # STEP 6: Convert stop sequences (string → list)
    if "stop" in openai_request:
        stop = openai_request["stop"]
        if isinstance(stop, str):
            claude_request["stopSequences"] = [stop]
        else:
            claude_request["stopSequences"] = stop
    
    return claude_request
```

#### Example: Input → Output

```json
// INPUT (OpenAI format)
{
  "model": "claude-3-7-sonnet",
  "messages": [
    {
      "role": "system",
      "content": "You are a Python expert. Always use best practices."
    },
    {
      "role": "user",
      "content": "Write a function to check if a number is prime."
    },
    {
      "role": "assistant",
      "content": "Here's a prime checker:\n\ndef is_prime(n):\n    if n < 2:\n        return False\n    ..."
    },
    {
      "role": "user",
      "content": "Make it more efficient."
    }
  ],
  "temperature": 0.5,
  "max_tokens": 2000,
  "top_p": 0.9,
  "stop": ["---END---"]
}

// OUTPUT (Claude 3.7 format)
{
  "modelId": "claude-3-7-sonnet",
  "system": "You are a Python expert. Always use best practices.",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Write a function to check if a number is prime."
        }
      ]
    },
    {
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "Here's a prime checker:\n\ndef is_prime(n):\n    if n < 2:\n        return False\n    ..."
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Make it more efficient."
        }
      ]
    }
  ],
  "temperature": 0.5,
  "maxTokens": 2000,
  "topP": 0.9,
  "stopSequences": ["---END---"]
}
```

### Step 3: Claude 3.7 → OpenAI Response Converter

Claude 3.7 response format is very different. Must convert back to OpenAI.

#### Claude 3.7 Response Format

```python
{
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Here's a more efficient prime checker:\n\ndef is_prime(n):\n    if n <= 1:\n        return False\n    if n <= 3:\n        return True\n    if n % 2 == 0 or n % 3 == 0:\n        return False\n    i = 5\n    while i * i <= n:\n        if n % i == 0 or n % (i + 2) == 0:\n            return False\n        i += 6\n    return True"
                }
            ]
        }
    },
    "usage": {
        "inputTokens": 187,
        "outputTokens": 128
    },
    "stopReason": "endTurn"
}
```

#### Conversion Code

From `proxy_helpers.py`:

```python
def convert_claude37_to_openai(
    claude_response: dict,
    model: str,
    request_id: str
) -> dict:
    """
    Convert Claude 3.7 response to OpenAI format.
    
    Handles:
    - Extracting text from nested content blocks
    - Stop reason mapping (endTurn → stop)
    - Token counting
    - Response structure building
    """
    
    try:
        # STEP 1: Extract message from Claude response
        message = claude_response.get("output", {}).get("message", {})
        
        if not message:
            raise ValueError("No message in Claude response")
        
        # STEP 2: Extract text from content blocks
        content_blocks = message.get("content", [])
        text_content = ""
        
        for block in content_blocks:
            if block.get("type") == "text":
                text_content += block.get("text", "")
        
        if not text_content:
            # Fallback: try to find text anywhere
            text_content = _search_for_text_in_response(claude_response)
        
        # STEP 3: Extract token counts
        usage = claude_response.get("usage", {})
        prompt_tokens = usage.get("inputTokens", 0)
        completion_tokens = usage.get("outputTokens", 0)
        
        # STEP 4: Map stop reason
        claude_stop_reason = claude_response.get("stopReason", "endTurn")
        openai_stop_reason = map_stop_reason(claude_stop_reason)
        
        # STEP 5: Extract cache tokens (if present)
        cache_tokens = 0
        if "usage" in claude_response:
            cache_tokens = usage.get("cacheCreationInputTokens", 0)
        
        # STEP 6: Build OpenAI response
        openai_response = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text_content
                    },
                    "finish_reason": openai_stop_reason,
                    "logprobs": None
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "prompt_tokens_details": {
                    "cached_tokens": cache_tokens
                } if cache_tokens > 0 else None,
                "completion_tokens_details": None
            }
        }
        
        # Remove None values
        if openai_response["usage"]["prompt_tokens_details"] is None:
            del openai_response["usage"]["prompt_tokens_details"]
        
        return openai_response
    
    except Exception as e:
        logging.error(f"Claude→OpenAI conversion failed: {e}", exc_info=True)
        raise


def _search_for_text_in_response(response: dict) -> str:
    """
    Fallback: Search entire response for first text block.
    Used if response structure is unexpected.
    """
    def search_recursive(obj):
        if isinstance(obj, dict):
            if obj.get("type") == "text" and "text" in obj:
                return obj["text"]
            for v in obj.values():
                result = search_recursive(v)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = search_recursive(item)
                if result:
                    return result
        return None
    
    return search_recursive(response) or ""
```

#### Example: Claude Response → OpenAI

```json
// Claude 3.7 Response
{
  "output": {
    "message": {
      "role": "assistant",
      "content": [
        {
          "type": "text",
          "text": "Here's a more efficient prime checker..."
        }
      ]
    }
  },
  "usage": {
    "inputTokens": 187,
    "outputTokens": 128,
    "cacheCreationInputTokens": 0
  },
  "stopReason": "endTurn"
}

// ↓ convert_claude37_to_openai()

// OpenAI Format
{
  "id": "chatcmpl-12345...",
  "object": "chat.completion",
  "created": 1705699200,
  "model": "claude-3-7-sonnet",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Here's a more efficient prime checker..."
      },
      "finish_reason": "stop",
      "logprobs": null
    }
  ],
  "usage": {
    "prompt_tokens": 187,
    "completion_tokens": 128,
    "total_tokens": 315
  }
}
```

### Converter Matrix: All Supported Models

| Model | Endpoint | Request Converter | Response Converter | Special Notes |
|-------|----------|-------------------|-------------------|---------------|
| claude-3-7-sonnet | /converse | OpenAI → Claude 3.7 | Claude 3.7 → OpenAI | Token caching support |
| claude-3-7-haiku | /converse | OpenAI → Claude 3.7 | Claude 3.7 → OpenAI | Same as sonnet |
| claude-4-opus | /converse | OpenAI → Claude 3.7 | Claude 3.7 → OpenAI | Latest Claude API |
| claude-4.5-sonnet | /converse | OpenAI → Claude 3.7 | Claude 3.7 → OpenAI | Latest release |
| claude-3.5-sonnet | /invoke | OpenAI → Claude 3.5 | Claude 3.5 → OpenAI | Older streaming format |
| claude-3.5-haiku | /invoke | OpenAI → Claude 3.5 | Claude 3.5 → OpenAI | Same as sonnet |
| claude-3-opus | /invoke | OpenAI → Claude 3.5 | Claude 3.5 → OpenAI | Legacy endpoint |
| gemini-1.5-pro | /generateContent | OpenAI → Gemini | Gemini → OpenAI | Different param names |
| gemini-1.5-flash | /generateContent | OpenAI → Gemini | Gemini → OpenAI | Faster, cheaper model |
| gpt-4* | N/A | No conversion | No conversion | Pass-through (not Bedrock) |

---

## Transform Pipeline: Request to Response

### The 7-Stage Pipeline

```
1. REQUEST PARSING
   ↓
2. MODEL DETECTION
   ↓
3. LOAD BALANCING
   ↓
4. TOKEN MANAGEMENT
   ↓
5. REQUEST TRANSFORM (OpenAI → Model Format)
   ↓
6. BACKEND EXECUTION
   ↓
7. RESPONSE TRANSFORM (Model Format → OpenAI)
   ↓
CLIENT RESPONSE
```

### Complete Pipeline Example

Request from client:

```json
{
  "model": "claude-3-7-sonnet",
  "messages": [
    {"role": "user", "content": "What is AI?"}
  ],
  "max_tokens": 500,
  "stream": false
}
```

#### Stage 1: Request Parsing

```python
# routers/chat.py

@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Parse headers
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    # Verify token
    verify_request_token(token)  # raises 401 if invalid
    
    # Parse body
    data = await request.json()
    
    # Validate required fields
    model = data.get("model")
    if not model:
        raise ValueError("model field required")
    
    messages = data.get("messages")
    if not messages:
        raise ValueError("messages field required")
    
    # Extract optional fields
    max_tokens = data.get("max_tokens")
    temperature = data.get("temperature", 0.7)
    stream = data.get("stream", False)
    
    # State after Stage 1
    request_state = {
        "model": "claude-3-7-sonnet",
        "messages": [...],
        "max_tokens": 500,
        "temperature": 0.7,
        "stream": False,
        "request_id": "req_abc123"
    }
```

#### Stage 2: Model Detection

```python
# proxy_helpers.py

def detect_model_endpoint(model: str) -> str:
    """Determine which Bedrock endpoint to use."""
    
    if is_claude_37_or_4(model):
        return "/converse"
    elif is_claude_model(model):
        return "/invoke"
    elif is_gemini_model(model):
        return "/generateContent"
    else:
        return "/chat/completions"

# Detection functions
def is_claude_37_or_4(model: str) -> bool:
    """Check if model is Claude 3.7, 4, or 4.5."""
    return any(pattern in model.lower() for pattern in [
        "claude-3-7",
        "claude-4",
        "claude-4.5",
        "claude-4-opus",  # legacy name
    ])

def is_claude_model(model: str) -> bool:
    """Check if model is any Claude version."""
    return any(pattern in model.lower() for pattern in [
        "claude-",
        "anthropic-",
    ])

def is_gemini_model(model: str) -> bool:
    """Check if model is Gemini."""
    return "gemini" in model.lower()

# Stage 2 result
request_state["detected_endpoint"] = "/converse"
request_state["model_family"] = "claude"
```

#### Stage 3: Load Balancing

```python
# load_balancer.py

def load_balance_url(model: str) -> tuple[str, str]:
    """
    Select deployment URL using round-robin.
    
    Returns:
        (subaccount_name, deployment_url)
    """
    
    config = load_proxy_config()
    subaccounts = list(config.subaccounts.values())
    
    # Find matching subaccount for model
    matching_subaccounts = [
        sa for sa in subaccounts
        if model in sa.models
    ]
    
    if not matching_subaccounts:
        raise ValueError(f"No subaccount has model {model}")
    
    # Round-robin select subaccount
    selected_sa = matching_subaccounts[
        config.load_balance_counter % len(matching_subaccounts)
    ]
    config.load_balance_counter += 1
    
    # Round-robin select deployment in subaccount
    deployments = selected_sa.deployments
    selected_deployment = deployments[
        selected_sa.counter % len(deployments)
    ]
    selected_sa.counter += 1
    
    return selected_sa.name, selected_deployment.url

# Stage 3 result
request_state["subaccount"] = "prod"
request_state["deployment_url"] = "https://bedrock-prod.sap.ai/..."
```

#### Stage 4: Token Management

```python
# auth/token_manager.py + routers/chat.py

def get_token(subaccount_name: str) -> TokenInfo:
    """Get cached or fresh OAuth token."""
    # (see Token Caching section for full implementation)
    pass

token_info = get_token("prod")

# Stage 4 result
request_state["token"] = "Bearer eyJ0eX..."
request_state["token_expires_at"] = datetime(2026, 3, 6, 14, 0, 0)
```

#### Stage 5: Request Transform

```python
# proxy_helpers.py

def convert_openai_to_claude37(openai_request: dict) -> dict:
    """OpenAI → Claude 3.7 format conversion."""
    
    # Sanitize (remove anthropic-specific fields)
    sanitized = sanitize_request_for_backend(openai_request)
    
    # Extract system message
    messages = sanitized.get("messages", [])
    system_message = None
    user_messages = []
    
    for msg in messages:
        if msg.get("role") == "system":
            system_message = msg.get("content")
        else:
            user_messages.append(msg)
    
    # Convert message format
    converted_messages = []
    for msg in user_messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        
        converted_messages.append({
            "role": msg.get("role"),
            "content": content
        })
    
    # Build Claude request
    claude_request = {
        "modelId": sanitized.get("model"),
        "messages": converted_messages,
        "maxTokens": sanitized.get("max_tokens", 1000),
        "temperature": sanitized.get("temperature", 0.7),
        "topP": sanitized.get("top_p", 0.9),
    }
    
    if system_message:
        claude_request["system"] = system_message
    
    if "stop" in sanitized:
        stop = sanitized["stop"]
        claude_request["stopSequences"] = (
            [stop] if isinstance(stop, str) else stop
        )
    
    return claude_request

# Stage 5 result
transformed_request = {
    "modelId": "claude-3-7-sonnet",
    "system": None,
    "messages": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "What is AI?"}]
        }
    ],
    "maxTokens": 500,
    "temperature": 0.7,
    "topP": 0.9
}
```

#### Stage 6: Backend Execution

```python
# handlers/bedrock_handler.py

async def invoke_bedrock(
    deployment_url: str,
    request: dict,
    token: str,
    model: str,
    stream: bool
) -> dict:
    """Send request to Bedrock SDK."""
    
    client = get_or_create_bedrock_client(deployment_url)
    
    # Determine endpoint
    if is_claude_37_or_4(model):
        response = await client.converse(
            deployment_id=deployment_url,
            **transformed_request,
            authorization=token
        )
    elif is_claude_model(model):
        response = await client.invoke(
            deployment_id=deployment_url,
            **transformed_request,
            authorization=token
        )
    else:  # Gemini
        response = await client.generate_content(
            deployment_id=deployment_url,
            **transformed_request,
            authorization=token
        )
    
    return response

# Stage 6 result (from Bedrock)
bedrock_response = {
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Artificial Intelligence (AI) is..."
                }
            ]
        }
    },
    "usage": {
        "inputTokens": 10,
        "outputTokens": 87
    },
    "stopReason": "endTurn"
}
```

#### Stage 7: Response Transform

```python
# proxy_helpers.py

def convert_claude37_to_openai(
    claude_response: dict,
    model: str,
    request_id: str
) -> dict:
    """Claude 3.7 response → OpenAI format."""
    
    # Extract message
    message = claude_response.get("output", {}).get("message", {})
    
    # Extract text
    content_blocks = message.get("content", [])
    text = ""
    for block in content_blocks:
        if block.get("type") == "text":
            text += block.get("text", "")
    
    # Extract tokens
    usage = claude_response.get("usage", {})
    prompt_tokens = usage.get("inputTokens", 0)
    completion_tokens = usage.get("outputTokens", 0)
    
    # Map stop reason
    stop_reason = map_stop_reason(claude_response.get("stopReason"))
    
    # Build OpenAI response
    return {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text
                },
                "finish_reason": stop_reason,
                "logprobs": None
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    }

# Final result
openai_response = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1705699200,
    "model": "claude-3-7-sonnet",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Artificial Intelligence (AI) is..."
            },
            "finish_reason": "stop",
            "logprobs": null
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 87,
        "total_tokens": 97
    }
}
```

---

## Error Handling & Retry Logic

### Error Classification

Not all errors are recoverable. The proxy uses this decision tree:

```
┌─────────────────────────────────────┐
│ Error Occurs                        │
└─────────────┬───────────────────────┘
              │
        Is it 429 (Rate Limit)?
        ├─ YES → Exponential backoff (1s→16s) [see RETRY SECTION]
        └─ NO → Continue
                │
                Is it 401/403 (Auth Error)?
                ├─ YES → Invalidate cache, retry ONCE [see AUTH RETRY SECTION]
                └─ NO → Continue
                        │
                        Is it 5xx (Server Error)?
                        ├─ YES → Return error to client
                        └─ NO → Continue
                                │
                                Is it 4xx (Client Error)?
                                ├─ YES → Return error to client
                                └─ NO → Unknown error
                                        └─ Return error to client
```

### Rate Limit Retry (HTTP 429)

**Why 429 is special**: Rate limits are temporary. After waiting, the request will likely succeed.

#### Detection

From `utils/retry.py` (89 lines):

```python
def is_rate_limit_error(error_response: dict) -> bool:
    """
    Detect if error is a rate limit (429).
    Checks multiple indicators since different backends report differently.
    """
    
    # Check HTTP status
    if error_response.get("status_code") == 429:
        return True
    
    # Check for rate limit error codes
    error_code = error_response.get("error_code", "")
    rate_limit_codes = [
        "ThrottlingException",
        "TooManyRequestsException",
        "RateLimitError",
        "ServiceUnavailableException",
    ]
    if error_code in rate_limit_codes:
        return True
    
    # Check error message
    error_message = error_response.get("message", "").lower()
    rate_limit_patterns = [
        "too many tokens",
        "rate limit",
        "throttling",
        "429",
        "service unavailable"
    ]
    if any(pattern in error_message for pattern in rate_limit_patterns):
        return True
    
    return False
```

#### Exponential Backoff Strategy

From `utils/retry.py`:

```python
@bedrock_retry  # Decorator that implements retry logic
async def invoke_with_retry(
    bedrock_request: dict,
    deployment_url: str,
    token: str,
    logger: logging.Logger
) -> dict:
    """
    Invoke Bedrock with exponential backoff retry on 429.
    
    Retry schedule:
    - Attempt 1: Immediate
    - Attempt 2: Wait 1s → Attempt 2
    - Attempt 3: Wait 2s → Attempt 3
    - Attempt 4: Wait 4s → Attempt 4
    - Attempt 5: Wait 8s → Attempt 5
    - Attempt 6: Wait 16s → Attempt 6 (give up, return error)
    
    Total wait time: 1 + 2 + 4 + 8 + 16 = 31 seconds max
    """
    
    client = get_or_create_bedrock_client(deployment_url)
    
    # Decorator handles retries automatically
    response = await client.invoke(
        **bedrock_request,
        authorization=token
    )
    
    return response
```

#### Decorator Implementation

```python
# utils/retry.py

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception
)

def bedrock_retry(func):
    """
    Decorator that retries on 429 errors with exponential backoff.
    """
    
    def is_retryable(exception):
        """Determine if exception should trigger retry."""
        
        # Only retry on rate limit errors
        if hasattr(exception, 'response'):
            status = exception.response.status_code
            if status == 429:
                return True
        
        if hasattr(exception, 'error_code'):
            if exception.error_code in [
                "ThrottlingException",
                "TooManyRequestsException"
            ]:
                return True
        
        # Don't retry on other errors
        return False
    
    return retry(
        retry=retry_if_exception(is_retryable),
        stop=stop_after_attempt(6),  # Max 5 retries (6 attempts total)
        wait=wait_exponential(multiplier=1, min=1, max=16),
        reraise=True
    )(func)
```

#### Example: Retry in Action

```
Request sent (attempt 1)
  ↓
Response: 429 Too Many Requests
  ↓
Log: "Rate limited, retrying in 1s..."
Wait 1 second
  ↓
Request sent (attempt 2)
  ↓
Response: 429 Too Many Requests
  ↓
Log: "Rate limited, retrying in 2s..."
Wait 2 seconds
  ↓
Request sent (attempt 3)
  ↓
Response: 200 OK
  ↓
Success! Return response to client

Total time: ~3 seconds (much better than returning error immediately)
```

### Authentication Error Retry (401/403)

**Why auth errors are special**: Token cache may be stale. Refresh token once before giving up.

#### Detection

From `auth/request_validator.py`:

```python
def is_auth_error(response) -> bool:
    """Check if error is auth-related (401 or 403)."""
    return response.status_code in [401, 403]
```

#### Retry Strategy

From `routers/chat.py`:

```python
async def chat_completions(request: Request):
    """Chat endpoint with auth retry."""
    
    try:
        # Get token (may be cached)
        token_info = get_token(subaccount)
        
        # First attempt
        response = await bedrock_sdk.invoke(
            request=backend_request,
            token=token_info.token,
            authorization=f"Bearer {token_info.token}"
        )
        
        if response.status_code in [401, 403]:
            raise AuthError(f"Auth failed: {response.status_code}")
        
        return response
    
    except AuthError as e:
        logging.warning(f"Auth error: {e}, invalidating token and retrying")
        
        # INVALIDATE CACHE
        invalidate_token(subaccount)
        
        # FETCH FRESH TOKEN
        try:
            fresh_token = get_token(subaccount)
        except Exception as e:
            logging.error(f"Token refresh failed: {e}")
            raise
        
        # RETRY ONCE with fresh token
        try:
            response = await bedrock_sdk.invoke(
                request=backend_request,
                token=fresh_token.token,
                authorization=f"Bearer {fresh_token.token}"
            )
            return response
        except AuthError as e:
            logging.error(f"Auth failed again after token refresh: {e}")
            raise
```

**Important**: Only ONE retry (AUTH_RETRY_MAX = 1). If it fails twice, give up.

### Other Error Handling

#### Non-Streaming Errors

```python
# routers/chat.py (non-streaming path)

try:
    response = await bedrock_sdk.invoke(...)
    return JSONResponse(
        content=openai_response,
        status_code=200
    )

except AuthError as e:
    # 401/403 - retry with fresh token (see above)
    logging.error(f"Auth error: {e}")
    return JSONResponse(
        content={"error": {"message": str(e), "type": "auth_error"}},
        status_code=401
    )

except TimeoutError as e:
    # Request took > 10 minutes - give up
    logging.error(f"Timeout: {e}")
    return JSONResponse(
        content={"error": {"message": "Request timeout", "type": "timeout"}},
        status_code=504
    )

except ValueError as e:
    # Malformed request - client's fault
    logging.error(f"Invalid request: {e}")
    return JSONResponse(
        content={"error": {"message": str(e), "type": "invalid_request_error"}},
        status_code=400
    )

except Exception as e:
    # Unexpected error
    logging.error(f"Unexpected error: {e}", exc_info=True)
    return JSONResponse(
        content={"error": {"message": "Internal server error", "type": "server_error"}},
        status_code=500
    )
```

#### Streaming Errors

Streaming is trickier: once HTTP 200 is sent, we can't change the status code.

```python
# handlers/streaming_generators.py

async def streaming_generator(...) -> AsyncGenerator[str, None]:
    """SSE generator with error handling."""
    
    request_id = str(uuid.uuid4())
    
    try:
        # Get client and invoke
        response_stream = await bedrock_sdk.converse_stream(...)
        
        # Stream chunks
        async for chunk in response_stream:
            # Convert and emit
            sse_chunk = convert_chunk_to_openai(chunk)
            yield f"event: chat.completion.chunk\ndata: {json.dumps(sse_chunk)}\n\n"
    
    except AuthError as e:
        logging.error(f"Auth error in stream: {e}")
        
        # CAN'T CHANGE STATUS (200 already sent)
        # EMIT ERROR AS SSE DATA CHUNK instead
        error_chunk = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [],
            "error": {
                "type": "auth_error",
                "message": str(e)
            }
        }
        
        yield f"event: chat.completion.chunk\n"
        yield f"data: {json.dumps(error_chunk)}\n\n"
    
    except TimeoutError as e:
        logging.error(f"Timeout in stream: {e}")
        
        # Same approach: emit as SSE
        error_chunk = {
            "id": f"chatcmpl-{request_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [],
            "error": {
                "type": "timeout",
                "message": "Request timed out"
            }
        }
        
        yield f"event: chat.completion.chunk\n"
        yield f"data: {json.dumps(error_chunk)}\n\n"
```

---

## Load Balancing Strategy

### Round-Robin Across Subaccounts and Deployments

The proxy distributes load across:
1. Multiple subaccounts
2. Multiple deployment URLs within each subaccount

```
┌─────────────────────────────────────┐
│ Request for claude-3-7-sonnet       │
└────────────┬────────────────────────┘
             │
    ┌────────▼──────────┐
    │ Which subaccounts │
    │ have this model?  │
    │                   │
    │ [prod, dev, test] │
    └────────┬──────────┘
             │
    ┌────────▼──────────────────────────┐
    │ Round-robin select subaccount      │
    │                                    │
    │ counter = 5                        │
    │ 5 % 3 = 2 (index)                  │
    │ selected = dev                     │
    └────────┬──────────────────────────┘
             │
    ┌────────▼────────────────────────────────┐
    │ Which deployments in dev?               │
    │                                         │
    │ [https://bedrock1/..., https://bedrock2/...] │
    └────────┬────────────────────────────────┘
             │
    ┌────────▼──────────────────────────┐
    │ Round-robin select deployment      │
    │                                    │
    │ counter = 7                        │
    │ 7 % 2 = 1 (index)                  │
    │ selected = bedrock2                │
    └────────┬──────────────────────────┘
             │
    URL: https://bedrock2-dev.sap.ai/...
```

### Code Implementation

From `load_balancer.py`:

```python
def load_balance_url(model: str) -> tuple[str, str]:
    """
    Select deployment URL for model using round-robin.
    
    Args:
        model: Model name (e.g., "claude-3-7-sonnet")
    
    Returns:
        (subaccount_name, deployment_url)
    
    Raises:
        ValueError: If model not found in any subaccount
    """
    
    config = load_proxy_config()
    
    # STEP 1: Find all subaccounts that have this model
    matching_subaccounts = []
    for subaccount in config.subaccounts.values():
        if model in subaccount.models:
            matching_subaccounts.append(subaccount)
    
    if not matching_subaccounts:
        # Try normalized model name (claude-3-7 → claude-3-7-sonnet)
        matching_subaccounts = _find_by_normalized_model(model, config)
    
    if not matching_subaccounts:
        raise ValueError(f"Model {model} not found in any subaccount")
    
    # STEP 2: Round-robin select subaccount
    subaccount_index = config.load_balance_counter % len(matching_subaccounts)
    selected_subaccount = matching_subaccounts[subaccount_index]
    config.load_balance_counter += 1
    
    logging.info(
        f"Load balance: selected subaccount {selected_subaccount.name}",
        extra={"model": model, "subaccount_index": subaccount_index}
    )
    
    # STEP 3: Round-robin select deployment in subaccount
    deployments = selected_subaccount.deployments
    
    if not deployments:
        raise ValueError(
            f"Subaccount {selected_subaccount.name} has no deployments"
        )
    
    deployment_index = selected_subaccount.counter % len(deployments)
    selected_deployment = deployments[deployment_index]
    selected_subaccount.counter += 1
    
    logging.info(
        f"Load balance: selected deployment {selected_deployment.url}",
        extra={"model": model, "subaccount_name": selected_subaccount.name}
    )
    
    return selected_subaccount.name, selected_deployment.url


def _find_by_normalized_model(
    requested_model: str,
    config: ProxyConfig
) -> list[SubAccountConfig]:
    """
    Fallback: try to match by normalized model name.
    
    Examples:
        - "claude-3-7" matches "claude-3-7-sonnet" and "claude-3-7-haiku"
        - "claude-3.5-sonnet" matches both claude-3.5-sonnet-20240229 and claude-3.5-sonnet-20240620
    """
    
    # Normalize requested model
    normalized_request = normalize_model_name(requested_model)
    
    matching = []
    for subaccount in config.subaccounts.values():
        for model_name in subaccount.models:
            if normalize_model_name(model_name).startswith(normalized_request):
                matching.append(subaccount)
                break  # Only add subaccount once
    
    return matching


def normalize_model_name(model: str) -> str:
    """
    Normalize model name for matching.
    
    Examples:
        claude-3-7-sonnet-20240229 → claude-3-7-sonnet
        claude-3.5-sonnet-v2 → claude-3.5-sonnet
    """
    
    # Remove version suffixes
    model = model.lower()
    
    # Remove date suffixes (20240229)
    model = re.sub(r'-\d{8}$', '', model)
    
    # Remove version suffixes (v1, v2, etc)
    model = re.sub(r'-v\d+$', '', model)
    
    return model
```

### Configuration Example

```json
{
  "load_balance_counter": 0,
  "subaccounts": {
    "prod": {
      "name": "prod",
      "oauth_url": "https://prod.sap.ai/oauth/token",
      "client_id": "...",
      "client_secret": "...",
      "models": [
        "claude-3-7-sonnet",
        "claude-3-7-haiku",
        "claude-4-opus",
        "gemini-1.5-pro"
      ],
      "deployments": [
        {"url": "https://bedrock-prod-1.sap.ai/converse"},
        {"url": "https://bedrock-prod-2.sap.ai/converse"},
        {"url": "https://bedrock-prod-3.sap.ai/converse"}
      ],
      "counter": 0
    },
    "dev": {
      "name": "dev",
      "oauth_url": "https://dev.sap.ai/oauth/token",
      "client_id": "...",
      "client_secret": "...",
      "models": [
        "claude-3-7-sonnet",
        "claude-3.5-sonnet",
        "gemini-1.5-flash"
      ],
      "deployments": [
        {"url": "https://bedrock-dev-1.sap.ai/converse"}
      ],
      "counter": 0
    }
  }
}
```

---

## Performance Considerations

### Token Caching Savings

```
Scenario: 1000 requests in 1 hour, 3 subaccounts

WITHOUT caching:
  - 1000 requests × 3 subaccounts × 1 OAuth fetch = 3000 OAuth calls
  - Time: 3000 × 200ms = 600 seconds = 10 minutes wasted
  - Network: 3000 HTTP requests to OAuth endpoint
  
WITH caching (5-min buffer):
  - 1 hour / 5 min = 12 token refreshes per subaccount
  - 12 × 3 subaccounts = 36 OAuth calls
  - Time: 36 × 200ms = 7.2 seconds
  - Network: 36 HTTP requests
  
Savings: 600s → 7.2s (83x faster)
```

### Streaming Efficiency

```
Non-streaming (full response):
  - Wait for entire model response (~3-10 seconds)
  - Convert entire response
  - Send to client
  - Client waits for complete response
  
Streaming (per-chunk):
  - Model starts sending chunks immediately
  - Convert each chunk (~50ms per chunk)
  - Send to client as SSE
  - Client receives tokens in real-time (perceived as faster)
  - Token latency to first byte: ~500ms (instead of 5000ms)
```

### Load Balancing Fairness

```
Configuration:
  - 3 subaccounts × 2 deployments = 6 total endpoints
  - 600 requests

Distribution (with round-robin):
  ✓ Each endpoint receives 100 requests
  ✓ Load evenly distributed
  ✓ No single endpoint overloaded
```

### Memory Efficiency: SDK Client Caching

```python
# utils/sdk_pool.py

class BedrocClientPool:
    """Cache SDK clients (expensive to create)."""
    
    def __init__(self):
        self._clients: dict[str, ClientWrapper] = {}  # key: deployment_url
        self._lock = threading.Lock()
    
    def get_or_create(self, deployment_url: str) -> ClientWrapper:
        """
        Get cached client or create new one.
        
        Without caching:
          - 1000 requests = 1000 SDK client instantiations
          - Memory: 1000 × 50MB = 50GB
          - Time: 1000 × 100ms = 100 seconds startup
        
        With caching (6 deployments):
          - 1000 requests = 6 SDK client instantiations
          - Memory: 6 × 50MB = 300MB
          - Time: 6 × 100ms = 600ms startup
        """
        
        with self._lock:
            if deployment_url not in self._clients:
                logging.info(f"Creating SDK client for {deployment_url}")
                self._clients[deployment_url] = ClientWrapper(
                    api_endpoint=deployment_url
                )
            
            return self._clients[deployment_url]
```

---

## Best Practices & Common Patterns

### 1. Always Verify Tokens First

```python
# ✅ CORRECT
@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    verify_request_token(token)  # Verify FIRST
    
    # Only then process request
    data = await request.json()
    ...

# ❌ WRONG - don't process request before verifying token
@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    data = await request.json()  # Bad: unnecessary parsing
    
    token = request.headers.get("Authorization", "")
    verify_request_token(token)  # Late: security issue
    ...
```

### 2. Use Model Detection Functions

```python
# ✅ CORRECT
from proxy_helpers import is_claude_37_or_4, is_claude_model

if is_claude_37_or_4(model):
    endpoint = "/converse"
elif is_claude_model(model):
    endpoint = "/invoke"
else:
    endpoint = "/chat/completions"

# ❌ WRONG - hardcoded model checks
if "claude-4" in model or "claude-3-7" in model:
    endpoint = "/converse"
elif "claude" in model:  # Too broad
    endpoint = "/invoke"
```

### 3. Handle Tokens with 5-Minute Buffer

```python
# ✅ CORRECT - token manager handles buffer automatically
token_info = get_token(subaccount)  # 5-min buffer built-in
use_token = token_info.token

# ❌ WRONG - ignoring buffer
token_expires_at = datetime.now() + timedelta(hours=1)  # No buffer!
if datetime.now() > token_expires_at:  # Will expire mid-request
    fetch_new_token()
```

### 4. Retry Only on 429 (Rate Limit)

```python
# ✅ CORRECT - only retry rate limits
@bedrock_retry  # Decorator handles 429 with backoff
async def invoke(...):
    response = await bedrock_sdk.invoke(...)
    return response

# ❌ WRONG - retrying all errors
try:
    response = await bedrock_sdk.invoke(...)
except Exception:
    response = await bedrock_sdk.invoke(...)  # Retry EVERYTHING
```

### 5. Emit Streaming Errors as SSE Chunks

```python
# ✅ CORRECT - error as SSE data
async def streaming_generator(...):
    try:
        async for chunk in response_stream:
            yield format_as_sse(chunk)
    except Exception as e:
        # Status 200 already sent, emit error as data
        error_chunk = {"error": {"message": str(e)}}
        yield f"event: chat.completion.chunk\ndata: {json.dumps(error_chunk)}\n\n"

# ❌ WRONG - trying to send status code mid-stream
async def streaming_generator(...):
    try:
        async for chunk in response_stream:
            yield format_as_sse(chunk)
    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500  # Too late! Status already 200
        )
```

### 6. Sanitize Before Converting Requests

```python
# ✅ CORRECT - sanitize first
def convert_openai_to_claude(...):
    sanitized = sanitize_request_for_backend(openai_request)
    # Then convert...
    return claude_request

# ❌ WRONG - send unsanitized data to backend
def convert_openai_to_claude(...):
    # Converts with cache_control, thinking, etc. still present
    claude_request = {
        "messages": openai_request["messages"],  # Unsanitized!
        "cache_control": openai_request.get("cache_control"),  # Don't send!
    }
    return claude_request
```

### 7. Use Logging for Debugging

```python
# ✅ CORRECT - structured logging with context
logging.info(
    "Load balance: selected deployment",
    extra={
        "model": model,
        "subaccount": subaccount_name,
        "deployment_url": deployment_url,
        "request_id": request_id
    }
)

# ❌ WRONG - no context
logging.info(f"selected deployment {deployment_url}")
```

### 8. Cache SDK Clients per Deployment

```python
# ✅ CORRECT - reuse expensive client objects
pool = BedrocClientPool()
client = pool.get_or_create(deployment_url)  # Cached

# ❌ WRONG - creating new client every request
client = ClientWrapper(deployment_url)  # Expensive!
response = await client.invoke(...)
# Client discarded, next request creates new one
```

---

## Appendices

### A. Configuration Structure

```python
# Pydantic models from config/config_parser.py

class ServiceKey(BaseModel):
    """OAuth service account credentials."""
    oauth_url: str
    client_id: str
    client_secret: str

class DeploymentConfig(BaseModel):
    """Bedrock deployment endpoint."""
    url: str
    
class SubAccountConfig(BaseModel):
    """Configuration for a single SAP subaccount."""
    name: str
    oauth_url: str
    client_id: str
    client_secret: str
    models: list[str]  # e.g., ["claude-3-7-sonnet", "gemini-1.5-pro"]
    deployments: list[DeploymentConfig]
    counter: int = 0  # Round-robin counter

class ProxyConfig(BaseModel):
    """Entire proxy configuration."""
    subaccounts: dict[str, SubAccountConfig]
    load_balance_counter: int = 0
    log_level: str = "INFO"
    timeout_seconds: int = 600
```

### B. Stop Reason Mapping

| Backend Model | Stop Reason | OpenAI Equivalent | Meaning |
|---------------|-------------|-------------------|---------|
| Claude | `end_turn` | `stop` | Response complete |
| Claude | `max_tokens` | `length` | Hit max token limit |
| Claude | `stop_sequence` | `stop` | Hit custom stop |
| Gemini | `STOP` | `stop` | Response complete |
| Gemini | `MAX_TOKENS` | `length` | Hit max token limit |
| OpenAI | `stop` | `stop` | Response complete |
| OpenAI | `length` | `length` | Hit max token limit |

### C. HTTP Error Codes

| Code | Meaning | Action | Retryable |
|------|---------|--------|-----------|
| 200 | Success | Return response | N/A |
| 400 | Bad request | Return error | No |
| 401 | Unauthorized | Refresh token, retry once | Yes (once) |
| 403 | Forbidden | Refresh token, retry once | Yes (once) |
| 429 | Rate limited | Exponential backoff | Yes |
| 500 | Server error | Return error | No |
| 502 | Bad gateway | Return error | No |
| 503 | Service unavailable | Return error | No |
| 504 | Gateway timeout | Return error | No |

### D. File Location Reference

```
Key files for common tasks:

Task: Add new endpoint
  File: routers/chat.py (207 lines)
  Pattern: Copy existing endpoint, modify route + logic

Task: Understand token caching
  File: auth/token_manager.py (132 lines)
  Pattern: get_token() → cache check → fetch → update

Task: Debug streaming issues
  File: handlers/streaming_generators.py (1355 lines)
  Pattern: Check chunk parsing → conversion → SSE format

Task: Add new model support
  Files: proxy_helpers.py (detector) + handlers/
  Pattern: Add detector function + converter class

Task: Fix format conversion
  File: proxy_helpers.py (1786 lines, Converters section)
  Pattern: Trace convert_X_to_Y() through all steps

Task: Understand retry logic
  File: utils/retry.py (89 lines)
  Pattern: Check is_rate_limit_error() + @bedrock_retry decorator

Task: Trace request flow
  File: routers/chat.py (207 lines)
  Pattern: Follow 7-stage pipeline in chat_completions()
```

### E. Debugging Checklist

When debugging an issue, check in this order:

- [ ] **Token expiry**: Is token near 5-minute buffer? Check `TokenManager.needs_refresh()`
- [ ] **Model detection**: Which endpoint is being used? Check `is_claude_37_or_4()` logic
- [ ] **Load balancing**: Which deployment was selected? Check logs for "selected deployment"
- [ ] **Request conversion**: Is OpenAI request properly converted to model format? Trace `convert_openai_to_X()`
- [ ] **Backend response parsing**: Can we extract text from response? Check `_search_for_text_in_response()`
- [ ] **Stop reason mapping**: Is stop reason mapped correctly? Check stop reason table
- [ ] **Streaming format**: Are SSE chunks properly formatted? Check `event:` and `data:` lines
- [ ] **Error handling**: Is error 429 or auth error? Check retry logic

### F. Cross-References

- **ARCHITECTURE.md** - High-level system design
- **TESTING.md** - Test patterns and coverage
- **LOGGING_SYSTEM.md** - Logging configuration
- **CLAUDE.md** - Claude-specific implementation details

### G. Glossary

| Term | Definition |
|------|-----------|
| **Converter** | Code that transforms OpenAI ↔ Claude ↔ Gemini format |
| **Detector** | Logic to determine which endpoint/converter to use based on model name |
| **Load balancing** | Round-robin selection of subaccount + deployment |
| **OAuth token** | Bearer token from SAP AI Core for API authentication |
| **SSE** | Server-Sent Events; streaming response format (`event:` + `data:` lines) |
| **Stop reason** | Why the model stopped generating (end_turn, max_tokens, stop_sequence) |
| **Subaccount** | SAP tenant/customer account with own OAuth credentials |
| **Deployment** | Individual Bedrock inference endpoint URL |
| **5-min buffer** | Token refresh 5 minutes before actual expiry to prevent mid-flight expiry |
| **Sanitization** | Removing model-specific fields (cache_control, thinking) before backend request |

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-19  
**Commit:** f358537  
**Status:** Complete  

For updates or corrections, refer to the project's main documentation at `/docs/`.
