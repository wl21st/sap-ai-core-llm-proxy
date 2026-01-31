"""Blueprint for /v1/embeddings endpoint."""

import uuid
from typing import TYPE_CHECKING, Dict

from flask import Blueprint, jsonify, request

from auth import RequestValidator
from blueprints.helpers import MockResponse
from handlers.streaming_handler import make_backend_request
from proxy_helpers import Detector
from utils.error_handlers import handle_http_429_error
from utils.logging_utils import get_server_logger, get_transport_logger

if TYPE_CHECKING:
    from config import ProxyConfig, ProxyGlobalContext, ServiceKey

logger = get_server_logger(__name__)
transport_logger = get_transport_logger(__name__)

embeddings_bp = Blueprint("embeddings", __name__)

# These will be set by register_blueprints() in proxy_server.py
_proxy_config: "ProxyConfig" = None  # type: ignore
_ctx: "ProxyGlobalContext" = None  # type: ignore

DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
API_VERSION_2023_05_15 = "2023-05-15"


def init_embeddings_blueprint(
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
from load_balancer import load_balance_url  # noqa: E402


def handle_embedding_service_call(input_text, model, encoding_format):
    """Prepare the request for SAP AI Core embeddings endpoint.

    Args:
        input_text: The input text to embed
        model: The embedding model to use
        encoding_format: The encoding format (optional)

    Returns:
        Tuple of (endpoint_url, payload, subaccount_name)
    """
    # Logic to prepare the request to SAP AI Core
    selected_url, subaccount_name, _, model = load_balance_url(model, _proxy_config)

    # Construct the URL based on the official SAP AI Core documentation
    # This is critical or it will return 404
    api_version = API_VERSION_2023_05_15
    endpoint_url = f"{selected_url.rstrip('/')}/embeddings?api-version={api_version}"

    # The payload for the embeddings endpoint only requires the input.
    modified_payload = {"input": input_text}

    return endpoint_url, modified_payload, subaccount_name


@embeddings_bp.route("/v1/embeddings", methods=["POST"])
def handle_embedding_request():
    """Handle embedding request endpoint."""
    import requests

    tid: str = str(uuid.uuid4())

    # Log raw request received from client
    request_body_str: str = request.get_data(as_text=True)
    logger.info(f"CLIENT_EMBED_REQ: tid={tid}, body={request_body_str}")
    transport_logger.info(
        f"CLIENT_EMBED_REQ: tid={tid}, url={request.url}, body={request_body_str}"
    )

    validator = RequestValidator(_proxy_config.secret_authentication_tokens)
    if not validator.validate(request):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.json
    input_text = payload.get("input")
    model = payload.get("model", DEFAULT_EMBEDDING_MODEL)
    encoding_format = payload.get("encoding_format")

    if not input_text:
        return jsonify({"error": "Input text is required"}), 400

    try:
        vendor_endpoint_url, upstream_payload, subaccount_name = (
            handle_embedding_service_call(input_text, model, encoding_format)
        )

        # Get token manager from global context
        token_manager = _ctx.get_token_manager(subaccount_name)
        subaccount_token = token_manager.get_token()
        subaccount = _proxy_config.subaccounts[subaccount_name]
        resource_group = subaccount.resource_group
        service_key: "ServiceKey" = subaccount.service_key
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Resource-Group": resource_group,
            "AI-Tenant-Id": service_key.identity_zone_id,
        }

        # Make backend request using shared function
        result = make_backend_request(
            url=vendor_endpoint_url,
            headers=headers,
            payload=upstream_payload,
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
                    429,
                    result.error_message or "",
                    result.response_data,
                    result.headers,
                )
                mock_error = requests.exceptions.HTTPError(response=mock_response)
                return handle_http_429_error(
                    mock_error, f"embedding request for {model}"
                )

            # Return error response
            if result.response_data:
                return jsonify(result.response_data), result.status_code
            else:
                return jsonify(
                    {"error": result.error_message or "Unknown error"}
                ), result.status_code

        # Return successful response
        return jsonify(result.response_data), result.status_code

    except Exception as e:
        logger.error(
            f"EMBED_ERR: tid={tid}, reason=unexpected_error, error={str(e)}",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500
