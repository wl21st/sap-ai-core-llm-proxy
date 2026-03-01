# Quick Wins: Top 5 Refactoring Opportunities

**Goal:** Maximum impact with minimal effort
**Estimated Time:** 4-6 hours total
**Risk Level:** Low (pure extractions, no logic changes)

---

## 1. Extract User/IP Identity Helper (30 minutes)

**Problem:** Duplicated 4 times across codebase
**Files:** `handlers/streaming_generators.py` (3x), `routers/chat.py` (1x)

### Create: `utils/logging_utils.py`

```python
def extract_request_identity(request: Request | None) -> tuple[str, str]:
    """Extract user ID and IP address from FastAPI request for logging."""
    if not request:
        return "unknown", "unknown_ip"
    
    user_id = request.headers.get("Authorization", "unknown")
    if user_id and len(user_id) > 20:
        user_id = f"{user_id[:20]}..."
    
    ip_address = request.client.host if request.client else "unknown_ip"
    return user_id, ip_address
```

### Replace in 4 locations with:
```python
user_id, ip_address = extract_request_identity(request)
```

**Impact:** -40 lines, improved consistency

---

## 2. Standardize Error Responses (45 minutes)

**Problem:** Inconsistent error formats across routers
**Files:** `routers/chat.py`, `routers/messages.py`, `routers/embeddings.py`

### Enhance: `utils/error_handlers.py`

```python
def create_error_response(
    message: str,
    status_code: int = 500,
    error_type: str = "api_error",
    use_anthropic_format: bool = False,
) -> JSONResponse:
    """Create standardized error response."""
    if use_anthropic_format:
        body = {
            "type": "error",
            "error": {"type": error_type, "message": message},
        }
    else:
        body = {"error": message}
    return JSONResponse(body, status_code=status_code)

def create_model_not_found_response(model: str, anthropic_format: bool = False) -> JSONResponse:
    """Create 404 response for model not found."""
    return create_error_response(
        f"Model '{model}' not available",
        status_code=404,
        error_type="not_found_error",
        use_anthropic_format=anthropic_format,
    )
```

**Impact:** -30 lines, consistent API errors

---

## 3. Consolidate Constants (20 minutes)

**Problem:** Duplicate constants across 4 files
**Files:** `routers/*.py`, `handlers/model_handlers.py`

### Create: `config/constants.py`

```python
"""Constants for SAP AI Core LLM Proxy."""

# Default Models
DEFAULT_GPT_MODEL = "gpt-4.1"
DEFAULT_CLAUDE_MODEL = "anthropic--claude-4.5-sonnet"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# API Versions
API_VERSION_2023_05_15 = "2023-05-15"
API_VERSION_BEDROCK_2023_05_31 = "bedrock-2023-05-31"
API_VERSION_2024_12_01_PREVIEW = "2024-12-01-preview"

# Random ID Range
RANDOM_ID_MIN = 10000000
RANDOM_ID_MAX = 99999999
```

### Replace imports in all files:
```python
from config.constants import DEFAULT_GPT_MODEL, API_VERSION_2023_05_15
```

**Impact:** Centralized configuration, easier maintenance

---

## 4. Remove Dead Code (5 minutes)

**Problem:** Duplicate variable assignment
**File:** `handlers/bedrock_handler.py:63-65`

### Change:
```python
# Before
chunk_data = ""

chunk_data = ""  # Duplicate!
for event in response_body:
    ...

# After
chunk_data = ""
for event in response_body:
    ...
```

**Impact:** -1 line, cleaner code

---

## 5. Extract Streaming Error Helper (60 minutes)

**Problem:** Error payload creation duplicated 5 times
**File:** `handlers/streaming_generators.py`

### Create in `handlers/streaming_generators.py`:

```python
def create_streaming_error_chunk(
    model: str,
    error_message: str,
    error_type: str = "proxy_error",
    status_code: int = 500,
    subaccount_name: str | None = None,
    is_chat_completion: bool = False,
) -> str:
    """Create standardized SSE error chunk."""
    from config.constants import RANDOM_ID_MIN, RANDOM_ID_MAX
    error_id = f"error-{random.randint(RANDOM_ID_MIN, RANDOM_ID_MAX)}"
    
    if is_chat_completion:
        payload = {
            "id": error_id.replace("error-", "chatcmpl-error-"),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"[PROXY ERROR: {error_message}]"},
                "finish_reason": "stop",
            }],
        }
    else:
        error_dict = {
            "message": error_message,
            "type": error_type,
            "code": status_code,
        }
        if subaccount_name:
            error_dict["subaccount"] = subaccount_name
        
        payload = {
            "id": error_id,
            "object": "error",
            "created": int(time.time()),
            "model": model,
            "error": error_dict,
        }
    
    return f"data: {json.dumps(payload)}\n\n"
```

### Replace 5 error payload blocks with:
```python
# For chunk processing errors (Claude/Gemini)
yield create_streaming_error_chunk(
    model=model,
    error_message="Failed to process upstream data",
    is_chat_completion=True,
)

# For HTTP/streaming errors
yield create_streaming_error_chunk(
    model=model,
    error_message=error_content,
    error_type="http_error",
    status_code=status_code,
    subaccount_name=subaccount_name,
)
```

**Impact:** -80 lines, standardized error format

---

## Testing Checklist

After implementing each quick win:

```bash
# 1. Run unit tests
make test

# 2. Start server
uvx --from . sap-ai-proxy --config config.json

# 3. Run integration tests (in another terminal)
make test-integration

# 4. Verify no behavior changes
git diff tests/  # Should be minimal or none
```

---

## Implementation Order

1. **Constants** (#3) - Foundation for others
2. **User/IP Helper** (#1) - Simple extraction
3. **Dead Code** (#4) - Quick cleanup
4. **Error Responses** (#2) - Standardization
5. **Streaming Error** (#5) - Largest impact

**Total Time:** ~3 hours
**Total Lines Saved:** ~150 lines
**Risk:** Minimal (pure extractions)

---

## Files Modified Summary

```
config/constants.py                     (NEW)
utils/logging_utils.py                  (ENHANCE)
utils/error_handlers.py                 (ENHANCE)
handlers/streaming_generators.py        (REFACTOR)
handlers/bedrock_handler.py            (CLEANUP)
routers/chat.py                        (USE HELPERS)
routers/messages.py                    (USE HELPERS)
routers/embeddings.py                  (USE HELPERS)
```

---

## Next Steps (After Quick Wins)

See `REFACTORING_ANALYSIS_PR21.md` for:
- Auth retry consolidation (#1)
- Response validation helper (#4)
- Request sanitization (#6)
- Additional opportunities (#7-14)
