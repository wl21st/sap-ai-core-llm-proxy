---
name: add-route
description: Scaffold a new FastAPI route for this proxy — creates routers/<name>.py with auth/request wiring boilerplate and a matching unit test stub in tests/unit/.
---

## Usage

`/add-route <route-name> <http-method> <path>`

Example: `/add-route health GET /v1/health`

## What this skill does

Given a route name, HTTP method, and path, scaffold three things:

### 1. `routers/<name>.py`

Follow the exact pattern of existing routers (e.g. `routers/status.py`, `routers/models.py`):

```python
"""Router for <path> endpoint."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from auth.request_validator import verify_request_token
from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

router = APIRouter()


@router.<method>("<path>", dependencies=[Depends(verify_request_token)])
async def <snake_case_name>(request: Request) -> JSONResponse:
    # TODO: implement
    return JSONResponse({"status": "ok"})
```

### 2. `tests/unit/test_<name>.py`

Minimal pytest stub matching the project's test conventions:

```python
"""Unit tests for <path> endpoint."""

import pytest
from fastapi.testclient import TestClient


def test_<snake_case_name>_returns_200(test_client: TestClient) -> None:
    response = test_client.get("<path>")
    assert response.status_code == 200
```

### 3. Wire up in `main.py`

Add to the imports line:
```python
from routers import chat, embeddings, logging as logging_router, messages, models, status, <name>
```

And register the router after the existing `app.include_router(status.router)` line:
```python
app.include_router(<name>.router)
```

## Notes

- Always use `verify_request_token` as a dependency unless the route is explicitly public (like `/v1/models` or status endpoints).
- Logger name should be `__name__` (module-scoped).
- File placement: `routers/<name>.py`, never in the project root.
- Run `/run-checks` after scaffolding to validate the new files.
