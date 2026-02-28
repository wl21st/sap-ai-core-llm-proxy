"""Router for /v1/chat/completions endpoint."""

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from auth.request_validator import verify_request_token
from handlers.model_handlers import (
    handle_claude_request,
    handle_default_request,
    handle_gemini_request,
)
from handlers.streaming_generators import generate_streaming_response
from handlers.streaming_handler import make_backend_request
from load_balancer import resolve_model_name
from proxy_helpers import Converters, Detector
from utils.logging_utils import get_server_logger, get_transport_logger

logger = get_server_logger(__name__)

router = APIRouter()

DEFAULT_GPT_MODEL = "gpt-4.1"


async def _handle_non_streaming_request(
    request: Request,
    url: str,
    headers: dict,
    payload: dict,
    model: str,
    subaccount_name: str,
    tid: str,
) -> JSONResponse:
    transport_logger = get_transport_logger(__name__)

    result = await make_backend_request(
        url=url,
        headers=headers,
        payload=payload,
        model=model,
        tid=tid,
        is_claude_model_fn=Detector.is_claude_model,
    )

    if not result.success:
        if result.status_code == 429:
            return JSONResponse(
                result.response_data or {"error": result.error_message},
                status_code=429,
            )

        if result.response_data:
            return JSONResponse(result.response_data, status_code=result.status_code)

        return JSONResponse(
            {"error": result.error_message or "Unknown error"},
            status_code=result.status_code,
        )

    response_data = result.response_data

    if result.is_sse_response:
        logger.info(
            "Claude model response is in SSE format, parsing as streaming response for non-streaming request"
        )

    if Detector.is_claude_model(model):
        final_response = Converters.convert_claude_to_openai(response_data, model)
    elif Detector.is_gemini_model(model):
        final_response = Converters.convert_gemini_to_openai(response_data, model)
    else:
        final_response = response_data

    total_tokens = final_response.get("usage", {}).get("total_tokens", 0)
    prompt_tokens = final_response.get("usage", {}).get("prompt_tokens", 0)
    completion_tokens = final_response.get("usage", {}).get("completion_tokens", 0)

    user_id = request.headers.get("Authorization", "unknown")
    if user_id and len(user_id) > 20:
        user_id = f"{user_id[:20]}..."
    ip_address = request.client.host if request.client else "unknown_ip"
    logger.info(
        "CHAT_RSP: tid=%s, user=%s, ip=%s, model=%s, sub_account=%s, prompt_tokens=%s, completion_tokens=%s, total_tokens=%s",
        tid,
        user_id,
        ip_address,
        model,
        subaccount_name,
        prompt_tokens,
        completion_tokens,
        total_tokens,
    )

    transport_logger.info(
        "RSP: tid=%s, status=200, body=%s", tid, json.dumps(final_response)
    )

    return JSONResponse(final_response)


@router.post("/v1/chat/completions", dependencies=[Depends(verify_request_token)])
async def proxy_openai_stream(request: Request):
    """Main handler for chat completions endpoint with multi-subAccount support."""
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

    resolved_model = resolve_model_name(effective_model, request.app.state.proxy_config)
    if resolved_model is None:
        error_message = f"Model {effective_model} is not supported."
        if effective_model != original_model:
            error_message = f"Models '{original_model}' and '{effective_model}'(fallback) are NOT defined in any subAccount"
        return JSONResponse({"error": error_message}, status_code=404)

    effective_model = resolved_model
    is_stream = payload.get("stream", False)
    logger.info("Model: %s, Streaming: %s", original_model, is_stream)

    try:
        if Detector.is_claude_model(original_model):
            endpoint_url, modified_payload, subaccount_name = handle_claude_request(
                payload, original_model, request.app.state.proxy_config
            )
        elif Detector.is_gemini_model(original_model):
            endpoint_url, modified_payload, subaccount_name = handle_gemini_request(
                payload, original_model, request.app.state.proxy_config
            )
        else:
            endpoint_url, modified_payload, subaccount_name = handle_default_request(
                payload, original_model, request.app.state.proxy_config
            )

        subaccount = request.app.state.proxy_config.subaccounts[subaccount_name]
        subaccount_token = request.app.state.proxy_context.get_token_manager(
            subaccount_name
        ).get_token()

        headers = {
            "AI-Resource-Group": subaccount.resource_group,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Tenant-Id": subaccount.service_key.identity_zone_id,
        }

        logger.info(
            "CHAT: tid=%s, url=%s, model=%s, sub_account=%s",
            tid,
            endpoint_url,
            effective_model,
            subaccount_name,
        )

        if not is_stream:
            return await _handle_non_streaming_request(
                request,
                endpoint_url,
                headers,
                modified_payload,
                original_model,
                subaccount_name,
                tid,
            )

        return StreamingResponse(
            generate_streaming_response(
                request,
                endpoint_url,
                headers,
                modified_payload,
                original_model,
                subaccount_name,
                tid,
            ),
            media_type="text/event-stream",
        )

    except ValueError as err:
        logger.error("CHAT: Value error, tid=%s, %s", tid, str(err), exc_info=True)
        return JSONResponse({"error": str(err)}, status_code=400)

    except Exception as err:
        logger.error("CHAT: Unexpected error, tid=%s, %s", tid, str(err), exc_info=True)
        return JSONResponse({"error": str(err)}, status_code=500)
