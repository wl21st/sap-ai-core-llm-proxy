# Repository Guidelines

## Project Structure

This Python 3.13 FastAPI proxy exposes OpenAI- and Anthropic-compatible APIs for SAP AI Core services. Top-level entry points are `main.py` (application factory and CLI) and `proxy_server.py` (compatibility entry point). API routers live in `routers/`; provider and streaming logic in `handlers/`; OAuth and request validation in `auth/`; Pydantic configuration in `config/`; and SDK pooling, retries, logging, and resilience utilities in `utils/`. Tests are organized under `tests/unit/`, `tests/integration/`, and `tests/api/`. Design and operational documentation is under `docs/`.

## Development Setup and Commands

Use `uv` for dependency management:

```bash
uv sync --group dev
uvx --from . sap-ai-proxy -c config.json
uv run pytest tests/unit/ -v
make test-cov
make test-integration
make build-tested
```

The integration suite requires a running proxy and valid SAP AI Core configuration. `make build-tested` runs tests and builds the PyInstaller artifact. Use `make release-docker` only when Docker is available and an image build is intended.

## Coding Style

Follow PEP 8 with four-space indentation. Use `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Add type hints to function signatures. Run `uv run ruff check .` and `uv run basedpyright` before submitting changes. Reuse SDK clients from `utils/sdk_pool.py`, protect shared state with locks, and route model detection through `proxy_helpers.py` rather than hardcoding model names.

## Testing Guidelines

Use pytest. Name files `test_*.py` and test functions `test_*`. Keep unit tests isolated with mocked external calls; mark live integrations with the project’s `real`, `smoke`, `streaming`, or `bedrock` markers. Run focused tests while iterating, then the relevant unit suite. No minimum coverage threshold is currently documented.

## Commits and Pull Requests

Use concise imperative commit subjects with the established prefixes: `fix:`, `docs:`, `chore:`, or `refactor:`. Pull requests should explain the change and rationale, list validation commands and results, identify configuration or API impact, and note security implications. Link a related issue when one exists.

## Security and Configuration

Start from `config.json.example`; never commit service keys, authentication tokens, or real tenant configuration. Keep local credentials outside tracked files. Tests that access Bedrock may require `~/.aicore/config.json` and live credentials.
