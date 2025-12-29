# Agent Guidelines for sap-ai-core-llm-proxy

## Build/Test Commands

### Setup & Running
- **Install dependencies**: `uv sync` (uses uv package manager, not pip)
- **Install dev dependencies**: `uv sync --extra dev`
- **Install build dependencies**: `uv sync --extra build`
- **Run proxy server (recommended)**: `uvx --from . sap-ai-proxy --config config.json`
- **Run proxy server (standard)**: `python proxy_server.py --config config.json`
- **Debug mode**: `python proxy_server.py --config config.json --debug`

### Testing (50+ tests, 28% coverage)
- **Run all unit tests**: `make test` (excludes integration tests)
- **Run with coverage**: `make test-cov`
- **Run verbose tests**: `make test-verbose`
- **Run specific test file**: `make test-file FILE=tests/test_proxy_server.py`
- **Run tests matching pattern**: `make test-pattern PATTERN=token`
- **Run integration tests**: `make test-integration` (requires running server)
- **Run integration smoke tests**: `make test-integration-smoke`
- **Run integration streaming tests**: `make test-integration-streaming`
- **Run integration tests for model**: `make test-integration-model MODEL=gpt-4.1`
- **Run single test**: `uv run pytest tests/test_name.py::test_function`

### Building & Release
- **Build binary**: `make build` or `make build-tested` (builds with PyInstaller)
- **Build debug version**: `make build-debug` (with console)
- **Clean artifacts**: `make clean` or `make clean-all`
- **Version management**: `make version-show`, `make version-bump-patch/minor/major`
- **Release workflow**: `make workflow-patch/minor/major` (bump, build, tag, prepare)
- **Prepare release**: `make release-prepare`
- **Upload to GitHub**: `make release-github`

## Architecture Overview

The proxy transforms SAP AI Core LLM APIs into OpenAI-compatible APIs with multi-model support.

**Core Files:**
- `proxy_server.py` (2501 lines) - Main Flask app, endpoints, token management, load balancing
- `proxy_helpers.py` (1414 lines) - Model detection, format conversion utilities
- `config/` - Pydantic-based configuration management
- `auth/` - Token management and request validation (thread-safe)
- `utils/` - Logging, error handlers, SDK utilities

**Key Features:**
- Multi-model support: Claude 4.x, Gemini 2.5, GPT-4o/4.1/o3
- Multi-subaccount load balancing with round-robin distribution
- OpenAI Chat Completions API (`/v1/chat/completions`)
- Anthropic Messages API (`/v1/messages`)
- OpenAI Embeddings API (`/v1/embeddings`)
- Streaming support via SSE

**Request Flow:**
```
Client → Authentication (verify_request_token)
      → Load Balancer (load_balance_url)
      → Token Manager (fetch_token for subaccount)
      → Format Converter (convert_openai_to_claude/gemini)
      → SAP AI Core API
      → Format Converter (convert_claude/gemini_to_openai)
      → Client Response
```

## Code Style (PEP 8)

- **Python version**: 3.13+ (required per pyproject.toml, <3.14)
- **Package manager**: Use `uv` commands, not pip (e.g., `uv add package`, `uv run python`)
- **Import order**: Standard library first, then third-party (Flask, requests, openai, litellm), then SAP AI SDK imports (ai_core_sdk, gen_ai_hub, sap-ai-sdk-gen)
- **Type hints**: Required for all function signatures (Dict, List, Optional, Any)
- **Naming conventions** (see `PYTHON_CONVENTIONS.md`):
  - Functions/variables: `snake_case` (e.g., `fetch_token`, `user_name`)
  - Classes: `PascalCase` (e.g., `ProxyConfig`, `TokenManager`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CLAUDE_MODEL`, `MAX_RETRIES`)
  - Private members: `_leading_underscore` (e.g., `_internal_helper`)
  - Booleans: Prefix with `is_`, `has_`, `can_`, `should_` (e.g., `is_valid`)
- **Classes**: Use Pydantic models or @dataclass with field() for data structures (see ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig)
- **Error handling**: Always use try-except with logging.error(); handle HTTP 429 with conservative retry logic (tenacity)
- **Logging**: Use logging module with levels (INFO/DEBUG/ERROR); support --debug flag via argparse
- **Threading**: Use threading.Lock for shared state (tokens, SDK clients); see _sdk_session_lock pattern
- **Caching**: Reuse expensive SDK objects (Session, clients) with thread-safe lazy initialization patterns
- **Docstrings**: Google-style docstrings with Args/Returns/Raises sections for all public functions
- **Flask routes**: Add logging at start of each route handler; verify tokens with verify_request_token()
- **Config**: Use Pydantic-based config (ProxyConfig) loaded from JSON; validate on startup

## Critical Implementation Details

### Token Management (auth/token_manager.py)
- Tokens cached per subaccount with 5-minute buffer before expiry
- Thread-safe using `threading.Lock()`
- Located in: `auth/token_manager.py:TokenManager.fetch_token()`

### Load Balancing (proxy_server.py:1605)
- Round-robin across subaccounts
- Round-robin across deployment URLs within subaccount
- Model fallback: Tries normalized model names if exact match not found
- Counter per subaccount: `proxy_config.subaccounts[name].counter`

### Model Detection (proxy_helpers.py)
- `is_claude_model()` - Detects Claude models (claude-*, sonnet-*, anthropic--)
- `is_claude_37_or_4()` - Detects Claude 3.7/4/4.5 variants (uses `/converse` endpoint)
- `is_gemini_model()` - Detects Gemini models (gemini-*)
- Claude 3.7/4/4.5: Uses `/converse` or `/converse-stream` endpoint
- Claude 3.5 and older: Uses `/invoke` or `/invoke-with-response-stream` endpoint
- Gemini: Uses `/generateContent` endpoint

### Format Conversion (proxy_helpers.py:Converters)
- Bidirectional converters for OpenAI ↔ Claude ↔ Gemini
- Handles system messages, tool calls, multi-turn conversations
- Streaming chunk conversion for SSE

### Retry Logic
- Conservative retry with exponential backoff (4 attempts max)
- Only retries on rate limit errors (429, "too many tokens")
- Uses `tenacity` library with `@bedrock_retry` decorator
- Configuration: `RETRY_MAX_ATTEMPTS=4`, `RETRY_MIN_WAIT=4s`, `RETRY_MAX_WAIT=16s`

### SAP AI SDK Integration
- Uses `gen_ai_hub.proxy.native.amazon.clients.ClientWrapper` for Bedrock
- SDK clients cached in `_bedrock_clients` dict per deployment ID
- Config loaded from `~/.aicore/config.json`

## Configuration

Multi-subaccount structure in `config.json`:
```json
{
  "subAccounts": {
    "account1": {
      "resource_group": "default",
      "service_key_json": "key1.json",
      "deployment_models": {
        "gpt-4o": ["https://api.ai..."],
        "claude-4.5": ["https://api.ai..."]
      }
    }
  },
  "secret_authentication_tokens": ["token1", "token2"],
  "port": 3001,
  "host": "127.0.0.1"
}
```

## Known Technical Debt

**High Priority:**
1. Monolithic Architecture - `proxy_server.py` is 2501 lines (see `docs/ARCHITECTURE.md`)
2. Hardcoded Model Normalization - `normalize_model_names()` has `if False:` at line 56
3. Limited Logging Configuration - Logging levels are hardcoded

**Medium Priority:**
4. No Connection Pooling - Creates new connection per request
5. Sensitive Data in Logs - Tokens may be partially logged
6. Global State - Uses global variables (`proxy_config`, `_bedrock_clients`)

See `docs/ARCHITECTURE.md` for complete technical debt analysis.
