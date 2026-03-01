"""Router for /v1/models endpoint."""

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from auth.request_validator import verify_request_token
from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

router = APIRouter()


@router.get("/v1/models", dependencies=[Depends(verify_request_token)])
@router.options("/v1/models")
async def list_models(request: Request) -> JSONResponse:
    """Lists all available models across all subAccounts."""
    logger.info("Received request to /v1/models")

    models: list[dict[str, Any]] = []
    timestamp = int(time.time())
    proxy_config = request.app.state.proxy_config

    for model_name in proxy_config.model_to_subaccounts.keys():
        models.append(
            {
                "id": model_name,
                "object": "model",
                "created": timestamp,
                "owned_by": "sap-ai-core",
            }
        )

    return JSONResponse({"object": "list", "data": models})
