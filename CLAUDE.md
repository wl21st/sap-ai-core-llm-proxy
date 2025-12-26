# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an SAP AI Core LLM Proxy Server that transforms SAP AI Core LLM APIs into OpenAI-compatible APIs. It supports multiple model providers (Claude, GPT, Gemini) and implements load balancing across multiple SAP AI Core subaccounts.

**Key Features:**
- Multi-model support: Claude 4.x, Gemini 2.5, GPT-4o/4.1/o3
- Multi-subaccount load balancing with round-robin distribution
- OpenAI Chat Completions API (`/v1/chat/completions`)
- Anthropic Messages API (`/v1/messages`)
- OpenAI Embeddings API (`/v1/embeddings`)
- Streaming support via Server-Sent Events (SSE)

## Development Commands

### Setup
```bash
# Install dependencies (using uv - recommended)
uv sync

# Install with dev dependencies
uv sync --extra dev

# Install build dependencies
uv sync --extra build
```

### Running the Server
```bash
# Standard mode
python proxy_server.py --config config.json

# Debug mode (detailed logging)
python proxy_server.py --config config.json --debug

# Using uv
uv run python proxy_server.py --config config.json
```

### Testing
```bash
# Run all unit tests (excludes integration tests)
make test

# Run tests with coverage report
make test-cov

# Run verbose tests
make test-verbose

# Run specific test file
make test-file FILE=tests/test_proxy_server.py

# Run tests matching a pattern
make test-pattern PATTERN=token

# Run integration tests (requires running server)
make test-integration

# Run integration smoke tests (quick validation)
make test-integration-smoke

# Run integration streaming tests
make test-integration-streaming

# Run integration tests for specific model
make test-integration-model MODEL=gpt-4.1
```

### Building
```bash
# Build binary executable
make build

# Build with tests
make build-tested

# Build debug version (with console)
make build-debug
```

### Linting & Type Checking
```bash
# Format code with black
uv run black .

# Check formatting with black
uv run black . --check

# Run ruff linter
uv run ruff check .

# Auto-fix with ruff
uv run ruff check . --fix

# Type checking with basedpyright
uv run basedpyright

# Run pylint
uv run pylint proxy_server.py proxy_helpers.py
```

## Architecture

### Core Structure

The codebase consists of:
- **`proxy_server.py`** (2348 lines) - Main Flask application with endpoints, token management, load balancing
- **`proxy_helpers.py`** (1193 lines) - Model detection and format conversion utilities
- **`config/`** - Configuration management using Pydantic models
- **`auth/`** - Authentication and token management (modular structure)
- **`utils/`** - Logging, error handlers, SDK utilities

### Key Components

1. **Configuration Management** (`config/`)
   - `ProxyConfig` - Multi-subaccount configuration
   - `SubAccountConfig` - Individual subaccount with deployment models
   - Pydantic-based validation

2. **Authentication** (`auth/`)
   - `TokenManager` - SAP AI Core OAuth token fetching and caching
   - `RequestValidator` - API request token verification
   - Thread-safe token caching with expiry

3. **Load Balancing** (`proxy_server.py:1605`)
   - Round-robin across subaccounts
   - Round-robin across deployment URLs within subaccount
   - Automatic model fallback

4. **Format Converters** (`proxy_helpers.py`)
   - OpenAI ↔ Claude format conversion
   - OpenAI ↔ Gemini format conversion
   - Streaming chunk conversion for SSE

5. **Endpoints**
   - `/v1/models` - List available models
   - `/v1/chat/completions` - OpenAI-compatible chat (streaming & non-streaming)
   - `/v1/messages` - Anthropic Claude Messages API (streaming & non-streaming)
   - `/v1/embeddings` - OpenAI embeddings API

### Data Flow

```
Client Request
  → Authentication (verify_request_token)
  → Load Balancer (load_balance_url)
  → Token Manager (fetch_token for subaccount)
  → Format Converter (convert_openai_to_claude/gemini)
  → SAP AI Core API
  → Format Converter (convert_claude/gemini_to_openai)
  → Client Response
```

### Model Detection

Model type is detected using helper functions in `proxy_helpers.py`:
- `is_claude_model()` - Detects Claude models (claude-*, sonnet-*, anthropic--)
- `is_claude_37_or_4()` - Detects Claude 3.7/4/4.5 variants
- `is_gemini_model()` - Detects Gemini models (gemini-*)

### Configuration File

The `config.json` uses multi-subaccount structure:
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

## Python Conventions

This project follows **PEP 8** conventions:
- Variables/functions: `snake_case` (e.g., `fetch_token`, `user_name`)
- Classes: `PascalCase` (e.g., `ProxyConfig`, `TokenManager`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CLAUDE_MODEL`, `MAX_RETRIES`)
- Private members: `_leading_underscore` (e.g., `_internal_helper`)
- Booleans: Prefix with `is_`, `has_`, `can_`, `should_` (e.g., `is_valid`)

**Type Hints:** Always use type hints for function signatures.

**See:** `PYTHON_CONVENTIONS.md` for detailed conventions.

## Critical Implementation Details

### 1. Token Management
- Tokens are cached per subaccount with 5-minute buffer before expiry
- Thread-safe using `threading.Lock()`
- Located in: `auth/token_manager.py:TokenManager.fetch_token()`

### 2. Load Balancing
- Round-robin counter per subaccount: `proxy_config.subaccounts[name].counter`
- Model fallback: Tries normalized model names if exact match not found
- Located in: `proxy_server.py:1605`

### 3. Streaming Responses
- Uses Flask `stream_with_context()` for SSE
- Converts backend chunks to OpenAI format on-the-fly
- Token usage extracted from final metadata chunk
- Located in: `proxy_server.py:2411` (streaming handlers)

### 4. Format Conversion
- Bidirectional converters for OpenAI/Claude/Gemini
- Handles system messages, tool calls, and multi-turn conversations
- Located in: `proxy_helpers.py:Converters` class

### 5. Retry Logic
- Conservative retry with exponential backoff (4 attempts max)
- Only retries on rate limit errors (429, "too many tokens")
- Uses `tenacity` library with `@bedrock_retry` decorator
- Configuration: `RETRY_MAX_ATTEMPTS=4`, `RETRY_MIN_WAIT=4s`, `RETRY_MAX_WAIT=16s`

### 6. SAP AI SDK Integration
- Uses `gen_ai_hub.proxy.native.amazon.clients.ClientWrapper` for Bedrock
- SDK clients are cached in `_bedrock_clients` dict per deployment ID
- Config loaded from `~/.aicore/config.json`

## Testing Strategy

### Unit Tests (`tests/`)
- **50 passing tests** with **28% coverage** (focused on critical paths)
- Mock external dependencies (HTTP, SDK calls, file I/O)
- Test dataclasses, model detection, conversion functions, token management, load balancing

### Integration Tests (`tests/integration/`)
- Test against live proxy server (localhost)
- Validate all 5 required models: `anthropic--claude-4.5-sonnet`, `sonnet-4.5`, `gpt-4.1`, `gpt-5`, `gemini-2.5-pro`
- Test streaming and non-streaming modes
- Enhanced request/response logging
- Markers: `@pytest.mark.real`, `@pytest.mark.smoke`, `@pytest.mark.streaming`

### Running Tests
Always run unit tests before committing:
```bash
make test
```

For integration tests, start the server first:
```bash
# Terminal 1
python proxy_server.py --config config.json

# Terminal 2
make test-integration
```

## Known Issues & Technical Debt

### High Priority
1. **Monolithic Architecture** - `proxy_server.py` is 2348 lines (see `docs/ARCHITECTURE.md`)
2. **Hardcoded Model Normalization** - `normalize_model_names()` has `if False:` at line 56
3. **Limited Logging Configuration** - Logging levels are hardcoded

### Medium Priority
4. **No Connection Pooling** - Creates new connection per request
5. **Sensitive Data in Logs** - Tokens may be partially logged
6. **Global State** - Uses global variables (`proxy_config`, `_bedrock_clients`)

See `docs/ARCHITECTURE.md` for complete technical debt analysis.

## Common Development Tasks

### Adding a New Model Provider
1. Add model detection function in `proxy_helpers.py:Detector`
2. Add format converters in `proxy_helpers.py:Converters`
3. Add streaming chunk conversion in `proxy_server.py` streaming handlers
4. Update model detection in endpoint handlers
5. Add tests in `tests/test_proxy_helpers.py`

### Adding a New Endpoint
1. Define Flask route in `proxy_server.py`
2. Add authentication with `verify_request_token()`
3. Implement load balancing with `load_balance_url()`
4. Add format conversion if needed
5. Add integration tests in `tests/integration/`

### Modifying Format Conversion
1. Update converter in `proxy_helpers.py:Converters`
2. Update corresponding reverse converter
3. Add unit tests in `tests/test_proxy_helpers.py`
4. Run integration tests to validate end-to-end

### Debugging Issues
1. Enable debug mode: `python proxy_server.py --config config.json --debug`
2. Check logs in `logs/` directory (if configured)
3. Use integration tests with logging: `pytest tests/integration/ --log-cli-level=DEBUG -v`
4. Inspect SAP AI Core responses in transport logs

## Important Files

- `proxy_server.py` - Main Flask application (2348 lines)
- `proxy_helpers.py` - Model detection and format conversion (1193 lines)
- `config/` - Configuration management with Pydantic
- `auth/` - Authentication and token management
- `utils/` - Logging, error handling, SDK utilities
- `config.json` - Server configuration (multi-subaccount)
- `pyproject.toml` - Project metadata and dependencies
- `Makefile` - Build, test, and release automation
- `docs/ARCHITECTURE.md` - Comprehensive architecture documentation
- `docs/TESTING.md` - Testing guide
- `tests/README.md` - Test suite documentation

## Release Process

The project uses a decoupled build/release workflow (see `docs/RELEASE_WORKFLOW.md`):

```bash
# 1. Build and test
make build-tested

# 2. Bump version
make version-bump-patch  # or minor/major

# 3. Commit, tag, and push
make workflow-commit-and-tag

# 4. Prepare release artifacts
make release-prepare

# 5. Upload to GitHub
make release-github
```

## Additional Resources

- **Architecture Diagrams:** `docs/ARCHITECTURE.md` - System overview, request flow, data models
- **Testing Guide:** `docs/TESTING.md` - Comprehensive testing documentation
- **Release Workflow:** `docs/RELEASE_WORKFLOW.md` - Complete release process
- **Python Conventions:** `PYTHON_CONVENTIONS.md` - Naming and style guide
- **Integration Tests:** `tests/integration/README.md` - Real integration test guide
