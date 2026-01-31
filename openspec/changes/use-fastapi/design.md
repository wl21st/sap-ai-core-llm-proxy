## Context

The current `sap-ai-core-llm-proxy` uses Flask and synchronous `requests` calls. This model is blocking: one thread per request. For LLM workloads, which often involve long-lived streaming connections, this quickly exhausts thread pools and limits concurrency. To achieve high throughput and lower latency, we are migrating to an asynchronous architecture using FastAPI and `httpx`. A critical part of this migration is transforming the payload conversion and streaming logic from synchronous generators to asynchronous streams.

## Goals / Non-Goals

**Goals:**
- **Full Async Pipeline**: End-to-end asynchronous handling from client request to backend response.
- **Non-blocking Transformations**: Logic that transforms payloads (OpenAI <-> Claude <-> Gemini) must not block the event loop.
- **Async Streaming**: Implement `async generator` patterns for Server-Sent Events (SSE).
- **Backward Compatibility**: maintain exact API behavior for clients.
- **Type Safety**: Leverage Pydantic for validation during transformations.

**Non-Goals:**
- **New Features**: We are not adding new model features or endpoints, only migrating existing ones.
- **Database Changes**: No persistence layer changes are in scope (config is in-memory/file-based).

## Decisions

### 1. Asynchronous Transformation Logic
**Decision**: Refactor `proxy_helpers.py` converters to be compatible with async execution, but keep them CPU-bound (synchronous functions) unless they perform I/O.
**Rationale**: Payload transformation is CPU-bound and fast. Making them `async def` adds overhead without benefit unless they await I/O. However, the *invocation* of these helpers will happen within async route handlers.
**Detail**:
- `Converters` class methods will remain synchronous.
- Route handlers will await `httpx` calls, then call converters on the result.
- For streaming, we will use `async for` to iterate over upstream chunks and apply transformations on each chunk.

### 2. Async Streaming with `httpx`
**Decision**: Use `httpx.AsyncClient` with `stream=True` for all backend calls.
**Rationale**: `requests` is synchronous. `httpx` provides a modern, async-native API that mirrors `requests`, simplifying migration while unlocking concurrency.
**Pattern**:
```python
async def generate_streaming_response(...):
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, ...) as response:
            async for chunk in response.aiter_lines():
                # Transform chunk (CPU-bound)
                transformed_chunk = transform(chunk)
                yield transformed_chunk
```

### 3. FastAPI Dependency Injection for Auth
**Decision**: Migrate `RequestValidator` to a FastAPI `Depends` callable.
**Rationale**: Flask uses decorators or manual calls inside routes. FastAPI's DI system is more idiomatic, allows for better testing (overriding dependencies), and automatically generates OpenAPI security schemes.

### 4. Global State Management
**Decision**: Use `contextlib.asynccontextmanager` for application lifespan (loading config, initializing SDK clients).
**Rationale**: Replaces the global code execution at the top of `proxy_server.py`. This ensures resources are loaded *before* the app starts serving requests and cleaned up gracefully.

## Risks / Trade-offs

- **[Risk] CPU-bound blocking**: If transformations (regex, parsing) are too heavy, they could block the async event loop.
    - *Mitigation*: The current transformations are lightweight JSON manipulations. If profiling shows blocking, we can offload to thread pools (`run_in_threadpool`), but this is likely unnecessary.
- **[Risk] `httpx` vs `requests` compatibility**: Subtle differences in timeout defaults or redirect handling.
    - *Mitigation*: We will explicitly configure `httpx` timeouts to match current 600s defaults and extensively test with the integration suite.
- **[Risk] Bedrock SDK Async**: The AWS Bedrock SDK (`boto3`) is synchronous.
    - *Mitigation*: Use `aioboto3` or run standard `boto3` calls in a thread pool using `fastapi.concurrency.run_in_threadpool`. Given the complexity of replacing the SDK, we will start with `run_in_threadpool` for Bedrock specifically.

## Open Questions
- Should we stick with `tenacity` for retries or switch to an async-native retry library?
    - *Tentative Answer*: `tenacity` supports `async` functions, so we can likely keep it.
