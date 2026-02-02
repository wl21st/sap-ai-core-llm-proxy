## Context

- We have implemented basic auto-discovery logic (in `config_parser.py` and `sdk_utils.py`) but haven't successfully loaded the alias map from JSON yet.
- The user requested two enhancements:
    1.  **Static JSON for Aliases**: Load `MODEL_ALIASES` from a JSON file (`config/aliases.json`).
    2.  **Caching**: Use `diskcache` to cache the deployment API response for a configurable duration (e.g., 7 days) to reduce startup latency and API calls.

## Goals

- **Performance**: Startup should be fast. Repeated restarts shouldn't spam the SAP AI Core API.
- **Configurability**: Cache duration should be configurable (default 7 days). Alias list should be easy to edit without code changes.

## Decisions

- **Alias Loading**: We will keep `MODEL_ALIASES` in `proxy_helpers.py` but populate it by reading `config/aliases.json`. If the file is missing/invalid, fallback to empty or hardcoded defaults (safety net).

- **Caching Strategy**:
    - We will use `diskcache.Cache` stored in `.cache/deployments` (or similar).
    - We will wrap `fetch_all_deployments` (or the internal query) with caching logic.
    - **Cache Key**: `hash(service_key.client_id + service_key.api_url + resource_group)`.
    - **Duration**: Default 7 days (604800 seconds). We can add a `CACHE_DURATION` env var or config setting.
    - **Invalidation**: If a user adds a new deployment, they might need to clear the cache. We should log where the cache is so they can delete it, or provide a CLI flag `--no-cache` / `--refresh`.

## Risks

- **Stale Data**: If a deployment is deleted or added, the proxy won't know for 7 days.
    - *Mitigation*: Add a `--refresh-cache` flag to the server/CLI to force a fetch.
- **Disk Usage**: `diskcache` is generally efficient, but we should ensure the cache dir is in `.gitignore`.

## Migration Plan

- Ensure `diskcache` is in `pyproject.toml` (done via `uv add`).
- Update `.gitignore` to exclude the cache directory.
