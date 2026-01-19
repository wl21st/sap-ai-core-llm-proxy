# Change: Extract Converters Module

## Why

The current `proxy_helpers.py` file contains ~1,407 lines of converter logic, model detection, streaming generators, and token usage tracking mixed together. This violates Single Responsibility Principle (SRP) and makes the code difficult to maintain, test, and extend. Additionally, streaming generators (~800 lines) are embedded in `proxy_server.py`, further increasing monolithic code issues.

This change is Phase 5 of the ongoing SOLID refactoring outlined in `docs/ARCHITECTURE.md`, which aims to complete the modularization of converter logic into a dedicated `converters/` module.

## What Changes

Extract converter-related functionality from `proxy_helpers.py` and `proxy_server.py` into a dedicated `converters/` module:

**New Module Structure:**
```
converters/
├── __init__.py                    # Public API exports + Converters class
├── detector.py                    # Model detection (Detector class)
├── mappings.py                    # Stop reasons, API versions, constants
├── reasoning.py                   # Thinking/budget token handling
├── token_usage.py                 # Token consumption extraction
├── request/                       # Request payload converters
│   ├── __init__.py
│   ├── openai_to_claude.py        # OpenAI → Claude (3.5 & 3.7/4)
│   ├── openai_to_gemini.py        # OpenAI → Gemini
│   ├── claude_to_openai.py        # Claude → OpenAI
│   ├── claude_to_gemini.py        # Claude → Gemini
│   └── claude_to_bedrock.py       # Claude → Bedrock format
├── response/                      # Response payload converters
│   ├── __init__.py
│   ├── claude_to_openai.py        # Claude response → OpenAI
│   ├── gemini_to_openai.py        # Gemini response → OpenAI
│   ├── gemini_to_claude.py        # Gemini response → Claude
│   └── openai_to_claude.py        # OpenAI response → Claude
└── streaming/                     # Streaming generators & chunk converters
    ├── __init__.py
    ├── generators.py              # generate_streaming_response(), generate_claude_streaming_response()
    ├── claude_chunks.py           # Claude chunk → OpenAI SSE
    ├── gemini_chunks.py           # Gemini chunk → OpenAI SSE
    └── openai_chunks.py           # OpenAI chunk → Claude SSE
```

**Key Changes:**
- Extract ~1,350 lines of converter functions from `proxy_helpers.py` into `converters/` subdirectories
- Extract ~800 lines of streaming generators from `proxy_server.py` into `converters/streaming/generators.py`
- Extract ~200 lines of thinking/reasoning and token usage logic from `proxy_server.py`
- Create `proxy_helpers.py` as a backward-compatibility facade (~50 lines)
- Update imports in `proxy_server.py` to use new `converters` module

**Backward Compatibility:**
- Keep `proxy_helpers.py` as a thin delegation layer with deprecation warnings
- Maintain existing API signatures through `Converters` class in `converters/__init__.py`

## Impact

**Affected Code:**
- `proxy_helpers.py`: Reduced from ~1,407 lines to ~50 lines (facade only)
- `proxy_server.py`: Reduced by ~800+ lines (streaming generators moved)
- New `converters/` module: ~17 files created

**Affected Capabilities:**
- `format-converters`: New capability extracted from proxy_helpers
- `streaming-support`: New capability extracted from proxy_server
- `model-detection`: New capability extracted from proxy_helpers
- `token-management`: Modified to use new TokenExtractor

**Breaking Changes:**
- None - backward compatibility maintained through facade layer

**Test Impact:**
- New unit tests for all converter modules (~10 test files)
- Integration tests to verify facade and import updates
- Estimated >90% coverage on `converters/` module

**Effort:**
- Estimated 10.5 days (12 implementation phases)

**Success Criteria:**
- All existing tests pass
- No import errors in `proxy_server.py`
- `proxy_helpers.py` facade works for backward compatibility
- New unit tests achieve >90% coverage on `converters/` module
- `proxy_server.py` reduced by ~800+ lines
- `proxy_helpers.py` reduced to <50 lines
