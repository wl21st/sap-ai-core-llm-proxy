"""Router for /openai/* endpoints — native OpenAI format, GPT models only, no conversion."""

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from auth.request_validator import verify_request_token
from handlers.model_handlers import handle_default_request
from handlers.streaming_generators import generate_streaming_response
from handlers.streaming_handler import make_backend_request
from load_balancer import load_balance_url, resolve_model_name
from utils.logging_utils import get_server_logger, get_transport_logger


def _is_claude_model(name: str) -> bool:
    lower = name.lower()
    return any(t in lower for t in ("claude", "anthropic--", "sonnet", "haiku", "opus"))


def _is_gemini_model(name: str) -> bool:
    return name.lower().startswith("gemini-")

logger = get_server_logger(__name__)
transport_logger = get_transport_logger(__name__)

router = APIRouter(prefix="/openai")

DEFAULT_GPT_MODEL = "gpt-4.1"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
API_VERSION_2023_05_15 = "2023-05-15"


def _is_openai_model(model: str) -> bool:
    """Return True if the model is an OpenAI/GPT model (not Claude, not Gemini)."""
    return not _is_claude_model(model) and not _is_gemini_model(model)


@router.post(
    "/v1/chat/completions",
    dependencies=[Depends(verify_request_token)],
    response_model=None,
)
async def openai_chat_completions(request: Request) -> JSONResponse | StreamingResponse:
    """OpenAI-native chat completions. Accepts and returns raw OpenAI format.
    Only GPT/OpenAI models are accepted; Claude and Gemini models are rejected.
    """
    tid = str(uuid.uuid4())
    raw_body = await request.body()
    transport_logger.info(
        "OPENAI REQ: tid=%s, url=%s, body=%s",
        tid,
        request.url,
        raw_body.decode("utf-8", errors="ignore"),
    )

    payload = await request.json()
    model = payload.get("model") or DEFAULT_GPT_MODEL
    proxy_config = request.app.state.proxy_config

    resolved = resolve_model_name(model, proxy_config)
    if resolved is None:
        return JSONResponse({"error": f"Model '{model}' not found."}, status_code=404)
    model = resolved

    if not _is_openai_model(model):
        return JSONResponse(
            {
                "error": f"Model '{model}' is not an OpenAI model. Use /anthropic or /gemini endpoints for other providers."
            },
            status_code=400,
        )

    is_stream = payload.get("stream", False)
    logger.info("OPENAI: tid=%s, model=%s, stream=%s", tid, model, is_stream)

    try:
        endpoint_url, modified_payload, subaccount_name = handle_default_request(
            payload, model, proxy_config
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

        if is_stream:
            return StreamingResponse(
                generate_streaming_response(
                    request,
                    endpoint_url,
                    headers,
                    modified_payload,
                    model,
                    subaccount_name,
                    tid,
                ),
                media_type="text/event-stream",
            )

        result = await run_in_threadpool(
            make_backend_request,
            url=endpoint_url,
            headers=headers,
            payload=modified_payload,
            model=model,
            tid=tid,
            is_claude_model_fn=_is_claude_model,
        )

        if not result.success:
            return JSONResponse(
                result.response_data or {"error": result.error_message},
                status_code=result.status_code,
            )
        return JSONResponse(result.response_data)

    except ValueError as err:
        return JSONResponse({"error": str(err)}, status_code=400)
    except Exception as err:
        logger.error("OPENAI: Unexpected error tid=%s: %s", tid, err, exc_info=True)
        return JSONResponse({"error": str(err)}, status_code=500)


@router.post("/v1/embeddings", dependencies=[Depends(verify_request_token)])
async def openai_embeddings(request: Request) -> JSONResponse:
    """OpenAI-native embeddings endpoint. Passes payload through without conversion."""
    tid = str(uuid.uuid4())
    payload = await request.json()
    input_text = payload.get("input")
    model = payload.get("model", DEFAULT_EMBEDDING_MODEL)
    proxy_config = request.app.state.proxy_config

    if not input_text:
        return JSONResponse({"error": "Input text is required"}, status_code=400)

    resolved_model = model
    if resolved_model not in proxy_config.model_to_subaccounts:
        resolved_model = DEFAULT_EMBEDDING_MODEL

    try:
        selected_url, subaccount_name, _, _ = load_balance_url(
            resolved_model, proxy_config
        )
    except ValueError as err:
        return JSONResponse({"error": str(err)}, status_code=404)

    endpoint_url = (
        f"{selected_url.rstrip('/')}/embeddings?api-version={API_VERSION_2023_05_15}"
    )
    subaccount = proxy_config.subaccounts[subaccount_name]
    token = request.app.state.proxy_context.get_token_manager(
        subaccount_name
    ).get_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "AI-Resource-Group": subaccount.resource_group,
        "AI-Tenant-Id": subaccount.service_key.identity_zone_id,
    }

    try:
        result = await run_in_threadpool(
            make_backend_request,
            url=endpoint_url,
            headers=headers,
            payload={"input": input_text},
            model=resolved_model,
            tid=tid,
             is_claude_model_fn=_is_claude_model,
        )
        if not result.success:
            return JSONResponse(
                result.response_data or {"error": result.error_message},
                status_code=result.status_code,
            )
        return JSONResponse(result.response_data)
    except Exception as err:
        logger.error("OPENAI EMBED: tid=%s: %s", tid, err, exc_info=True)
        return JSONResponse({"error": str(err)}, status_code=500)


@router.get("/v1/models", dependencies=[Depends(verify_request_token)])
async def openai_list_models(request: Request) -> JSONResponse:
    """List only OpenAI/GPT models (excludes Claude and Gemini)."""
    proxy_config = request.app.state.proxy_config
    timestamp = int(time.time())
    models: list[dict[str, Any]] = [
        {"id": name, "object": "model", "created": timestamp, "owned_by": "openai"}
        for name in proxy_config.model_to_subaccounts
        if _is_openai_model(name)
    ]
    return JSONResponse({"object": "list", "data": models})
