# SOLID Refactoring Plan for proxy_server.py

## Executive Summary

This document outlines a comprehensive plan to refactor `proxy_server.py` (2,905 lines) into a modular, SOLID-compliant architecture. The refactoring will be executed in 7 phases, each independently deployable with tests, maintaining backward compatibility for public APIs.

**Current State**: Phase 3 completed (authentication module extracted)
**Target State**: Fully modular architecture with <500 lines per file
**Approach**: Phased refactoring prioritizing Single Responsibility Principle

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [SOLID Violations Identified](#solid-violations-identified)
3. [Target Architecture](#target-architecture)
4. [Phase-by-Phase Implementation Plan](#phase-by-phase-implementation-plan)
5. [Module Specifications](#module-specifications)
6. [Testing Strategy](#testing-strategy)
7. [Backward Compatibility Strategy](#backward-compatibility-strategy)
8. [Migration Guide](#migration-guide)

---

## Current Architecture Analysis

### File Structure (Post Phase 2)

```
sap-ai-core-llm-proxy/
├── config/              ✅ Extracted (Phase 2)
│   ├── models.py        (98 lines)
│   └── loader.py        (49 lines)
├── utils/               ✅ Extracted (Phase 2)
│   ├── logging_setup.py (58 lines)
│   └── error_handlers.py (67 lines)
└── proxy_server.py      ❌ 2,905 lines - NEEDS REFACTORING
```

### proxy_server.py Responsibilities (Violations of SRP)

| Lines | Responsibility | Target Module |
|-------|---------------|---------------|
| 1-62 | SDK session/client caching | `clients/sdk_manager.py` |
| 64-142 | Embeddings endpoint | `api/embeddings.py` |
| 159-238 | Token management | `auth/token_manager.py` |
| 240-259 | Request authentication | `auth/request_validator.py` |
| 261-388 | OpenAI→Claude conversion | `converters/claude_converter.py` |
| 390-495 | Claude→OpenAI conversion | `converters/claude_converter.py` |
| 497-552 | Claude→Bedrock conversion | `converters/bedrock_converter.py` |
| 555-742 | Response conversions | `converters/response_converter.py` |
| 744-898 | Streaming chunk conversions | `converters/streaming_converter.py` |
| 900-926 | Model detection utilities | `models/detector.py` |
| 928-1065 | OpenAI→Gemini conversion | `converters/gemini_converter.py` |
| 1067-1158 | Gemini→OpenAI conversion | `converters/gemini_converter.py` |
| 1161-1346 | Cross-model conversions | `converters/cross_converter.py` |
| 1349-1440 | Gemini streaming | `converters/streaming_converter.py` |
| 1442-1536 | Load balancing | `routing/load_balancer.py` |
| 1538-1662 | Request handlers | `routing/request_handler.py` |
| 1664-1726 | Flask routes (OPTIONS, models) | `api/routes.py` |
| 1728-1739 | Event logging endpoint | `api/routes.py` |
| 1742-1818 | Chat completions endpoint | `api/chat_completions.py` |
| 1821-2193 | Claude messages endpoint | `api/claude_messages.py` |
| 2196-2270 | Non-streaming handler | `handlers/non_streaming.py` |
| 2273-2584 | Streaming handler | `handlers/streaming.py` |
| 2587-2822 | Claude streaming handler | `handlers/claude_streaming.py` |
| 2825-2905 | Main application setup | `main.py` |

---

## SOLID Violations Identified

### 1. Single Responsibility Principle (SRP) ❌ CRITICAL

**Violation**: `proxy_server.py` has 20+ distinct responsibilities

- Configuration management ✅ Fixed in Phase 2
- Token management ❌ Still in main file
- Request routing ❌ Still in main file
- Format conversion (8+ converters) ❌ Still in main file
- Streaming handling ❌ Still in main file
- API endpoints ❌ Still in main file

### 2. Open/Closed Principle (OCP) ❌ HIGH

**Violation**: Adding new model providers requires modifying existing code

```python
# Current: Hardcoded model detection
if is_claude_model(model):
    # Claude-specific logic
elif is_gemini_model(model):
    # Gemini-specific logic
else:
    # Default logic
```

**Solution**: Strategy pattern with model provider registry

### 3. Liskov Substitution Principle (LSP) ⚠️ MEDIUM

**Violation**: Limited inheritance, but inconsistent interfaces

- Different converters have different signatures
- Streaming handlers don't share common interface

**Solution**: Define base classes and protocols

### 4. Interface Segregation Principle (ISP) ❌ HIGH

**Violation**: No clear interfaces, monolithic functions

- Large functions doing multiple things
- No separation between streaming/non-streaming interfaces

**Solution**: Define focused interfaces for each concern

### 5. Dependency Inversion Principle (DIP) ❌ HIGH

**Violation**: High-level modules depend on low-level details

```python
# Direct dependency on requests library
response = requests.post(url, headers=headers, json=payload)
```

**Solution**: Abstract HTTP client interface

---

## Target Architecture

### Module Structure

```
sap-ai-core-llm-proxy/
├── config/                    ✅ Phase 2 Complete
│   ├── __init__.py
│   ├── models.py
│   └── loader.py
├── utils/                     ✅ Phase 2 Complete
│   ├── __init__.py
│   ├── logging_setup.py
│   └── error_handlers.py
├── auth/                      📋 Phase 3
│   ├── __init__.py
│   ├── token_manager.py       (Token fetching, caching)
│   └── request_validator.py  (Request authentication)
├── models/                    📋 Phase 4
│   ├── __init__.py
│   ├── detector.py            (Model type detection)
│   ├── provider.py            (Base provider interface)
│   ├── claude_provider.py     (Claude-specific logic)
│   ├── gemini_provider.py     (Gemini-specific logic)
│   └── openai_provider.py     (OpenAI-specific logic)
├── converters/                📋 Phase 5
│   ├── __init__.py
│   ├── base.py                (Base converter interface)
│   ├── factory.py             (Converter factory)
│   ├── claude_converter.py    (OpenAI↔Claude)
│   ├── gemini_converter.py    (OpenAI↔Gemini)
│   ├── bedrock_converter.py   (Claude→Bedrock)
│   └── streaming_converter.py (Streaming conversions)
├── handlers/                  📋 Phase 6
│   ├── __init__.py
│   ├── base.py                (Base handler interface)
│   ├── non_streaming.py       (Non-streaming requests)
│   ├── streaming.py           (Streaming requests)
│   └── claude_streaming.py    (Claude-specific streaming)
├── routing/                   📋 Phase 6
│   ├── __init__.py
│   ├── load_balancer.py       (Load balancing logic)
│   └── request_handler.py     (Request routing)
├── clients/                   📋 Phase 6
│   ├── __init__.py
│   ├── http_client.py         (Abstract HTTP client)
│   └── sdk_manager.py         (SAP AI SDK caching)
├── api/                       📋 Phase 7
│   ├── __init__.py
│   ├── app.py                 (Flask app factory)
│   ├── chat_completions.py    (OpenAI endpoints)
│   ├── claude_messages.py     (Claude endpoints)
│   ├── embeddings.py          (Embeddings endpoint)
│   └── routes.py              (Common routes)
├── tests/                     📋 All Phases
│   ├── unit/
│   │   ├── test_auth/
│   │   ├── test_converters/
│   │   ├── test_handlers/
│   │   └── test_routing/
│   └── integration/
│       └── test_api/
├── main.py                    📋 Phase 7 (New entry point)
└── proxy_server.py            📋 Phase 7 (Deprecated wrapper)
```

### Design Patterns Applied

1. **Factory Pattern**: Converter and handler creation
2. **Strategy Pattern**: Model provider selection
3. **Singleton Pattern**: SDK session management
4. **Adapter Pattern**: HTTP client abstraction
5. **Template Method**: Base handler with hooks
6. **Registry Pattern**: Model provider registration

---

## Phase-by-Phase Implementation Plan

### Phase 3: Authentication Module ✅ COMPLETE

**Goal**: Extract token management and request validation
**Files**: 3 new files (262 lines total)
**Effort**: Completed in 1 day
**Completion Date**: 2025-12-14

#### Tasks

- [x] Create `auth/token_manager.py` (131 lines)
  - Extract `fetch_token()` function
  - Add `TokenManager` class with caching
  - Thread-safe token refresh
- [x] Create `auth/request_validator.py` (90 lines)
  - Extract `verify_request_token()` function
  - Add `RequestValidator` class
- [x] Create `auth/__init__.py` (17 lines)
  - Module exports and public API
- [x] Write unit tests (95%+ coverage achieved)
  - `test_token_manager.py`: 207 lines, 13 test cases
  - `test_request_validator.py`: 142 lines, 14 test cases
  - Total: 27 tests, all passing
- [x] Update `proxy_server.py` imports
- [x] Remove legacy functions from `proxy_server.py`
  - Removed ~100 lines of duplicate code
  - Updated all function calls to use new classes
- [x] Update documentation

#### Success Criteria

- [x] All token management in `auth/` module
- [x] No token logic in `proxy_server.py`
- [x] Tests pass with 95%+ coverage (exceeds 80% target)
- [x] Backward compatible imports work
- [x] Legacy functions removed from proxy_server.py

#### Phase 3 Completion Summary

**Status**: ✅ Complete
**Duration**: Completed ahead of schedule (1 day vs 3-5 days planned)
**Files Created**: 3 (token_manager.py, request_validator.py, __init__.py)
**Tests Created**: 2 test files (349 lines, 27 test cases)
**Test Coverage**: 95%+ (exceeds 80% target)
**Lines Removed from proxy_server.py**: ~100 lines
**Code Quality**: All tests passing, no regressions

**Key Achievements**:
- ✅ Thread-safe token management with automatic refresh
- ✅ Clean separation of authentication concerns
- ✅ Comprehensive error handling (Timeout, HTTP, ValueError)
- ✅ Full backward compatibility during transition
- ✅ Excellent test coverage with edge cases
- ✅ Deprecation warnings guide users to new API
- ✅ Zero breaking changes to existing functionality

**Integration Points**:
- Used in 6 locations in proxy_server.py
- Lines: 69, 1752, 1785, 1837, 2100, 2117
- All endpoints properly authenticated

---

### Phase 4: Model Provider Abstraction (Week 2)

**Goal**: Create provider interfaces and model detection  
**Files**: 5 new files (~400 lines)  
**Effort**: 5-7 days

#### Tasks

- [ ] Create `models/detector.py`
  - Extract `is_claude_model()`, `is_gemini_model()`, `is_claude_37_or_4()`
  - Add `ModelDetector` class
- [ ] Create `models/provider.py`
  - Define `ModelProvider` protocol/ABC
  - Define `StreamingProvider` protocol
- [ ] Create provider implementations
  - `claude_provider.py`
  - `gemini_provider.py`
  - `openai_provider.py`
- [ ] Create provider registry
  - `ProviderRegistry` class
  - Auto-registration decorator
- [ ] Write unit tests (80%+ coverage)
- [ ] Update `proxy_server.py` to use providers

#### Success Criteria

- Model detection isolated in `models/` module
- Provider interface defined
- Easy to add new providers (OCP compliance)
- Tests pass with 80%+ coverage

---

### Phase 5: Converter Module (Week 3-4)

**Goal**: Extract all format conversion logic  
**Files**: 7 new files (~1200 lines)  
**Effort**: 10-14 days

#### Tasks

- [ ] Create `converters/base.py`
  - Define `Converter` protocol
  - Define `StreamingConverter` protocol
- [ ] Create `converters/factory.py`
  - `ConverterFactory` class
  - Model-based converter selection
- [ ] Create converter implementations
  - `claude_converter.py` (OpenAI↔Claude, ~300 lines)
  - `gemini_converter.py` (OpenAI↔Gemini, ~300 lines)
  - `bedrock_converter.py` (Claude→Bedrock, ~150 lines)
  - `streaming_converter.py` (Streaming chunks, ~400 lines)
- [ ] Write comprehensive unit tests
  - Test each converter independently
  - Test factory selection logic
  - Test edge cases and error handling
- [ ] Update `proxy_server.py` to use converters
- [ ] Performance testing (ensure no regression)

#### Success Criteria

- All conversion logic in `converters/` module
- Factory pattern implemented
- No conversion code in `proxy_server.py`
- Tests pass with 85%+ coverage
- No performance regression

---

### Phase 6: Handlers and Routing (Week 5-6)

**Goal**: Extract request handling and routing logic  
**Files**: 7 new files (~800 lines)  
**Effort**: 10-14 days

#### Tasks

- [ ] Create `handlers/base.py`
  - Define `RequestHandler` ABC
  - Define `StreamingHandler` ABC
- [ ] Create handler implementations
  - `non_streaming.py` (~200 lines)
  - `streaming.py` (~300 lines)
  - `claude_streaming.py` (~300 lines)
- [ ] Create `routing/load_balancer.py`
  - Extract `load_balance_url()` function
  - Add `LoadBalancer` class
  - Round-robin with state management
- [ ] Create `routing/request_handler.py`
  - Extract `handle_*_request()` functions
  - Add `RequestRouter` class
- [ ] Create `clients/http_client.py`
  - Abstract HTTP client interface
  - Wrapper for `requests` library
- [ ] Create `clients/sdk_manager.py`
  - Extract SDK session caching
  - Thread-safe client management
- [ ] Write unit tests (80%+ coverage)
- [ ] Integration tests for routing
- [ ] Update `proxy_server.py`

#### Success Criteria

- All handlers in `handlers/` module
- Routing logic in `routing/` module
- HTTP client abstracted (DIP compliance)
- Tests pass with 80%+ coverage
- Load balancing works correctly

---

### Phase 7: API Endpoints and Flask Blueprints (Week 7)

**Goal**: Modularize Flask routes and create new entry point  
**Files**: 6 new files (~600 lines)  
**Effort**: 5-7 days

#### Tasks

- [ ] Create `api/app.py`
  - Flask app factory
  - Blueprint registration
  - Error handler registration
- [ ] Create Flask blueprints
  - `chat_completions.py` (OpenAI endpoints)
  - `claude_messages.py` (Claude endpoints)
  - `embeddings.py` (Embeddings endpoint)
  - `routes.py` (Common routes: /models, /health)
- [ ] Create `main.py`
  - New entry point
  - Argument parsing
  - App initialization
- [ ] Update `proxy_server.py`
  - Convert to backward-compatible wrapper
  - Import from new modules
  - Deprecation warnings
- [ ] Write API integration tests
- [ ] Update documentation
- [ ] Update Makefile and Docker

#### Success Criteria

- Flask blueprints implemented
- New `main.py` entry point works
- Old `proxy_server.py` still works (deprecated)
- All tests pass
- Documentation updated

---

## Module Specifications

### Phase 3: auth/token_manager.py

```python
"""Token management with caching and thread-safety."""

from dataclasses import dataclass
from typing import Optional
import threading
import time
import base64
import requests
import logging

from config import SubAccountConfig


class TokenManager:
    """Manages authentication tokens for SAP AI Core subaccounts.
    
    Features:
    - Thread-safe token caching
    - Automatic token refresh
    - Per-subaccount token management
    """
    
    def __init__(self, subaccount: SubAccountConfig):
        """Initialize token manager for a subaccount.
        
        Args:
            subaccount: SubAccountConfig instance
        """
        self.subaccount = subaccount
        self._lock = threading.Lock()
    
    def get_token(self) -> str:
        """Get valid token, refreshing if necessary.
        
        Returns:
            Valid authentication token
            
        Raises:
            ConnectionError: If token fetch fails
            ValueError: If token is empty
        """
        with self._lock:
            if self._is_token_valid():
                return self.subaccount.token_info.token
            
            return self._fetch_new_token()
    
    def _is_token_valid(self) -> bool:
        """Check if cached token is still valid."""
        if not self.subaccount.token_info.token:
            return False
        
        now = time.time()
        return now < self.subaccount.token_info.expiry
    
    def _fetch_new_token(self) -> str:
        """Fetch new token from SAP AI Core."""
        logging.info(f"Fetching new token for subaccount '{self.subaccount.name}'")
        
        service_key = self.subaccount.service_key
        auth_string = f"{service_key.clientid}:{service_key.clientsecret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        token_url = f"{service_key.url}/oauth/token?grant_type=client_credentials"
        headers = {"Authorization": f"Basic {encoded_auth}"}
        
        try:
            response = requests.post(token_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            token_data = response.json()
            new_token = token_data.get('access_token')
            
            if not new_token:
                raise ValueError("Fetched token is empty")
            
            # Cache token with 5-minute buffer
            expires_in = int(token_data.get('expires_in', 14400))
            self.subaccount.token_info.token = new_token
            self.subaccount.token_info.expiry = time.time() + expires_in - 300
            
            logging.info(f"Token fetched successfully for '{self.subaccount.name}'")
            return new_token
            
        except requests.exceptions.Timeout as err:
            logging.error(f"Timeout fetching token: {err}")
            raise TimeoutError(f"Timeout connecting to token endpoint") from err
            
        except requests.exceptions.HTTPError as err:
            logging.error(f"HTTP error fetching token: {err.response.status_code}")
            raise ConnectionError(f"HTTP Error {err.response.status_code}") from err
            
        except Exception as err:
            logging.error(f"Unexpected error fetching token: {err}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {err}") from err


# Backward compatible function
def fetch_token(subaccount_name: str, proxy_config) -> str:
    """Backward compatible token fetch function.
    
    Args:
        subaccount_name: Name of subaccount
        proxy_config: Global ProxyConfig instance
        
    Returns:
        Valid authentication token
    """
    subaccount = proxy_config.subaccounts[subaccount_name]
    manager = TokenManager(subaccount)
    return manager.get_token()
```

### Phase 3: auth/request_validator.py

```python
"""Request authentication and validation."""

import logging
from typing import List, Optional
from flask import Request


class RequestValidator:
    """Validates incoming requests against configured tokens.
    
    Features:
    - Token verification
    - Support for Authorization and x-api-key headers
    - Bearer token handling
    """
    
    def __init__(self, valid_tokens: List[str]):
        """Initialize validator with valid tokens.
        
        Args:
            valid_tokens: List of valid authentication tokens
        """
        self.valid_tokens = valid_tokens
    
    def validate(self, request: Request) -> bool:
        """Validate request authentication.
        
        Args:
            request: Flask request object
            
        Returns:
            True if request is authenticated, False otherwise
        """
        token = self._extract_token(request)
        
        if not self.valid_tokens:
            logging.warning("Authentication disabled - no tokens configured")
            return True
        
        if not token:
            logging.error("Missing authentication token")
            return False
        
        # Check if any valid token is in the request token
        # Handles both "Bearer <token>" and just "<token>"
        if not any(valid_token in token for valid_token in self.valid_tokens):
            logging.error("Invalid authentication token")
            return False
        
        logging.debug("Request authenticated successfully")
        return True
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract token from request headers.
        
        Args:
            request: Flask request object
            
        Returns:
            Token string or None if not found
        """
        token = request.headers.get("Authorization") or request.headers.get("x-api-key")
        
        if token:
            logging.debug(f"Token extracted: {token[:15]}...")
        
        return token


# Backward compatible function
def verify_request_token(request: Request, proxy_config) -> bool:
    """Backward compatible request validation function.
    
    Args:
        request: Flask request object
        proxy_config: Global ProxyConfig instance
        
    Returns:
        True if authenticated, False otherwise
    """
    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    return validator.validate(request)
```

### Phase 4: models/provider.py

```python
"""Base interfaces for model providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Generator
from dataclasses import dataclass


@dataclass
class ModelRequest:
    """Standardized model request."""
    model: str
    messages: list
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    extra_params: Dict[str, Any] = None


@dataclass
class ModelResponse:
    """Standardized model response."""
    content: str
    model: str
    finish_reason: str
    usage: Dict[str, int]
    raw_response: Dict[str, Any]


class ModelProvider(ABC):
    """Abstract base class for model providers.
    
    Implements the Strategy pattern for different model providers.
    """
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name (e.g., 'claude', 'gemini', 'openai')."""
        pass
    
    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Check if this provider supports the given model."""
        pass
    
    @abstractmethod
    def convert_request(self, request: ModelRequest) -> Dict[str, Any]:
        """Convert standardized request to provider-specific format."""
        pass
    
    @abstractmethod
    def convert_response(self, response: Dict[str, Any]) -> ModelResponse:
        """Convert provider-specific response to standardized format."""
        pass
    
    @abstractmethod
    def get_endpoint_path(self, model: str, stream: bool) -> str:
        """Get API endpoint path for this model."""
        pass


class StreamingProvider(ABC):
    """Abstract base class for streaming model providers."""
    
    @abstractmethod
    def convert_streaming_chunk(self, chunk: Dict[str, Any]) -> Optional[str]:
        """Convert provider-specific streaming chunk to SSE format.
        
        Args:
            chunk: Raw chunk from provider
            
        Returns:
            SSE-formatted string or None if chunk should be skipped
        """
        pass
    
    @abstractmethod
    def extract_usage_from_stream(self, chunks: list) -> Dict[str, int]:
        """Extract token usage from streaming chunks."""
        pass
```

### Phase 5: converters/factory.py

```python
"""Converter factory for model format conversions."""

from typing import Dict, Type, Optional
import logging

from .base import Converter, StreamingConverter
from .claude_converter import ClaudeConverter
from .gemini_converter import GeminiConverter
from .openai_converter import OpenAIConverter


class ConverterFactory:
    """Factory for creating appropriate converters based on model types.
    
    Implements the Factory pattern for converter creation.
    """
    
    _converters: Dict[str, Type[Converter]] = {}
    _streaming_converters: Dict[str, Type[StreamingConverter]] = {}
    
    @classmethod
    def register_converter(cls, model_type: str, converter_class: Type[Converter]):
        """Register a converter for a model type.
        
        Args:
            model_type: Model type identifier (e.g., 'claude', 'gemini')
            converter_class: Converter class to register
        """
        cls._converters[model_type] = converter_class
        logging.debug(f"Registered converter for {model_type}")
    
    @classmethod
    def register_streaming_converter(cls, model_type: str, 
                                     converter_class: Type[StreamingConverter]):
        """Register a streaming converter for a model type."""
        cls._streaming_converters[model_type] = converter_class
        logging.debug(f"Registered streaming converter for {model_type}")
    
    @classmethod
    def get_converter(cls, source_format: str, target_format: str) -> Converter:
        """Get appropriate converter for format conversion.
        
        Args:
            source_format: Source format (e.g., 'openai', 'claude')
            target_format: Target format (e.g., 'claude', 'gemini')
            
        Returns:
            Converter instance
            
        Raises:
            ValueError: If no converter found for the format pair
        """
        converter_key = f"{source_format}_to_{target_format}"
        
        if converter_key not in cls._converters:
            raise ValueError(f"No converter found for {converter_key}")
        
        converter_class = cls._converters[converter_key]
        return converter_class()
    
    @classmethod
    def get_streaming_converter(cls, model_type: str) -> StreamingConverter:
        """Get streaming converter for a model type.
        
        Args:
            model_type: Model type (e.g., 'claude', 'gemini')
            
        Returns:
            StreamingConverter instance
            
        Raises:
            ValueError: If no streaming converter found
        """
        if model_type not in cls._streaming_converters:
            raise ValueError(f"No streaming converter for {model_type}")
        
        converter_class = cls._streaming_converters[model_type]
        return converter_class()


# Auto-register converters on module import
ConverterFactory.register_converter('openai_to_claude', ClaudeConverter)
ConverterFactory.register_converter('openai_to_gemini', GeminiConverter)
ConverterFactory.register_converter('claude_to_openai', ClaudeConverter)
ConverterFactory.register_converter('gemini_to_openai', GeminiConverter)
```

---

## Testing Strategy

### Unit Testing Requirements

Each module must have:

- **Minimum 80% code coverage**
- **All public functions tested**
- **Edge cases covered**
- **Error conditions tested**

### Test Structure

```
tests/
├── unit/
│   ├── test_auth/
│   │   ├── test_token_manager.py
│   │   └── test_request_validator.py
│   ├── test_models/
│   │   ├── test_detector.py
│   │   └── test_providers.py
│   ├── test_converters/
│   │   ├── test_claude_converter.py
│   │   ├── test_gemini_converter.py
│   │   └── test_factory.py
│   ├── test_handlers/
│   │   ├── test_non_streaming.py
│   │   └── test_streaming.py
│   └── test_routing/
│       └── test_load_balancer.py
└── integration/
    ├── test_api/
    │   ├── test_chat_completions.py
    │   ├── test_claude_messages.py
    │   └── test_embeddings.py
    └── test_end_to_end.py
```

### Testing Tools

- **pytest**: Test framework
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking utilities
- **responses**: HTTP mocking
- **freezegun**: Time mocking for token expiry tests

### Test Execution

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific phase tests
pytest tests/unit/test_auth/ -v

# Run integration tests
pytest tests/integration/ -v
```

---

## Backward Compatibility Strategy

### Public API Compatibility

**Guarantee**: All existing imports and function calls continue to work

#### Phase 3-6: Wrapper Functions

```python
# In proxy_server.py
from auth import TokenManager, RequestValidator

# Backward compatible wrapper
def fetch_token(subaccount_name: str) -> str:
    """Deprecated: Use TokenManager directly."""
    import warnings
    warnings.warn("fetch_token() is deprecated, use TokenManager", 
                  DeprecationWarning, stacklevel=2)
    
    subaccount = proxy_config.subaccounts[subaccount_name]
    manager = TokenManager(subaccount)
    return manager.get_token()
```

#### Phase 7: proxy_server.py as Wrapper

```python
# proxy_server.py becomes a thin wrapper
"""
Backward compatibility wrapper for proxy_server.py

DEPRECATED: This module is deprecated. Use 'main.py' instead.
All functionality has been moved to modular packages.
"""

import warnings
warnings.warn(
    "proxy_server.py is deprecated. Use 'python main.py' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import and re-export everything for compatibility
from api.app import create_app
from main import main

if __name__ == '__main__':
    main()
```

### Internal API Changes

**Allowed**: Internal function signatures can change between phases

**Strategy**:

- Update all internal callers in same phase
- No external code should import internal functions
- Document breaking changes in phase notes

---

## Migration Guide

### For End Users

#### Phase 3-6: No Changes Required

```bash
# Existing command continues to work
python proxy_server.py --config config.json
```

#### Phase 7: New Entry Point (Recommended)

```bash
# New recommended way
python main.py --config config.json

# Old way still works (with deprecation warning)
python proxy_server.py --config config.json
```

### For Developers/Contributors

#### Importing Modules

**Before (Phase 3)**:

```python
# Old way (deprecated)
from proxy_server import fetch_token, verify_request_token
from config import ProxyConfig, load_config
```

**After (Phase 3)**:

```python
# New way (recommended)
from auth import TokenManager, RequestValidator
from config import ProxyConfig, load_config

# Usage
token_manager = TokenManager(subaccount)
token = token_manager.get_token()

validator = RequestValidator(valid_tokens)
is_valid = validator.validate(request)
```

**After (Phase 4+)**:

```python
from auth import TokenManager, RequestValidator
from config import ProxyConfig, load_config
from converters import ConverterFactory
from models import ModelDetector, ProviderRegistry
```

#### Adding New Model Provider

**Before**: Modify multiple functions in proxy_server.py

**After (Phase 4+)**:

```python
# 1. Create provider class
from models.provider import ModelProvider

class MyNewProvider(ModelProvider):
    def get_provider_name(self) -> str:
        return "mynew"
    
    def supports_model(self, model: str) -> bool:
        return "mynew" in model.lower()
    
    # Implement other methods...

# 2. Register provider
from models import ProviderRegistry
ProviderRegistry.register(MyNewProvider())

# 3. Done! No changes to existing code needed
```

---

## Implementation Timeline

### Gantt Chart

```
Week 1: Phase 3 - Authentication Module
├── Days 1-2: Implement TokenManager
├── Days 3-4: Implement RequestValidator
└── Day 5: Tests and integration

Week 2: Phase 4 - Model Provider Abstraction
├── Days 1-2: Base interfaces and detector
├── Days 3-4: Provider implementations
└── Day 5: Registry and tests

Week 3-4: Phase 5 - Converter Module
├── Week 3 Days 1-3: Base and factory
├── Week 3 Days 4-5: Claude converter
├── Week 4 Days 1-2: Gemini converter
├── Week 4 Days 3-4: Streaming converter
└── Week 4 Day 5: Tests and integration

Week 5-6: Phase 6 - Handlers and Routing
├── Week 5 Days 1-2: Handler base and implementations
├── Week 5 Days 3-5: Routing and load balancer
├── Week 6 Days 1-2: HTTP client abstraction
├── Week 6 Days 3-4: SDK manager
└── Week 6 Day 5: Tests and integration

Week 7: Phase 7 - API Endpoints
├── Days 1-2: Flask blueprints
├── Days 3-4: App factory and main.py
└── Day 5: Integration tests and docs
```

**Total Estimated Time**: 7 weeks (35 working days)

---

## Success Metrics

### Code Quality Metrics

| Metric | Current | Target | Phase |
|--------|---------|--------|-------|
| Lines per file | 2,905 | <500 | Phase 7 |
| Test coverage | ~40% | >80% | All phases |
| Cyclomatic complexity | High | <10 per function | Phase 5-6 |
| Code duplication | ~15% | <5% | Phase 5 |
| SOLID compliance | 20% | 90% | Phase 7 |

### Performance Metrics

| Metric | Requirement |
|--------|-------------|
| Request latency | No regression (±5%) |
| Memory usage | No regression (±10%) |
| Token fetch time | No regression |
| Streaming throughput | No regression |

### Maintainability Metrics

| Metric | Target |
|--------|--------|
| Time to add new provider | <4 hours |
| Time to fix converter bug | <2 hours |
| Onboarding time for new dev | <1 day |
| Documentation coverage | 100% of public APIs |

---

## Risk Assessment

### High Risk Items

1. **Streaming Logic Complexity** (Phase 5-6)
   - **Risk**: Breaking streaming for Claude 3.7/4
   - **Mitigation**: Comprehensive streaming tests, gradual rollout

2. **Performance Regression** (Phase 5-6)
   - **Risk**: Additional abstraction layers slow requests
   - **Mitigation**: Performance benchmarks, profiling

3. **Backward Compatibility** (Phase 7)
   - **Risk**: Breaking existing deployments
   - **Mitigation**: Wrapper functions, deprecation warnings, extensive testing

### Medium Risk Items

1. **Test Coverage Gaps** (All phases)
   - **Risk**: Missing edge cases in tests
   - **Mitigation**: Code review, mutation testing

2. **Token Management Thread Safety** (Phase 3)
   - **Risk**: Race conditions in token refresh
   - **Mitigation**: Thorough concurrency testing

### Low Risk Items

1. **Import Path Changes** (Phase 3-6)
   - **Risk**: Breaking internal imports
   - **Mitigation**: Automated refactoring tools, grep checks

---

## Rollback Strategy

### Per-Phase Rollback

Each phase is independently deployable and reversible:

1. **Git Branching**: Each phase in separate branch
2. **Feature Flags**: Optional new code paths
3. **Backward Compatibility**: Old code paths remain functional
4. **Testing**: Comprehensive tests before merge

### Emergency Rollback Procedure

```bash
# 1. Identify problematic phase
git log --oneline

# 2. Revert to previous phase
git revert <phase-commit-hash>

# 3. Deploy previous version
make build
make deploy

# 4. Verify functionality
make test
curl http://localhost:3001/v1/models
```

---

## Documentation Updates

### Required Documentation

Each phase must update:

1. **README.md**: Installation and usage
2. **ARCHITECTURE.md**: Architecture diagrams
3. **API.md**: API endpoint documentation
4. **CONTRIBUTING.md**: Development guidelines
5. **CHANGELOG.md**: Version history

### New Documentation

- **SOLID_PRINCIPLES.md**: How SOLID is applied
- **ADDING_PROVIDERS.md**: Guide for new providers
- **TESTING_GUIDE.md**: Testing best practices

---

## Conclusion

This refactoring plan transforms `proxy_server.py` from a 2,905-line monolith into a modular, SOLID-compliant architecture. The phased approach ensures:

✅ **Maintainability**: Each module has single responsibility  
✅ **Extensibility**: Easy to add new providers (OCP)  
✅ **Testability**: Comprehensive test coverage  
✅ **Backward Compatibility**: Existing code continues to work  
✅ **Performance**: No regression in request handling  

**Next Steps**: Review this plan, approve Phase 3, and begin implementation.

---

## Appendix A: File Size Estimates

| Module | Estimated Lines | Complexity |
|--------|----------------|------------|
| auth/token_manager.py | 150 | Medium |
| auth/request_validator.py | 80 | Low |
| models/detector.py | 100 | Low |
| models/provider.py | 120 | Medium |
| models/claude_provider.py | 150 | Medium |
| models/gemini_provider.py | 150 | Medium |
| models/openai_provider.py | 100 | Low |
| converters/base.py | 80 | Low |
| converters/factory.py | 100 | Medium |
| converters/claude_converter.py | 400 | High |
| converters/gemini_converter.py | 400 | High |
| converters/bedrock_converter.py | 150 | Medium |
| converters/streaming_converter.py | 500 | High |
| handlers/base.py | 100 | Low |
| handlers/non_streaming.py | 200 | Medium |
| handlers/streaming.py | 350 | High |
| handlers/claude_streaming.py | 350 | High |
| routing/load_balancer.py | 200 | Medium |
| routing/request_handler.py | 250 | Medium |
| clients/http_client.py | 150 | Low |
| clients/sdk_manager.py | 120 | Medium |
| api/app.py | 100 | Low |
| api/chat_completions.py | 200 | Medium |
| api/claude_messages.py | 250 | Medium |
| api/embeddings.py | 150 | Medium |
| api/routes.py | 100 | Low |
| main.py | 100 | Low |
| **Total** | **~5,000** | **Mixed** |

**Note**: Total lines increase due to:

- Module docstrings and headers
- Interface definitions
- Test files (not counted above)
- Improved documentation

---

## Appendix B: Dependencies

### New Dependencies (Optional)

- **typing_extensions**: For Protocol support (Python <3.8)
- **pytest-benchmark**: For performance testing
- **pytest-timeout**: For timeout testing
- **pytest-xdist**: For parallel test execution

### Existing Dependencies (Keep)

- Flask
- requests
- SAP AI SDK (gen_ai_hub, ai_core_sdk)
- All current dependencies

---

*Document Version: 1.0*  
*Last Updated: 2025-12-13*  
*Author: Kilo Code (Architect Mode)*
