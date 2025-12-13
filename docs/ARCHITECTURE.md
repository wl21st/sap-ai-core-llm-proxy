# SAP AI Core LLM Proxy - Architecture Documentation

**Version**: 0.1.16  
**Last Updated**: 2025-12-13  
**Status**: Production

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Current Problems](#current-problems)
4. [Technical Debt](#technical-debt)
5. [Backlog Summary](#backlog-summary)

---

## System Overview

The SAP AI Core LLM Proxy is a Flask-based proxy server that transforms SAP AI Core LLM APIs into OpenAI-compatible APIs. It supports multiple model providers (Claude, Gemini, OpenAI) and implements load balancing across multiple SAP AI Core subaccounts.

### Key Features

- **Multi-Model Support**: Claude 4.x, Gemini 2.5, GPT-4o, GPT-o3
- **Multi-SubAccount Load Balancing**: Distributes requests across multiple SAP AI Core accounts
- **API Compatibility**: OpenAI Chat Completions API, Anthropic Messages API
- **Streaming Support**: Server-Sent Events (SSE) for real-time responses
- **Token Management**: Automatic token caching and refresh
- **Format Conversion**: Automatic request/response format conversion between providers

---

## Architecture Diagrams

### 1. System Architecture

```mermaid
graph TB
    subgraph "Client Applications"
        A[Cursor IDE]
        B[Claude Code]
        C[Cline]
        D[Cherry Studio]
        E[Custom Apps]
    end

    subgraph "Proxy Server - proxy_server.py"
        F[Flask Application]
        G[Authentication Layer]
        H[Load Balancer]
        I[Token Manager]
        J[Format Converters]
        K[Streaming Handlers]
        L[SDK Client Cache]
    end

    subgraph "SAP AI Core Backend"
        M[SubAccount 1]
        N[SubAccount 2]
        O[SubAccount N]
        
        M --> M1[Claude 4.5]
        M --> M2[GPT-4o]
        N --> N1[Gemini 2.5]
        N --> N2[Claude 4.5]
        O --> O1[GPT-o3]
    end

    A --> F
    B --> F
    C --> F
    D --> F
    E --> F
    
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L
    
    L --> M
    L --> N
    L --> O
    
    style F fill:#4CAF50
    style G fill:#2196F3
    style H fill:#FF9800
    style I fill:#9C27B0
    style J fill:#F44336
    style K fill:#00BCD4
    style L fill:#FFEB3B
```

### 2. Request Flow - OpenAI Chat Completions

```mermaid
sequenceDiagram
    participant Client
    participant Flask as Flask App
    participant Auth as Authentication
    participant Router as Load Balancer
    participant Token as Token Manager
    participant Conv as Format Converter
    participant SAP as SAP AI Core
    
    Client->>Flask: POST /v1/chat/completions
    Flask->>Auth: verify_request_token()
    Auth-->>Flask: Token Valid
    
    Flask->>Router: load_balance_url(model)
    Router-->>Flask: selected_url, subaccount
    
    Flask->>Token: fetch_token(subaccount)
    Token->>SAP: POST /oauth/token
    SAP-->>Token: access_token
    Token-->>Flask: cached_token
    
    Flask->>Conv: convert_openai_to_claude()
    Conv-->>Flask: claude_payload

    Flask->>SAP: POST /invoke (with token)
    SAP-->>Flask: claude_response
    
    Flask->>Conv: convert_claude_to_openai()
    Conv-->>Flask: openai_response
    
    Flask-->>Client: 200 OK (OpenAI format)
```

### 3. Request Flow - Streaming

```mermaid
sequenceDiagram
    participant Client
    participant Flask as Flask App
    participant Stream as Streaming Handler
    participant SAP as SAP AI Core
    
    Client->>Flask: POST /v1/chat/completions (stream=true)
    Flask->>Flask: Authentication & Routing
    
    Flask->>Stream: generate_streaming_response()
    Stream->>SAP: POST /converse-stream

    loop For each chunk
        SAP-->>Stream: SSE chunk
        Stream->>Stream: convert_claude37_chunk_to_openai()
        Stream-->>Client: data: {...}\n\n
    end
    
    SAP-->>Stream: metadata chunk (usage)
    Stream->>Stream: Extract token usage
    Stream-->>Client: data: [DONE]\n\n

    Note over Stream: Log token usage
```

### 4. Data Model

```mermaid
classDiagram
    class ProxyConfig {
        +Dict~str,SubAccountConfig~ subaccounts
        +List~str~ secret_authentication_tokens
        +int port
        +str host
        +Dict~str,List[str]~ model_to_subaccounts
        +initialize()
        +build_model_mapping()
    }
    
    class SubAccountConfig {
        +str name
        +str resource_group
        +str service_key_json
        +Dict~str,List[str]~ deployment_models
        +ServiceKey service_key
        +TokenInfo token_info
        +Dict~str,List[str]~ normalized_models
        +load_service_key()
        +normalize_model_names()
    }
    
    class ServiceKey {
        +str clientid
        +str clientsecret
        +str url
        +str identityzoneid
    }
    
    class TokenInfo {
        +Optional~str~ token
        +float expiry
        +Lock lock
    }
    
    ProxyConfig "1" *-- "many" SubAccountConfig
    SubAccountConfig "1" *-- "1" ServiceKey
    SubAccountConfig "1" *-- "1" TokenInfo
```

### 5. Component Architecture

```mermaid
graph LR
    subgraph "Core Components - 2991 lines"
        A[Configuration<br/>Management]
        B[Authentication<br/>& Token Mgmt]
        C[Load Balancing<br/>& Routing]
        D[Format<br/>Converters]
        E[Streaming<br/>Handlers]
        F[API<br/>Endpoints]
    end
    
    subgraph "External Dependencies"
        G[Flask]
        H[Requests]
        I[SAP AI SDK]
        J[Threading]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    
    F --> G
    D --> H
    E --> I
    B --> J
    
    style A fill:#FFE082
    style B fill:#81C784
    style C fill:#64B5F6
    style D fill:#FF8A65
    style E fill:#BA68C8
    style F fill:#4DB6AC
```

### 6. Load Balancing Strategy

```mermaid
graph TD
    A[Client Request<br/>model=claude-4.5-sonnet] --> B{Model Available?}
    B -->|Yes| C[Get SubAccounts<br/>with Model]
    B -->|No| D[Try Fallback Models]
    D --> C
    
    C --> E[Round-Robin<br/>SubAccount Selection]
    E --> F[SubAccount 1<br/>Counter: 0]
    E --> G[SubAccount 2<br/>Counter: 1]
    E --> H[SubAccount N<br/>Counter: N]
    
    F --> I{Multiple URLs?}
    G --> I
    H --> I
    
    I -->|Yes| J[Round-Robin<br/>URL Selection]
    I -->|No| K[Use Single URL]
    
    J --> L[Selected URL]
    K --> L
    
    L --> M[Increment Counters]
    M --> N[Return URL +<br/>SubAccount Info]
    
    style A fill:#E3F2FD
    style C fill:#FFF9C4
    style E fill:#C8E6C9
    style J fill:#FFCCBC
    style N fill:#B2DFDB
```

### 7. Token Management Flow

```mermaid
stateDiagram-v2
    [*] --> CheckCache: fetch_token(subaccount)
    
    CheckCache --> ValidToken: Token exists & not expired
    CheckCache --> FetchNew: Token missing or expired
    
    ValidToken --> [*]: Return cached token
    
    FetchNew --> BuildAuth: Encode credentials
    BuildAuth --> RequestToken: POST /oauth/token
    
    RequestToken --> Success: 200 OK
    RequestToken --> Timeout: Connection timeout
    RequestToken --> HTTPError: 4xx/5xx
    RequestToken --> NetworkError: Network failure

    Success --> CacheToken: Store with expiry
    CacheToken --> [*]: Return new token
    
    Timeout --> ClearCache: Set token=None
    HTTPError --> ClearCache
    NetworkError --> ClearCache
    ClearCache --> [*]: Raise error
    
    note right of CacheToken
        Expiry = now + expires_in - 300s
        (5 minute buffer)
    end note
```

### 8. Format Conversion Pipeline

```mermaid
graph LR
    subgraph "Input Formats"
        A1[OpenAI Format]
        A2[Claude Format]
        A3[Gemini Format]
    end
    
    subgraph "Converters"
        B1[convert_openai_to_claude]
        B2[convert_openai_to_claude37]
        B3[convert_openai_to_gemini]
        B4[convert_claude_to_openai]
        B5[convert_claude37_to_openai]
        B6[convert_gemini_to_openai]
        B7[convert_claude_request_to_openai]
        B8[convert_claude_request_to_gemini]
    end
    
    subgraph "Output Formats"
        C1[Claude API]
        C2[Gemini API]
        C3[OpenAI API]
    end
    
    A1 --> B1
    A1 --> B2
    A1 --> B3
    A2 --> B4
    A2 --> B5
    A2 --> B7
    A2 --> B8
    A3 --> B6
    
    B1 --> C1
    B2 --> C1
    B3 --> C2
    B4 --> C3
    B5 --> C3
    B6 --> C3
    B7 --> C3
    B8 --> C2
    
    style B1 fill:#FFCDD2
    style B2 fill:#F8BBD0
    style B3 fill:#E1BEE7
    style B4 fill:#D1C4E9
    style B5 fill:#C5CAE9
    style B6 fill:#BBDEFB
    style B7 fill:#B3E5FC
    style B8 fill:#B2EBF2
```

---

## Current Problems

### 1. Monolithic Architecture (CRITICAL)

**Location**: [`proxy_server.py`](../proxy_server.py) (2991 lines)

**Issue**: Single file contains all functionality - configuration, authentication, routing, conversion, streaming, and API endpoints.

**Impact**:
- Difficult to maintain and test
- High coupling between components
- Hard to add new features
- Violates Single Responsibility Principle

**Evidence**:
```python
# All in one file:
- Configuration management (lines 23-95)
- Token management (lines 322-401)
- Authentication (lines 403-422)
- Format converters (lines 424-1592)
- Load balancing (lines 1593-1687)
- API endpoints (lines 1815-2331)
- Streaming handlers (lines 2411-2906)
```

### 2. Hardcoded Model Normalization (HIGH)

**Location**: [`proxy_server.py:56-67`](../proxy_server.py#L56-L67)

**Issue**: Model name normalization is disabled with hardcoded `if False:` statement.

```python
def normalize_model_names(self):
    """Normalize model names by removing prefixes like 'anthropic--'"""
    if False:  # ❌ Hardcoded - should be configurable
        self.normalized_models = {
            key.replace("anthropic--", ""): value
            for key, value in self.deployment_models.items()
        }
```

**Impact**:
- Cannot normalize model names without code changes
- Inconsistent model naming across deployments
- Requires code modification for different naming conventions

### 3. No Automated Testing (CRITICAL)

**Location**: Project-wide

**Issue**: Zero test coverage - no unit tests, integration tests, or API tests.

**Impact**:
- Cannot safely refactor code
- Risk of regressions with every change
- Difficult to validate bug fixes
- No confidence in deployments

**Missing Tests**:
- Configuration loading and validation
- Token management and caching
- Format conversion functions (8+ converters)
- Load balancing logic
- Streaming response handling
- API endpoint behavior

### 4. Inconsistent Configuration Naming (MEDIUM)

**Location**: [`proxy_server.py:316-320`](../proxy_server.py#L316-L320), `config.json`

**Issue**: Configuration file named `config.json` but should be `profile.json` for clarity.

**Impact**:
- Confusing naming convention
- Doesn't reflect multi-profile nature
- Inconsistent with industry standards

### 5. Limited Logging Configuration (HIGH)

**Location**: [`proxy_server.py:261-281`](../proxy_server.py#L261-L281)

**Issue**: Logging is hardcoded and not configurable.

```python
# Hardcoded logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
```

**Impact**:
- Cannot adjust log levels without code changes
- No structured logging
- No log rotation configuration
- No separate log files for different components

### 6. No Connection Management (HIGH)

**Location**: Throughout request handling code

**Issue**: No connection pooling, retry logic, or circuit breaker pattern.

**Impact**:
- Poor performance (new connection per request)
- No automatic retry on transient failures
- No protection against cascading failures
- Hardcoded timeouts

### 7. Sensitive Data in Logs (SECURITY)

**Location**: Multiple logging statements

**Issue**: Tokens and credentials may be logged.

```python
logging.info(f"verify_request_token, Token received in request: {token[:15]}...")
```

**Impact**:
- Security risk if logs are compromised
- Compliance issues (GDPR, SOC2)
- No automatic redaction

### 8. No Health Monitoring (MEDIUM)

**Location**: Missing functionality

**Issue**: No health checks, metrics, or performance monitoring.

**Impact**:
- Cannot detect service degradation
- No visibility into backend performance
- Difficult to troubleshoot issues
- No alerting capabilities

---

## Technical Debt

### 1. SOLID Principles Violations

**Severity**: HIGH  
**Effort to Fix**: 2-4 weeks

**Violations**:

1. **Single Responsibility Principle (SRP)**
   - `proxy_server.py` handles 7+ responsibilities
   - Functions like `proxy_openai_stream()` (76 lines) do too much
   - `generate_streaming_response()` (258 lines) is too complex

2. **Open/Closed Principle (OCP)**
   - Adding new model providers requires modifying existing code
   - No plugin architecture for converters
   - Tightly coupled conversion logic

3. **Dependency Inversion Principle (DIP)**
   - Direct dependencies on Flask, requests, SAP SDK
   - No abstraction layer for external APIs
   - Hard to mock for testing

**Recommended Refactoring**:
```
src/
├── config/          # Configuration management
├── auth/            # Authentication & tokens
├── routing/         # Load balancing
├── converters/      # Format converters (pluggable)
├── streaming/       # Streaming handlers
├── api/             # API endpoints (Flask blueprints)
└── clients/         # External API clients
```

### 2. Global State Management

**Severity**: MEDIUM  
**Effort to Fix**: 1 week

**Issues**:
```python
# Global variables
proxy_config = ProxyConfig()  # Line 98
_sdk_session = None           # Line 107
_bedrock_clients = {}         # Line 109
token = None                  # Line 284
```

**Impact**:
- Thread safety concerns
- Difficult to test
- Hidden dependencies
- State pollution in tests

### 3. Error Handling Inconsistency

**Severity**: MEDIUM  
**Effort to Fix**: 1 week

**Issues**:
- Mix of exception types (ValueError, ConnectionError, RuntimeError)
- Inconsistent error response formats
- Some errors not logged properly
- No error categorization

**Example**:
```python
# Different error handling patterns
return jsonify({"error": "Unauthorized"}), 401
return jsonify({"type": "error", "error": {...}}), 400
raise ValueError("Model not found")
```

### 4. Code Duplication

**Severity**: MEDIUM  
**Effort to Fix**: 1-2 weeks

**Duplicated Logic**:
- Model type detection (`is_claude_model`, `is_gemini_model`, `is_claude_37_or_4`)
- Streaming chunk conversion (similar patterns for Claude/Gemini/OpenAI)
- Error handling in multiple endpoints
- Token usage logging (repeated 3+ times)

### 5. Magic Numbers and Strings

**Severity**: LOW  
**Effort to Fix**: 2-3 days

**Examples**:
```python
timeout=600                    # Should be configurable
backupCount=7                  # Should be in config
max_tokens=4096000            # Should be constant
"bedrock-2023-05-31"          # Should be constant
```

### 6. Incomplete Documentation

**Severity**: MEDIUM  
**Effort to Fix**: 1 week

**Missing**:
- API documentation (OpenAPI/Swagger)
- Architecture diagrams (now addressed in this document)
- Deployment guide
- Troubleshooting guide
- Performance tuning guide

### 7. No Observability

**Severity**: HIGH  
**Effort to Fix**: 2 weeks

**Missing**:
- Structured logging
- Distributed tracing
- Metrics collection (Prometheus)
- Performance profiling
- Request correlation IDs

---

## Backlog Summary

### High Priority (Must Have)

| # | Item | Effort | Risk | Impact |
|---|------|--------|------|--------|
| 1 | Fix Model Name Normalization | 1-3d | Low | Medium |
| 2 | Add Automated Test Cases | 2-4w | Low | Critical |
| 3 | Standardize Config File Naming | 1-3d | Medium | Low |
| 4 | Add Transport Logging | 1-2w | Low | High |
| 5 | Make Logging Configurable | 1-3d | Low | High |

**Total Effort**: ~5-7 weeks

### Medium Priority (Should Have)

| # | Item | Effort | Risk | Impact |
|---|------|--------|------|--------|
| 6 | Refactor to SOLID Principles | 2-4w | High | Critical |
| 7 | Generate profile.json Tool | 1-2w | Low | Medium |
| 8 | Abbreviated Request Logging | 1-3d | Low | Medium |
| 9 | Connection Management | 1-2w | Medium | High |
| 10 | Performance Monitoring | 1-2w | Low | High |

**Total Effort**: ~6-10 weeks

### Low Priority (Nice to Have)

| # | Item | Effort | Risk | Impact |
|---|------|--------|------|--------|
| 11 | Metrics & Monitoring | 1-2w | Low | Medium |
| 12 | Rate Limiting | 1-3d | Low | Medium |
| 13 | Request Caching | 1-2w | Medium | Medium |
| 14 | WebSocket Support | 2-4w | High | Low |

**Total Effort**: ~5-9 weeks

### Prioritization Matrix

```mermaid
graph TD
    subgraph "Critical - Do First"
        A[Automated Tests]
        B[SOLID Refactoring]
        C[Connection Mgmt]
    end
    
    subgraph "High Priority - Do Soon"
        D[Logging Config]
        E[Transport Logging]
        F[Performance Monitor]
    end
    
    subgraph "Medium Priority - Plan"
        G[Model Normalization]
        H[Config Naming]
        I[Profile Generator]
    end
    
    subgraph "Low Priority - Future"
        J[Rate Limiting]
        K[Caching]
        L[WebSocket]
    end
    
    style A fill:#FF5252
    style B fill:#FF5252
    style C fill:#FF5252
    style D fill:#FFA726
    style E fill:#FFA726
    style F fill:#FFA726
    style G fill:#FFEE58
    style H fill:#FFEE58
    style I fill:#FFEE58
    style J fill:#66BB6A
    style K fill:#66BB6A
    style L fill:#66BB6A
```

### Recommended Implementation Order

**Phase 1: Foundation (Weeks 1-4)**
1. Add automated test framework and initial tests
2. Make logging configurable
3. Fix model name normalization

**Phase 2: Stability (Weeks 5-8)**
4. Implement connection management with retry logic
5. Add transport logging with rotation
6. Add performance monitoring

**Phase 3: Architecture (Weeks 9-16)**
7. Refactor to SOLID principles (incremental)
8. Standardize configuration naming
9. Create profile generator tool

**Phase 4: Enhancement (Weeks 17+)**
10. Add metrics and monitoring endpoints
11. Implement rate limiting
12. Add request caching
13. Consider WebSocket support

---

## Metrics & KPIs

### Current State

- **Lines of Code**: 2,991 (single file)
- **Test Coverage**: 0%
- **Cyclomatic Complexity**: High (functions >50 lines)
- **Technical Debt Ratio**: ~40% (estimated)
- **SOLID Compliance**: Low

### Target State (6 months)

- **Lines of Code**: <500 per file
- **Test Coverage**: >80%
- **Cyclomatic Complexity**: Medium (functions <30 lines)
- **Technical Debt Ratio**: <15%
- **SOLID Compliance**: High

---

## Conclusion

The SAP AI Core LLM Proxy is a functional system that successfully bridges multiple LLM providers with SAP AI Core. However, it suffers from significant technical debt due to its monolithic architecture and lack of testing.

**Key Recommendations**:

1. **Immediate**: Add automated tests to prevent regressions
2. **Short-term**: Implement connection management and monitoring
3. **Medium-term**: Refactor to SOLID principles for maintainability
4. **Long-term**: Add advanced features (caching, rate limiting, WebSocket)

**Success Criteria**:
- All critical paths have test coverage
- Code is organized into logical modules
- Performance is monitored and optimized
- System is production-ready with proper observability

---

**Document Version**: 1.0  
**Next Review**: 2025-01-13  
**Maintained By**: Architecture Team