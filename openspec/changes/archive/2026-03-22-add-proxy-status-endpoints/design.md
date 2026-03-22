## Context

The proxy server currently lacks exposed operational endpoints for monitoring and diagnostics. Operators need a way to programmatically check server health, view load‑balancing statistics, and retrieve configuration details without relying on external health‑check tools. This change introduces three new endpoints (`/health`, `/stats`, `/info`) to provide JSON status information while preserving existing functionality.

## Goals / Non-Goals

**Goals**
- Add `/health` endpoint that returns a simple JSON indicating the server is running.
- Add `/stats` endpoint that returns JSON with request counters, load‑balancer metrics, and uptime.
- Add `/info` endpoint that returns JSON with proxy configuration details (active subaccounts, default model, etc.).
- Validate required keys in `config.json` at startup and fail early if missing.

**Non-Goals**
- Modify existing API response formats.
- Introduce breaking changes to current endpoints.
- Implement authentication mechanisms beyond the existing token validation.

## Decisions

- **Endpoint Placement**: Register new routes directly in `proxy_server.py` under the Flask app, using the same blueprint pattern as existing routes.
- **Response Format**: All endpoints return JSON with a consistent top‑level `status` field (`"ok"` for health, `"metrics"` for stats, `"details"` for info).
- **Metric Collection**: Use the existing thread‑safe request counter in `utils/metrics.py`; expose it via `/stats` without additional overhead.
- **Configuration Validation**: Add a small validation routine at server start‑up that checks for required configuration keys (`subaccounts`, `default_model`) and returns a clear error if absent.
- **Error Handling**: Return HTTP 503 for `/health` if the server fails to initialize; return HTTP 400 with an error message if config validation fails.
- **Alternative Approaches Considered**: 
  - Using Flask‑RESTful for richer request parsing – rejected due to unnecessary dependency.
  - Exposing metrics via a separate service – rejected to keep all proxy status within the same process.

## Risks / Trade-offs

- **Performance Overhead**: Frequent stats queries could impact latency. Mitigation: aggregate metrics only on demand and keep counters incremental.
- **Information Exposure**: `/info` may reveal internal configuration. Mitigation: reuse existing token‑based authentication and limit exposure to authorized clients.
- **Maintenance Complexity**: Adding new routes increases code size. Mitigation: keep implementation minimal and ensure thorough unit tests.

## Migration Plan

- Deploy the new code alongside the existing server; no service restart required.
- The new endpoints are additive — no existing routes are removed or altered.
- Rollback: remove the added route registrations and associated config‑validation logic; the previous behavior is restored automatically.

## Open Questions

- Should `/stats` include per‑model request breakdown or aggregate counts only?
- Is additional logging needed for diagnostic purposes, or does existing logging suffice?
- Are there any organizational policies regarding the exposure of subaccount details via `/info`?

These decisions will be revisited during the implementation phase based on feedback from reviewers and testing results.