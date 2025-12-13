# Agent Guidelines for sap-ai-core-llm-proxy

## Build/Test Commands

- **Install dependencies**: `uv sync` (preferred) or `pip install -r requirements.txt`
- **Run proxy server**: `python proxy_server.py --config config.json`
- **Debug mode**: `python proxy_server.py --config config.json --debug`
- **Run tests**: `make test` (uses pytest if available)
- **Build binary**: `make build` or `make build-tested` (with tests)
- **Run single test**: No test files exist yet in this project

## Code Style

- **Python version**: 3.13 (required, see pyproject.toml)
- **Imports**: Use dataclasses for config structures, standard library first, then third-party (Flask, requests), then SAP AI SDK imports
- **Type hints**: Use typing annotations (Dict, List, Optional, Any) where applicable
- **Classes**: Use @dataclass for data structures (see ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig in proxy_server.py)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Error handling**: Use try-except with proper logging; handle HTTP 429 errors with dedicated handler (handle_http_429_error)
- **Logging**: Use logging module; support --debug flag for detailed output
- **Threading**: Use threading.Lock for shared resources (tokens, SDK clients)
- **Caching**: Reuse expensive objects (SDK sessions/clients) with thread-safe caching patterns
- **Documentation**: Include docstrings for functions/classes; maintain detailed README.md
