## 1. Setup and Core Dependencies

- [ ] 1.1 Add `fastapi`, `uvicorn`, `httpx`, `pytest-asyncio` to project dependencies and update lockfile
- [ ] 1.2 Create `main.py` entry point with `create_app()` factory
- [ ] 1.3 Implement `Lifespan` context manager in `main.py` for config loading
- [ ] 1.4 Refactor `auth/request_validator.py` to expose `verify_request_token` dependency

## 2. Async Networking Layer

- [ ] 2.1 Refactor `handlers/streaming_handler.py` to use `httpx.AsyncClient`
- [ ] 2.2 Refactor `handlers/bedrock_handler.py` to use `run_in_threadpool`
- [ ] 2.3 Rewrite `handlers/streaming_generators.py` as async generators using `aiter_lines()`

## 3. Router Implementation

- [ ] 3.1 Migrate `blueprints/models.py` to `routers/models.py`
- [ ] 3.2 Migrate `blueprints/embeddings.py` to `routers/embeddings.py`
- [ ] 3.3 Migrate `blueprints/chat_completions.py` to `routers/chat.py` (including streaming)
- [ ] 3.4 Migrate `blueprints/messages.py` to `routers/messages.py` (including streaming)
- [ ] 3.5 Migrate `blueprints/event_logging.py` to `routers/logging.py`

## 4. Integration and Cleanup

- [ ] 4.1 Update `proxy_server.py` to be a thin wrapper or deprecate it
- [ ] 4.2 Update tests to use `httpx.AsyncClient` for integration testing
- [ ] 4.3 Verify all endpoints with existing test suite
- [ ] 4.4 Remove `flask` dependency and cleanup old blueprint files
