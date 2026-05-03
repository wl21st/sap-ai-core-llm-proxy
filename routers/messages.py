"""Router for /v1/messages endpoint (Anthropic Claude Messages API)."""

import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper
from tenacity import RetryError

from auth.request_validator import verify_request_token
from handlers.bedrock_handler import (
    invoke_bedrock_non_streaming,
    invoke_bedrock_streaming,
    read_response_body_stream,
)
from handlers.streaming_generators import (
    generate_bedrock_streaming_response,
    generate_claude_streaming_response,
)
from handlers.streaming_handler import make_backend_request
from load_balancer import load_balance_url
from proxy_helpers import Converters, Detector
from utils.auth_retry import log_auth_error_retry
from utils.cert_errors import is_certificate_error
from utils.circuit_breaker import CircuitBreakerOpenError, get_ssl_circuit_breaker
from utils.logging_utils import get_server_logger, get_transport_logger
from utils.retry import unified_retry as bedrock_retry, retry_on_rate_limit
from config import SubAccountConfig
from utils.sdk_pool import get_bedrock_client, invalidate_bedrock_client
from utils.sdk_utils import extract_deployment_id

logger = get_server_logger(__name__)
transport_logger = get_transport_logger(__name__)

router = APIRouter()

DEFAULT_CLAUDE_MODEL: str = "anthropic--claude-4.5-sonnet"
API_VERSION_BEDROCK_2023_05_31 = "bedrock-2023-05-31"
API_VERSION_2024_12_01_PREVIEW = "2024-12-01-preview"
API_VERSION_2023_05_15 = "2023-05-15"


def _handle_certificate_recovery(
    model: str,
    sub_account_config: SubAccountConfig,
    deployment_id: str,
    body_json: str,
    ca_cert_bundle: str | None,
    is_streaming: bool,
):
    """Recover from certificate errors by invalidating session and retrying.

    Consolidates certificate error recovery logic shared by streaming and non-streaming
    handlers.  A per-model circuit breaker guards this function: after
    ``DEFAULT_FAILURE_THRESHOLD`` consecutive recovery failures the circuit opens
    and subsequent calls raise ``CircuitBreakerOpenError`` immediately (→ HTTP 503)
    without touching the server.  The circuit moves to HALF_OPEN after the
    cooldown period, allowing one probe request through.

    Returns:
        Tuple of (bedrock_client, response_status, response_body)

    Raises:
        CircuitBreakerOpenError: If the SSL recovery circuit is currently OPEN.
        Exception: If recovery fails (recorded as a circuit failure).
    """
    breaker = get_ssl_circuit_breaker(model)

    def _do_recovery():
        logger.warning(
            "Certificate error detected: invalidating SDK session and retrying",
            exc_info=True,
        )
        invalidate_bedrock_client(model, invalidate_session=True)

        bedrock_client = get_bedrock_client(
            sub_account_config=sub_account_config,
            model_name=model,
            deployment_id=deployment_id,
            ca_cert_bundle=ca_cert_bundle,
        )

        if is_streaming:
            response = invoke_bedrock_streaming(bedrock_client, body_json)
        else:
            response = invoke_bedrock_non_streaming(bedrock_client, body_json)

        response_status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        response_body = response.get("body")

        return bedrock_client, response_status, response_body

    return breaker.call(_do_recovery)


@router.post("/v1/messages", dependencies=[Depends(verify_request_token)])
async def proxy_claude_request(request: Request):
    """Handles requests compatible with the Anthropic Claude Messages API."""
    tid: str = str(uuid.uuid4())

    request_body_bytes = await request.body()
    request_body_str = request_body_bytes.decode("utf-8", errors="ignore")
    logger.info("REQ: tid=%s, body=%s", tid, request_body_str)
    transport_logger.info(
        "REQ: tid=%s, url=%s, body=%s", tid, request.url, request_body_str
    )

    request_body_json = await request.json()
    request_model = request_body_json.get("model")
    if (request_model is None) or (request_model == ""):
        request_model = DEFAULT_CLAUDE_MODEL
        logger.info("hardcode request_model to: %s", request_model)
    else:
        logger.info("request_model is: %s", request_model)

    if not request_model:
        return JSONResponse(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Missing 'model' parameter",
                },
            },
            status_code=400,
        )

    proxy_config = request.app.state.proxy_config
    proxy_context = request.app.state.proxy_context

    try:
        selected_url, subaccount_name, resource_group, model = load_balance_url(
            request_model, proxy_config
        )
    except ValueError as e:
        logger.error("Model validation failed: %s", e, exc_info=True)
        return JSONResponse(
            {
                "type": "error",
                "error": {
                    "type": "not_found_error",
                    "message": f"Model '{request_model}' not available",
                },
            },
            status_code=404,
        )

    if not Detector.is_claude_model(model):
        logger.warning(
            "Model '%s' is not a Claude model, falling back to original implementation",
            model,
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

    logger.info("Request from Claude API for model: %s", model)
    stream = request_body_json.get("stream", False)

    # Extract ca_cert_bundle once to avoid repeated lookups
    ca_cert_bundle = proxy_context.get_ca_cert_bundle()

    try:
        logger.info(
            "Obtaining SAP AI SDK client for model[%s] for subaccount[%s]",
            model,
            subaccount_name,
        )
        bedrock_client: ClientWrapper = get_bedrock_client(
            sub_account_config=proxy_config.subaccounts[subaccount_name],
            model_name=model,
            deployment_id=extract_deployment_id(selected_url),
            ca_cert_bundle=ca_cert_bundle,
        )
        logger.info("SAP AI SDK client ready (cached)")

        conversation = request_body_json.get("messages", [])
        logger.debug("Original conversation: %s", conversation)

        thinking_cfg_preview = request_body_json.get("thinking")
        logger.info(
            "Claude request context: stream=%s, messages=%s, has_thinking=%s",
            stream,
            len(conversation) if isinstance(conversation, list) else "unknown",
            isinstance(thinking_cfg_preview, dict),
        )

        for message in conversation:
            content = message.get("content")
            if isinstance(content, list):
                items_to_remove = []
                for i, item in enumerate(content):
                    if item.get("type") == "text" and (
                        not item.get("text") or item.get("text") == ""
                    ):
                        items_to_remove.append(i)
                for i in reversed(items_to_remove):
                    content.pop(i)

        body = request_body_json.copy()
        logger.info("Original request body keys: %s", list(body.keys()))
        body.pop("model", None)
        body.pop("stream", None)
        body["anthropic_version"] = API_VERSION_BEDROCK_2023_05_31

        unsupported_fields = ["context_management", "metadata", "output_config"]
        for field in unsupported_fields:
            if field in body:
                logger.info(
                    "Removing unsupported top-level field '%s' from request body",
                    field,
                )
                body.pop(field, None)

        thinking_cfg = body.get("thinking")
        if isinstance(thinking_cfg, dict) and "context_management" in thinking_cfg:
            logger.info("Removing 'context_management' from thinking config")
            thinking_cfg.pop("context_management", None)

        tools_list = body.get("tools")
        if isinstance(tools_list, list):
            for tool in tools_list:
                if isinstance(tool, dict):
                    tool.pop("input_examples", None)
                    custom = tool.get("custom")
                    if isinstance(custom, dict):
                        custom.pop("input_examples", None)

        raw_max_tokens = body.get("max_tokens")
        max_tokens_value = None
        if raw_max_tokens is not None:
            try:
                max_tokens_value = int(raw_max_tokens)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid max_tokens value '%s' in request; resetting to None",
                    raw_max_tokens,
                )
                max_tokens_value = None

        if isinstance(thinking_cfg, dict):
            budget_tokens = thinking_cfg.get("budget_tokens")
            if isinstance(budget_tokens, int):
                required_min_tokens = budget_tokens + 1
                if max_tokens_value is None or max_tokens_value <= budget_tokens:
                    body["max_tokens"] = required_min_tokens
                    logger.info(
                        "Adjusted max_tokens to %s to satisfy thinking.budget_tokens=%s",
                        required_min_tokens,
                        budget_tokens,
                    )

        body_json = json.dumps(body)

        if stream:
            try:
                response = invoke_bedrock_streaming(bedrock_client, body_json)
                response_status = response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                response_body = response.get("body")

                # Check for authentication errors and retry with fresh client
                if response_status in [401, 403]:
                    logger.warning(
                        log_auth_error_retry(
                            response_status, f"SDK for model '{model}'"
                        )
                    )
                    invalidate_bedrock_client(model, invalidate_session=False)
                    bedrock_client = get_bedrock_client(
                        sub_account_config=proxy_config.subaccounts[subaccount_name],
                        model_name=model,
                        deployment_id=extract_deployment_id(selected_url),
                        ca_cert_bundle=ca_cert_bundle,
                    )
                    response = invoke_bedrock_streaming(bedrock_client, body_json)
                    response_status = response.get("ResponseMetadata", {}).get(
                        "HTTPStatusCode"
                    )
                    response_body = response.get("body")

                if response_status is None:
                    return JSONResponse(
                        {
                            "type": "error",
                            "error": {
                                "type": "api_error",
                                "message": "Malformed response from backend API",
                            },
                        },
                        status_code=500,
                    )

                if response_status != 200:
                    return JSONResponse(
                        {
                            "type": "error",
                            "error": {
                                "type": "api_error",
                                "message": f"Backend API returned status {response_status}",
                            },
                        },
                        status_code=response_status,
                    )

                if response_body is None:
                    return JSONResponse(
                        {
                            "type": "error",
                            "error": {
                                "type": "api_error",
                                "message": "Empty response body from backend API",
                            },
                        },
                        status_code=500,
                    )
            except Exception as e:
                if isinstance(e, CircuitBreakerOpenError):
                    return JSONResponse(
                        {
                            "type": "error",
                            "error": {
                                "type": "overloaded_error",
                                "message": str(e),
                            },
                        },
                        status_code=503,
                        headers={"Retry-After": str(int(e.retry_after) + 1)},
                    )
                elif is_certificate_error(e):
                    try:
                        _, response_status, response_body = (
                            _handle_certificate_recovery(
                                model,
                                proxy_config.subaccounts[subaccount_name],
                                extract_deployment_id(selected_url),
                                body_json,
                                ca_cert_bundle,
                                is_streaming=True,
                            )
                        )
                        if response_status != 200 or response_body is None:
                            return JSONResponse(
                                {
                                    "type": "error",
                                    "error": {
                                        "type": "api_error",
                                        "message": "Bedrock request failed after certificate recovery",
                                    },
                                },
                                status_code=response_status or 500,
                            )
                    except CircuitBreakerOpenError as cb_err:
                        return JSONResponse(
                            {
                                "type": "error",
                                "error": {
                                    "type": "overloaded_error",
                                    "message": str(cb_err),
                                },
                            },
                            status_code=503,
                            headers={"Retry-After": str(int(cb_err.retry_after) + 1)},
                        )
                    except Exception as retry_error:
                        logger.error(
                            "Retry after cert error failed: %s",
                            retry_error,
                            exc_info=True,
                        )
                        return JSONResponse(
                            {
                                "type": "error",
                                "error": {
                                    "type": "api_error",
                                    "message": "Certificate error recovery failed",
                                },
                            },
                            status_code=500,
                        )
                else:
                    logger.error("Error before streaming: %s", e, exc_info=True)
                    return JSONResponse(
                        {
                            "type": "error",
                            "error": {"type": "api_error", "message": str(e)},
                        },
                        status_code=500,
                    )

            return StreamingResponse(
                generate_bedrock_streaming_response(response_body, tid),
                media_type="text/event-stream",
            )

        try:
            response = invoke_bedrock_non_streaming(bedrock_client, body_json)
            response_status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            response_body = response.get("body")

            # Check for authentication errors and retry with fresh client
            if response_status in [401, 403]:
                logger.warning(
                    log_auth_error_retry(response_status, f"SDK for model '{model}'")
                )
                invalidate_bedrock_client(model, invalidate_session=False)
                bedrock_client = get_bedrock_client(
                    sub_account_config=proxy_config.subaccounts[subaccount_name],
                    model_name=model,
                    deployment_id=extract_deployment_id(selected_url),
                    ca_cert_bundle=ca_cert_bundle,
                )
                response = invoke_bedrock_non_streaming(bedrock_client, body_json)
                response_status = response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                response_body = response.get("body")
        except Exception as e:
            if isinstance(e, CircuitBreakerOpenError):
                return JSONResponse(
                    {
                        "type": "error",
                        "error": {
                            "type": "overloaded_error",
                            "message": str(e),
                        },
                    },
                    status_code=503,
                    headers={"Retry-After": str(int(e.retry_after) + 1)},
                )
            elif is_certificate_error(e):
                try:
                    _, response_status, response_body = _handle_certificate_recovery(
                        model,
                        proxy_config.subaccounts[subaccount_name],
                        extract_deployment_id(selected_url),
                        body_json,
                        ca_cert_bundle,
                        is_streaming=False,
                    )
                except CircuitBreakerOpenError as cb_err:
                    return JSONResponse(
                        {
                            "type": "error",
                            "error": {
                                "type": "overloaded_error",
                                "message": str(cb_err),
                            },
                        },
                        status_code=503,
                        headers={"Retry-After": str(int(cb_err.retry_after) + 1)},
                    )
                except Exception as retry_error:
                    logger.error(
                        "Retry after cert error failed: %s",
                        retry_error,
                        exc_info=True,
                    )
                    return JSONResponse(
                        {
                            "type": "error",
                            "error": {
                                "type": "api_error",
                                "message": "Certificate error recovery failed",
                            },
                        },
                        status_code=500,
                    )
            else:
                raise

        # Check for malformed response
        if response_status is None:
            return JSONResponse(
                {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": "Malformed response from backend API",
                    },
                },
                status_code=500,
            )

        if response_body is not None:
            chunk_data = read_response_body_stream(response_body)
            response_json = json.loads(chunk_data)

            logger.info("OUT_RSP_BODY: tid=%s, %s", tid, json.dumps(response_json))

            return JSONResponse(response_json, status_code=response_status)
        else:
            error_status = response_status if response_status >= 400 else 500
            return JSONResponse(
                {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": "Empty response body from backend API",
                    },
                },
                status_code=error_status,
            )

    except RetryError as err:
        logger.error("RetryError in Claude request: %s", err, exc_info=True)
        return JSONResponse(
            {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": "Bedrock retry failed",
                },
            },
            status_code=500,
        )
    except Exception as err:
        logger.error("Error in Claude request: %s", err, exc_info=True)
        return JSONResponse(
            {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": str(err),
                },
            },
            status_code=500,
        )
