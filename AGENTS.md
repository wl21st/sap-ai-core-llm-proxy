# Agent Guidelines for sap-ai-core-llm-proxy

## Build/Test Commands

- **Install dependencies**: `uv sync` (uses uv package manager, not pip)
- **Activate virtual environment**: `source .venv/bin/activate`
- **Run proxy server**: `python proxy_server.py --config config.json`
- **Debug mode**: `python proxy_server.py --config config.json --debug`
- **Run tests**: `make test` (uses pytest if available, currently no test files exist)
- **Run single test**: `uv run pytest tests/test_name.py::test_function` (when tests exist)
- **Build binary**: `make build` or `make build-tested` (builds with PyInstaller)
- **Clean artifacts**: `make clean` or `make clean-all`
- **Version management**: `make version-show`, `make version-bump-patch/minor/major`
- **Release workflow**: `make workflow-patch/minor/major` (bump, build, tag, prepare)

## Code Style

- **Python version**: 3.13+ (required per pyproject.toml, <3.14)
- **Package manager**: Use `uv` commands, not pip (e.g., `uv add package`, `uv run python`)
- **Import order**: Standard library first, then third-party (Flask, requests, openai, litellm), then SAP AI SDK imports (ai_core_sdk, gen_ai_hub, sap-ai-sdk-gen)
- **Type hints**: Use typing module annotations (Dict, List, Optional, Any) for all function signatures
- **Classes**: Use @dataclass with field() for data structures (see ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig)
- **Naming**: snake_case for functions/variables/modules, PascalCase for classes, UPPER_CASE for constants
- **Error handling**: Always use try-except with logging.error(); handle HTTP 429 with handle_http_429_error() function
- **Logging**: Use logging module with levels (INFO/DEBUG/ERROR); support --debug flag via argparse
- **Threading**: Use threading.Lock for shared state (tokens, SDK clients); see _sdk_session_lock pattern
- **Caching**: Reuse expensive SDK objects (Session, clients) with thread-safe lazy initialization patterns
- **Docstrings**: Google-style docstrings with Args/Returns/Raises sections for all public functions
- **Flask routes**: Add logging at start of each route handler; verify tokens with verify_request_token()
- **Config**: Use dataclass-based config (ProxyConfig) loaded from JSON; validate on startup
