# PROJECT KNOWLEDGE BASE

**Single Source of Truth** for AI coding assistants working in the `sap-ai-core-llm-proxy` repository.

---

## 1. Overview
The **SAP AI Core LLM Proxy** transforms heterogeneous SAP AI Core APIs into standard OpenAI- and Anthropic-compatible endpoints with multi-model round-robin load balancing.

---

## 2. Codebase Structure
```
./
├── main.py                    # FastAPI application entrypoint & app factory
├── proxy_server.py            # Legacy/compatibility entrypoint
├── proxy_helpers.py           # Format converters & model detection helpers
├── load_balancer.py           # Multi-subaccount round-robin distribution
├── routers/                   # Modular FastAPI routers
│   ├── chat.py                # /v1/chat/completions (OpenAI format)
│   ├── messages.py            # /v1/messages (Anthropic Messages API)
│   ├── models.py              # /v1/models (OpenAI format)
│   ├── embeddings.py          # /v1/embeddings (OpenAI format)
│   └── status.py              # /health, /info, /stats observability endpoints
├── handlers/                  # Model handlers & SSE streaming generators
├── auth/                      # OAuth token manager (thread-safe) & request validator
├── config/                    # Pydantic configuration parser & models
├── utils/                     # SDK pool, logger setup, circuit breaker, retry logic
├── docs/                      # Comprehensive repository documentation
└── tests/                     # Test suites (unit/, api/, integration/)
```

---

## 3. Architecture & Key Implementation Details

### Model Detection (`proxy_helpers.py:Detector`)
- `is_claude_37_or_4()` — Claude 3.7/4/4.5 → uses `/converse` endpoint
- `is_claude_model()` — All Claude models (`claude-*`, `sonnet-*`, `anthropic--*`)
- `is_gemini_model()` — Gemini models (`gemini-*`)

### Endpoint & Protocol Selection
- **Claude 3.7/4/4.5**: `/converse` or `/converse-stream` → parsed with `convert_claude37_to_openai()`
- **Claude 3.5/older**: `/invoke` or `/invoke-with-response-stream` → parsed with `convert_claude_to_openai()`
- **Gemini**: `/generateContent` or `/streamGenerateContent` → parsed with `convert_gemini_to_openai()`
- **OpenAI/GPT**: `/chat/completions` → standard format
- **Anthropic Messages API (`/v1/messages`)**: Direct Bedrock SDK dispatch with unsupported fields (`metadata`, `output_config`, `context_management`) automatically stripped.

### Multi-Tenant Token Management & Load Balancing
- Tokens cached per subaccount with a 5-minute safety buffer before expiry (`auth/token_manager.py`).
- Thread-safe caching using `threading.Lock()`.
- Load balancing rotates requests across configured subaccounts and deployment URLs with model fallback (`load_balancer.py`).

### Resilience & Retries
- Retry logic with exponential backoff on HTTP 429 / ThrottlingException using `tenacity`.
- Automatic TLS certificate auto-discovery and recovery fallback (`utils/sdk_pool.py`).

---

## 4. Development Conventions

### Python (PEP 8)
- Variables & Functions: `snake_case` (e.g., `fetch_token`)
- Classes & Models: `PascalCase` (e.g., `SubAccountConfig`, `TokenManager`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CLAUDE_MODEL`, `MAX_RETRIES`)
- Private Members: `_leading_underscore` (e.g., `_internal_helper`)
- Booleans: Prefix with `is_`, `has_`, `can_`, `should_` (e.g., `is_valid`)
- Type Hints: Required for all function signatures.

### Anti-Patterns
1. **Never bypass token validation**: All endpoints must verify request tokens via `RequestValidator`.
2. **Never create redundant connections**: Reuse SDK clients from `utils/sdk_pool.py`.
3. **Never hardcode model names**: Use detection functions from `proxy_helpers.py:Detector`.
4. **Never modify global state without locks**: Shared state must be protected by `threading.Lock()`.

---

## 5. Developer Commands

### Environment & Dependencies
```bash
uv sync                                    # Install dependencies (uses uv, not pip)
uv sync --group dev                        # Install with development tools
```

### Running the Proxy
```bash
uvx --from . sap-ai-proxy -c config.json    # Run server (recommended)
uvx --from . sap-ai-proxy -c config.json -d # Debug mode
python main.py -c config.json              # Direct run
```

### Testing
```bash
uv run pytest tests/unit/ -v               # Run all unit tests (285+ tests)
make test                                  # Unit tests via make
make test-integration                      # Integration tests (requires running proxy)
uv run pytest tests/unit/ --cov=.          # Coverage report
```

### Linting & Formatting
```bash
uv run ruff check .                        # Lint code with ruff
uv run ruff check . --fix                  # Auto-fix lint issues
uv run basedpyright                        # Type check with basedpyright
```

### Building & Releasing
```bash
make build-tested                          # Run tests and build PyInstaller binary
make version-bump-patch                    # Bump patch version (0.1.0 → 0.1.1)
make release-prepare                       # Package release archives
make release-github                        # Publish GitHub release
```

---

## 6. Documentation Map

- **Master Index**: [`docs/README.md`](./docs/README.md)
- **Architecture**: [`docs/architecture/architecture.md`](./docs/architecture/architecture.md)
- **Technical Debt**: [`docs/architecture/technical-debt.md`](./docs/architecture/technical-debt.md)
- **Configuration & Validation**: [`docs/configuration/config-validation.md`](./docs/configuration/config-validation.md)
- **Logging System**: [`docs/configuration/logging-system.md`](./docs/configuration/logging-system.md)
- **Troubleshooting**: [`docs/guides/troubleshooting.md`](./docs/guides/troubleshooting.md)
- **Release Workflows**: [`docs/guides/release-quick-start.md`](./docs/guides/release-quick-start.md)
- **Python Conventions**: [`docs/guides/python-conventions.md`](./docs/guides/python-conventions.md)
- **Testing Guide**: [`docs/testing/testing.md`](./docs/testing/testing.md)

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **sap-ai-core-llm-proxy** (6208 symbols, 8716 relationships, 72 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/sap-ai-core-llm-proxy/context` | Codebase overview, check index freshness |
| `gitnexus://repo/sap-ai-core-llm-proxy/clusters` | All functional areas |
| `gitnexus://repo/sap-ai-core-llm-proxy/processes` | All execution flows |
| `gitnexus://repo/sap-ai-core-llm-proxy/process/{name}` | Step-by-step execution trace |

<!-- gitnexus:end -->
