## 1. Setup and Core Dependencies

- [x] 1.1 Add `fastapi`, `uvicorn`, `httpx`, `pytest-asyncio` to project dependencies and update lockfile
- [x] 1.2 Create `main.py` entry point with `create_app()` factory
- [x] 1.3 Implement `Lifespan` context manager in `main.py` for config loading
- [x] 1.4 Refactor `auth/request_validator.py` to expose `verify_request_token` dependency

## 2. Async Networking Layer

- [x] 2.1 Refactor `handlers/streaming_handler.py` to use `httpx.AsyncClient`
- [x] 2.2 Refactor `handlers/bedrock_handler.py` to use `run_in_threadpool`
- [x] 2.3 Rewrite `handlers/streaming_generators.py` as async generators using `aiter_lines()`

## 3. Router Implementation

- [x] 3.1 Migrate `blueprints/models.py` to `routers/models.py`
- [x] 3.2 Migrate `blueprints/embeddings.py` to `routers/embeddings.py`
- [x] 3.3 Migrate `blueprints/chat_completions.py` to `routers/chat.py` (including streaming)
- [x] 3.4 Migrate `blueprints/messages.py` to `routers/messages.py` (including streaming)
- [x] 3.5 Migrate `blueprints/event_logging.py` to `routers/logging.py`

## 4. Integration and Cleanup

- [x] 4.1 Update `proxy_server.py` to be a thin wrapper or deprecate it
- [x] 4.2 Update tests to use `httpx.AsyncClient` for integration testing
- [x] 4.3 Verify all endpoints with existing test suite
- [x] 4.4 Remove `flask` dependency and cleanup old blueprint files
