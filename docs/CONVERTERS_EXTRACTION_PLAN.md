# Converters Module Extraction Plan

**Version**: 1.0  
**Created**: 2026-01-18  
**Status**: Approved  
**Estimated Effort**: 10.5 days  

---

## 1. Executive Summary

This plan extracts AI API payload conversion, reasoning/thinking token handling, token consumption tracking, and streaming generators from `proxy_helpers.py` and `proxy_server.py` into a dedicated `converters/` module. This aligns with Phase 5 of the architectural refactoring outlined in `docs/ARCHITECTURE.md`.

### Key Decisions

| # | Decision Point | Resolution |
|---|----------------|------------|
| 1 | Module name | `converters/` |
| 2 | Reasoning token tracking for future models | No - not needed now |
| 3 | Streaming generators location | Move to `converters/streaming/` |
| 4 | Backward compatibility | Yes - keep `proxy_helpers.py` as facade |

---

## 2. Current State Analysis

### Components to Extract

| Component | Current Location | Lines | Description |
|-----------|-----------------|-------|-------------|
| **Detector class** | `proxy_helpers.py:11-76` | ~65 | Model detection (`is_claude_model`, `is_gemini_model`, etc.) |
| **Converters class** | `proxy_helpers.py:78-1431` | ~1350 | All format converters (OpenAI↔Claude↔Gemini) |
| **Thinking/Reasoning handling** | `proxy_server.py:1008-1082` | ~75 | `thinking.budget_tokens` adjustment, `reasoning_effort` passthrough |
| **Token consumption tracking** | `proxy_server.py:1633-1648, 1786-1798, 1875-1885` | ~50 | Token usage extraction & logging |
| **Stop reason mapping** | Multiple places in both files | ~40 | Claude↔OpenAI↔Gemini stop reason mappings |
| **Streaming chunk conversion** | `proxy_helpers.py:686-873` | ~190 | Chunk-level format conversion |
| **Streaming generators** | `proxy_server.py:1688-2500+` | ~800+ | `generate_streaming_response()`, `generate_claude_streaming_response()` |

---

## 3. Target Module Structure

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

---

## 4. Detailed Extraction Mapping

### 4.1 From `proxy_helpers.py`

| Source Lines | Target File | Function/Class |
|--------------|-------------|----------------|
| 11-76 | `converters/detector.py` | `Detector` class |
| 88-108 | `converters/request/openai_to_claude.py` | `convert_openai_to_claude()` |
| 110-238 | `converters/request/openai_to_claude.py` | `convert_openai_to_claude37()` |
| 240-285 | `converters/request/claude_to_openai.py` | `convert_claude_request_to_openai()` |
| 287-366 | `converters/request/claude_to_gemini.py` | `convert_claude_request_to_gemini()` |
| 368-440 | `converters/request/claude_to_bedrock.py` | `convert_claude_request_for_bedrock()` |
| 442-502 | `converters/response/claude_to_openai.py` | `convert_claude_to_openai()` |
| 504-684 | `converters/response/claude_to_openai.py` | `convert_claude37_to_openai()` |
| 686-717 | `converters/streaming/claude_chunks.py` | `convert_claude_chunk_to_openai()` |
| 719-872 | `converters/streaming/claude_chunks.py` | `convert_claude37_chunk_to_openai()` |
| 874-1019 | `converters/request/openai_to_gemini.py` | `convert_openai_to_gemini()` |
| 1021-1130 | `converters/response/gemini_to_openai.py` | `convert_gemini_to_openai()` |
| 1132-1206 | `converters/response/gemini_to_claude.py` | `convert_gemini_response_to_claude()` |
| 1208-1305 | `converters/response/openai_to_claude.py` | `convert_openai_response_to_claude()` |
| 1307-1322 | `converters/streaming/gemini_chunks.py` | `convert_gemini_chunk_to_claude_delta()` |
| 1324-1336 | `converters/streaming/openai_chunks.py` | `convert_openai_chunk_to_claude_delta()` |
| 1338-1431 | `converters/streaming/gemini_chunks.py` | `convert_gemini_chunk_to_openai()` |

### 4.2 From `proxy_server.py`

| Source Lines | Target File | Function/Content |
|--------------|-------------|------------------|
| 1008-1082 | `converters/reasoning.py` | Thinking/budget_tokens adjustment logic |
| 1633-1648 | `converters/token_usage.py` | Token extraction (non-streaming) |
| 1786-1798 | `converters/token_usage.py` | Token extraction (Claude 3.7 streaming metadata) |
| 1931-1944 | `converters/token_usage.py` | Token extraction (Gemini usageMetadata) |
| 1688-2189 | `converters/streaming/generators.py` | `generate_streaming_response()` |
| 2192-2500+ | `converters/streaming/generators.py` | `generate_claude_streaming_response()` |

---

## 5. Key Module Designs

### 5.1 `converters/detector.py`

```python
"""Model detection utilities."""

import logging

logger = logging.getLogger(__name__)


class Detector:
    """Detect model types from model name strings."""

    CLAUDE_PREFIXES = ("claude-", "anthropic--claude-")
    CLAUDE_KEYWORDS = ("sonnet", "opus", "haiku")
    GEMINI_PREFIXES = ("gemini-", "models/gemini-")
    CLAUDE_37_4_PATTERNS = ("claude-3-7", "claude-3.7", "claude-4", "claude-sonnet-4")

    @staticmethod
    def is_claude_model(model: str) -> bool:
        """Check if model is a Claude model."""
        if not model:
            return False
        model_lower = model.lower()
        return (
            any(model_lower.startswith(p) for p in Detector.CLAUDE_PREFIXES)
            or any(kw in model_lower for kw in Detector.CLAUDE_KEYWORDS)
            or model_lower.startswith("anthropic--")
        )

    @staticmethod
    def is_claude_37_or_4(model: str) -> bool:
        """Check if model is Claude 3.7 or 4.x (uses /converse endpoint)."""
        if not model:
            return False
        model_lower = model.lower()
        return any(p in model_lower for p in Detector.CLAUDE_37_4_PATTERNS)

    @staticmethod
    def is_gemini_model(model: str) -> bool:
        """Check if model is a Gemini model."""
        if not model:
            return False
        model_lower = model.lower()
        return any(model_lower.startswith(p) for p in Detector.GEMINI_PREFIXES)
```

### 5.2 `converters/mappings.py`

```python
"""Shared mappings and constants for format conversion."""

# API Version Constants
API_VERSION_2023_05_15 = "2023-05-15"
API_VERSION_2024_12_01_PREVIEW = "2024-12-01-preview"

# Stop Reason Mappings
class StopReasonMapper:
    """Map stop/finish reasons between providers."""

    CLAUDE_TO_OPENAI = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }

    OPENAI_TO_CLAUDE = {
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "stop_sequence",
        "tool_calls": "tool_use",
    }

    GEMINI_TO_OPENAI = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
        "OTHER": "stop",
    }

    @classmethod
    def claude_to_openai(cls, reason: str) -> str:
        return cls.CLAUDE_TO_OPENAI.get(reason, "stop")

    @classmethod
    def openai_to_claude(cls, reason: str) -> str:
        return cls.OPENAI_TO_CLAUDE.get(reason, "end_turn")

    @classmethod
    def gemini_to_openai(cls, reason: str) -> str:
        return cls.GEMINI_TO_OPENAI.get(reason, "stop")
```

### 5.3 `converters/reasoning.py`

```python
"""Reasoning and thinking token configuration handling."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ReasoningConfig:
    """Handle thinking/reasoning token configuration for different providers."""

    UNSUPPORTED_THINKING_FIELDS = ("context_management",)

    @staticmethod
    def adjust_for_claude(body: dict[str, Any]) -> dict[str, Any]:
        """
        Adjust max_tokens to satisfy thinking.budget_tokens constraints.
        
        Claude requires max_tokens > thinking.budget_tokens.
        """
        thinking_cfg = body.get("thinking")
        if not isinstance(thinking_cfg, dict):
            return body

        # Remove unsupported fields
        for field in ReasoningConfig.UNSUPPORTED_THINKING_FIELDS:
            if field in thinking_cfg:
                logger.info(f"Removing '{field}' from thinking config")
                thinking_cfg.pop(field, None)

        # Adjust max_tokens if needed
        budget_tokens = thinking_cfg.get("budget_tokens")
        if isinstance(budget_tokens, int):
            max_tokens = body.get("max_tokens")
            required_min = budget_tokens + 1

            if max_tokens is None or max_tokens <= budget_tokens:
                body["max_tokens"] = required_min
                logger.info(
                    f"Adjusted max_tokens to {required_min} to satisfy "
                    f"thinking.budget_tokens={budget_tokens}"
                )
            else:
                logger.debug(
                    f"max_tokens={max_tokens} already greater than "
                    f"thinking.budget_tokens={budget_tokens}"
                )

        return body

    @staticmethod
    def passthrough_reasoning_effort(
        source_payload: dict[str, Any],
        target_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass through reasoning_effort for OpenAI o-series models."""
        if "reasoning_effort" in source_payload:
            target_payload["reasoning_effort"] = source_payload["reasoning_effort"]
        return target_payload
```

### 5.4 `converters/token_usage.py`

```python
"""Token usage extraction and tracking."""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Unified token usage representation."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    def to_openai_format(self) -> dict[str, int]:
        """Convert to OpenAI usage format."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def to_claude_format(self) -> dict[str, int]:
        """Convert to Claude usage format."""
        return {
            "input_tokens": self.prompt_tokens,
            "output_tokens": self.completion_tokens,
        }


class TokenExtractor:
    """Extract token usage from various response formats."""

    @staticmethod
    def from_openai_response(response: dict[str, Any]) -> TokenUsage:
        """Extract from OpenAI response format."""
        usage = response.get("usage", {})
        return TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    @staticmethod
    def from_claude_response(response: dict[str, Any]) -> TokenUsage:
        """Extract from Claude response format."""
        usage = response.get("usage", {})
        prompt = usage.get("input_tokens", 0)
        completion = usage.get("output_tokens", 0)
        return TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )

    @staticmethod
    def from_claude37_metadata(metadata: dict[str, Any]) -> TokenUsage:
        """Extract from Claude 3.7/4 streaming metadata chunk."""
        usage = metadata.get("usage", {})
        return TokenUsage(
            prompt_tokens=usage.get("inputTokens", 0),
            completion_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("totalTokens", 0),
        )

    @staticmethod
    def from_gemini_usage_metadata(metadata: dict[str, Any]) -> TokenUsage:
        """Extract from Gemini usageMetadata."""
        return TokenUsage(
            prompt_tokens=metadata.get("promptTokenCount", 0),
            completion_tokens=metadata.get("candidatesTokenCount", 0),
            total_tokens=metadata.get("totalTokenCount", 0),
        )
```

### 5.5 `converters/streaming/generators.py` (Signature)

```python
"""Streaming response generators."""

import json
import logging
import random
import time
from typing import Any, Generator

import requests

from converters.detector import Detector
from converters.mappings import StopReasonMapper
from converters.token_usage import TokenExtractor, TokenUsage
from converters.streaming.claude_chunks import (
    convert_claude_chunk_to_openai,
    convert_claude37_chunk_to_openai,
)
from converters.streaming.gemini_chunks import convert_gemini_chunk_to_openai

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """Encapsulates request context for streaming generators."""
    user_id: str
    ip_address: str
    headers: dict[str, str]


def generate_streaming_response(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    model: str,
    subaccount_name: str,
    tid: str,
    request_context: RequestContext,
    token_usage_logger: logging.Logger,
    transport_logger: logging.Logger,
) -> Generator[str, None, None]:
    """
    Generate streaming response from backend API.
    
    Moved from proxy_server.py. Handles Claude 3.7/4, Gemini, and OpenAI streaming.
    """
    # Implementation moved from proxy_server.py:1688-2189
    ...


def generate_claude_streaming_response(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    model: str,
    subaccount_name: str,
) -> Generator[bytes, None, None]:
    """
    Generate streaming response in Anthropic Claude Messages API format.
    
    Moved from proxy_server.py. Converts backend streams to Claude format.
    """
    # Implementation moved from proxy_server.py:2192-2500+
    ...
```

---

## 6. Backward Compatibility

After extraction, `proxy_helpers.py` becomes a thin delegation layer:

```python
# proxy_helpers.py (after extraction)
"""
Backward compatibility layer - delegates to converters module.

DEPRECATED: Import directly from converters module instead.
This file will be removed in a future version.
"""

import warnings

from converters import Converters
from converters.detector import Detector

__all__ = ["Detector", "Converters"]

# Issue deprecation warning on import
warnings.warn(
    "proxy_helpers is deprecated. Import from converters module directly.",
    DeprecationWarning,
    stacklevel=2,
)
```

And `converters/__init__.py` provides the unified interface:

```python
# converters/__init__.py
"""
Converters module - AI API payload conversion and bridging.

Provides format conversion between OpenAI, Claude, and Gemini APIs.
"""

from converters.detector import Detector
from converters.mappings import StopReasonMapper, API_VERSION_2023_05_15, API_VERSION_2024_12_01_PREVIEW
from converters.reasoning import ReasoningConfig
from converters.token_usage import TokenUsage, TokenExtractor

# Request converters
from converters.request.openai_to_claude import (
    convert_openai_to_claude,
    convert_openai_to_claude37,
)
from converters.request.openai_to_gemini import convert_openai_to_gemini
from converters.request.claude_to_openai import convert_claude_request_to_openai
from converters.request.claude_to_gemini import convert_claude_request_to_gemini
from converters.request.claude_to_bedrock import convert_claude_request_for_bedrock

# Response converters
from converters.response.claude_to_openai import (
    convert_claude_to_openai,
    convert_claude37_to_openai,
)
from converters.response.gemini_to_openai import convert_gemini_to_openai
from converters.response.gemini_to_claude import convert_gemini_response_to_claude
from converters.response.openai_to_claude import convert_openai_response_to_claude

# Streaming converters
from converters.streaming.claude_chunks import (
    convert_claude_chunk_to_openai,
    convert_claude37_chunk_to_openai,
)
from converters.streaming.gemini_chunks import (
    convert_gemini_chunk_to_openai,
    convert_gemini_chunk_to_claude_delta,
)
from converters.streaming.openai_chunks import convert_openai_chunk_to_claude_delta
from converters.streaming.generators import (
    generate_streaming_response,
    generate_claude_streaming_response,
    RequestContext,
)


class Converters:
    """
    Unified converter interface for backward compatibility.
    
    Provides static methods matching the original Converters class API.
    """
    # Request converters
    convert_openai_to_claude = staticmethod(convert_openai_to_claude)
    convert_openai_to_claude37 = staticmethod(convert_openai_to_claude37)
    convert_openai_to_gemini = staticmethod(convert_openai_to_gemini)
    convert_claude_request_to_openai = staticmethod(convert_claude_request_to_openai)
    convert_claude_request_to_gemini = staticmethod(convert_claude_request_to_gemini)
    convert_claude_request_for_bedrock = staticmethod(convert_claude_request_for_bedrock)
    
    # Response converters
    convert_claude_to_openai = staticmethod(convert_claude_to_openai)
    convert_claude37_to_openai = staticmethod(convert_claude37_to_openai)
    convert_gemini_to_openai = staticmethod(convert_gemini_to_openai)
    convert_gemini_response_to_claude = staticmethod(convert_gemini_response_to_claude)
    convert_openai_response_to_claude = staticmethod(convert_openai_response_to_claude)
    
    # Streaming chunk converters
    convert_claude_chunk_to_openai = staticmethod(convert_claude_chunk_to_openai)
    convert_claude37_chunk_to_openai = staticmethod(convert_claude37_chunk_to_openai)
    convert_gemini_chunk_to_openai = staticmethod(convert_gemini_chunk_to_openai)
    convert_gemini_chunk_to_claude_delta = staticmethod(convert_gemini_chunk_to_claude_delta)
    convert_openai_chunk_to_claude_delta = staticmethod(convert_openai_chunk_to_claude_delta)


__all__ = [
    # Classes
    "Detector",
    "Converters",
    "StopReasonMapper",
    "ReasoningConfig",
    "TokenUsage",
    "TokenExtractor",
    "RequestContext",
    # Constants
    "API_VERSION_2023_05_15",
    "API_VERSION_2024_12_01_PREVIEW",
    # Request converters
    "convert_openai_to_claude",
    "convert_openai_to_claude37",
    "convert_openai_to_gemini",
    "convert_claude_request_to_openai",
    "convert_claude_request_to_gemini",
    "convert_claude_request_for_bedrock",
    # Response converters
    "convert_claude_to_openai",
    "convert_claude37_to_openai",
    "convert_gemini_to_openai",
    "convert_gemini_response_to_claude",
    "convert_openai_response_to_claude",
    # Streaming
    "convert_claude_chunk_to_openai",
    "convert_claude37_chunk_to_openai",
    "convert_gemini_chunk_to_openai",
    "convert_gemini_chunk_to_claude_delta",
    "convert_openai_chunk_to_claude_delta",
    "generate_streaming_response",
    "generate_claude_streaming_response",
]
```

---

## 7. Implementation Phases

| Phase | Task | Effort | Files Created/Modified |
|-------|------|--------|------------------------|
| **1** | Create `converters/` directory structure & `__init__.py` files | 0.5d | 8 `__init__.py` files |
| **2** | Extract `mappings.py` (stop reasons, API versions) | 0.5d | 1 file |
| **3** | Extract `detector.py` (model detection) | 0.5d | 1 file |
| **4** | Extract `reasoning.py` (thinking/budget handling) | 1d | 1 file |
| **5** | Extract `token_usage.py` (consumption tracking) | 1d | 1 file |
| **6** | Extract `request/` converters | 1.5d | 5 files |
| **7** | Extract `response/` converters | 1d | 4 files |
| **8** | Extract `streaming/` chunk converters | 1d | 3 files |
| **9** | Move streaming generators to `streaming/generators.py` | 1.5d | 1 file |
| **10** | Update `proxy_helpers.py` as backward-compat facade | 0.5d | 1 file modified |
| **11** | Update imports in `proxy_server.py` | 0.5d | 1 file modified |
| **12** | Add/update unit tests | 1.5d | ~10 test files |

**Total Estimated Effort: 10.5 days**

---

## 8. Testing Strategy

### 8.1 Unit Tests Per Module

| Module | Test File | Key Test Cases |
|--------|-----------|----------------|
| `detector.py` | `tests/converters/test_detector.py` | Model detection for all providers |
| `mappings.py` | `tests/converters/test_mappings.py` | Stop reason mappings |
| `reasoning.py` | `tests/converters/test_reasoning.py` | Budget token adjustment, field cleanup |
| `token_usage.py` | `tests/converters/test_token_usage.py` | Extraction from all response formats |
| `request/*` | `tests/converters/request/test_*.py` | Request payload conversion |
| `response/*` | `tests/converters/response/test_*.py` | Response payload conversion |
| `streaming/*` | `tests/converters/streaming/test_*.py` | Chunk conversion, generators |

### 8.2 Integration Tests

- Verify `proxy_helpers.py` facade still works
- Verify `proxy_server.py` imports work after update
- End-to-end streaming tests

---

## 9. Rollback Plan

If issues arise during extraction:

1. **Phase-level rollback**: Each phase is independent; revert the specific phase's commits
2. **Full rollback**: `proxy_helpers.py` facade ensures existing imports continue working
3. **Feature flag**: Add `USE_NEW_CONVERTERS=false` env var to fall back to old code (optional)

---

## 10. Success Criteria

- [ ] All existing tests pass
- [ ] No import errors in `proxy_server.py`
- [ ] `proxy_helpers.py` facade works for backward compatibility
- [ ] New unit tests achieve >90% coverage on `converters/` module
- [ ] `proxy_server.py` reduced by ~800+ lines (streaming generators moved)
- [ ] `proxy_helpers.py` reduced to <50 lines (facade only)

---

## 11. Dependencies

- No external dependencies added
- Internal dependencies:
  - `converters/streaming/generators.py` depends on `converters/detector.py`, `converters/mappings.py`, `converters/token_usage.py`
  - All converter modules depend on `converters/mappings.py`

---

## 12. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Import cycles | Medium | High | Careful dependency ordering; use TYPE_CHECKING imports |
| Streaming generator state issues | Medium | High | Thorough integration testing; keep request context encapsulated |
| Backward compat breaks | Low | Medium | Facade layer + deprecation warnings |
| Test coverage gaps | Low | Medium | Phase 12 dedicated to testing |

---

**Document Version**: 1.0  
**Next Review**: After Phase 6 completion  
**Owner**: Architecture Team
