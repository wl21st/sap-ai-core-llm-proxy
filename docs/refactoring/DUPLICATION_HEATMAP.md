# Code Duplication Heatmap - PR #21 Analysis

Visual representation of code duplication across the FastAPI migration.

---

## Duplication Severity Map

```
🔴 CRITICAL (5+ duplicates)
🟠 HIGH (3-4 duplicates)
🟡 MEDIUM (2 duplicates)
🟢 LOW (architectural duplication)
```

---

## 1. handlers/streaming_generators.py (1,100+ lines)

```
Lines      Pattern                          Severity  Occurrences
----------------------------------------------------------------------
370-381    User/IP extraction               🟠 HIGH    3x in file
305-320    Error payload (chat.completion)  🔴 CRITICAL 2x in file
485-502    Error payload (chat.completion)  🔴 CRITICAL (see above)
685-698    Error payload (error object)     🔴 CRITICAL 3x in file
728-741    Error payload (error object)     🔴 CRITICAL (see above)
750-763    Error payload (error object)     🔴 CRITICAL (see above)
335-361    Final usage chunk                🟡 MEDIUM  2x in file
508-541    Final usage chunk                🟡 MEDIUM  (see above)
382-391    Token usage logging              🟠 HIGH    3x in file
555-564    Token usage logging              🟠 HIGH    (see above)
655-664    Token usage logging              🟠 HIGH    (see above)
```

**Total Duplication:** ~200 lines (18% of file)

---

## 2. routers/messages.py (357 lines)

```
Lines      Pattern                          Severity  Occurrences
----------------------------------------------------------------------
213-229    Auth retry (streaming)           🟡 MEDIUM  2x in file
286-298    Auth retry (non-streaming)       🟡 MEDIUM  (see above)
231-265    Response validation (streaming)  🟡 MEDIUM  2x in file
300-331    Response validation (non-stream) 🟡 MEDIUM  (see above)
62-71      Error response (Anthropic fmt)   🟠 HIGH    5x in file
82-91      Error response (Anthropic fmt)   🟠 HIGH    (see above)
98-107     Error response (Anthropic fmt)   🟠 HIGH    (see above)
232-253    Error response (Anthropic fmt)   🟠 HIGH    (see above)
303-330    Error response (Anthropic fmt)   🟠 HIGH    (see above)
```

**Total Duplication:** ~120 lines (34% of file)

---

## 3. routers/chat.py (208 lines)

```
Lines      Pattern                          Severity  Occurrences
----------------------------------------------------------------------
52-63      Error response handling          🟠 HIGH    3x in file
83-97      User/IP + token logging          🟠 HIGH    Dup with generators
134-137    Model not found error            🟠 HIGH    2x across routers
203-207    Generic error handling           🟠 HIGH    2x in file
```

**Total Duplication:** ~30 lines (14% of file)

---

## 4. routers/embeddings.py (122 lines)

```
Lines      Pattern                          Severity  Occurrences
----------------------------------------------------------------------
97-110     Error response handling          🟠 HIGH    3x in file
67         Simple error response            🟠 HIGH    (see above)
121        Generic error handling           🟠 HIGH    (see above)
```

**Total Duplication:** ~20 lines (16% of file)

---

## 5. handlers/bedrock_handler.py (72 lines)

```
Lines      Pattern                          Severity  Occurrences
----------------------------------------------------------------------
63-65      chunk_data = "" (duplicate)      🟢 LOW     Dead code
```

**Total Duplication:** 1 line (1% of file)

---

## 6. Cross-File Duplication Patterns

### Constants (4 files)
```
File                              Constant                     Duplicates
------------------------------------------------------------------------
routers/chat.py                   DEFAULT_GPT_MODEL            🟡 MEDIUM (2x)
handlers/model_handlers.py        DEFAULT_GPT_MODEL            🟡 MEDIUM (see above)
routers/messages.py               API_VERSION_2023_05_15       🟠 HIGH (3x)
routers/embeddings.py             API_VERSION_2023_05_15       🟠 HIGH (see above)
handlers/model_handlers.py        API_VERSION_2023_05_15       🟠 HIGH (see above)
```

### User/IP Extraction (4 files)
```
File                              Lines      Duplicates
--------------------------------------------------------
streaming_generators.py           370-381    🔴 CRITICAL (4x)
streaming_generators.py           543-554    🔴 CRITICAL (see above)
streaming_generators.py           642-652    🔴 CRITICAL (see above)
routers/chat.py                   83-86      🔴 CRITICAL (see above)
```

---

## Summary Statistics

| File | Total Lines | Duplicate Lines | Duplicate % |
|------|-------------|-----------------|-------------|
| streaming_generators.py | 1,100+ | ~200 | 18% |
| routers/messages.py | 357 | ~120 | 34% |
| routers/chat.py | 208 | ~30 | 14% |
| routers/embeddings.py | 122 | ~20 | 16% |
| bedrock_handler.py | 72 | 1 | 1% |

**Total Identified Duplication:** ~371 lines across 5 files

---

## Top Duplication Hotspots

### 1. Error Payload Generation (🔴 CRITICAL)
- **5 occurrences** in `streaming_generators.py`
- **5 occurrences** in `routers/messages.py`
- **Impact:** ~110 lines

### 2. User/IP Extraction (🔴 CRITICAL)
- **4 occurrences** across 2 files
- **Impact:** ~40 lines

### 3. Token Usage Logging (🟠 HIGH)
- **3 occurrences** in `streaming_generators.py`
- **Impact:** ~30 lines

### 4. Authentication Retry (🟡 MEDIUM)
- **2 occurrences** in `routers/messages.py`
- **Impact:** ~30 lines

### 5. Response Validation (🟡 MEDIUM)
- **2 occurrences** in `routers/messages.py`
- **Impact:** ~50 lines

---

## Recommended Action Plan

### Phase 1: Address Critical Duplications
1. Create `create_streaming_error_chunk()` helper
2. Create `extract_request_identity()` helper
3. **Impact:** -150 lines (41% of total duplication)

### Phase 2: Address High Duplications
4. Create `log_token_usage()` helper
5. Standardize error responses across routers
6. **Impact:** -60 lines (16% of total duplication)

### Phase 3: Address Medium Duplications
7. Create `retry_bedrock_on_auth_error()` helper
8. Create `validate_bedrock_response()` helper
9. **Impact:** -80 lines (22% of total duplication)

### Phase 4: Maintenance
10. Consolidate constants to `config/constants.py`
11. Remove dead code
12. **Impact:** -10 lines + improved maintainability

---

## Visualization: File Duplication Density

```
streaming_generators.py  ████████████████████ 18% duplication
routers/messages.py      ██████████████████████████████████ 34% duplication
routers/chat.py          ██████████████ 14% duplication
routers/embeddings.py    ████████████████ 16% duplication
bedrock_handler.py       █ 1% duplication
```

---

## Related Documents

- `REFACTORING_ANALYSIS_PR21.md` - Detailed analysis with code examples
- `REFACTORING_QUICK_WINS.md` - Top 5 quick wins with implementation guide
