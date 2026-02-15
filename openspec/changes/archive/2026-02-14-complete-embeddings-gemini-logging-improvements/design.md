## Context

The proxy server handles three distinct concerns:
1. **Embeddings endpoint** (`proxy_server.py:108-136`) - Currently requires an explicit model but has no fallback
2. **Streaming responses** (`handlers/streaming_generators.py`) - Currently converts standard Gemini format but not Gemini-2.5-pro's variant
3. **Deployment inspection utility** (`inspect_deployments.py`) - Uses `print()` instead of logging

## Goals

- Embeddings: Provide fallback model detection without breaking existing explicit model requests
- Gemini streaming: Extend streaming support to Gemini-2.5-pro while preserving compatibility with existing converters
- Logging: Refactor `inspect_deployments.py` to use logger for all output

## Non-Goals

- Changing the embeddings API contract
- Modifying the overall streaming architecture
- Adding new CLI flags or configuration options

## Decisions

### Decision 1: Embeddings Default Model Strategy

**Approach:** Check if `model` is None/empty in `handle_embedding_service_call()`, then attempt to use the first available model from the current subaccount's deployment list.

**Rationale:** 
- Graceful fallback without new config options
- Consistent with load balancing logic already in place
- If no default available, raise ValueError with clear message

**Implementation:** Add logic before `load_balance_url()` call to resolve a default if needed.

### Decision 2: Gemini-2.5-pro Format Detection

**Approach:** Detect Gemini-2.5-pro format by checking for the specific structure `{candidates: [{content: {parts: [...]}}]}` in streaming chunks.

**Rationale:**
- Format detection is more resilient than model name matching
- Allows handling of Gemini-2.5-pro variant without modifying the routing logic
- Can be extended if other Gemini variants emerge

**Implementation:** Add a helper function `is_gemini_2_5_pro_format()` in `streaming_generators.py` that checks chunk structure, then delegate to appropriate converter.

### Decision 3: Logging Refactor Scope

**Approach:** Replace all `print()` calls with `logger.info()`, preserving output format exactly.

**Rationale:**
- Minimal change, maximum benefit
- Maintains visual consistency for users
- Enables log level filtering and redirection

**Implementation:** Direct 1-to-1 replacement of `print()` → `logger.info()` in `inspect_deployments.py`.
