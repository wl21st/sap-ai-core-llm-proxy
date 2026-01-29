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

# Retry configuration constants (centralized for future configurability)
RETRY_MAX_ATTEMPTS = 4  # Total attempts (1 original + 3 retries)
RETRY_MULTIPLIER = 2  # Exponential backoff multiplier
RETRY_MIN_WAIT = 4  # Minimum wait time in seconds
RETRY_MAX_WAIT = 16  # Maximum wait time in seconds

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


@app.route("/v1/embeddings", methods=["POST"])
def handle_embedding_request():
    tid: str = str(uuid.uuid4())

    # Log raw request received from client
    request_body_str: str = request.get_data(as_text=True)
    logger.info(f"CLIENT_EMBED_REQ: tid={tid}, body={request_body_str}")
    transport_logger.info(
        f"CLIENT_EMBED_REQ: tid={tid}, url={request.url}, body={request_body_str}"
    )

    validator = RequestValidator(proxy_config.secret_authentication_tokens)
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
        token_manager = ctx.get_token_manager(subaccount_name)
        subaccount_token = token_manager.get_token()
        subaccount = proxy_config.subaccounts[subaccount_name]
        resource_group = subaccount.resource_group
        service_key: ServiceKey = subaccount.service_key
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
                class MockResponse:
                    def __init__(self, status_code, text, data, headers):
                        self.status_code = status_code
                        self.text = text
                        self._data = data
                        self.headers = headers if headers else {}

                    def json(self):
                        return self._data if self._data else {}

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


@app.route("/v1/models", methods=["GET", "OPTIONS"])
def list_models() -> tuple[Response, int]:
    """Lists all available models across all subAccounts."""
    logger.info("Received request to /v1/models, headers={request.headers}")

    models: list[dict[str, Any]] = []
    timestamp = int(time.time())

    for model_name in proxy_config.model_to_subaccounts.keys():
        models.append(
            {
                "id": model_name,
                "object": "model",
                "created": timestamp,
                "owned_by": "sap-ai-core",
            }
        )

    return jsonify({"object": "list", "data": models}), 200


@app.route("/api/event_logging/batch", methods=["POST", "OPTIONS"])
def handle_event_logging():
    """Dummy endpoint for Claude Code event logging to prevent 404 errors."""
    logger.info("Received request to /api/event_logging/batch")
    logger.debug(f"Request headers: {request.headers}")
    logger.debug(f"Request body: {request.get_json(silent=True)}")

    # Return success response for event logging
    return jsonify({"status": "success", "message": "Events logged successfully"}), 200


content_type = "Application/json"


@app.route("/v1/chat/completions", methods=["POST"])
def proxy_openai_stream():
    """Main handler for chat completions endpoint with multi-subAccount support."""
    logger.info("Received request to /v1/chat/completions")
    tid = str(uuid.uuid4())

    # Log raw request received from client
    transport_logger.info(
        f"REQ: tid={tid}, url={request.url}, body={request.get_data(as_text=True)}"
    )

    # Verify client authentication token
    validator = RequestValidator(proxy_config.secret_authentication_tokens)
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
    resolved_model = resolve_model_name(effective_model)
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
                payload, original_model
            )
        elif Detector.is_gemini_model(original_model):
            endpoint_url, modified_payload, subaccount_name = handle_gemini_request(
                payload, original_model
            )
        else:
            endpoint_url, modified_payload, subaccount_name = handle_default_request(
                payload, original_model
            )

        # Get token for the selected subAccount
        subaccount = proxy_config.subaccounts[subaccount_name]
        subaccount_token = ctx.get_token_manager(subaccount_name).get_token()

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


@app.route("/v1/messages", methods=["POST"])
def proxy_claude_request():
    """Handles requests that are compatible with the Anthropic Claude Messages API using SAP AI SDK."""
    tid: str = str(uuid.uuid4())

    # Log raw request received from client
    request_body_str: str = request.get_data(as_text=True)
    logger.info(f"REQ: tid={tid}, body={request_body_str}")
    transport_logger.info(f"REQ: tid={tid}, url={request.url}, body={request_body_str}")

    # Validate API key using proxy config authentication
    api_key = request.headers.get("X-Api-Key", "")
    if not api_key:
        api_key = request.headers.get("Authorization", "").replace("Bearer ", "")

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

    # Get request body and extract model
    request_body_json = request.get_json(cache=False)

    # Handle missing model by hardcoding to anthropic--claude-4.5-sonnet
    request_model = request_body_json.get("model")
    if (request_model is None) or (request_model == ""):
        # Hardcode to anthropic--claude-4.5-sonnet if no model specified
        request_model = DEFAULT_CLAUDE_MODEL
        logger.info(f"hardcode request_model to: {request_model}")
    else:
        logger.info(f"request_model is: {request_model}")

    if not request_model:
        return jsonify(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Missing 'model' parameter",
                },
            }
        ), 400

    # Validate model availability
    try:
        selected_url, subaccount_name, resource_group, model = load_balance_url(
            request_model
        )
    except ValueError as e:
        logger.error(f"Model validation failed: {e}", exc_info=True)

        return jsonify(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": f"Model '{request_model}' not available",
                },
            }
        ), 400

    # Check if this is an Anthropic model that should use the SDK
    if not Detector.is_claude_model(model):
        logger.warning(
            f"Model '{model}' is not a Claude model, falling back to original implementation"
        )
        # Fall back to original implementation for non-Claude models
        return proxy_claude_request_original()

    logger.info(f"Request from Claude API for model: {model}")

    # Extract streaming flag, default to True
    stream = request_body_json.get("stream", True)

    try:
        # Use cached SAP AI SDK client for the model
        logger.info(
            f"Obtaining SAP AI SDK client for model[{model}] for subaccount[{subaccount_name}]"
        )

        bedrock_client: ClientWrapper = get_bedrock_client(
            sub_account_config=proxy_config.subaccounts[subaccount_name],
            model_name=model,
            deployment_id=extract_deployment_id(selected_url),
        )
        logger.info("SAP AI SDK client ready (cached)")

        # Get the conversation messages
        conversation = request_body_json.get("messages", [])
        logger.debug(f"Original conversation: {conversation}")

        thinking_cfg_preview = request_body_json.get("thinking")
        logger.info(
            "Claude request context: stream=%s, messages=%s, has_thinking=%s",
            stream,
            len(conversation) if isinstance(conversation, list) else "unknown",
            isinstance(thinking_cfg_preview, dict),
        )

        # Process conversation to handle empty text content and image compression
        for message in conversation:
            content = message.get("content")
            if isinstance(content, list):
                items_to_remove = []
                for i, item in enumerate(content):
                    if item.get("type") == "text" and (
                        not item.get("text") or item.get("text") == ""
                    ):
                        # Mark empty text items for removal
                        items_to_remove.append(i)
                    elif (
                        item.get("type") == "image"
                        and item.get("source", {}).get("type") == "base64"
                    ):
                        # Compress image data if available (would need ImageCompressor utility)
                        image_data = item.get("source", {}).get("data")
                        if image_data:
                            # Note: ImageCompressor would need to be imported/implemented
                            # For now, keeping original data
                            logger.debug("Image data found in message content")

                # Remove empty text items (in reverse order to maintain indices)
                for i in reversed(items_to_remove):
                    content.pop(i)

        # Prepare the request body for Bedrock
        body = request_body_json.copy()

        # Log the original request body for debugging
        logger.info("Original request body keys: %s", list(body.keys()))

        # Remove model and stream from body as they're handled separately
        body.pop("model", None)
        body.pop("stream", None)

        # Add required anthropic_version for Bedrock
        body["anthropic_version"] = API_VERSION_BEDROCK_2023_05_31

        # Remove unsupported fields for Bedrock
        unsupported_fields = ["context_management", "metadata", "output_config"]
        for field in unsupported_fields:
            if field in body:
                logger.info(
                    "Removing unsupported top-level field '%s' from request body", field
                )
                body.pop(field, None)

        # Check for context_management in thinking config
        thinking_cfg = body.get("thinking")
        if isinstance(thinking_cfg, dict):
            if "context_management" in thinking_cfg:
                logger.info("Removing 'context_management' from thinking config")
                thinking_cfg.pop("context_management", None)

        # Remove unsupported fields inside tools for Bedrock
        tools_list = body.get("tools")
        removed_count = 0
        if isinstance(tools_list, list):
            for idx, tool in enumerate(tools_list):
                if isinstance(tool, dict):
                    # Remove top-level input_examples
                    if "input_examples" in tool:
                        tool.pop("input_examples", None)
                        removed_count += 1
                    # Remove nested custom.input_examples
                    custom = tool.get("custom")
                    if isinstance(custom, dict) and "input_examples" in custom:
                        custom.pop("input_examples", None)
                        removed_count += 1

        # Ensure max_tokens obeys thinking budget constraints
        thinking_cfg = body.get("thinking")
        raw_max_tokens = body.get("max_tokens")
        max_tokens_value = None
        if raw_max_tokens is not None:
            try:
                max_tokens_value = int(raw_max_tokens)
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid max_tokens value '{raw_max_tokens}' in request; resetting to None"
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
                else:
                    logger.debug(
                        "max_tokens=%s already greater than thinking.budget_tokens=%s",
                        max_tokens_value,
                        budget_tokens,
                    )
            else:
                logger.debug("No integer thinking.budget_tokens found in request")
        elif thinking_cfg is not None:
            logger.debug("Ignoring non-dict thinking config in request body")

        if body.get("max_tokens") is not None:
            logger.info(
                "Final max_tokens for model %s request: %s",
                model,
                body["max_tokens"],
            )
        else:
            logger.info("No max_tokens specified after adjustment for model %s", model)

        # Log final body keys before sending to Bedrock
        logger.info("Final request body keys before Bedrock: %s", list(body.keys()))
        if "thinking" in body:
            logger.info(
                "Thinking config keys: %s",
                list(body["thinking"].keys())
                if isinstance(body["thinking"], dict)
                else type(body["thinking"]),
            )

        # Convert body to JSON string for Bedrock API
        body_json = json.dumps(body)

        # Pretty-print the body JSON for easier debugging
        try:
            pretty_body_json = json.dumps(
                json.loads(body_json), indent=2, ensure_ascii=False
            )
        except Exception:
            pretty_body_json = body_json
        logger.info("Request body for Bedrock (pretty):\n%s", pretty_body_json)

        # Log request being sent to Bedrock/LLM service
        transport_logger.info(
            f"OUT_REQ: tid={tid}, model={model}, body={pretty_body_json}"
        )

        if stream:
            # Handle streaming response
            # Check for errors before starting the stream (to return proper status code)
            try:
                response = invoke_bedrock_streaming(bedrock_client, body_json)
                # Extract status code if available - default to None to detect malformed responses
                response_status = response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                response_body = response.get("body")

                # Check for malformed response first (missing status code)
                if response_status is None:
                    logger.error("Missing HTTPStatusCode in response metadata")
                    error_response = {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": "Malformed response from backend API",
                        },
                    }
                    return jsonify(error_response), 500

                # If status is not 200, return error before starting stream
                if response_status != 200:
                    logger.error(f"Non-200 status code from SDK: {response_status}")
                    error_response = {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": f"Backend API returned status {response_status}",
                        },
                    }
                    return jsonify(error_response), response_status

                # If we detect an error before streaming starts, return error response
                if response_body is None:
                    logger.error(
                        "Response body is None from SDK invoke_model_with_response_stream"
                    )
                    error_response = {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": "Empty response body from backend API",
                        },
                    }
                    # At this point, response_status is 200, so we return 500 for error
                    return jsonify(error_response), 500

            except Exception as e:
                # If error occurs before streaming, we can return proper error status
                logger.error(f"Error before streaming: {e}", exc_info=True)
                error_response = {
                    "type": "error",
                    "error": {"type": "api_error", "message": str(e)},
                }
                return jsonify(error_response), 500

            # Stream is healthy, proceed with streaming response
            # Use extracted generator from handlers/streaming_generators.py (Phase 6d)
            return (
                Response(
                    generate_bedrock_streaming_response(response_body, tid),
                    mimetype="text/event-stream",
                ),
                200,
            )

        else:
            # Handle non-streaming response
            response = invoke_bedrock_non_streaming(bedrock_client, body_json)
            # Extract status code from response metadata - default to None to detect malformed responses
            response_status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            response_body = response.get("body")

            # Check for malformed response (missing status code)
            if response_status is None:
                logger.error("Missing HTTPStatusCode in response metadata")
                return jsonify(
                    {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": "Malformed response from backend API",
                        },
                    }
                ), 500

            if response_body is not None:
                # Read the response body
                chunk_data = read_response_body_stream(response_body)

                if chunk_data:
                    final_response = json.loads(chunk_data)
                    logger.debug(f"Non-streaming response: {final_response}")

                    # Log response from Bedrock
                    transport_logger.info(
                        f"OUT_RSP: tid={tid}, STATUS={response_status}"
                    )
                    transport_logger.info(
                        f"OUT_RSP: tid={tid}, BODY={json.dumps(final_response)}"
                    )

                    # Log response being sent to client
                    transport_logger.info(f"RSP: tid={tid}, STATUS={response_status}")
                    transport_logger.info(
                        f"RSP: tid={tid}, BODY={json.dumps(final_response)}"
                    )

                    # Use actual response status code
                    return jsonify(final_response), response_status
                else:
                    logger.warning("Empty chunk_data from non-streaming response body")
                    error_status = response_status if response_status >= 400 else 500
                    return jsonify(
                        {
                            "type": "error",
                            "error": {
                                "type": "api_error",
                                "message": "Empty response data from backend API",
                            },
                        }
                    ), error_status
            else:
                logger.error("Response body is None from SDK invoke_model")
                error_status = response_status if response_status >= 400 else 500
                return jsonify(
                    {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": "Empty response body from backend API",
                        },
                    }
                ), error_status

    except Exception as e:
        # Check if this is a rate limit error from retry exhaustion
        if isinstance(e, RetryError) and hasattr(e, "__cause__"):
            cause = e.__cause__
            # Use the same retry_on_rate_limit function to classify the error
            if retry_on_rate_limit(cause):
                logger.warning(f"Rate limit exceeded for Anthropic proxy request: {e}")
                error_dict = {
                    "type": "error",
                    "error": {
                        "type": "rate_limit_error",
                        "message": "Rate limit exceeded. Please try again later.",
                    },
                }
                return jsonify(error_dict), 429

        logger.error(
            f"Error handling Anthropic proxy request using SDK: {e}", exc_info=True
        )
        error_dict = {
            "type": "error",
            "error": {"type": "api_error", "message": str(e)},
        }
        return jsonify(error_dict), 500


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
    args = parse_arguments()

    # Setup logging using the new modular function
    init_logging(debug=args.debug)

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
