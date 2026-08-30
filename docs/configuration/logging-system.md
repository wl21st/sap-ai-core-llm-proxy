# Logging System & Keywords Reference

The SAP AI Core LLM Proxy implements a structured logging architecture designed for high observability, debugging, and auditability across requests, vendor calls, and streaming chunks.

---

## 1. Log Architecture & Loggers

The server uses specialized loggers for different operational concerns:

```python
# Core loggers
logger = get_server_logger(__name__)           # General application events & errors
transport_logger = get_transport_logger(__name__)  # Inbound/outbound HTTP payloads
token_usage_logger = get_server_logger("token_usage")  # Token counts & cost metrics
```

### Log Levels
- **Server Logs (`INFO`/`ERROR`)**: Server lifecycle, configuration warnings, error stack traces.
- **Transport Logs (`INFO`)**: Wire-level client requests/responses and vendor requests/responses.
- **Token Usage Logs (`INFO`)**: Structured token counts (input, output, cached, reasoning).
- **Debug Logs (`DEBUG`)**: Detailed state transitions and raw socket/stream chunks.

---

## 2. Transport Log Keyword Dictionary

The proxy attaches short, structured prefixes to transport logs to make searching and log filtering straightforward:

| Keyword | Direction | Description | Example |
|---|---|---|---|
| `REQ` | Client → Proxy | Inbound request received from client | `REQ: tid=a1b2, url=/v1/chat/completions` |
| `RSP` | Proxy → Client | Outbound response sent to client | `RSP: tid=a1b2, status=200` |
| `OUT_REQ` | Proxy → Vendor | Outbound request dispatched to SAP AI Core / Bedrock | `OUT_REQ: tid=a1b2, MODEL=anthropic--claude-4.5-sonnet` |
| `OUT_RSP` | Vendor → Proxy | Inbound response received from SAP AI Core / Bedrock | `OUT_RSP: tid=a1b2, status=200` |
| `CHUNK` | Stream ↔ Both | Streaming chunk emitted or received | `CHUNK: tid=a1b2, delta={"content": "Hello"}` |
| `DONE` | Stream ↔ Both | Streaming completion marker emitted | `DONE: tid=a1b2, Streaming completed` |
| `ERR` | Error ↔ Both | Error response emitted | `ERR: tid=a1b2, status=429, Rate limit exceeded` |

---

## 3. Log Flow Sequences

### Non-Streaming Request
```
Client Request
      │
      ▼
  [REQ] ──► [OUT_REQ] ──► SAP AI Core / Bedrock
                               │
  [RSP] ◄── [OUT_RSP] ◄────────┘
```

### Streaming Request
```
Client Request
      │
      ▼
  [REQ] ──► [OUT_REQ] ──► SAP AI Core / Bedrock
                               │
  [CHUNK] ◄── [CHUNK] ◄────────┤
  [CHUNK] ◄── [CHUNK] ◄────────┤
  [DONE]  ◄── [DONE]  ◄────────┘
```

---

## 4. Useful Grep Commands for Log Analysis

```bash
# View all client-side requests
grep "REQ:" logs/server_*.log

# View all vendor requests and models targeted
grep "OUT_REQ:" logs/server_*.log

# View all error responses
grep "ERR:" logs/server_*.log

# Follow streaming chunks and completion markers
grep -E "CHUNK:|DONE:" logs/server_*.log

# Trace a specific transaction ID
grep "tid=a1b2c3d4" logs/server_*.log

# Extract token usage summaries
grep "TOKEN_USAGE" logs/server_*.log
```
