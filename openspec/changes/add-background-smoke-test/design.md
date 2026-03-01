## Context

The proxy currently lacks automated verification of authentication health for Anthropic, OpenAI, and embedding model endpoints. Operators need a background mechanism that periodically checks auth status, initiates re‑authentication when needed, and exposes configuration via APIs. This ensures early detection of auth failures and supports dynamic adjustment of check frequency.

## Goals / Non-Goals

**Goals**
- Implement a background service that runs periodic authentication status checks and re‑auth flows for Anthropic, OpenAI, and embedding models.
- Make the check interval configurable, defaulting to 5 minutes, with APIs to retrieve and update the interval.
- Execute the checks in a separate thread or scheduler to avoid blocking the main request pipeline.
- Provide API endpoints to configure the background smoke test and to fetch the current configuration.

**Non-Goals**
- Modify existing smoke‑test logic beyond adding the new auth‑focused checks.
- Implement UI components for configuration changes.
- Support additional model providers not listed.
- Introduce breaking changes to existing endpoints.

## Decisions

- **Scheduler Choice**: Use Python’s `threading.Timer` alongside a daemon worker thread for simplicity and compatibility with the existing codebase; alternatively, adopt `APScheduler` for more robust scheduling (chosen for its clarity and built‑in cron‑like syntax).
- **Configuration Storage**: Extend the current JSON configuration schema to include `background_smoke_test.interval_seconds`; default value set to 300 (5 minutes).
- **API Design**: Add two new Flask routes under `/smoke-test`:
  - `GET /smoke-test/config` – returns the current configuration (interval, last run status, etc.).
  - `POST /smoke-test/config` – accepts JSON payload to update the interval; validates input before applying changes.
- **Thread Management**: Initialize the background worker during proxy startup, store the thread reference in a module‑level variable, and ensure graceful shutdown on signal receipt.
- **Error Handling**: Log failures with appropriate severity; on transient errors, retry up to three times with exponential backoff; on permanent failures, mark the check as failed in the configuration exposure endpoint.
- **Alternative Approaches Considered**:
  - Using a separate microservice for health checks – rejected due to added operational overhead.
  - Integrating with existing Celery tasks – rejected because the project avoids external task queues for simple periodic jobs.

## Risks / Trade-offs

- **Performance Overhead**: Frequent checks could increase load on upstream model endpoints. Mitigation: Use a conservative default interval (5 min) and allow operators to increase it; implement exponential backoff on retry.
- **Thread‑Safety**: Concurrent access to configuration could lead to race conditions. Mitigation: Protect config updates with a `threading.Lock`.
- **Complexity in Shutdown**: Ensuring the background thread terminates cleanly on process exit. Mitigation: Register signal handlers to join the thread before shutdown.
- **Configuration Consistency**: Clients may update the interval while a check is in progress. Mitigation: Apply new interval only after the current cycle completes.

These decisions balance simplicity, maintainability, and reliability while meeting the functional requirements outlined in the proposal.