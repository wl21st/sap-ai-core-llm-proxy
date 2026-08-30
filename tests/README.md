# Test Suite for SAP AI Core LLM Proxy

This directory contains the test suite for the SAP AI Core LLM Proxy.

---

## 1. Directory Structure

```
tests/
├── unit/                      # Unit tests with mocked dependencies
│   ├── routers/               # FastAPI route tests (chat, models, messages, status)
│   ├── test_auth/             # Authentication & token manager tests
│   ├── test_handlers/         # SSE streaming & model response handler tests
│   └── test_load_balancer.py  # Load balancing & model resolution tests
│
├── api/                       # Direct Bedrock SDK API tests (backend validation)
│   ├── test_bedrock_unsupported_fields.py
│   └── README.md
│
└── integration/               # End-to-end integration tests (requires running proxy)
    ├── test_chat_completions.py
    ├── test_messages_endpoint.py
    ├── test_models_endpoint.py
    └── README.md
```

---

## 2. Running Tests

```bash
# Run unit tests (Fast, no external dependencies needed)
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/unit/ --cov=. --cov-report=term-missing

# Run integration tests (Requires running server on localhost)
make test-integration
# or
uv run pytest tests/integration/ -m real -v

# Run direct Bedrock API tests
uv run pytest tests/api/ -m bedrock -v
```

---

## 3. Best Practices for Writing Tests

1. **Isolation**: Unit tests should mock external network requests and file I/O.
2. **FastAPI Dependency Injection**: Use FastAPI `dependency_overrides` when testing route handlers.
3. **Parametrization**: Use `@pytest.mark.parametrize` for testing multi-model behaviors.
4. **Markers**: Use `@pytest.mark.unit`, `@pytest.mark.real`, `@pytest.mark.bedrock`, or `@pytest.mark.streaming`.
