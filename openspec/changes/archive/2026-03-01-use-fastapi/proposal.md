## Why

The current Flask-based implementation uses synchronous blocking I/O (via `requests`) which limits concurrency and performance, especially for long-lived streaming LLM requests. Migrating to FastAPI with asynchronous I/O will significantly improve throughput, scalability, and resource utilization, while also providing automatic OpenAPI documentation and better type safety through Pydantic integration.

## What Changes

- **Framework Migration**: Replace Flask with FastAPI.
- **Async Networking**: Replace synchronous `requests` library with asynchronous `httpx` for all backend calls.
- **Streaming Logic**: Rewrite streaming generators to use Python `async` generators and iterators.
- **Routing**: Convert Flask Blueprints to FastAPI `APIRouter`s.
- **Authentication**: Refactor `RequestValidator` to use FastAPI's Dependency Injection system (`Depends`).
- **Configuration**: Migrate global state management to Dependency Injection patterns.
- **Testing**: Update test suite to support asynchronous testing with `pytest-asyncio` and `httpx`.

## Capabilities

### New Capabilities
- `fastapi-core`: The core FastAPI application structure, lifespan management, and dependency injection setup.
- `async-networking`: Asynchronous HTTP client implementation and streaming response handling using `httpx`.
- `api-routes`: Implementation of standard OpenAI-compatible and Anthropic-compatible endpoints using FastAPI routers.

### Modified Capabilities
<!-- No existing OpenSpecs to modify -->

## Impact

- **Codebase**:
    - Major refactor of `proxy_server.py`.
    - Complete rewrite of `blueprints/` to use `APIRouter`.
    - Significant updates to `handlers/` for async support.
    - Updates to `auth/` for dependency injection.
- **Dependencies**:
    - Remove `flask`.
    - Add `fastapi`, `uvicorn`, `httpx`, `pytest-asyncio`.
- **Breaking Changes**:
    - CLI entry point might need adjustment (though `sap-ai-proxy` command will be preserved).
    - Internal function signatures will change to `async def`.
