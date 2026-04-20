"""Router for /gemini/* endpoints — native Google Gemini REST format, Gemini models only.

Exposes:
  POST /gemini/v1beta/models/{model}:generateContent          (non-streaming)
  POST /gemini/v1beta/models/{model}:streamGenerateContent    (streaming)
  GET  /gemini/v1beta/models                                  (list Gemini models)
  GET  /gemini/v1beta/models/{model}                          (single model info)

Requests and responses are in native Gemini REST format — no conversion is applied.
The payload is forwarded as-is to the SAP AI Core Gemini deployment.
"""

import time
import uuid
from typing import Any, AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from auth.request_validator import verify_request_token
from load_balancer import load_balance_url
from handlers.streaming_handler import make_backend_request
from utils.logging_utils import get_server_logger, get_transport_logger

_GEMINI_PREFIXES = ("gemini-",)


def _is_gemini_model(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(p) for p in _GEMINI_PREFIXES)


def _is_claude_model(name: str) -> bool:
    lower = name.lower()
    return any(t in lower for t in ("claude", "anthropic--", "sonnet", "haiku", "opus"))

logger = get_server_logger(__name__)
transport_logger = get_transport_logger(__name__)

router = APIRouter(prefix="/gemini")


async def _stream_gemini_native(
    url: str,
    headers: dict,
    payload: dict,
    tid: str,
) -> AsyncGenerator[bytes, None]:
    """Stream raw Gemini SSE response back to the client without conversion."""
    async with httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream(
            "POST", url, headers=headers, json=payload
        ) as response:
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk


@router.post(
    "/v1beta/models/{model:path}",
    dependencies=[Depends(verify_request_token)],
    response_model=None,
)
async def gemini_generate(
    request: Request, model: str
) -> JSONResponse | StreamingResponse:
    """Native Gemini generateContent / streamGenerateContent endpoint.

    The path suffix (:generateContent or :streamGenerateContent) is captured as
    part of the {model} path parameter, e.g. "gemini-2.5-pro:generateContent".
    Streaming is detected by the :streamGenerateContent suffix or ?alt=sse query param.
    """
    tid = str(uuid.uuid4())
    raw_body = await request.body()
    transport_logger.info(
        "GEMINI REQ: tid=%s, url=%s, body=%s",
        tid,
        request.url,
        raw_body.decode("utf-8", errors="ignore"),
    )

    # Strip action suffix to get the bare model name for load balancing
    bare_model = model
    is_stream = False
    for suffix in (":streamGenerateContent", ":generateContent"):
        if bare_model.endswith(suffix):
            bare_model = bare_model[: -len(suffix)]
            is_stream = suffix == ":streamGenerateContent"
            break

    # Also honour ?alt=sse as a streaming signal (Gemini SDK uses this)
    if request.query_params.get("alt") == "sse":
        is_stream = True

    proxy_config = request.app.state.proxy_config

    # Validate it's actually a Gemini model
    if not _is_gemini_model(bare_model):
        return JSONResponse(
            {
                "error": {
                    "code": 400,
                    "message": f"Model '{bare_model}' is not a Gemini model. Use /openai or /anthropic endpoints for other providers.",
                    "status": "INVALID_ARGUMENT",
                }
            },
            status_code=400,
        )

    try:
        selected_url, subaccount_name, _, resolved_model = load_balance_url(
            bare_model, proxy_config
        )
    except ValueError:
        return JSONResponse(
            {
                "error": {
                    "code": 404,
                    "message": f"Model '{bare_model}' not found.",
                    "status": "NOT_FOUND",
                }
            },
            status_code=404,
        )

    # Build the backend Gemini endpoint URL
    if is_stream:
        endpoint_url = (
            f"{selected_url.rstrip('/')}/models/{resolved_model}:streamGenerateContent"
        )
    else:
        endpoint_url = (
            f"{selected_url.rstrip('/')}/models/{resolved_model}:generateContent"
        )

    subaccount = proxy_config.subaccounts[subaccount_name]
    token = request.app.state.proxy_context.get_token_manager(
        subaccount_name
    ).get_token()
    headers = {
        "AI-Resource-Group": subaccount.resource_group,
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "AI-Tenant-Id": subaccount.service_key.identity_zone_id,
    }

    payload = await request.json()

    logger.info(
        "GEMINI: tid=%s, model=%s, url=%s, stream=%s",
        tid,
        resolved_model,
        endpoint_url,
        is_stream,
    )

    try:
        if is_stream:
            return StreamingResponse(
                _stream_gemini_native(endpoint_url, headers, payload, tid),
                media_type="text/event-stream",
            )

        result = await run_in_threadpool(
            make_backend_request,
            url=endpoint_url,
            headers=headers,
            payload=payload,
            model=resolved_model,
            tid=tid,
            is_claude_model_fn=_is_claude_model,
        )

        if not result.success:
            return JSONResponse(
                result.response_data
                or {
                    "error": {
                        "code": result.status_code,
                        "message": result.error_message,
                        "status": "ERROR",
                    }
                },
                status_code=result.status_code,
            )
        return JSONResponse(result.response_data)

    except ValueError as err:
        return JSONResponse(
            {"error": {"code": 400, "message": str(err), "status": "INVALID_ARGUMENT"}},
            status_code=400,
        )
    except Exception as err:
        logger.error("GEMINI: Unexpected error tid=%s: %s", tid, err, exc_info=True)
        return JSONResponse(
            {"error": {"code": 500, "message": str(err), "status": "INTERNAL"}},
            status_code=500,
        )


@router.get("/v1beta/models", dependencies=[Depends(verify_request_token)])
async def gemini_list_models(request: Request) -> JSONResponse:
    """List available Gemini models in Google AI REST format."""
    proxy_context = request.app.state.proxy_context
    proxy_config = request.app.state.proxy_config
    models: list[dict[str, Any]] = []

    registry = getattr(proxy_context, "foundation_model_registry", None)
    names = registry.get_model_names() if registry else [
        n for n in proxy_config.model_to_subaccounts if n != "*"
    ]

    for name in names:
        if _is_gemini_model(name):
            models.append({
                "name": f"models/{name}",
                "baseModelId": name,
                "version": "001",
                "displayName": name,
                "description": f"SAP AI Core hosted {name}",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 8192,
                "supportedGenerationMethods": ["generateContent", "streamGenerateContent"],
            })
    return JSONResponse({"models": models})


@router.get("/v1beta/models/{model}", dependencies=[Depends(verify_request_token)])
async def gemini_get_model(request: Request, model: str) -> JSONResponse:
    """Get info for a single Gemini model."""
    proxy_config = request.app.state.proxy_config
    if not _is_gemini_model(model):
        return JSONResponse(
            {
                "error": {
                    "code": 404,
                    "message": f"Model '{model}' not found.",
                    "status": "NOT_FOUND",
                }
            },
            status_code=404,
        )
    return JSONResponse(
        {
            "name": f"models/{model}",
            "baseModelId": model,
            "version": "001",
            "displayName": model,
            "description": f"SAP AI Core hosted {model}",
            "inputTokenLimit": 1048576,
            "outputTokenLimit": 8192,
            "supportedGenerationMethods": ["generateContent", "streamGenerateContent"],
        }
    )
