"""Router for /anthropic/* endpoints — native Anthropic Messages API format, Claude models only."""

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from auth.request_validator import verify_request_token
from routers.messages import proxy_claude_request
from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

router = APIRouter(prefix="/anthropic")

_CLAUDE_PREFIXES = ("anthropic--", "claude-", "sonnet", "haiku", "opus")


def _is_claude_model(name: str) -> bool:
    """Return True if the model name looks like a Claude/Anthropic model."""
    lower = name.lower()
    return any(lower.startswith(p) or p in lower for p in _CLAUDE_PREFIXES)


@router.post("/v1/messages", dependencies=[Depends(verify_request_token)])
async def anthropic_messages(request: Request) -> JSONResponse:
    """Native Anthropic Messages API. Accepts and returns Anthropic format directly.
    Claude models only. Identical to /v1/messages but scoped under /anthropic prefix.
    """
    return await proxy_claude_request(request)


@router.get("/v1/models", dependencies=[Depends(verify_request_token)])
async def anthropic_list_models(request: Request) -> JSONResponse:
    """List only Claude/Anthropic models from the foundation model registry."""
    proxy_context = request.app.state.proxy_context
    timestamp = int(time.time())
    models: list[dict[str, Any]] = []

    registry = getattr(proxy_context, "foundation_model_registry", None)
    if registry is not None:
        for name in registry.get_model_names():
            if _is_claude_model(name):
                models.append(
                    {"id": name, "object": "model", "created": timestamp, "owned_by": "anthropic"}
                )
    else:
        # Legacy fallback: filter from model_to_subaccounts
        proxy_config = request.app.state.proxy_config
        for name in proxy_config.model_to_subaccounts:
            if name != "*" and _is_claude_model(name):
                models.append(
                    {"id": name, "object": "model", "created": timestamp, "owned_by": "anthropic"}
                )

    return JSONResponse({"object": "list", "data": models})
