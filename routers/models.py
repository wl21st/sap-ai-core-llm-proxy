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
    """Lists all available models across all subAccounts.

    For Orchestration V2 deployments, returns the list of foundation models
    from the FoundationModelRegistry (populated from GET /v2/lm/foundation-models
    or the static fallback list).

    For legacy per-model deployments, returns models from the
    model_to_subaccounts config mapping.
    """
    logger.info("Received request to /v1/models")

    timestamp = int(time.time())
    proxy_config = request.app.state.proxy_config
    proxy_context = request.app.state.proxy_context

    models: list[dict[str, Any]] = []

    # Orchestration V2 path: use FoundationModelRegistry
    registry = getattr(proxy_context, "foundation_model_registry", None)
    if registry is not None and "*" in proxy_config.model_to_subaccounts:
        # Trigger a background refresh if TTL has expired
        try:
            registry.refresh(
                subaccounts=proxy_config.subaccounts,
                token_managers=proxy_context.token_managers,
                ca_cert_bundle=getattr(proxy_context, "ca_cert_bundle", None),
            )
        except Exception as exc:
            logger.warning("Failed to refresh foundation model registry: %s", exc)

        for model_info in registry.get_all_models():
            name = model_info.get("name") or model_info.get("model_name") or model_info.get("id", "")
            if not name:
                continue
            models.append(
                {
                    "id": name,
                    "object": "model",
                    "created": timestamp,
                    "owned_by": model_info.get("provider", "sap-ai-core"),
                }
            )
        return JSONResponse({"object": "list", "data": models})

    # Legacy path: return from model_to_subaccounts config mapping
    for model_name in proxy_config.model_to_subaccounts.keys():
        if model_name == "*":
            continue  # Skip the wildcard sentinel key
        models.append(
            {
                "id": model_name,
                "object": "model",
                "created": timestamp,
                "owned_by": "sap-ai-core",
            }
        )

    return JSONResponse({"object": "list", "data": models})
