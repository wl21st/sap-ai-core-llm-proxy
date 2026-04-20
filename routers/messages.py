"""Router for /v1/messages endpoint (Anthropic Claude Messages API).

Accepts native Anthropic Messages API requests, converts them to OpenAI format,
routes through SAP AI Core Orchestration V2, then converts the response back to
Anthropic format.
"""

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from auth.request_validator import verify_request_token
from load_balancer import select_subaccount_for_orchestration
from proxy_helpers import Converters, Detector
from utils.logging_utils import get_server_logger, get_transport_logger
from utils.model_aliases import resolve_model_name as resolve_alias
from utils.orchestration_client import get_orchestration_client

logger = get_server_logger(__name__)
transport_logger = get_transport_logger(__name__)

router = APIRouter()

DEFAULT_CLAUDE_MODEL: str = "anthropic--claude-4.5-sonnet"


@router.post("/v1/messages", dependencies=[Depends(verify_request_token)])
async def proxy_claude_request(request: Request):
    """Handles requests compatible with the Anthropic Claude Messages API.

    Converts the Anthropic Messages request to OpenAI format, routes through
    Orchestration V2, then converts the response back to Anthropic format.
    """
    tid: str = str(uuid.uuid4())

    request_body_bytes = await request.body()
    request_body_str = request_body_bytes.decode("utf-8", errors="ignore")
    logger.info("REQ: tid=%s, body=%s", tid, request_body_str)
    transport_logger.info(
        "REQ: tid=%s, url=%s, body=%s", tid, request.url, request_body_str
    )

    request_body_json = await request.json()
    request_model = request_body_json.get("model")
    if not request_model:
        request_model = DEFAULT_CLAUDE_MODEL
        logger.info("No model in request, defaulting to: %s", request_model)
    else:
        logger.info("Request model: %s", request_model)

    proxy_config = request.app.state.proxy_config
    proxy_context = request.app.state.proxy_context

    # Resolve model alias
    model_aliases = getattr(proxy_context, "model_aliases", None)
    canonical_model = resolve_alias(request_model, model_aliases)
    if canonical_model != request_model:
        logger.info(
            "Model alias resolved: '%s' → '%s' (tid=%s)",
            request_model,
            canonical_model,
            tid,
        )

    # Validate it's a Claude model (this endpoint is Claude-only)
    if not Detector.is_claude_model(canonical_model) and not Detector.is_claude_model(request_model):
        logger.warning(
            "Model '%s' is not a Claude model — /v1/messages only supports Claude",
            canonical_model,
        )
        return JSONResponse(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Only Claude models are supported by this endpoint",
                },
            },
            status_code=400,
        )

    # Validate against foundation model registry if available
    registry = getattr(proxy_context, "foundation_model_registry", None)
    if registry is not None:
        # Refresh registry (respecting TTL) to ensure we have the latest models
        try:
            registry.refresh(
                subaccounts=proxy_config.subaccounts,
                token_managers=proxy_context.token_managers,
                ca_cert_bundle=getattr(proxy_context, "ca_cert_bundle", None),
            )
        except Exception as exc:
            logger.warning("Failed to refresh foundation model registry: %s", exc)
    
    if registry is not None and not registry.is_known_model(canonical_model):
        logger.warning(
            "Model '%s' not in foundation model registry (tid=%s)", canonical_model, tid
        )
        return JSONResponse(
            {
                "type": "error",
                "error": {
                    "type": "not_found_error",
                    "message": f"Model '{canonical_model}' not available in foundation model registry.",
                },
            },
            status_code=404,
        )

    # Round-robin subaccount selection
    try:
        subaccount_name = select_subaccount_for_orchestration(proxy_config)
    except ValueError as e:
        logger.error("No V2 subaccount available, tid=%s: %s", tid, e)
        return JSONResponse(
            {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": f"No Orchestration V2 subaccount configured: {e}",
                },
            },
            status_code=503,
        )

    subaccount = proxy_config.subaccounts[subaccount_name]
    token = proxy_context.get_token_manager(subaccount_name).get_token()
    stream = request_body_json.get("stream", False)

    # Convert Anthropic Messages → OpenAI Chat Completion format
    openai_payload = Converters.convert_claude_request_to_openai(request_body_json)
    openai_payload["model"] = canonical_model
    if stream:
        openai_payload["stream"] = True

    messages = openai_payload.get("messages", [])
    params = {
        k: v
        for k, v in openai_payload.items()
        if k not in ("model", "messages", "stream")
    }

    logger.info(
        "MESSAGES_V2: tid=%s, model=%s, sub=%s, stream=%s, msgs=%d",
        tid,
        canonical_model,
        subaccount_name,
        stream,
        len(messages),
    )

    client = get_orchestration_client()

    try:
        if not stream:
            openai_response = await run_in_threadpool(
                client.invoke,
                subaccount=subaccount,
                token=token,
                model=canonical_model,
                messages=messages,
                params=params,
            )
            # Convert OpenAI response → Anthropic Messages response format
            claude_response = Converters.convert_openai_response_to_claude(openai_response)
            logger.info(
                "MESSAGES_RSP: tid=%s, model=%s, sub=%s",
                tid,
                canonical_model,
                subaccount_name,
            )
            transport_logger.info(
                "RSP: tid=%s, status=200, body=%s", tid, json.dumps(claude_response)
            )
            return JSONResponse(claude_response)

        # Streaming: convert OpenAI SSE chunks → Anthropic SSE chunks
        async def _stream_gen():
            msg_id = f"msg_{uuid.uuid4().hex[:24]}"
            # Send message_start event
            yield _sse(
                {
                    "type": "message_start",
                    "message": {
                        "id": msg_id,
                        "type": "message",
                        "role": "assistant",
                        "model": canonical_model,
                        "content": [],
                        "stop_reason": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                }
            )
            yield _sse({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
            yield _sse({"type": "ping"})

            input_tokens = 0
            output_tokens = 0
            stop_reason = "end_turn"

            async for chunk_bytes in _iter_sync_generator(
                client.invoke_stream(
                    subaccount=subaccount,
                    token=token,
                    model=canonical_model,
                    messages=messages,
                    params=params,
                )
            ):
                # Parse SSE lines from the raw bytes chunk
                for line in chunk_bytes.decode("utf-8", errors="ignore").splitlines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        openai_chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # Extract usage if present (final chunk)
                    usage = openai_chunk.get("usage") or {}
                    if usage:
                        input_tokens = usage.get("prompt_tokens", input_tokens)
                        output_tokens = usage.get("completion_tokens", output_tokens)

                    delta = Converters.convert_openai_chunk_to_claude_delta(openai_chunk)
                    if delta:
                        yield _sse(delta)

                    # Track stop reason
                    choices = openai_chunk.get("choices", [])
                    if choices:
                        fr = choices[0].get("finish_reason")
                        if fr:
                            stop_reason_map = {
                                "stop": "end_turn",
                                "length": "max_tokens",
                                "tool_calls": "tool_use",
                                "content_filter": "stop_sequence",
                            }
                            stop_reason = stop_reason_map.get(fr, "end_turn")

            yield _sse({"type": "content_block_stop", "index": 0})
            yield _sse(
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                    "usage": {"output_tokens": output_tokens},
                }
            )
            yield _sse({"type": "message_stop"})

        return StreamingResponse(_stream_gen(), media_type="text/event-stream")

    except Exception as err:
        import requests as _requests

        if isinstance(err, _requests.HTTPError) and err.response is not None:
            status = err.response.status_code
            logger.error("MESSAGES_V2: HTTP %s, tid=%s: %s", status, tid, err)
            return JSONResponse(
                {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": f"Backend returned HTTP {status}",
                    },
                },
                status_code=status,
            )
        logger.error("MESSAGES_V2: Unexpected error, tid=%s: %s", tid, err, exc_info=True)
        return JSONResponse(
            {
                "type": "error",
                "error": {"type": "api_error", "message": str(err)},
            },
            status_code=500,
        )


def _sse(data: dict) -> bytes:
    """Encode a dict as a Server-Sent Events data line."""
    return f"data: {json.dumps(data)}\n\n".encode("utf-8")


async def _iter_sync_generator(gen):
    """Async wrapper for a synchronous generator (runs next() in thread pool)."""
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
