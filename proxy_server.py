import ast
import json
import random
import sys
import time
import uuid
from logging import Logger
from typing import Dict, Any

import requests
from botocore.exceptions import ClientError  # noqa: F401 - used in bedrock_handler
from flask import Flask, Response, jsonify, request, stream_with_context
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper

# SAP AI SDK imports
from tenacity import (
    RetryError,
)

from auth import RequestValidator
from auth.token_manager import TokenManager

# Import from new modular structure
from config import ProxyConfig, load_proxy_config, ServiceKey, ProxyGlobalContext
from proxy_helpers import Converters, Detector
from utils.error_handlers import handle_http_429_error
from utils.logging_utils import get_server_logger, get_transport_logger, init_logging
from utils.sdk_utils import extract_deployment_id

# Initialize token logger (will be configured on first use)
logger: Logger = get_server_logger(__name__)
transport_logger: Logger = get_transport_logger(__name__)
token_usage_logger: Logger = get_server_logger("token_usage")

ctx: ProxyGlobalContext

from utils.sdk_pool import get_bedrock_client  # noqa: E402

API_VERSION_2023_05_15 = "2023-05-15"
API_VERSION_2024_12_01_PREVIEW = "2024-12-01-preview"
API_VERSION_BEDROCK_2023_05_31 = "bedrock-2023-05-31"

DEFAULT_CLAUDE_MODEL: str = "anthropic--claude-4.5-sonnet"
DEFAULT_GEMINI_MODEL: str = "gemini-2.5-pro"
DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
DEFAULT_GPT_MODEL = "gpt-4.1"

# Retry configuration - now unified in utils/retry.py
from utils.retry import (
    RETRY_MAX_ATTEMPTS,
    RETRY_MULTIPLIER,
    RETRY_MIN_WAIT,
    RETRY_MAX_WAIT,
)

"""SAP API Reference are documented at https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/example-payloads-for-inferencing-third-party-models"""

# Bedrock handler - extracted to handlers/bedrock_handler.py
from handlers.bedrock_handler import (
    invoke_bedrock_streaming,
    invoke_bedrock_non_streaming,
    read_response_body_stream,
)

# Streaming generators - extracted to handlers/streaming_generators.py (Phase 6d)
from handlers.streaming_generators import (
    generate_bedrock_streaming_response,
    generate_streaming_response,
    generate_claude_streaming_response,
)


# Global configuration
proxy_config: ProxyConfig = ProxyConfig()

app = Flask(__name__)


def register_blueprints(
    app: Flask, config: ProxyConfig, context: ProxyGlobalContext
) -> None:
    """Register all Flask blueprints with the application.

    Args:
        app: The Flask application instance
        config: The proxy configuration
        context: The global context
    """
    from blueprints import (
        chat_completions_bp,
        messages_bp,
        embeddings_bp,
        models_bp,
        event_logging_bp,
        init_chat_completions_blueprint,
        init_messages_blueprint,
        init_embeddings_blueprint,
        init_models_blueprint,
    )

    # Initialize blueprints with config and context
    init_chat_completions_blueprint(config, context)
    init_messages_blueprint(config, context)
    init_embeddings_blueprint(config, context)
    init_models_blueprint(config, context)

    # Register blueprints
    app.register_blueprint(chat_completions_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(embeddings_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(event_logging_bp)

    logger.info("Registered all blueprints successfully")


# Embeddings endpoint moved to blueprints/embeddings.py


def handle_embedding_service_call(input_text, model, encoding_format):
    # Logic to prepare the request to SAP AI Core
    # TODO: Add default model for embedding
    selected_url, subaccount_name, _, model = load_balance_url(model)

    # Construct the URL based on the official SAP AI Core documentation
    # This is critical or it will return 404
    # TODO: Follow up on what is the required
    api_version = API_VERSION_2023_05_15
    endpoint_url = f"{selected_url.rstrip('/')}/embeddings?api-version={api_version}"

    # The payload for the embeddings endpoint only requires the input.
    modified_payload = {"input": input_text}

    return endpoint_url, modified_payload, subaccount_name


def format_embedding_response(response, model):
    # Logic to convert the response to OpenAI format
    embedding_data = response.get("embedding", [])
    return {
        "object": "list",
        "data": [{"object": "embedding", "embedding": embedding_data, "index": 0}],
        "model": model,
        "usage": {
            "prompt_tokens": len(embedding_data),
            "total_tokens": len(embedding_data),
        },
    }


# Version utilities - extracted to version.py
from version import get_version_info, get_version, get_git_hash, get_version_string

# CLI argument parsing - extracted to cli.py
from cli import parse_arguments

# Load balancing - extracted to load_balancer.py
from load_balancer import (
    resolve_model_name as _resolve_model_name,
    load_balance_url as _load_balance_url,
)


def resolve_model_name(model_name):
    """Resolve model name with backward-compatible wrapper."""
    return _resolve_model_name(model_name, proxy_config)


def load_balance_url(model):
    """Load balance URL with backward-compatible wrapper.

    This wrapper uses the global proxy_config.
    For new code, import from load_balancer and pass proxy_config explicitly.
    """
    return _load_balance_url(model, proxy_config)


# Streaming helpers - extracted to handlers/streaming_handler.py
from handlers.streaming_handler import (
    BackendRequestResult,
    get_claude_stop_reason_from_gemini_chunk,
    get_claude_stop_reason_from_openai_chunk,
    make_backend_request,
    parse_sse_response_to_claude_json as _parse_sse_response_to_claude_json,
)


def parse_sse_response_to_claude_json(response_text):
    """Parse SSE response to Claude JSON - backward-compatible wrapper."""
    return _parse_sse_response_to_claude_json(response_text)


# Model handlers - extracted to handlers/model_handlers.py
from handlers.model_handlers import (
    handle_claude_request as _handle_claude_request,
    handle_gemini_request as _handle_gemini_request,
    handle_default_request as _handle_default_request,
)


def handle_claude_request(payload, model="3.5-sonnet"):
    """Handle Claude model request with multi-subAccount support.

    This is a backward-compatible wrapper that uses the global proxy_config.
    For new code, import from handlers.model_handlers and pass proxy_config explicitly.
    """
    return _handle_claude_request(payload, model, proxy_config)


def handle_gemini_request(payload, model="gemini-2.5-pro"):
    """Handle Gemini model request with multi-subAccount support.

    This is a backward-compatible wrapper that uses the global proxy_config.
    For new code, import from handlers.model_handlers and pass proxy_config explicitly.
    """
    return _handle_gemini_request(payload, model, proxy_config)


def handle_default_request(payload, model=DEFAULT_GPT_MODEL):
    """Handle default (non-Claude, non-Gemini) model request with multi-subAccount support.

    This is a backward-compatible wrapper that uses the global proxy_config.
    For new code, import from handlers.model_handlers and pass proxy_config explicitly.
    """
    return _handle_default_request(payload, model, proxy_config)


# Models endpoint moved to blueprints/models.py
# Event logging endpoint moved to blueprints/event_logging.py


content_type = "Application/json"


# Chat completions endpoint moved to blueprints/chat_completions.py


# Messages endpoint moved to blueprints/messages.py


def proxy_claude_request_original():
    """Original implementation preserved as fallback."""
    logger.info("Using original Claude request implementation")

    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    if not validator.validate(request):
        return jsonify(
            {
                "type": "error",
                "error": {
                    "type": "authentication_error",
                    "message": "Invalid API Key provided.",
                },
            }
        ), 401

    payload = request.json
    model = payload.get("model")
    if not model:
        return jsonify(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Missing 'model' parameter",
                },
            }
        ), 400

    is_stream = payload.get("stream", False)
    logger.info(f"Claude API request for model: {model}, Streaming: {is_stream}")

    try:
        base_url, subaccount_name, resource_group, model = load_balance_url(model)
        token_manager = ctx.get_token_manager(subaccount_name)
        subaccount_token = token_manager.get_token()

        # Convert incoming Claude payload to the format expected by the backend model
        if Detector.is_gemini_model(model):
            backend_payload = Converters.convert_claude_request_to_gemini(payload)
            endpoint_path = (
                f"/models/{model}:streamGenerateContent"
                if is_stream
                else f"/models/{model}:generateContent"
            )
        elif Detector.is_claude_model(model):
            backend_payload = Converters.convert_claude_request_for_bedrock(payload)
            if is_stream:
                endpoint_path = (
                    "/converse-stream"
                    if Detector.is_claude_37_or_4(model)
                    else "/invoke-with-response-stream"
                )
            else:
                endpoint_path = (
                    "/converse" if Detector.is_claude_37_or_4(model) else "/invoke"
                )
        else:  # Assume OpenAI-compatible
            backend_payload = Converters.convert_claude_request_to_openai(payload)
            api_version = (
                API_VERSION_2024_12_01_PREVIEW
                if any(m in model for m in ["o3", "o4-mini", "o3-mini"])
                else API_VERSION_2023_05_15
            )
            endpoint_path = f"/chat/completions?api-version={api_version}"

        endpoint_url = f"{base_url.rstrip('/')}{endpoint_path}"

        service_key: ServiceKey | None = proxy_config.subaccounts[
            subaccount_name
        ].service_key
        headers = {
            "AI-Resource-Group": resource_group,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Tenant-Id": service_key.identity_zone_id,
        }

        # Handle anthropic-specific headers
        for h in ["anthropic-version", "anthropic-beta"]:
            if h in request.headers:
                headers[h] = request.headers[h]

        # Add default anthropic-beta header for Claude streaming if not already present
        if Detector.is_claude_model(model) and is_stream:
            existing_beta = request.headers.get("anthropic-beta", "")
            if "fine-grained-tool-streaming-2025-05-14" not in existing_beta:
                if existing_beta:
                    # Append to existing anthropic-beta header
                    headers["anthropic-beta"] = (
                        f"{existing_beta},fine-grained-tool-streaming-2025-05-14"
                    )
                else:
                    # Set new anthropic-beta header
                    headers["anthropic-beta"] = "fine-grained-tool-streaming-2025-05-14"

        logger.info(
            f"Forwarding converted request to {endpoint_url} for subAccount '{subaccount_name}'"
        )

        if not is_stream:
            # Generate TID for logging (internal to this fallback function)
            tid = str(uuid.uuid4())

            result = make_backend_request(
                endpoint_url,
                headers=headers,
                payload=backend_payload,
                model=model,
                tid=tid,
                is_claude_model_fn=Detector.is_claude_model,
            )

            if not result.success:
                logger.error(
                    f"Error in Claude request({model}): {result.error_message}"
                )
                if result.response_data:
                    return jsonify(result.response_data), result.status_code
                else:
                    return jsonify({"error": result.error_message}), result.status_code

            backend_json = result.response_data

            if Detector.is_gemini_model(model):
                final_response = Converters.convert_gemini_response_to_claude(
                    backend_json, model
                )
            elif Detector.is_claude_model(model):
                final_response = backend_json
            else:
                final_response = Converters.convert_openai_response_to_claude(
                    backend_json
                )

            # Log the response for debug purposes
            logger.info(
                f"Final response to client: {json.dumps(final_response, indent=2)}"
            )

            return jsonify(final_response), result.status_code
        else:
            return Response(
                stream_with_context(
                    generate_claude_streaming_response(
                        endpoint_url, headers, backend_payload, model, subaccount_name
                    )
                ),
                content_type="text/event-stream",
            )

    except ValueError as err:
        logger.error(
            f"Value error during Claude request handling: {err}", exc_info=True
        )
        return jsonify(
            {
                "type": "error",
                "error": {"type": "invalid_request_error", "message": str(err)},
            }
        ), 400
    except requests.exceptions.HTTPError as err:
        logger.error(f"HTTP error in Claude request({model}): {err}", exc_info=True)
        try:
            return jsonify(err.response.json()), err.response.status_code
        except Exception as json_err:
            return jsonify(
                {"error": str(err)}
            ), err.response.status_code if err.response else 500
    except Exception as err:
        logger.error(
            f"Unexpected error during Claude request handling: {err}", exc_info=True
        )
        return jsonify(
            {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": "An unexpected error occurred.",
                },
            }
        ), 500


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
            class MockResponse:
                def __init__(self, status_code, text, data, headers):
                    self.status_code = status_code
                    self.text = text
                    self._data = data
                    self.headers = headers if headers else {}

                def json(self):
                    return self._data if self._data else {}

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


def main() -> None:
    """Main entry point for the SAP AI Core LLM Proxy Server."""
    # Deprecation Warning
    import warnings

    warnings.warn(
        "proxy_server.py is deprecated and will be removed in a future version. "
        "Please use 'sap-ai-proxy' (via main.py) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    print("WARNING: proxy_server.py is deprecated. Use 'sap-ai-proxy' instead.")

    args = parse_arguments()

    # Setup logging using the new modular function
    init_logging(debug=args.debug)

    # Handle cache refresh flag before loading config
    if args.refresh_cache:
        from utils.cache_utils import clear_deployment_cache

        logger.info("Clearing deployment cache due to --refresh-cache flag...")
        clear_deployment_cache()
        logger.info("Cache cleared successfully")

    # Log version information at startup
    version_info = get_version_string()
    logger.info(f"SAP AI Core LLM Proxy Server - Version: {version_info}")

    logger.info(f"Loading configuration from: {args.config}")

    # Load the proxy config and initialize global context
    global ctx
    ctx = ProxyGlobalContext()
    ctx.initialize(load_proxy_config(args.config))

    global proxy_config
    proxy_config = ctx.config

    # Get server configuration
    host = proxy_config.host
    if args.port is not None:
        port = args.port
        logger.info(
            f"Port override: Using CLI argument --port {port} (config file specifies {proxy_config.port})"
        )
    else:
        port = proxy_config.port

    logger.info(
        f"Loaded multi-subAccount configuration with {len(proxy_config.subaccounts)} subAccounts"
    )
    logger.info(f"Available subAccounts: {', '.join(proxy_config.subaccounts.keys())}")
    logger.info(
        f"Available models: {', '.join(proxy_config.model_to_subaccounts.keys())}"
    )

    # Register all blueprints
    register_blueprints(app, proxy_config, ctx)

    logger.info(f"Starting proxy server on host {host} and port {port}...")
    logger.info(f"API Host: http://{host}:{port}/v1")
    logger.info("Available endpoints:")
    logger.info(f"  - OpenAI Compatible API: http://{host}:{port}/v1/chat/completions")
    logger.info(f"  - Anthropic Claude API: http://{host}:{port}/v1/messages")
    logger.info(f"  - Models Listing: http://{host}:{port}/v1/models")
    logger.info(f"  - Embeddings API: http://{host}:{port}/v1/embeddings")
    app.run(host=host, port=port, debug=args.debug)


if __name__ == "__main__":
    main()
