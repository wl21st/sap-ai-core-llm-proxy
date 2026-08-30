# Testing Guide for SAP AI Core LLM Proxy

This document outlines the testing architecture, pytest markers, commands, and guidelines for the SAP AI Core LLM Proxy project.

---

## 1. Test Suite Architecture

```
tests/
├── unit/                      # Fast, isolated unit tests (mocked external calls)
│   ├── routers/               # Router tests (chat, models, messages, status)
│   ├── test_auth/             # Token manager and request validator tests
│   ├── test_handlers/         # Streaming handler and generator tests
│   └── test_load_balancer.py  # Load balancing and routing tests
│
├── api/                       # Direct Bedrock SDK tests (requires ~/.aicore/config.json)
│   └── test_bedrock_unsupported_fields.py
│
└── integration/               # End-to-end integration tests against running proxy
    ├── test_chat_completions.py
    ├── test_messages_endpoint.py
    └── test_models_endpoint.py
```

---

## 2. Running Tests

### Unit Tests (Recommended for CI / Fast Feedback)
```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# Run with coverage report
uv run pytest tests/unit/ --cov=. --cov-report=term-missing
```

### Integration Tests (Against Live Localhost Proxy)
```bash
# Start proxy in background or separate terminal:
uvx --from . sap-ai-proxy --config config.json

# Run integration tests
uv run pytest tests/integration/ -m real -v
```

### Direct Bedrock API Tests
```bash
# Requires valid ~/.aicore/config.json
uv run pytest tests/api/ -m bedrock -v
```

---

## 3. Pytest Markers Reference

| Marker | Description |
|---|---|
| `@pytest.mark.unit` | Isolated unit tests |
| `@pytest.mark.real` | End-to-end integration tests against a live server |
| `@pytest.mark.bedrock` | Direct Bedrock SDK backend tests |
| `@pytest.mark.smoke` | Quick smoke validation tests |
| `@pytest.mark.streaming` | Server-Sent Events (SSE) streaming tests |
