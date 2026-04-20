"""Router for /v1/chat/completions endpoint.

All inference routes through SAP AI Core Orchestration V2.
Each subaccount must be configured with an `orchestration_url`
(or have one auto-discovered at startup).
"""

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from auth.request_validator import verify_request_token
from load_balancer import select_subaccount_for_orchestration
from utils.logging_utils import get_server_logger, get_transport_logger
from utils.model_aliases import resolve_model_name as resolve_alias
from utils.orchestration_client import get_orchestration_client

logger = get_server_logger(__name__)

router = APIRouter()

DEFAULT_GPT_MODEL = "gpt-4.1"


@router.post("/v1/chat/completions", dependencies=[Depends(verify_request_token)])
async def proxy_openai_stream(request: Request):
    """Main handler for chat completions via Orchestration V2."""
    transport_logger = get_transport_logger(__name__)

    logger.info("Received request to /v1/chat/completions")
    tid = str(uuid.uuid4())

    raw_body = await request.body()
    transport_logger.info(
        "REQ: tid=%s, url=%s, body=%s",
        tid,
        request.url,
        raw_body.decode("utf-8", errors="ignore"),
    )

    payload = await request.json()
    original_model = payload.get("model")
    effective_model = original_model or DEFAULT_GPT_MODEL

    if not original_model:
        logger.warning(
            "No model specified in request, using fallback model %s",
            effective_model,
        )

    proxy_config = request.app.state.proxy_config
    proxy_context = request.app.state.proxy_context

    return await _handle_orchestration_v2(
        request=request,
        payload=payload,
        original_model=original_model,
        effective_model=effective_model,
        proxy_config=proxy_config,
        proxy_context=proxy_context,
        tid=tid,
        transport_logger=transport_logger,
    )


def _is_orchestration_v2_available(proxy_config) -> bool:
    """Return True if any subaccount is configured for Orchestration V2."""
    return "*" in proxy_config.model_to_subaccounts


async def _handle_orchestration_v2(
    request: Request,
    payload: dict,
    original_model: str | None,
    effective_model: str,
    proxy_config,
    proxy_context,
    tid: str,
    transport_logger,
) -> JSONResponse | StreamingResponse:
    """Handle a chat completion request via Orchestration V2.

    Performs:
    1. Model alias resolution
    2. Foundation model registry validation (404 for unknown models)
    3. Round-robin subaccount selection
    4. Orchestration V2 POST (streaming or non-streaming)
    """
    transport_logger = get_transport_logger(__name__)
    user_id = request.headers.get("Authorization", "unknown")
    if user_id and len(user_id) > 20:
        user_id = f"{user_id[:20]}..."
    ip_address = request.client.host if request.client else "unknown_ip"

    # Step 1: Resolve model alias
    model_aliases = getattr(proxy_context, "model_aliases", None)
    canonical_model = resolve_alias(effective_model, model_aliases)
    if canonical_model != effective_model:
        logger.info(
            "Model alias resolved: '%s' → '%s' (tid=%s)", effective_model, canonical_model, tid
        )

    # Step 2: Validate against foundation model registry
    registry = getattr(proxy_context, "foundation_model_registry", None)
    if registry is not None and not registry.is_known_model(canonical_model):
        logger.warning(
            "Model '%s' not available in foundation model registry (tid=%s)",
            canonical_model,
            tid,
        )
        return JSONResponse(
            {
                "error": {
                    "message": f"Model '{canonical_model}' not available in foundation model registry.",
                    "type": "not_found_error",
                    "code": "model_not_found",
                }
            },
            status_code=404,
        )

    # Step 3: Round-robin subaccount selection
    try:
        subaccount_name = select_subaccount_for_orchestration(proxy_config)
    except ValueError as err:
        logger.error("CHAT: No V2 subaccount available, tid=%s, %s", tid, str(err))
        return JSONResponse({"error": str(err)}, status_code=503)

    subaccount = proxy_config.subaccounts[subaccount_name]
    token = proxy_context.get_token_manager(subaccount_name).get_token()

    is_stream = payload.get("stream", False)
    messages = payload.get("messages", [])
    params = {
        k: v
        for k, v in payload.items()
        if k not in ("model", "messages", "stream")
    }

    logger.info(
        "CHAT_V2: tid=%s, model=%s→%s, sub_account=%s, stream=%s",
        tid,
        effective_model,
        canonical_model,
        subaccount_name,
        is_stream,
    )

    client = get_orchestration_client()

    try:
        if not is_stream:
            response_data = await run_in_threadpool(
                client.invoke,
                subaccount=subaccount,
                token=token,
                model=canonical_model,
                messages=messages,
                params=params,
            )
            usage = response_data.get("usage", {})
            logger.info(
                "CHAT_RSP_V2: tid=%s, user=%s, ip=%s, model=%s, sub_account=%s, "
                "prompt_tokens=%s, completion_tokens=%s, total_tokens=%s",
                tid,
                user_id,
                ip_address,
                canonical_model,
                subaccount_name,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
            )
            transport_logger.info(
                "RSP: tid=%s, status=200, body=%s", tid, json.dumps(response_data)
            )
            return JSONResponse(response_data)

        # Streaming
        async def _stream_gen():
            async for chunk in _iter_sync_generator(
                client.invoke_stream(
                    subaccount=subaccount,
                    token=token,
                    model=canonical_model,
                    messages=messages,
                    params=params,
                )
            ):
                yield chunk

        return StreamingResponse(_stream_gen(), media_type="text/event-stream")

    except Exception as err:
        import requests as _requests

        if isinstance(err, _requests.HTTPError) and err.response is not None:
            status = err.response.status_code
            try:
                err_body = err.response.json()
            except Exception:
                err_body = {"error": str(err)}
            logger.error(
                "CHAT_V2: HTTP error %s, tid=%s, %s", status, tid, str(err)
            )
            return JSONResponse(err_body, status_code=status)

        logger.error(
            "CHAT_V2: Unexpected error, tid=%s, %s", tid, str(err), exc_info=True
        )
        return JSONResponse({"error": str(err)}, status_code=500)


async def _iter_sync_generator(gen):
    """Async wrapper for a synchronous generator."""
    import asyncio

    loop = asyncio.get_event_loop()
    sentinel = object()

    def _next():
        try:
            return next(gen)
        except StopIteration:
            return sentinel

    while True:
        chunk = await loop.run_in_executor(None, _next)
        if chunk is sentinel:
            break
        yield chunk
