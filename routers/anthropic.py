"""Router for /anthropic/* endpoints — native Anthropic Messages API format, Claude models only."""

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from auth.request_validator import verify_request_token
from proxy_helpers import Detector
from routers.messages import proxy_claude_request
from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

router = APIRouter(prefix="/anthropic")


@router.post("/v1/messages", dependencies=[Depends(verify_request_token)])
async def anthropic_messages(request: Request) -> JSONResponse:
    """Native Anthropic Messages API. Accepts and returns Anthropic format directly.
    Claude models only. Identical to /v1/messages but scoped under /anthropic prefix.
    """
    return await proxy_claude_request(request)


@router.get("/v1/models", dependencies=[Depends(verify_request_token)])
async def anthropic_list_models(request: Request) -> JSONResponse:
    """List only Claude/Anthropic models."""
    proxy_config = request.app.state.proxy_config
    timestamp = int(time.time())
    models: list[dict[str, Any]] = [
        {"id": name, "object": "model", "created": timestamp, "owned_by": "anthropic"}
        for name in proxy_config.model_to_subaccounts
        if Detector.is_claude_model(name)
    ]
    return JSONResponse({"object": "list", "data": models})
