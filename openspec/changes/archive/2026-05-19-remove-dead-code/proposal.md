## Why

The codebase has accumulated 47 unused imports, 11 unused local variables, and dead code across production and test files. Removing them reduces cognitive load, eliminates misleading dependencies, and keeps static analysis output clean so real issues stand out.

## What Changes

- Remove 14 unused imports from production files (`config/`, `handlers/`, `routers/`, `utils/`)
- Remove 33 unused imports from test files
- Remove 11 unused local variable assignments from test files
- Remove `load_balancer.get_counters()` — defined but never called anywhere (production or tests)
- Remove `handlers/streaming_generators.generate_bedrock_streaming_response_sync()` — defined but never called anywhere (only the async variant is used)
- No behavior changes — all removals are unreferenced symbols
- Add unit API tests to assert key route handlers still respond correctly post-cleanup
- Add integration smoke tests to confirm end-to-end behavior is unchanged

## Capabilities

### New Capabilities
<!-- None — this is a cleanup change with no new behavior -->

### Modified Capabilities
<!-- No spec-level behavior changes -->

## Impact

- **Files changed**: `load_balancer.py`, `handlers/streaming_generators.py`, `config/config_parser.py`, `routers/messages.py`, `utils/cache_utils.py`, `utils/metrics_middleware.py`, and ~15 test files
- **Kept intentionally**: `load_balancer.reset_counters()` (test fixture utility), `proxy_server.format_embedding_response()` (has dedicated unit test)
- **No API changes** — all removed symbols are internal and unreferenced
- **No dependency changes** — imports being removed are already unused
- **Test suite** — all existing tests must continue to pass after cleanup
- **New unit API tests** — added to `tests/unit/` covering routes touched by cleanup (`/v1/chat/completions`, `/v1/messages`, `/v1/models`)
- **New integration tests** — added to `tests/integration/` as smoke tests for the same routes post-cleanup
