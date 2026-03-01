## Why

Introduce a background smoke test that periodically verifies authentication status and performs re‑authentication for Anthropic, OpenAI, and embedding model endpoints. The test should run on a configurable interval (default 5 minutes) and expose APIs to configure and retrieve the current settings. This ensures the proxy remains healthy and responsive, catching auth‑related issues early without manual intervention.

## What Changes

- Add a background service that executes authentication status checks and re‑authentication flows for Anthropic, OpenAI, and embedding models on a scheduled basis.
- Make the check interval configurable, defaulting to 5 minutes, with an API to update the interval.
- Add API endpoints to retrieve the current configuration and to apply a new configuration.
- Integrate the scheduled execution using a timer or thread‑based approach in Python.
- Update configuration validation to include the new smoke‑test settings.

## Capabilities

### New Capabilities
- `background-smoke-test`: Periodic authentication status and re‑authentication checks for Anthropic, OpenAI, and embedding endpoints.
- `configurable-interval`: Adjustable interval for the background checks, default 5 minutes.
- `api-reconfigure-smoke-test`: Endpoint to modify the smoke‑test configuration.
- `api-show-smoke-test-config`: Endpoint to fetch the current configuration.

### Modified Capabilities
- `smoke-test`: Extended to include authn status verification and re‑auth across Anthropic, OpenAI, and embedding model providers.

## Impact

- **Code**: New background thread management, configuration schema extensions, and additional Flask routes in `proxy_server.py`.
- **APIs**: Introduction of `/smoke-test/config` (GET/POST) and related health‑check endpoints.
- **Dependencies**: May interact with existing timer/scheduler utilities; ensure thread safety.
- **Breaking Changes**: None – all changes are additive and preserve existing functionality.