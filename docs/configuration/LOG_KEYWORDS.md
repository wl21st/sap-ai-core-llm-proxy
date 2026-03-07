# SAP AI Core LLM Proxy - Log Keywords Reference

This document lists all log keywords used in the proxy server transport logs and provides grep commands to find specific log entries for debugging and monitoring.

## Log Keywords Overview

The proxy server uses structured logging with specific keywords to distinguish between different types of operations:

### Client-Side Operations
- `REQ` - Incoming requests from clients
- `RSP` - Outgoing responses to clients

### Vendor-Side Operations  
- `OUT_REQ` - Outgoing requests to AI vendor (AWS Bedrock)
- `OUT_RSP` - Incoming responses from AI vendor (AWS Bedrock)

### Streaming Operations
- `CHUNK` - Streaming response data chunks
- `DONE` - Stream completion signals

### Error Operations
- `ERR` - Error responses and failures

## Grep Commands for Log Analysis

### Find All Transport Logs
```bash
grep "transport_logger" proxy_server.log
```

### Client Operations
```bash
# All client interactions
grep "CLIENT_" proxy_server.log

# Client requests only
grep "REQ" proxy_server.log

# Client responses only  
grep "RSP" proxy_server.log
```

### Vendor Operations
```bash
# All vendor interactions
grep "OUT_" proxy_server.log

# Requests to vendor
grep "OUT_REQ" proxy_server.log

# Responses from vendor
grep "OUT_RSP" proxy_server.log
```

### Streaming Operations
```bash
# All streaming data
grep "CHUNK\|DONE" proxy_server.log

# Streaming chunks only
grep "CHUNK" proxy_server.log

# Stream completions only
grep "DONE" proxy_server.log
```

### Error Operations
```bash
# All errors
grep "ERR" proxy_server.log
```

### Advanced Filtering

#### Find logs for specific trace ID
```bash
# Replace TID with actual trace ID
grep "tid=TID" proxy_server.log
```

#### Find logs for specific endpoint
```bash
# Chat completions
grep "REQ.*chat/completions" proxy_server.log

# Embeddings
grep "REQ.*embeddings" proxy_server.log

# Messages
grep "REQ.*messages" proxy_server.log
```

#### Find logs with specific status codes
```bash
# Successful responses (2xx)
grep "RSP.*status=2" proxy_server.log

# Error responses (4xx/5xx)
grep "RSP.*status=[45]" proxy_server.log
```

#### Find streaming sessions
```bash
# Complete streaming session for a trace ID
grep "tid=TID" proxy_server.log | grep "CHUNK\|DONE"
```

## Log Format Structure

All transport logs follow this format:
```
LOG_TYPE: tid=TRACE_ID, additional_fields...
```

### Examples
```
REQ: tid=12345678-1234-1234-1234-123456789abc, url=http://..., body={...}
OUT_REQ: tid=12345678-1234-1234-1234-123456789abc, MODEL=claude-3-5-sonnet, BODY={...}
CHUNK: tid=12345678-1234-1234-1234-123456789abc, {...}
RSP: tid=12345678-1234-1234-1234-123456789abc, status=200, body={...}
DONE: tid=12345678-1234-1234-1234-123456789abc, Streaming completed
```

## Quick Reference

| Keyword | Direction | Description |
|---------|-----------|-------------|
| `REQ` | → Client | Request received from client |
| `RSP` | ← Client | Response sent to client |
| `OUT_REQ` | → Vendor | Request sent to AI vendor |
| `OUT_RSP` | ← Vendor | Response received from AI vendor |
| `CHUNK` | ↔ Both | Streaming data chunk |
| `DONE` | ↔ Both | Stream completion |
| `ERR` | ← Both | Error response |

## Monitoring Tips

1. **Request/Response Balance**: Number of `REQ` should match `RSP`
2. **Vendor Calls**: Each `REQ` should have corresponding `OUT_REQ`/`OUT_RSP`
3. **Streaming Health**: Look for `DONE` after `CHUNK` sequences
4. **Error Patterns**: Check `ERR` logs for failure points

## Log Levels

Transport logs are written at `INFO` level by default. To see them:
```bash
# Set log level to INFO or DEBUG
export LOG_LEVEL=INFO
python proxy_server.py
```</content>
<parameter name="filePath">docs/LOG_KEYWORDS.md