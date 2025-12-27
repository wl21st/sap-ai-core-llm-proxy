# SAP AI Core LLM Proxy - Logging System Documentation

## Overview

The SAP AI Core LLM Proxy implements a comprehensive, structured logging system designed for production monitoring, debugging, and observability. This document details the logging architecture, keywords, and best practices.

## Architecture

### Log Levels
- **Transport Logs**: Core business logic (INFO level)
- **Server Logs**: Application events and errors (INFO/ERROR level)
- **Token Usage Logs**: Usage metrics (INFO level)
- **Debug Logs**: Detailed debugging information (DEBUG level)

### Log Components
```python
# Core loggers
logger = get_server_logger(__name__)           # Server events
transport_logger = get_transport_logger(__name__)  # Client ↔ Vendor communication
token_usage_logger = get_server_logger("token_usage")  # Usage metrics
```

## Log Keywords Reference

### Client-Side Operations
| Keyword | Direction | Purpose | Example |
|---------|-----------|---------|---------|
| `CLIENT_REQ` | → Client | Request received from client | `CLIENT_REQ: tid=abc123, url=/v1/chat/completions` |
| `CLIENT_RSP` | ← Client | Response sent to client | `CLIENT_RSP: tid=abc123, status=200` |

### Vendor-Side Operations
| Keyword | Direction | Purpose | Example |
|---------|-----------|---------|---------|
| `VENDOR_REQ` | → Vendor | Request sent to AI vendor | `VENDOR_REQ: tid=abc123, MODEL=claude-3-5-sonnet` |
| `VENDOR_RSP` | ← Vendor | Response received from AI vendor | `VENDOR_RSP: tid=abc123, status=200` |

### Streaming Operations
| Keyword | Direction | Purpose | Example |
|---------|-----------|---------|---------|
| `CHUNK` | ↔ Both | Streaming data chunks | `CHUNK: tid=abc123, {"choices":[{"delta":{"content":"Hello"}}]}` |
| `DONE` | ↔ Both | Stream completion | `DONE: tid=abc123, Streaming completed` |

### Error Operations
| Keyword | Direction | Purpose | Example |
|---------|-----------|---------|---------|
| `ERR` | ← Both | Error responses | `ERR: tid=abc123, status=429, Rate limit exceeded` |

## Endpoint-Specific Logging

### Chat Completions (`/v1/chat/completions`)
```
CLIENT_REQ → VENDOR_REQ → VENDOR_RSP → CLIENT_RSP
    ↓          ↓          ↓          ↓
  Client →  Bedrock  →  Bedrock  →  Client
```

### Messages API (`/v1/messages`)
```
CLIENT_REQ → VENDOR_REQ → VENDOR_RSP → CLIENT_RSP
    ↓          ↓          ↓          ↓
  Client →  Bedrock  →  Bedrock  →  Client
```

### Embeddings (`/v1/embeddings`)
```
EMB_REQ → VENDOR_REQ → VENDOR_RSP
   ↓          ↓          ↓
Client →  Bedrock  →  Client
```

## Log Format Standards

### Transport Log Format
```
LOG_TYPE: tid=TRACE_ID, key1=value1, key2=value2, ...
```

### Key Fields
- `tid`: UUID trace ID for request correlation
- `url`: Request URL endpoint
- `body`: Request/response payload (truncated for large content)
- `status`: HTTP status code
- `MODEL`: AI model name (for vendor requests)
- Custom fields per operation type

## Grep Commands for Analysis

### Basic Queries
```bash
# All transport logs
grep "transport_logger" proxy_server.log

# Client interactions
grep "CLIENT_" proxy_server.log

# Vendor interactions
grep "VENDOR_" proxy_server.log

# Streaming data
grep "CHUNK\|DONE" proxy_server.log

# Errors
grep "ERR" proxy_server.log
```

### Advanced Filtering
```bash
# Specific trace ID
grep "tid=12345678-1234-1234-1234-123456789abc" proxy_server.log

# Chat completions only
grep "CLIENT_REQ.*chat/completions" proxy_server.log

# Error responses
grep "CLIENT_RSP.*status=[45]" proxy_server.log

# Streaming session
grep "tid=TRACE_ID" proxy_server.log | grep "CHUNK\|DONE"
```

## Monitoring and Debugging

### Health Checks
1. **Request/Response Balance**: `CLIENT_REQ` count should match `CLIENT_RSP`
2. **Vendor Communication**: Each `CLIENT_REQ` should have `VENDOR_REQ`/`VENDOR_RSP`
3. **Streaming Integrity**: `DONE` should follow `CHUNK` sequences
4. **Error Patterns**: Monitor `ERR` logs for failure points

### Performance Monitoring
```bash
# Response time analysis (requires timestamp parsing)
grep "CLIENT_RSP" proxy_server.log | head -20

# Token usage tracking
grep "token_usage" proxy_server.log

# Rate limiting events
grep "429\|rate.limit" proxy_server.log
```

### Troubleshooting
```bash
# Failed requests
grep "CLIENT_RSP.*status=[5]" proxy_server.log

# Missing vendor responses
grep "CLIENT_REQ" proxy_server.log | grep -v "VENDOR_REQ"

# Streaming issues
grep "CHUNK.*error\|DONE.*error" proxy_server.log
```

## Configuration

### Log Levels
```python
# Set in environment or config
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Log Rotation
Transport logs support timestamp-based rotation:
```
proxy_server.log.2024-01-15
proxy_server.log.2024-01-16
```

## Best Practices

### Development
- Use `DEBUG` level for detailed troubleshooting
- Enable transport logging for API debugging
- Monitor trace IDs across request lifecycle

### Production
- Use `INFO` level for normal operations
- Archive logs regularly
- Monitor error patterns
- Set up alerts for critical failures

### Security
- Transport logs contain request/response data
- Redact sensitive information in production
- Implement log encryption if required
- Follow data retention policies

## Log Evolution

The logging system has evolved through several phases:

1. **Phase 1**: Basic logging with inconsistent formats
2. **Phase 2**: Structured logging with trace IDs
3. **Phase 3**: Standardized keywords (`CLIENT_*`, `VENDOR_*`)
4. **Phase 4**: Endpoint-specific prefixes (`EMB_*` for embeddings)
5. **Phase 5**: Clear directional naming (`VENDOR_*` vs `BACKEND_*`)

## Future Enhancements

- Distributed tracing integration (OpenTelemetry)
- Metrics export (Prometheus)
- Structured logging with JSON format
- Log aggregation and analysis tools
- Real-time monitoring dashboards</content>
<parameter name="filePath">docs/LOGGING_SYSTEM.md