"""Blueprint for /v1/chat/completions endpoint."""

import uuid
from typing import TYPE_CHECKING

from flask import Blueprint, Response, jsonify, request, stream_with_context

from auth import RequestValidator
from blueprints.helpers import MockResponse
from handlers.model_handlers import (
    handle_claude_request,
    handle_gemini_request,
    handle_default_request,
)
from handlers.streaming_generators import generate_streaming_response
from proxy_helpers import Detector
from utils.logging_utils import get_server_logger

if TYPE_CHECKING:
    from config import ProxyConfig, ProxyGlobalContext

logger = get_server_logger(__name__)

chat_completions_bp = Blueprint("chat_completions", __name__)

# These will be set by register_blueprints() in proxy_server.py
_proxy_config: "ProxyConfig" = None  # type: ignore
_ctx: "ProxyGlobalContext" = None  # type: ignore

DEFAULT_GPT_MODEL = "gpt-4.1"


def init_chat_completions_blueprint(
    proxy_config: "ProxyConfig", ctx: "ProxyGlobalContext"
) -> None:
    """Initialize blueprint with configuration and context.

    Args:
        proxy_config: The proxy configuration
        ctx: The global context
    """
    global _proxy_config, _ctx
    _proxy_config = proxy_config
    _ctx = ctx


# Import after globals are defined
from load_balancer import resolve_model_name, load_balance_url  # noqa: E402


def handle_non_streaming_request(url, headers, payload, model, subaccount_name, tid):
    """Handle non-streaming request to backend API.

    Args:
        url: Backend API endpoint URL
        headers: Request headers
        payload: Request payload
        model: Model name
        subaccount_name: Name of the selected subAccount
        tid: Trace UUID for logging correlation

    Returns:
        Flask response with the API result
    """
    import json
    import requests
    from handlers.streaming_handler import make_backend_request
    from proxy_helpers import Converters
    from utils.error_handlers import handle_http_429_error
    from utils.logging_utils import get_transport_logger

    transport_logger = get_transport_logger(__name__)

    # Make request using shared backend request function
    result = make_backend_request(
        url=url,
        headers=headers,
        payload=payload,
        model=model,
        tid=tid,
        is_claude_model_fn=Detector.is_claude_model,
    )

    # Handle failed requests
    if not result.success:
        # Check for 429 error (rate limiting)
        if result.status_code == 429:
            # Create a mock HTTPError for the 429 handler
            mock_response = MockResponse(
                429, result.error_message or "", result.response_data, result.headers
            )
            mock_error = requests.exceptions.HTTPError(response=mock_response)
            return handle_http_429_error(
                mock_error, f"non-streaming request for {model}"
            )

        # Return error response
        if result.response_data:
            return jsonify(result.response_data), result.status_code
        else:
            return jsonify(
                {"error": result.error_message or "Unknown error"}
            ), result.status_code

    # Process successful response
    response_data = result.response_data

    # Log SSE parsing if applicable
    if result.is_sse_response:
        logger.info(
            "Claude model response is in SSE format, parsing as streaming response for non-streaming request"
        )

    # Convert response based on model type
    if Detector.is_claude_model(model):
        final_response = Converters.convert_claude_to_openai(response_data, model)
    elif Detector.is_gemini_model(model):
        final_response = Converters.convert_gemini_to_openai(response_data, model)
    else:
        final_response = response_data

    # Extract token usage
    total_tokens = final_response.get("usage", {}).get("total_tokens", 0)
    prompt_tokens = final_response.get("usage", {}).get("prompt_tokens", 0)
    completion_tokens = final_response.get("usage", {}).get("completion_tokens", 0)

    # Log token usage with subAccount information
    user_id = request.headers.get("Authorization", "unknown")
    if user_id and len(user_id) > 20:
        user_id = f"{user_id[:20]}..."
    ip_address = request.remote_addr or request.headers.get(
        "X-Forwarded-For", "unknown_ip"
    )
    logger.info(
        f"CHAT_RSP: tid={tid}, user={user_id}, ip={ip_address}, model={model}, sub_account={subaccount_name}, "
        f"prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}, total_tokens={total_tokens}"
    )

    # Log response being sent to client
    transport_logger.info(
        f"RSP: tid={tid}, status=200, body={json.dumps(final_response)}"
    )

    return jsonify(final_response), 200


@chat_completions_bp.route("/v1/chat/completions", methods=["POST"])
def proxy_openai_stream():
    """Main handler for chat completions endpoint with multi-subAccount support."""
    from utils.logging_utils import get_transport_logger

    logger.info("Received request to /v1/chat/completions")
    transport_logger = get_transport_logger(__name__)
    tid = str(uuid.uuid4())

    # Log raw request received from client
    transport_logger.info(
        f"REQ: tid={tid}, url={request.url}, body={request.get_data(as_text=True)}"
    )

    # Verify client authentication token
    validator = RequestValidator(_proxy_config.secret_authentication_tokens)
    if not validator.validate(request):
        logger.info("Unauthorized request received. Token verification failed.")
        return jsonify({"error": "Unauthorized"}), 401

    # Extract model from the request payload
    payload = request.json
    original_model = payload.get("model")
    effective_model = original_model or DEFAULT_GPT_MODEL

    if not original_model:
        logger.warning(
            f"No model specified in request, using fallback model {effective_model}"
        )

    # Try to resolve model name using fallback logic
    resolved_model = resolve_model_name(effective_model, _proxy_config)
    if resolved_model is None:
        error_message: str = f"Model {effective_model} is not supported."
        if effective_model != original_model:
            error_message = f"Models '{original_model}' and '{effective_model}'(fallback) are NOT defined in any subAccount"

        return jsonify({"error": error_message}), 404

    effective_model = resolved_model

    # Check streaming mode
    is_stream = payload.get("stream", False)
    logger.info(f"Model: {original_model}, Streaming: {is_stream}")

    try:
        # Handle request based on model type
        if Detector.is_claude_model(original_model):
            endpoint_url, modified_payload, subaccount_name = handle_claude_request(
                payload, original_model, _proxy_config
            )
        elif Detector.is_gemini_model(original_model):
            endpoint_url, modified_payload, subaccount_name = handle_gemini_request(
                payload, original_model, _proxy_config
            )
        else:
            endpoint_url, modified_payload, subaccount_name = handle_default_request(
                payload, original_model, _proxy_config
            )

        # Get token for the selected subAccount
        subaccount = _proxy_config.subaccounts[subaccount_name]
        subaccount_token = _ctx.get_token_manager(subaccount_name).get_token()

        # Get resource group for the selected subAccount
        resource_group = subaccount.resource_group

        # Get service key for tenant ID
        service_key = subaccount.service_key

        # Prepare headers for the backend request
        headers = {
            "AI-Resource-Group": resource_group,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Tenant-Id": service_key.identity_zone_id,
        }

        logger.info(
            f"CHAT: tid={tid}, url={endpoint_url}, model={effective_model}, sub_account={subaccount_name}"
        )

        # Handle non-streaming requests
        if not is_stream:
            return handle_non_streaming_request(
                endpoint_url,
                headers,
                modified_payload,
                original_model,
                subaccount_name,
                tid,
            )

        # Handle streaming requests
        return Response(
            stream_with_context(
                generate_streaming_response(
                    endpoint_url,
                    headers,
                    modified_payload,
                    original_model,
                    subaccount_name,
                    tid,
                )
            ),
            content_type="text/event-stream",
        )

    except ValueError as err:
        logger.error(f"CHAT: Value error, tid={tid}, {str(err)}", exc_info=True)
        return jsonify({"error": str(err)}), 400

    except Exception as err:
        logger.error(f"CHAT: Unexpected error, tid={tid}, {str(err)}", exc_info=True)
        return jsonify({"error": str(err)}), 500
