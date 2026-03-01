## Why

Add health, stats, and info endpoints to the proxy server so operators can monitor server status, retrieve load‑balancing details, and diagnose issues without external tools.

## What Changes

- Add `/health` endpoint that returns a simple JSON status indicating the server is running.
- Add `/stats` endpoint that returns JSON with request counters, load‑balancer metrics, and uptime.
- Add `/info` endpoint that returns JSON with proxy configuration details (e.g., active subaccounts, default model).
- Validate required keys in `config.json` at startup and fail early if missing.

## Capabilities

### New Capabilities
- `health`: New capability providing the `/health` endpoint.
- `stats`: New capability providing the `/stats` endpoint.
- `info`: New capability providing the `/info` endpoint.

### Modified Capabilities
- `proxy-config`: Updated to include validation of required configuration keys.

## Impact

- **Code**: Modifications to `proxy_server.py` to register new routes; updates to `config/` validation logic.
- **APIs**: New endpoints under the root path; responses are JSON and require no auth beyond existing token checks.
- **Dependencies**: May affect the load balancer module and logging configuration.
- **Breaking Changes**: None; all changes are additive.