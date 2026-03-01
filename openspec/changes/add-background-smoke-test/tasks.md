## 1. Project Setup

- [ ] 1.1 Create a new Python module `background_smoke_test.py` under `src/` for the background service.
- [ ] 1.2 Add `sqlite3` usage to `utils/db.py` for result history storage.

## 2. Configuration

- [ ] 2.1 Extend `config.json` schema to include `background_smoke_test.interval_seconds` with default 300.
- [ ] 2.2 Implement validation for the new config field.

## 3. Database Integration

- [ ] 3.1 Create `smoke_test_results` table in SQLite with columns `id INTEGER PRIMARY KEY`, `timestamp DATETIME`, `provider TEXT`, `status TEXT`, `latency_ms INTEGER`.
- [ ] 3.2 Implement helper functions `init_db()`, `record_result(provider, status, latency_ms)` in `utils/db.py`.

## 4. Background Service

- [ ] 4.1 Implement a daemon thread that triggers the smoke test cycle based on the configured interval.
- [ ] 4.2 Use `threading.Timer` or `APScheduler` to schedule the job; ensure thread-safety for config updates.
- [ ] 4.3 Log start/stop of the background service.

## 5. Smoke Test Execution

- [ ] 5.1 For each provider (Anthropic, OpenAI, embedding), send an authentication status request.
- [ ] 5.2 On success, log provider status as "ok"; on failure, trigger re-auth flow.
- [ ] 5.3 Capture latency and status of each check.

## 6. Re-authentication Flow

- [ ] 6.1 Re-use existing token acquisition logic from `auth/` module.
- [ ] 6.2 Implement retry with exponential backoff (max 3 attempts).
- [ ] 6.3 On successful re-auth, update cache and log event.

## 7. API Endpoints

- [ ] 7.1 Add `GET /smoke-test/config` to return current interval and last run status.
- [ ] 7.2 Add `POST /smoke-test/config` to accept JSON payload updating `interval_seconds`; validate and persist.
- [ ] 7.3 Add `GET /smoke-test/results` to serve recent result history from SQLite (e.g., last 10 entries).

## 8. Integration & Registration

- [ ] 8.1 Register the new Flask routes in `proxy_server.py`.
- [ ] 8.2 Import and start the background service during app initialization.
- [ ] 8.3 Ensure graceful shutdown by joining the background thread on signal.

## 9. Testing

- [ ] 9.1 Write unit tests for DB helper functions.
- [ ] 9.2 Write integration test for the background scheduler (mock timer).
- [ ] 9.3 Add pytest cases for the new API endpoints using the test client.

## 10. Documentation

- [ ] 10.1 Update README with configuration options for the background smoke test.
- [ ] 10.2 Add OpenAPI snippets for the new endpoints.