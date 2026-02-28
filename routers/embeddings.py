"""Router for /v1/embeddings endpoint."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from auth.request_validator import verify_request_token
from handlers.streaming_handler import make_backend_request
from load_balancer import load_balance_url
from proxy_helpers import Detector
from utils.logging_utils import get_server_logger, get_transport_logger

logger = get_server_logger(__name__)
transport_logger = get_transport_logger(__name__)

router = APIRouter()

DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
API_VERSION_2023_05_15 = "2023-05-15"


def _handle_embedding_service_call(
    proxy_config: Any, input_text: Any, model: str
) -> tuple[str, dict[str, Any], str]:
    resolved_model = model
    if (
        resolved_model not in proxy_config.model_to_subaccounts
        or not proxy_config.model_to_subaccounts.get(resolved_model)
    ):
        logger.info(
            "Model '%s' not available, attempting fallback to default '%s'",
            model,
            DEFAULT_EMBEDDING_MODEL,
        )
        resolved_model = DEFAULT_EMBEDDING_MODEL

    selected_url, subaccount_name, _, _ = load_balance_url(resolved_model, proxy_config)
    endpoint_url = (
        f"{selected_url.rstrip('/')}/embeddings?api-version={API_VERSION_2023_05_15}"
    )
    modified_payload = {"input": input_text}
    return endpoint_url, modified_payload, subaccount_name


@router.post("/v1/embeddings", dependencies=[Depends(verify_request_token)])
async def handle_embedding_request(request: Request) -> JSONResponse:
    """Handle embedding request endpoint."""
    tid: str = str(uuid.uuid4())

    request_body_str: str = await request.body()
    logger.info("CLIENT_EMBED_REQ: tid=%s, body=%s", tid, request_body_str)
    transport_logger.info(
        "CLIENT_EMBED_REQ: tid=%s, url=%s, body=%s",
        tid,
        request.url,
        request_body_str,
    )

    payload = await request.json()
    input_text = payload.get("input")
    model = payload.get("model", DEFAULT_EMBEDDING_MODEL)

    if not input_text:
        return JSONResponse({"error": "Input text is required"}, status_code=400)

    proxy_config = request.app.state.proxy_config
    proxy_context = request.app.state.proxy_context

    try:
        vendor_endpoint_url, upstream_payload, subaccount_name = (
            _handle_embedding_service_call(proxy_config, input_text, model)
        )

        token_manager = proxy_context.get_token_manager(subaccount_name)
        subaccount_token = token_manager.get_token()
        subaccount = proxy_config.subaccounts[subaccount_name]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Resource-Group": subaccount.resource_group,
            "AI-Tenant-Id": subaccount.service_key.identity_zone_id,
        }

        result = await make_backend_request(
            url=vendor_endpoint_url,
            headers=headers,
            payload=upstream_payload,
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
                return JSONResponse(
                    result.response_data, status_code=result.status_code
                )
            return JSONResponse(
                {"error": result.error_message or "Unknown error"},
                status_code=result.status_code,
            )

        return JSONResponse(result.response_data, status_code=result.status_code)

    except Exception as e:
        logger.error(
            "EMBED_ERR: tid=%s, reason=unexpected_error, error=%s",
            tid,
            str(e),
            exc_info=True,
        )
        return JSONResponse({"error": str(e)}, status_code=500)
