## 1. Remove unused imports from production files

- [x] 1.1 Run `ruff check . --select F401,F811 --fix` to auto-remove all unused imports in production files (`config/`, `handlers/`, `routers/`, `utils/`)
- [x] 1.2 Verify `git diff` — confirm only import lines were removed, no logic touched
- [x] 1.3 Run `make test` to confirm all tests still pass

## 2. Remove unused imports from test files

- [x] 2.1 Run `ruff check tests/ --select F401,F811 --fix` to auto-remove unused imports across all test files
- [x] 2.2 Verify `git diff` — confirm only import lines were removed
- [x] 2.3 Run `make test` to confirm all tests still pass

## 3. Remove unused local variables from test files

- [x] 3.1 Review `tests/conftest.py:51` (`after_count`) — remove assignment or prefix with `_` if intentional
- [x] 3.2 Review `tests/integration/test_chat_completions.py:338,617,663` (`use_streaming`) — remove or replace with `_`
- [x] 3.3 Review `tests/test_proxy_helpers.py:806,893,906,1168,1187,1408` (`result`, `mock_warning`) — remove unused assignments
- [x] 3.4 Review `tests/unit/routers/test_chat_router.py:49` (`response`) — remove or assert on value
- [x] 3.5 Run `make test` to confirm all tests still pass after variable cleanup

## 4. Remove unused methods

- [x] 4.1 Delete `get_counters()` from `load_balancer.py` (~line 246) — confirmed zero callers in production and tests
- [x] 4.2 Delete `generate_bedrock_streaming_response_sync()` from `handlers/streaming_generators.py` (~line 970) and its helper `_sync_iter_async_generator` if that helper is only called by this function
- [x] 4.3 Run `make test` to confirm deletions don't break anything

## 5. Add unit API tests

- [x] 5.1 Create `tests/unit/test_api_routes_post_cleanup.py` with unit tests for `/v1/chat/completions`, `/v1/messages`, and `/v1/models` using FastAPI `TestClient` and mocked backends
- [x] 5.2 Run `make test` to confirm new unit tests pass

## 6. Add integration smoke tests

- [x] 6.1 Create `tests/integration/test_cleanup_smoke.py` with smoke tests asserting no 500s on `/v1/chat/completions`, `/v1/messages`, and `/v1/models` after cleanup
- [x] 6.2 Run `make test-integration-smoke` against a live server to confirm

## 7. Final validation

- [x] 7.1 Run `ruff check . --select F401,F811,F841` to confirm zero remaining violations
- [x] 7.2 Run `make test` for final green-light confirmation
