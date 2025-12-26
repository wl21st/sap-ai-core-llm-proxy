# SAP AI Core LLM Proxy - Development Backlog

This document tracks planned improvements, features, and technical debt items for the SAP AI Core LLM Proxy project.
**Last Updated**: 2025-12-13

**Risk Levels**:

- **Low**: Minimal impact on existing functionality, well-understood changes
- **Medium**: Some impact on existing code, requires careful testing
- **High**: Significant architectural changes, requires extensive testing and migration

---

- [Backlog Overview](#backlog-overview)
- [High Priority](#high-priority)
  - [1. Fix Model Name Normalization Configuration](#1-fix-model-name-normalization-configuration)
  - [2. Add Automated Test Cases](#2-add-automated-test-cases)
  - [3. Standardize Configuration File Naming](#3-standardize-configuration-file-naming)
  - [4. Add Transport Logging with Timestamp Rotation](#4-add-transport-logging-with-timestamp-rotation)
  - [5. Make Logging Configurable](#5-make-logging-configurable)
  - [6. Add Automatic HTTP 429 Throttling Handler](#6-add-automatic-http-429-throttling-handler)
  - [7. Split proxy_server.py into Multiple Modules](#7-split-proxy_serverpy-into-multiple-modules)
  - [8. Fix Claude Model ID Mapping](#8-fix-claude-model-id-mapping)
- [Medium Priority](#medium-priority)
  - [9. Refactor Python Classes to Follow SOLID Principles](#9-refactor-python-classes-to-follow-solid-principles)
  - [10. Generate profile.json from SAP AI Core Service Connection](#10-generate-profilejson-from-sap-ai-core-service-connection)
  - [11. Add Abbreviated Request/Response Logging](#11-add-abbreviated-requestresponse-logging)
  - [12. Implement Stable Connection Management and Reconnect](#12-implement-stable-connection-management-and-reconnect)
  - [13. Add SAP AI Service Model Transport Speed and Health Monitoring](#13-add-sap-ai-service-model-transport-speed-and-health-monitoring)
- [Low Priority / Future Enhancements](#low-priority--future-enhancements)
  - [14. Add Metrics and Monitoring](#14-add-metrics-and-monitoring)
  - [15. Add Rate Limiting](#15-add-rate-limiting)
  - [16. Add Request Caching](#16-add-request-caching)
  - [17. Add WebSocket Support](#17-add-websocket-support)
- [Completed Items](#completed-items)
- [Notes](#notes)

---

## Backlog Overview

| # | Item | Priority | Effort | Risk | Status |
|---|------|----------|--------|------|--------|
| 1 | [Fix Model Name Normalization Configuration](#1-fix-model-name-normalization-configuration) | High | Small (1-3d) | Low | 🔴 To Do |
| 2 | [Add Automated Test Cases](#2-add-automated-test-cases) | High | Large (2-4w) | Low | 🔴 To Do |
| 3 | [Security filter to prevent uploading of the sensitive information to LLM](#3-security-filter-to-prevent-uploading-of-the-sensitive-information-to-llm) | High | Small (1-3d) | Medium | 🔴 To Do |
| 4 | [Standardize Configuration File Naming](#4-standardize-configuration-file-naming) | High | Small (1-3d) | Medium | 🔴 To Do |
| 5 | [Add Transport Logging with Timestamp Rotation](#5-add-transport-logging-with-timestamp-rotation) | High | Medium (1-2w) | Low | 🔴 To Do |
| 6 | [Make Logging Configurable](#6-make-logging-configurable) | High | Small (1-3d) | Low | 🔴 To Do |
| 6 | [Add Automatic HTTP 429 Throttling Handler](#6-add-automatic-http-429-throttling-handler) | High | Small (1-3d) | Low | 🔴 To Do |
| 7 | [Split proxy_server.py into Multiple Modules](#7-split-proxy_serverpy-into-multiple-modules) | High | Medium (1-2w) | Medium | 🔴 To Do |
| 8 | [Fix Claude Model ID Mapping](#8-fix-claude-model-id-mapping) | High | Small (1-3d) | Low | 🔴 To Do |
| 9 | [Refactor Python Classes to Follow SOLID Principles](#9-refactor-python-classes-to-follow-solid-principles) | Medium | Large (2-4w) | High | 🔴 To Do |
| 10 | [Generate profile.json from SAP AI Core Service Connection](#10-generate-profilejson-from-sap-ai-core-service-connection) | Medium | Medium (1-2w) | Low | 🔴 To Do |
| 11 | [Add Abbreviated Request/Response Logging](#11-add-abbreviated-requestresponse-logging) | Medium | Small (1-3d) | Low | 🔴 To Do |
| 12 | [Implement Stable Connection Management and Reconnect](#12-implement-stable-connection-management-and-reconnect) | Medium | Medium (1-2w) | Medium | 🔴 To Do |
| 13 | [Add SAP AI Service Model Transport Speed and Health Monitoring](#13-add-sap-ai-service-model-transport-speed-and-health-monitoring) | Medium | Medium (1-2w) | Low | 🔴 To Do |
| 14 | [Add Metrics and Monitoring](#14-add-metrics-and-monitoring) | Low | Medium (1-2w) | Low | 🔴 To Do |
| 15 | [Add Rate Limiting](#15-add-rate-limiting) | Low | Small (1-3d) | Low | 🔴 To Do |
| 16 | [Add Request Caching](#16-add-request-caching) | Low | Medium (1-2w) | Medium | 🔴 To Do |
| 17 | [Add WebSocket Support](#17-add-websocket-support) | Low | Large (2-4w) | High | 🔴 To Do |

## High Priority

### 1. Fix Model Name Normalization Configuration

**Status**: 🔴 To Do  
**Priority**: High  
**Effort**: Small (1-3 days)  
**Risk**: Low  
**Related Code**: [`proxy_server.py:56-67`](../proxy_server.py#L56-L67)

#### Description

The [`normalize_model_names()`](../proxy_server.py#L56) method in [`SubAccountConfig`](../proxy_server.py#L37) class currently has a hardcoded `if False:` statement that disables the model name normalization logic (removing prefixes like `anthropic--`).

#### Current Code

```python
def normalize_model_names(self):
    """Normalize model names by removing prefixes like 'anthropic--'"""
    if False:  # ❌ Hardcoded condition
        self.parsed_models_url_list = {
            key.replace("anthropic--", ""): value
            for key, value in self.model_to_deployment_urls.items()
        }
    else:
        self.parsed_models_url_list = {
            key: value
            for key, value in self.model_to_deployment_urls.items()
        }
```

#### Proposed Solution

- Add a configuration option in `profile.json` to control model name normalization
- Make the normalization behavior configurable per subAccount
- Support custom prefix patterns for different model providers

#### Example Configuration

```json
{
  "subAccounts": {
    "subAccount1": {
      "resource_group": "default",
      "service_key_json": "service_key.json",
      "normalize_model_names": true,
      "model_name_prefixes_to_remove": ["anthropic--", "openai--"],
      "deployment_models": {
        "anthropic--claude-4.5-sonnet": ["https://..."]
      }
    }
  }
}
```

#### Acceptance Criteria

- [ ] Add `normalize_model_names` boolean flag to subAccount configuration
- [ ] Add `model_name_prefixes_to_remove` list to subAccount configuration
- [ ] Update [`normalize_model_names()`](../proxy_server.py#L56) to use configuration
- [ ] Maintain backward compatibility with existing configurations
- [ ] Add unit tests for normalization logic
- [ ] Update documentation with configuration examples

---

### 2. Add Automated Test Cases

**Status**: 🔴 To Do  
**Priority**: High  
**Effort**: Large (2-4 weeks)  
**Risk**: Low  
**Related Files**: New `tests/` directory

#### Description

The project currently lacks comprehensive automated test coverage. This makes it difficult to ensure code quality, prevent regressions, and safely refactor code.

#### Test Categories Needed

##### Unit Tests

- [ ] Configuration loading and validation
- [ ] Model name normalization
- [ ] Token management and caching
- [ ] Request/response conversion functions
  - [ ] [`convert_openai_to_claude()`](../proxy_server.py#L424)
  - [ ] [`convert_claude_to_openai()`](../proxy_server.py#L718)
  - [ ] [`convert_openai_to_gemini()`](../proxy_server.py#L1079)
  - [ ] [`convert_gemini_to_openai()`](../proxy_server.py#L1218)
- [ ] Load balancing logic
- [ ] Error handling and retry mechanisms

##### Integration Tests

- [ ] End-to-end request flow for Claude models
- [ ] End-to-end request flow for Gemini models
- [ ] End-to-end request flow for OpenAI models
- [ ] Streaming response handling
- [ ] Non-streaming response handling
- [ ] Multi-subAccount routing
- [ ] Authentication and authorization

##### API Tests

- [ ] `/v1/chat/completions` endpoint
- [ ] `/v1/messages` endpoint (Claude API)
- [ ] `/v1/models` endpoint
- [ ] `/v1/embeddings` endpoint
- [ ] Error response formats
- [ ] Rate limiting behavior

#### Testing Framework

- Use `pytest` as the primary testing framework
- Use `pytest-mock` for mocking external dependencies
- Use `pytest-asyncio` for async test support
- Use `responses` or `httpretty` for HTTP mocking

#### Test Structure

```text
tests/
├── unit/
│   ├── test_config.py
│   ├── test_conversions.py
│   ├── test_load_balancing.py
│   └── test_token_management.py
├── integration/
│   ├── test_claude_flow.py
│   ├── test_gemini_flow.py
│   └── test_openai_flow.py
├── api/
│   ├── test_chat_completions.py
│   ├── test_messages.py
│   └── test_models.py
├── fixtures/
│   ├── sample_configs.py
│   ├── sample_requests.py
│   └── sample_responses.py
└── conftest.py
```

#### Acceptance Criteria

- [ ] Achieve >80% code coverage
- [ ] All critical paths have test coverage
- [ ] Tests run in CI/CD pipeline
- [ ] Tests are documented and maintainable
- [ ] Mock external dependencies (SAP AI Core API)
- [ ] Add test documentation in `docs/testing.md`

---

### 3. Standardize Configuration File Naming

**Status**: 🔴 To Do  
**Priority**: High  
**Effort**: Small (1-3 days)  
**Risk**: Medium  
**Related Files**: [`proxy_server.py`](../proxy_server.py), `config.json`

#### Description

The project currently uses `config.json` as the configuration file name, but it should be renamed to `profile.json` to better reflect its purpose and align with common naming conventions. This change will improve clarity and consistency across the codebase.

#### Current State

- Configuration file: `config.json`
- References throughout codebase use "config"
- Command-line argument: `--config`

#### Proposed Changes

1. **Rename configuration file**: `config.json` → `profile.json`
2. **Update command-line argument**: `--config` → `--profile`
3. **Update all references in code and documentation**
4. **Maintain backward compatibility** with `--config` flag (deprecated)

#### Files to Update

- [ ] [`proxy_server.py`](../proxy_server.py) - Update argument parser and references
- [ ] `README.md` - Update documentation and examples
- [ ] `config.json.example` → `profile.json.example`
- [ ] All documentation files in `docs/`
- [ ] Docker configuration files
- [ ] CI/CD configuration files

#### Migration Strategy

```python
# Support both old and new naming for backward compatibility
parser.add_argument("--profile", type=str, default="profile.json",
                    help="Path to the profile configuration file")
parser.add_argument("--config", type=str, dest="profile",
                    help="(Deprecated) Use --profile instead")
# Warn users about deprecated flag
if args.proxy_config:
    logging.warning("--config flag is deprecated, please use --profile instead")
```

#### Example Usage

```bash
# New way (recommended)
python proxy_server.py --profile profile.json
# Old way (deprecated but still works)
python proxy_server.py --config config.json
```

#### Acceptance Criteria

- [ ] All references to `config.json` updated to `profile.json`
- [ ] Command-line argument changed to `--profile`
- [ ] Backward compatibility maintained with deprecation warning
- [ ] All documentation updated
- [ ] Example files renamed
- [ ] Migration guide added to documentation
- [ ] Deprecation notice added to CHANGELOG

---

### 4. Add Transport Logging with Timestamp Rotation

**Status**: 🔴 To Do  
**Priority**: High  
**Effort**: Medium (1-2 weeks)  
**Risk**: Low  
**Related Files**: [`proxy_server.py`](../proxy_server.py), New `logging/` module

#### Description

Implement comprehensive transport logging that captures both HTTP requests and responses in dedicated log files with automatic timestamp-based rotation. This will help with debugging, auditing, and troubleshooting production issues.

#### Requirements

1. **Separate log files for requests and responses**
   - `logs/transport/requests/request_YYYYMMDD_HHMMSS.log`
   - `logs/transport/responses/response_YYYYMMDD_HHMMSS.log`
2. **Timestamp-based rotation**
   - Rotate logs hourly, daily, or by size
   - Keep configurable retention period (e.g., 7 days)
   - Compress old logs automatically
3. **Structured logging format**
   - JSON format for easy parsing
   - Include timestamp, request ID, model, subAccount, headers, body

#### Proposed Implementation

```python
import logging
from logging.handlers import TimedRotatingFileHandler
import json
from datetime import datetime
class TransportLogger:
    def __init__(self, log_dir="logs/transport"):
        self.log_dir = log_dir
        self.request_logger = self._setup_logger("requests")
        self.response_logger = self._setup_logger("responses")
    
    def _setup_logger(self, log_type):
        logger = logging.getLogger(f"transport.{log_type}")
        logger.setLevel(logging.INFO)
        
        # Create directory if not exists
        log_path = os.path.join(self.log_dir, log_type)
        os.makedirs(log_path, exist_ok=True)
        
        # Rotating file handler (daily rotation, keep 7 days)
        handler = TimedRotatingFileHandler(
            filename=os.path.join(log_path, f"{log_type}.log"),
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        
        # JSON formatter
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def log_request(self, request_id, method, url, headers, body, model, subaccount):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "type": "request",
            "method": method,
            "url": url,
            "headers": dict(headers),
            "body": body,
            "model": model,
            "subaccount": subaccount
        }
        self.request_logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    def log_response(self, request_id, status_code, headers, body, duration_ms):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "type": "response",
            "status_code": status_code,
            "headers": dict(headers),
            "body": body,
            "duration_ms": duration_ms
        }
        self.response_logger.info(json.dumps(log_entry, ensure_ascii=False))
```

#### Configuration Options

Add to `profile.json`:

```json
{
  "logging": {
    "transport": {
      "enabled": true,
      "log_dir": "logs/transport",
      "rotation": {
        "when": "midnight",
        "interval": 1,
        "backup_count": 7
      },
      "compression": {
        "enabled": true,
        "format": "gzip"
      },
      "include_headers": true,
      "include_body": true,
      "max_body_size": 10000
    }
  }
}
```

#### Log File Structure

```text
logs/
└── transport/
    ├── requests/
    │   ├── request.log                    # Current log
    │   ├── request.log.2025-12-03         # Yesterday's log
    │   ├── request.log.2025-12-02.gz      # Compressed older log
    │   └── ...
    └── responses/
        ├── response.log                   # Current log
        ├── response.log.2025-12-03        # Yesterday's log
        ├── response.log.2025-12-02.gz     # Compressed older log
        └── ...
```

#### Acceptance Criteria

- [ ] Separate log files for requests and responses
- [ ] Automatic timestamp-based rotation (configurable)
- [ ] Configurable retention period
- [ ] Automatic compression of old logs
- [ ] JSON structured logging format
- [ ] Include request ID for correlation
- [ ] Configurable via `profile.json`
- [ ] Performance impact < 5ms per request
- [ ] Documentation with examples
- [ ] Log analysis tools/scripts provided

---

### 5. Make Logging Configurable

**Status**: 🔴 To Do  
**Priority**: High  
**Effort**: Small (1-3 days)  
**Risk**: Low  
**Related Files**: [`proxy_server.py`](../proxy_server.py)

#### Description

Make the logging system fully configurable through `profile.json`, allowing users to control log levels, formats, outputs, and what gets logged without modifying code.

#### Current State

- Logging is hardcoded in [`proxy_server.py`](../proxy_server.py)
- Log level set via `--debug` flag only
- Limited control over what gets logged
- No configuration file support for logging

#### Proposed Configuration

Add comprehensive logging configuration to `profile.json`:

```json
{
  "logging": {
    "version": 1,
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": {
      "console": {
        "enabled": true,
        "level": "INFO",
        "format": "%(levelname)s - %(message)s"
      },
      "file": {
        "enabled": true,
        "level": "DEBUG",
        "filename": "logs/proxy.log",
        "max_bytes": 10485760,
        "backup_count": 5
      },
      "error_file": {
        "enabled": true,
        "level": "ERROR",
        "filename": "logs/error.log",
        "max_bytes": 10485760,
        "backup_count": 5
      }
    },
    "loggers": {
      "proxy_server": {
        "level": "INFO",
        "handlers": ["console", "file"]
      },
      "token_usage": {
        "level": "INFO",
        "handlers": ["file"],
        "filename": "logs/token_usage.log"
      },
      "transport": {
        "level": "DEBUG",
        "handlers": ["file"]
      }
    },
    "filters": {
      "sensitive_data": {
        "enabled": true,
        "redact_patterns": [
          "Bearer .*",
          "clientsecret.*",
          "password.*"
        ]
      }
    },
    "content_logging": {
      "log_request_headers": true,
      "log_request_body": true,
      "log_response_headers": true,
      "log_response_body": true,
      "max_body_length": 1000,
      "redact_sensitive_fields": true
    }
  }
}
```

#### Implementation

```python
import logging.config
import json
def setup_logging(config_path="profile.json"):
    """Setup logging from configuration file"""
    with open(config_path) as f:
        config = json.load(f)
    
    logging_config = config.get("logging", {})
    
    # Setup basic logging
    log_level = getattr(logging, logging_config.get("level", "INFO"))
    log_format = logging_config.get("format", 
                                    "%(asctime)s - %(levelname)s - %(message)s")
    
    logging.basicConfig(level=log_level, format=log_format)
    
    # Setup handlers
    for handler_name, handler_config in logging_config.get("handlers", {}).items():
        if handler_config.get("enabled", True):
            setup_handler(handler_name, handler_config)
    
    # Setup loggers
    for logger_name, logger_config in logging_config.get("loggers", {}).items():
        setup_logger(logger_name, logger_config)
    
    # Setup filters
    if logging_config.get("filters", {}).get("sensitive_data", {}).get("enabled"):
        setup_sensitive_data_filter(logging_config["filters"]["sensitive_data"])
```

#### Log Level Hierarchy

```text
CRITICAL (50) - System failures, immediate action required
ERROR (40)    - Errors that need attention
WARNING (30)  - Warning messages
INFO (20)     - General information (default)
DEBUG (10)    - Detailed debugging information
NOTSET (0)    - All messages
```

#### Acceptance Criteria

- [ ] Logging fully configurable via `profile.json`
- [ ] Support multiple log levels per logger
- [ ] Support multiple handlers (console, file, rotating file)
- [ ] Support log filtering and redaction
- [ ] Backward compatibility with `--debug` flag
- [ ] Environment variable override support (e.g., `LOG_LEVEL=DEBUG`)
- [ ] Sensitive data redaction (tokens, passwords)
- [ ] Configurable content logging (headers, body)
- [ ] Documentation with examples
- [ ] Validation of logging configuration

---

### 6. Add Automatic HTTP 429 Throttling Handler

**Status**: 🔴 To Do
**Priority**: High
**Effort**: Small (1-3 days)
**Risk**: Low
**Related Files**: [`proxy_server.py`](../proxy_server.py)

#### Description

Implement automatic handling of HTTP 429 (Too Many Requests) status codes from SAP AI Core backend services. The proxy currently has a [`handle_http_429_error()`](../proxy_server.py) function but needs enhanced automatic retry logic with exponential backoff and proper rate limit header parsing.

#### Current State

- Basic HTTP 429 error handling exists
- No automatic retry mechanism
- No rate limit header parsing (Retry-After, X-RateLimit-*)
- No configurable retry strategy

#### Proposed Solution

Enhance the existing throttling handler with:

1. **Automatic retry with exponential backoff**
2. **Parse and respect Retry-After headers**
3. **Parse rate limit headers** (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
4. **Configurable retry attempts and delays**
5. **Logging of throttling events**

#### Implementation

```python
import time
from typing import Optional

def handle_http_429_with_retry(response, max_retries=3, base_delay=1.0):
    """
    Handle HTTP 429 errors with automatic retry and exponential backoff.
    
    Args:
        response: HTTP response object with 429 status
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
    
    Returns:
        Retry delay in seconds, or None if max retries exceeded
    """
    retry_after = response.headers.get('Retry-After')
    
    if retry_after:
        # Retry-After can be seconds or HTTP date
        try:
            delay = int(retry_after)
        except ValueError:
            # Parse HTTP date format
            from email.utils import parsedate_to_datetime
            retry_date = parsedate_to_datetime(retry_after)
            delay = (retry_date - datetime.now(timezone.utc)).total_seconds()
    else:
        # Use exponential backoff if no Retry-After header
        delay = base_delay * (2 ** (max_retries - 1))
    
    # Log rate limit information
    rate_limit_info = {
        'limit': response.headers.get('X-RateLimit-Limit'),
        'remaining': response.headers.get('X-RateLimit-Remaining'),
        'reset': response.headers.get('X-RateLimit-Reset'),
        'retry_after': retry_after,
        'calculated_delay': delay
    }
    
    logging.warning(f"HTTP 429 throttling detected. Rate limit info: {rate_limit_info}")
    
    return delay

def make_request_with_throttling(url, method='POST', max_retries=3, **kwargs):
    """
    Make HTTP request with automatic 429 throttling handling.
    
    Args:
        url: Request URL
        method: HTTP method
        max_retries: Maximum retry attempts
        **kwargs: Additional request parameters
    
    Returns:
        Response object
    """
    for attempt in range(max_retries + 1):
        response = requests.request(method, url, **kwargs)
        
        if response.status_code == 429:
            if attempt < max_retries:
                delay = handle_http_429_with_retry(response, max_retries - attempt)
                logging.info(f"Retrying after {delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            else:
                logging.error(f"Max retries ({max_retries}) exceeded for HTTP 429")
                raise Exception(f"Rate limit exceeded after {max_retries} retries")
        
        return response
```

#### Configuration

Add to `profile.json`:

```json
{
  "throttling": {
    "enabled": true,
    "max_retries": 3,
    "base_delay": 1.0,
    "max_delay": 60.0,
    "respect_retry_after": true,
    "log_throttling_events": true
  }
}
```

#### Acceptance Criteria

- [ ] Automatic retry on HTTP 429 errors
- [ ] Parse and respect Retry-After header
- [ ] Parse rate limit headers (X-RateLimit-*)
- [ ] Exponential backoff when no Retry-After header
- [ ] Configurable max retries and delays
- [ ] Comprehensive logging of throttling events
- [ ] Unit tests for retry logic
- [ ] Documentation with configuration examples

---

### 7. Split proxy_server.py into Multiple Modules

**Status**: 🔴 To Do
**Priority**: High
**Effort**: Medium (1-2 weeks)
**Risk**: Medium
**Related Files**: [`proxy_server.py`](../proxy_server.py)

#### Description

The [`proxy_server.py`](../proxy_server.py) file has grown to over 2900 lines and contains multiple responsibilities. Split it into logical modules to improve maintainability, readability, and testability. This is a prerequisite for the larger SOLID refactoring effort.

#### Current Issues

- Single file with 2900+ lines
- Multiple responsibilities mixed together
- Difficult to navigate and maintain
- Hard to test individual components
- Violates Single Responsibility Principle

#### Proposed Module Structure

```text
proxy_server/
├── __init__.py
├── main.py                      # Entry point, Flask app setup
├── config.py                    # Configuration classes (ProxyConfig, SubAccountConfig)
├── auth.py                      # Authentication and token management
├── models.py                    # Model routing and load balancing
├── converters/
│   ├── __init__.py
│   ├── claude.py                # Claude format conversions
│   ├── gemini.py                # Gemini format conversions
│   └── openai.py                # OpenAI format conversions
├── streaming/
│   ├── __init__.py
│   ├── claude_stream.py         # Claude streaming handlers
│   ├── gemini_stream.py         # Gemini streaming handlers
│   └── openai_stream.py         # OpenAI streaming handlers
├── endpoints/
│   ├── __init__.py
│   ├── chat_completions.py      # /v1/chat/completions
│   ├── messages.py              # /v1/messages
│   ├── models.py                # /v1/models
│   └── embeddings.py            # /v1/embeddings
└── utils.py                     # Utility functions

# Keep proxy_server.py as backward-compatible entry point
proxy_server.py                  # Import and run from proxy_server/main.py
```

#### Migration Strategy

1. **Phase 1: Extract configuration** (config.py)
   - Move ProxyConfig, SubAccountConfig, ServiceKey classes
   - Keep backward compatibility
2. **Phase 2: Extract converters** (converters/)
   - Move conversion functions to separate files
   - Maintain function signatures
3. **Phase 3: Extract streaming** (streaming/)
   - Move streaming handlers to separate files
4. **Phase 4: Extract endpoints** (endpoints/)
   - Move Flask route handlers to separate files
   - Use Flask Blueprints
5. **Phase 5: Create main entry point** (main.py)
   - Import and wire up all modules
   - Keep proxy_server.py as wrapper for backward compatibility

#### Backward Compatibility

```python
# proxy_server.py - backward compatible wrapper
"""
SAP AI Core LLM Proxy Server
This file is maintained for backward compatibility.
The actual implementation is in the proxy_server/ module.
"""
from proxy_server.main import app, main

if __name__ == "__main__":
    main()
```

#### Acceptance Criteria

- [ ] Code split into logical modules (<500 lines each)
- [ ] Each module has single, clear responsibility
- [ ] Backward compatibility maintained
- [ ] All existing functionality works unchanged
- [ ] Import paths updated throughout codebase
- [ ] Documentation updated with new structure
- [ ] No breaking changes for existing users
- [ ] Tests pass after refactoring

---

### 8. Fix Claude Model ID Mapping

**Status**: 🔴 To Do
**Priority**: High
**Effort**: Small (1-3 days)
**Risk**: Low
**Related Files**: [`proxy_server.py`](../proxy_server.py)

#### Description

The proxy needs to return correct model IDs for Claude 4.5 and Claude 4 models in responses. Currently, model ID mapping may not correctly handle all Claude model variants, especially when converting between OpenAI and Claude API formats.

#### Current Issues

- Model ID inconsistencies in responses
- Claude 4.5 Sonnet may return incorrect ID
- Claude 4 (Opus) may return incorrect ID
- Model name normalization affects ID mapping

#### Affected Models

- `claude-4.5-sonnet` (should map to `claude-sonnet-4-20250514`)
- `claude-4-opus` (should map to `claude-opus-4-20250514`)
- `anthropic--claude-4.5-sonnet` (with prefix)
- `anthropic--claude-4-opus` (with prefix)

#### Proposed Solution

Create a comprehensive model ID mapping configuration:

```python
# Model ID mappings for Claude models
CLAUDE_MODEL_ID_MAP = {
    # Claude 4.5 variants
    "claude-4.5-sonnet": "claude-sonnet-4-20250514",
    "anthropic--claude-4.5-sonnet": "claude-sonnet-4-20250514",
    "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    
    # Claude 4 variants
    "claude-4-opus": "claude-opus-4-20250514",
    "anthropic--claude-4-opus": "claude-opus-4-20250514",
    "claude-opus-4-20250514": "claude-opus-4-20250514",
    
    # Claude 3.5 variants (for reference)
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    "anthropic--claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
}

def get_correct_claude_model_id(model_name: str) -> str:
    """
    Get the correct Claude model ID for API responses.
    
    Args:
        model_name: Input model name (may have prefix or be normalized)
    
    Returns:
        Correct Claude model ID for API responses
    """
    # Normalize the model name (remove common prefixes)
    normalized = model_name.replace("anthropic--", "")
    
    # Look up in mapping
    return CLAUDE_MODEL_ID_MAP.get(normalized, model_name)
```

#### Update Response Conversion

```python
def convert_claude_to_openai(claude_response, model, stream=False):
    """Convert Claude API response to OpenAI format"""
    # ... existing code ...
    
    # Use correct model ID in response
    correct_model_id = get_correct_claude_model_id(model)
    
    openai_response = {
        "id": f"chatcmpl-{claude_response.get('id', '')}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": correct_model_id,  # Use correct ID
        # ... rest of response ...
    }
```

#### Configuration

Add to `profile.json`:

```json
{
  "model_id_mappings": {
    "claude-4.5-sonnet": "claude-sonnet-4-20250514",
    "claude-4-opus": "claude-opus-4-20250514",
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022"
  }
}
```

#### Acceptance Criteria

- [ ] Correct model IDs returned for Claude 4.5 Sonnet
- [ ] Correct model IDs returned for Claude 4 Opus
- [ ] Model ID mapping handles prefixed names
- [ ] Model ID mapping handles normalized names
- [ ] Configuration-based model ID mappings
- [ ] Backward compatibility maintained
- [ ] Unit tests for model ID mapping
- [ ] Documentation with model ID reference

---

## Medium Priority

### 9. Refactor Python Classes to Follow SOLID Principles

**Status**: 🔴 To Do  
**Priority**: Medium  
**Effort**: Large (2-4 weeks)  
**Risk**: High  
**Related Files**: [`proxy_server.py`](../proxy_server.py)

#### Description

The current codebase has grown organically and violates several SOLID principles. The main [`proxy_server.py`](../proxy_server.py) file is over 2900 lines and contains multiple responsibilities. Refactoring to follow SOLID principles will improve maintainability, testability, and extensibility.

#### Current Issues

1. **Single Responsibility Principle (SRP)** - Violated
   - [`proxy_server.py`](../proxy_server.py) handles configuration, routing, conversion, streaming, authentication, and more
   - Functions like [`proxy_openai_stream()`](../proxy_server.py#L1881) and [`proxy_claude_request()`](../proxy_server.py#L1960) are too large
2. **Open/Closed Principle (OCP)** - Violated
   - Adding new model providers requires modifying existing code
   - Conversion logic is tightly coupled to specific model types
3. **Liskov Substitution Principle (LSP)** - Not Applicable
   - Limited use of inheritance currently
4. **Interface Segregation Principle (ISP)** - Violated
   - No clear interfaces defined for different components
5. **Dependency Inversion Principle (DIP)** - Violated
   - High-level modules depend on low-level modules
   - No abstraction layer for external API calls

#### Proposed Architecture

```text
src/
├── __init__.py
├── main.py                          # Application entry point
├── config/
│   ├── __init__.py
│   ├── loader.py                    # Configuration loading
│   ├── validator.py                 # Configuration validation
│   └── models.py                    # Configuration data models
├── auth/
│   ├── __init__.py
│   ├── token_manager.py             # Token caching and refresh
│   └── request_validator.py        # Request authentication
├── routing/
│   ├── __init__.py
│   ├── load_balancer.py             # Load balancing logic
│   └── model_router.py              # Model-to-endpoint routing
├── converters/
│   ├── __init__.py
│   ├── base.py                      # Base converter interface
│   ├── claude_converter.py          # Claude format conversions
│   ├── gemini_converter.py          # Gemini format conversions
│   └── openai_converter.py          # OpenAI format conversions
├── streaming/
│   ├── __init__.py
│   ├── base.py                      # Base streaming handler
│   ├── claude_streaming.py          # Claude streaming logic
│   ├── gemini_streaming.py          # Gemini streaming logic
│   └── openai_streaming.py          # OpenAI streaming logic
├── api/
│   ├── __init__.py
│   ├── chat_completions.py          # /v1/chat/completions endpoint
│   ├── messages.py                  # /v1/messages endpoint
│   ├── models.py                    # /v1/models endpoint
│   └── embeddings.py                # /v1/embeddings endpoint
├── clients/
│   ├── __init__.py
│   ├── base.py                      # Base API client interface
│   ├── sap_ai_core_client.py        # SAP AI Core API client
│   └── bedrock_client.py            # AWS Bedrock client wrapper
└── utils/
    ├── __init__.py
    ├── logging.py                   # Logging utilities
    └── errors.py                    # Custom exception classes
```

#### Refactoring Steps

1. **Phase 1: Extract Configuration Management**
   - [ ] Create `config/` module
   - [ ] Move configuration loading logic
   - [ ] Add configuration validation
   - [ ] Create configuration data models using `dataclasses` or `pydantic`
2. **Phase 2: Extract Authentication**
   - [ ] Create `auth/` module
   - [ ] Move token management logic
   - [ ] Implement token caching strategy
   - [ ] Add request validation
3. **Phase 3: Extract Converters**
   - [ ] Create `converters/` module
   - [ ] Define base converter interface
   - [ ] Implement model-specific converters
   - [ ] Add converter factory pattern
4. **Phase 4: Extract Streaming Logic**
   - [ ] Create `streaming/` module
   - [ ] Define base streaming handler
   - [ ] Implement model-specific streaming handlers
   - [ ] Add streaming factory pattern
5. **Phase 5: Extract API Endpoints**
   - [ ] Create `api/` module
   - [ ] Split endpoints into separate files
   - [ ] Use Flask Blueprints for organization
   - [ ] Add endpoint-specific error handling
6. **Phase 6: Extract Client Logic**
   - [ ] Create `clients/` module
   - [ ] Define base client interface
   - [ ] Implement SAP AI Core client
   - [ ] Add client factory pattern

#### Design Patterns to Apply

- **Factory Pattern**: For creating converters, streaming handlers, and clients
- **Strategy Pattern**: For different conversion and streaming strategies
- **Dependency Injection**: For loose coupling between components
- **Repository Pattern**: For configuration and token storage
- **Chain of Responsibility**: For request processing pipeline

#### Acceptance Criteria

- [ ] Each module has a single, well-defined responsibility
- [ ] New model providers can be added without modifying existing code
- [ ] All dependencies are injected, not hardcoded
- [ ] Code is organized into logical modules
- [ ] Each file is <500 lines of code
- [ ] All refactored code has test coverage
- [ ] Documentation is updated to reflect new architecture
- [ ] Backward compatibility is maintained during transition

---

### 10. Generate profile.json from SAP AI Core Service Connection

**Status**: 🔴 To Do  
**Priority**: Medium  
**Effort**: Medium (1-2 weeks)  
**Risk**: Low  
**Related Files**: New `tools/` directory

#### Description

Currently, users must manually create and maintain the `profile.json` file with deployment URLs and model mappings. This is error-prone and requires manual updates when deployments change. We should provide a tool to automatically generate the configuration by querying the SAP AI Core service.

#### Proposed Solution

Create a CLI tool that:

1. Connects to SAP AI Core using service key credentials
2. Queries available deployments and models
3. Generates a properly formatted `profile.json` file
4. Optionally validates the generated configuration

#### Tool Structure

```text
tools/
├── __init__.py
├── profile_generator.py             # Main configuration generator
├── sap_ai_core_api.py              # SAP AI Core API wrapper
└── templates/
    └── profile_template.json        # Configuration template
```

#### Usage Example

```bash
# Generate profile from service key file
python -m tools.profile_generator \
  --service-key service_key.json \
  --output profile.json
# Generate profile with multiple subAccounts
python -m tools.profile_generator \
  --service-key-1 service_key_1.json \
  --service-key-2 service_key_2.json \
  --output profile.json
# Validate existing profile
python -m tools.profile_generator \
  --validate profile.json
# Update existing profile with new deployments
python -m tools.profile_generator \
  --service-key service_key.json \
  --update profile.json
```

#### Features

- [ ] Query SAP AI Core for available deployments
- [ ] Automatically detect model types (Claude, Gemini, OpenAI)
- [ ] Generate deployment URL mappings
- [ ] Support multiple subAccounts
- [ ] Validate service key credentials
- [ ] Merge with existing configuration (update mode)
- [ ] Dry-run mode to preview changes
- [ ] Interactive mode for user input
- [ ] Export to different formats (JSON, YAML)

#### API Endpoints to Query

```python
# Get deployments
GET /v2/lm/deployments
# Get deployment details
GET /v2/lm/deployments/{deployment_id}
# Get available models
GET /v2/lm/models
# Get resource groups
GET /v2/lm/resourceGroups
```

#### Generated Configuration Example

```json
{
  "subAccounts": {
    "production": {
      "resource_group": "default",
      "service_key_json": "service_key_prod.json",
      "normalize_model_names": true,
      "model_name_prefixes_to_remove": ["anthropic--"],
      "deployment_models": {
        "anthropic--claude-4.5-sonnet": [
          "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d123abc"
        ],
        "gemini-2.5-pro": [
          "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d456def"
        ]
      }
    }
  },
  "secret_authentication_tokens": [
    "your-secret-token-here"
  ],
  "port": 3001,
  "host": "127.0.0.1",
  "_generated_at": "2025-12-04T12:00:00Z",
  "_generated_by": "profile_generator v1.0.0"
}
```

#### Acceptance Criteria

- [ ] Tool successfully connects to SAP AI Core
- [ ] Tool queries and lists all available deployments
- [ ] Tool generates valid `profile.json` format
- [ ] Tool supports multiple subAccounts
- [ ] Tool validates generated configuration
- [ ] Tool has comprehensive error handling
- [ ] Tool has interactive and non-interactive modes
- [ ] Tool is documented with usage examples
- [ ] Tool includes unit tests
- [ ] Tool can update existing configurations without data loss

---

### 11. Add Abbreviated Request/Response Logging

**Status**: 🔴 To Do  
**Priority**: Medium  
**Effort**: Small (1-3 days)  
**Risk**: Low  
**Related Files**: [`proxy_server.py`](../proxy_server.py)

#### Description

Implement a "low hanging fruit" feature to dump abbreviated (summary) versions of requests and responses to logs. This provides quick visibility into traffic patterns without the overhead of full transport logging.

#### Requirements

1. **Abbreviated request logging**
   - Request ID, timestamp, method, endpoint
   - Model name, subAccount
   - Request size (bytes)
   - Key headers (excluding sensitive data)
2. **Abbreviated response logging**
   - Request ID (for correlation), timestamp
   - Status code, response size (bytes)
   - Duration (ms)
   - Token usage summary
3. **Single-line format** for easy grep/parsing

#### Proposed Implementation

```python
def log_request_summary(request_id, method, endpoint, model, subaccount, size_bytes):
    """Log abbreviated request information"""
    logging.info(
        f"REQ [{request_id}] {method} {endpoint} | "
        f"model={model} subaccount={subaccount} size={size_bytes}B"
    )
def log_response_summary(request_id, status_code, size_bytes, duration_ms, 
                        tokens_in=0, tokens_out=0):
    """Log abbreviated response information"""
    logging.info(
        f"RES [{request_id}] {status_code} | "
        f"size={size_bytes}B duration={duration_ms}ms "
        f"tokens={tokens_in}→{tokens_out}"
    )
```

#### Example Log Output

```text
2025-12-04 10:15:23 - INFO - REQ [req_abc123] POST /v1/chat/completions | model=claude-4.5-sonnet subaccount=prod size=1234B
2025-12-04 10:15:25 - INFO - RES [req_abc123] 200 | size=5678B duration=1850ms tokens=150→450
2025-12-04 10:15:26 - INFO - REQ [req_def456] POST /v1/messages | model=gemini-2.5-pro subaccount=dev size=890B
2025-12-04 10:15:27 - INFO - RES [req_def456] 200 | size=2340B duration=980ms tokens=80→220
```

#### Configuration

Add to `profile.json`:

```json
{
  "logging": {
    "abbreviated_logging": {
      "enabled": true,
      "include_request_summary": true,
      "include_response_summary": true,
      "include_token_usage": true,
      "log_level": "INFO"
    }
  }
}
```

#### Benefits

- **Low overhead**: Minimal performance impact
- **Easy to parse**: Single-line format
- **Quick debugging**: See traffic patterns at a glance
- **Correlation**: Request ID links request/response pairs
- **Metrics**: Easy to extract for analysis

#### Acceptance Criteria

- [ ] Single-line log format for requests
- [ ] Single-line log format for responses
- [ ] Request ID for correlation
- [ ] Include key metrics (size, duration, tokens)
- [ ] Configurable via `profile.json`
- [ ] Performance impact < 1ms per request
- [ ] Works with existing logging configuration
- [ ] Documentation with examples
- [ ] Log parsing examples/scripts provided

---

### 12. Implement Stable Connection Management and Reconnect

**Status**: 🔴 To Do  
**Priority**: Medium  
**Effort**: Medium (1-2 weeks)  
**Risk**: Medium  
**Related Files**: [`proxy_server.py`](../proxy_server.py), New `connection/` module

#### Description

Implement robust connection management with automatic reconnection logic to handle network failures, timeouts, and transient errors when communicating with SAP AI Core backend services.

#### Current Issues

- No automatic retry on connection failures
- No connection pooling
- No circuit breaker pattern
- Timeouts are hardcoded
- No graceful degradation

#### Proposed Solution

Implement a connection manager with:

1. **Connection pooling** for reusing HTTP connections
2. **Automatic retry** with exponential backoff
3. **Circuit breaker** to prevent cascading failures
4. **Health checks** for backend availability
5. **Graceful degradation** when backends are unavailable

#### Implementation

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
class ConnectionManager:
    def __init__(self, config):
        self.config = config
        self.session = self._create_session()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get("failure_threshold", 5),
            recovery_timeout=config.get("recovery_timeout", 60)
        )
    
    def _create_session(self):
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.get("max_retries", 3),
            backoff_factor=self.config.get("backoff_factor", 1),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config.get("pool_connections", 10),
            pool_maxsize=self.config.get("pool_maxsize", 20),
            pool_block=False
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def request(self, method, url, **kwargs):
        """Make a request with circuit breaker protection"""
        if self.circuit_breaker.is_open():
            raise ConnectionError("Circuit breaker is open")
        
        try:
            response = self.session.request(method, url, **kwargs)
            self.circuit_breaker.record_success()
            return response
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    def is_open(self):
        if self.state == "open":
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half_open"
                return False
            return True
        return False

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logging.error(f"Circuit breaker opened after {self.failure_count} failures")
```

#### Configuration

Add to `profile.json`:

```json
{
  "connection": {
    "max_retries": 3,
    "backoff_factor": 1,
    "timeout": {
      "connect": 10,
      "read": 300
    },
    "pool_connections": 10,
    "pool_maxsize": 20,
    "circuit_breaker": {
      "enabled": true,
      "failure_threshold": 5,
      "recovery_timeout": 60
    },
    "health_check": {
      "enabled": true,
      "interval": 30,
      "timeout": 5
    }
  }
}
```

#### Retry Strategy

```text
Attempt 1: Immediate
Attempt 2: Wait 1s  (backoff_factor * 2^0)
Attempt 3: Wait 2s  (backoff_factor * 2^1)
Attempt 4: Wait 4s  (backoff_factor * 2^2)
```

#### Circuit Breaker States

```text
CLOSED → OPEN → HALF_OPEN → CLOSED
  ↑                            ↓
  └────────────────────────────┘
  
CLOSED:     Normal operation
OPEN:       Reject all requests (fast fail)
HALF_OPEN:  Allow test request to check recovery
```

#### Health Check

```python
def health_check_worker(connection_manager, interval=30):
    """Background worker to check backend health"""
    while True:
        for subaccount_name, subaccount in proxy_config.subaccounts.items():
            try:
                # Simple health check request
                response = connection_manager.request(
                    "GET",
                    f"{subaccount.base_url}/health",
                    timeout=5
                )
                if response.status_code == 200:
                    logging.debug(f"Health check OK for {subaccount_name}")
                else:
                    logging.warning(f"Health check failed for {subaccount_name}: {response.status_code}")
            except Exception as e:
                logging.error(f"Health check error for {subaccount_name}: {e}")
        
        time.sleep(interval)
```

#### Acceptance Criteria

- [ ] Connection pooling implemented
- [ ] Automatic retry with exponential backoff
- [ ] Circuit breaker pattern implemented
- [ ] Configurable retry strategy
- [ ] Configurable timeouts
- [ ] Health check background worker
- [ ] Graceful degradation on failures
- [ ] Metrics for connection health
- [ ] Documentation with configuration examples
- [ ] Unit tests for retry and circuit breaker logic

---

### 13. Add SAP AI Service Model Transport Speed and Health Monitoring

**Status**: 🔴 To Do  
**Priority**: Medium  
**Effort**: Medium (1-2 weeks)  
**Risk**: Low  
**Related Files**: New `monitoring/` module

#### Description

Implement comprehensive monitoring of SAP AI Core service transport performance and health. Track request/response speeds, latencies, throughput, and service availability per model and subAccount. Provide real-time visibility into backend service performance.

#### Requirements

1. **Transport Speed Metrics**
   - Request/response latency (p50, p95, p99)
   - Throughput (requests per second)
   - Data transfer rates (bytes/sec)
   - Time to first byte (TTFB)
   - Streaming chunk delivery rate
2. **Health Monitoring**
   - Service availability per subAccount
   - Model availability per deployment
   - Error rates and types
   - Success/failure ratios
   - Circuit breaker state
3. **Performance Tracking**
   - Token generation speed (tokens/sec)
   - Model-specific latency patterns
   - SubAccount performance comparison
   - Time-series data for trending

#### Proposed Implementation

```python
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List
import threading
@dataclass
class TransportMetrics:
    """Metrics for a single request"""
    request_id: str
    model: str
    subaccount: str
    start_time: float
    end_time: float = 0
    ttfb: float = 0  # Time to first byte
    request_size: int = 0
    response_size: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    status_code: int = 0
    error: str = None
    
    @property
    def duration_ms(self) -> float:
        """Total request duration in milliseconds"""
        return (self.end_time - self.start_time) * 1000 if self.end_time else 0
    
    @property
    def tokens_per_second(self) -> float:
        """Token generation speed"""
        duration_sec = (self.end_time - self.start_time) if self.end_time else 0
        return self.tokens_out / duration_sec if duration_sec > 0 else 0
    
    @property
    def throughput_bps(self) -> float:
        """Data throughput in bytes per second"""
        duration_sec = (self.end_time - self.start_time) if self.end_time else 0
        return self.response_size / duration_sec if duration_sec > 0 else 0
class PerformanceMonitor:
    def __init__(self, window_size=1000):
        self.window_size = window_size
        self.metrics_by_model = defaultdict(lambda: deque(maxlen=window_size))
        self.metrics_by_subaccount = defaultdict(lambda: deque(maxlen=window_size))
        self.lock = threading.Lock()
    
    def record_metric(self, metric: TransportMetrics):
        """Record a transport metric"""
        with self.lock:
            self.metrics_by_model[metric.model].append(metric)
            self.metrics_by_subaccount[metric.subaccount].append(metric)
    
    def get_model_stats(self, model: str) -> Dict:
        """Get statistics for a specific model"""
        with self.lock:
            metrics = list(self.metrics_by_model[model])
        
        if not metrics:
            return {}
        
        latencies = [m.duration_ms for m in metrics if m.duration_ms > 0]
        ttfbs = [m.ttfb for m in metrics if m.ttfb > 0]
        token_speeds = [m.tokens_per_second for m in metrics if m.tokens_per_second > 0]
        success_count = sum(1 for m in metrics if 200 <= m.status_code < 300)
        error_count = sum(1 for m in metrics if m.status_code >= 400 or m.error)
        
        return {
            "model": model,
            "total_requests": len(metrics),
            "success_rate": success_count / len(metrics) if metrics else 0,
            "error_rate": error_count / len(metrics) if metrics else 0,
            "latency": {
                "p50": self._percentile(latencies, 50),
                "p95": self._percentile(latencies, 95),
                "p99": self._percentile(latencies, 99),
                "avg": sum(latencies) / len(latencies) if latencies else 0
            },
            "ttfb": {
                "p50": self._percentile(ttfbs, 50),
                "p95": self._percentile(ttfbs, 95),
                "avg": sum(ttfbs) / len(ttfbs) if ttfbs else 0
            },
            "token_speed": {
                "avg": sum(token_speeds) / len(token_speeds) if token_speeds else 0,
                "p50": self._percentile(token_speeds, 50),
                "p95": self._percentile(token_speeds, 95)
            }
        }
    
    def get_subaccount_stats(self, subaccount: str) -> Dict:
        """Get statistics for a specific subAccount"""
        with self.lock:
            metrics = list(self.metrics_by_subaccount[subaccount])
        
        if not metrics:
            return {}

        latencies = [m.duration_ms for m in metrics if m.duration_ms > 0]
        success_count = sum(1 for m in metrics if 200 <= m.status_code < 300)
        error_count = sum(1 for m in metrics if m.status_code >= 400 or m.error)
        
        # Calculate availability (last 100 requests)
        recent_metrics = metrics[-100:]
        recent_success = sum(1 for m in recent_metrics if 200 <= m.status_code < 300)
        availability = recent_success / len(recent_metrics) if recent_metrics else 0
        
        return {
            "subaccount": subaccount,
            "total_requests": len(metrics),
            "success_rate": success_count / len(metrics) if metrics else 0,
            "error_rate": error_count / len(metrics) if metrics else 0,
            "availability": availability,
            "latency": {
                "p50": self._percentile(latencies, 50),
                "p95": self._percentile(latencies, 95),
                "p99": self._percentile(latencies, 99),
                "avg": sum(latencies) / len(latencies) if latencies else 0
            }
        }
    
    def get_health_status(self) -> Dict:
        """Get overall health status"""
        with self.lock:
            all_metrics = []
            for metrics in self.metrics_by_subaccount.values():
                all_metrics.extend(metrics)
        
        if not all_metrics:
            return {"status": "unknown", "message": "No metrics available"}
        
        # Check recent metrics (last 50)
        recent_metrics = sorted(all_metrics, key=lambda m: m.end_time)[-50:]
        recent_errors = sum(1 for m in recent_metrics if m.status_code >= 400 or m.error)
        error_rate = recent_errors / len(recent_metrics)
        
        if error_rate > 0.5:
            status = "critical"
            message = f"High error rate: {error_rate:.1%}"
        elif error_rate > 0.2:
            status = "degraded"
            message = f"Elevated error rate: {error_rate:.1%}"
        else:
            status = "healthy"
            message = "All systems operational"
        
        return {
            "status": status,
            "message": message,
            "error_rate": error_rate,
            "total_requests": len(all_metrics)
        }
    
    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """Calculate percentile of a list of values"""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
# Global performance monitor instance
performance_monitor = PerformanceMonitor()
# Usage in request handling
def track_request_performance(func):
    """Decorator to track request performance"""
    def wrapper(*args, **kwargs):
        metric = TransportMetrics(
            request_id=generate_request_id(),
            model=kwargs.get('model', 'unknown'),
            subaccount=kwargs.get('subaccount_name', 'unknown'),
            start_time=time.time()
        )
        
        try:
            # Record time to first byte for streaming
            first_byte_time = None
            
            result = func(*args, **kwargs)
            
            metric.end_time = time.time()
            metric.status_code = 200
            
            performance_monitor.record_metric(metric)
            return result
            
        except Exception as e:
            metric.end_time = time.time()
            metric.error = str(e)
            metric.status_code = 500
            performance_monitor.record_metric(metric)
            raise
    
    return wrapper
```

#### Monitoring Endpoints

Add new endpoints to expose metrics:

```python
@app.route('/v1/monitoring/health', methods=['GET'])
def get_health():
    """Get overall health status"""
    return jsonify(performance_monitor.get_health_status())
@app.route('/v1/monitoring/models/<model>/stats', methods=['GET'])
def get_model_stats(model):
    """Get statistics for a specific model"""
    stats = performance_monitor.get_model_stats(model)
    if not stats:
        return jsonify({"error": "Model not found or no metrics available"}), 404
    return jsonify(stats)
@app.route('/v1/monitoring/subaccounts/<subaccount>/stats', methods=['GET'])
def get_subaccount_stats(subaccount):
    """Get statistics for a specific subAccount"""
    stats = performance_monitor.get_subaccount_stats(subaccount)
    if not stats:
        return jsonify({"error": "SubAccount not found or no metrics available"}), 404
    return jsonify(stats)
@app.route('/v1/monitoring/dashboard', methods=['GET'])
def get_dashboard():
    """Get comprehensive monitoring dashboard data"""
    dashboard = {
        "health": performance_monitor.get_health_status(),
        "models": {},
        "subaccounts": {}
    }
    
    # Get stats for all models
    for model in proxy_config.model_to_subaccounts.keys():
        stats = performance_monitor.get_model_stats(model)
        if stats:
            dashboard["models"][model] = stats

    # Get stats for all subAccounts
    for subaccount in proxy_config.subaccounts.keys():
        stats = performance_monitor.get_subaccount_stats(subaccount)
        if stats:
            dashboard["subaccounts"][subaccount] = stats
    
    return jsonify(dashboard)
```

#### Configuration

Add to `profile.json`:

```json
{
  "monitoring": {
    "enabled": true,
    "metrics_window_size": 1000,
    "track_transport_speed": true,
    "track_token_speed": true,
    "track_ttfb": true,
    "endpoints": {
      "health": "/v1/monitoring/health",
      "dashboard": "/v1/monitoring/dashboard"
    },
    "alerts": {
      "enabled": true,
      "error_rate_threshold": 0.2,
      "latency_threshold_ms": 5000,
      "availability_threshold": 0.95
    }
  }
}
```

#### Dashboard Output Example

```json
{
  "health": {
    "status": "healthy",
    "message": "All systems operational",
    "error_rate": 0.02,
    "total_requests": 1000
  },
  "models": {
    "claude-4.5-sonnet": {
      "model": "claude-4.5-sonnet",
      "total_requests": 450,
      "success_rate": 0.98,
      "error_rate": 0.02,
      "latency": {
        "p50": 1850,
        "p95": 3200,
        "p99": 4500,
        "avg": 2100
      },
      "ttfb": {
        "p50": 450,
        "p95": 850,
        "avg": 520
      },
      "token_speed": {
        "avg": 45.2,
        "p50": 42.0,
        "p95": 55.0
      }
    }
  },
  "subaccounts": {
    "production": {
      "subaccount": "production",
      "total_requests": 800,
      "success_rate": 0.98,
      "error_rate": 0.02,
      "availability": 0.99,
      "latency": {
        "p50": 1900,
        "p95": 3300,
        "p99": 4600,
        "avg": 2150
      }
    }
  }
}
```

#### Acceptance Criteria

- [ ] Track request/response latency (p50, p95, p99)
- [ ] Track time to first byte (TTFB)
- [ ] Track token generation speed
- [ ] Track throughput and data transfer rates
- [ ] Monitor service availability per subAccount
- [ ] Monitor model availability per deployment
- [ ] Track error rates and types
- [ ] Provide health status endpoint
- [ ] Provide per-model statistics endpoint
- [ ] Provide per-subAccount statistics endpoint
- [ ] Provide comprehensive dashboard endpoint
- [ ] Configurable metrics window size
- [ ] Configurable alerting thresholds
- [ ] Performance impact < 2ms per request
- [ ] Documentation with API examples
- [ ] Integration with existing logging

---

## Low Priority / Future Enhancements

### 14. Add Metrics and Monitoring

**Status**: 🔴 To Do  
**Priority**: Low  
**Effort**: Medium (1-2 weeks)  
**Risk**: Low

#### Description

Add Prometheus metrics and health check endpoints for monitoring proxy performance and availability.

#### Features

- [ ] Request count by model and subAccount
- [ ] Request latency histograms
- [ ] Token usage metrics
- [ ] Error rate tracking
- [ ] Health check endpoint (`/health`)
- [ ] Readiness check endpoint (`/ready`)
- [ ] Metrics endpoint (`/metrics`)

---

### 15. Add Rate Limiting

**Status**: 🔴 To Do  
**Priority**: Low  
**Effort**: Small (1-3 days)  
**Risk**: Low

#### Description

Implement rate limiting to prevent abuse and ensure fair usage across clients.

#### Features

- [ ] Per-client rate limiting
- [ ] Per-model rate limiting
- [ ] Configurable rate limits
- [ ] Rate limit headers in responses
- [ ] Redis-based rate limiting for distributed deployments

---

### 16. Add Request Caching

**Status**: 🔴 To Do  
**Priority**: Low  
**Effort**: Medium (1-2 weeks)  
**Risk**: Medium

#### Description

Implement caching for identical requests to reduce API calls and improve response times.

#### Features

- [ ] Cache identical requests
- [ ] Configurable TTL
- [ ] Cache invalidation strategies
- [ ] Redis-based caching for distributed deployments
- [ ] Cache hit/miss metrics

---

### 17. Add WebSocket Support

**Status**: 🔴 To Do  
**Priority**: Low  
**Effort**: Large (2-4 weeks)  
**Risk**: High

#### Description

Add WebSocket support for real-time bidirectional communication with LLM models.

#### Features

- [ ] WebSocket endpoint for streaming
- [ ] Connection management
- [ ] Heartbeat/ping-pong
- [ ] Reconnection handling
- [ ] WebSocket authentication

---

## Completed Items

_No completed items yet._
---

## Notes

- This backlog is a living document and will be updated as priorities change
- Each item should be broken down into smaller tasks when work begins
- Consider creating GitHub issues for tracking individual items
- Estimate effort using T-shirt sizing: Small (1-3 days), Medium (1-2 weeks), Large (2-4 weeks)
- Risk levels help prioritize items and plan testing strategies

**Legend**:

- 🔴 To Do
- 🟡 In Progress
- 🟢 Completed
- ⏸️ On Hold
- ❌ Cancelled
