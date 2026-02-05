"""Blueprint for /v1/messages endpoint (Anthropic Claude Messages API)."""

import json
import uuid
from typing import TYPE_CHECKING

from flask import Blueprint, Response, jsonify, request, stream_with_context
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper
from tenacity import RetryError

from auth import RequestValidator
from blueprints.helpers import (
    validate_api_key,
    create_invalid_request_error,
    create_api_error,
    create_rate_limit_error,
    create_error_response,
)
from handlers.bedrock_handler import (
    invoke_bedrock_streaming,
    invoke_bedrock_non_streaming,
    read_response_body_stream,
)
from utils.retry import unified_retry as bedrock_retry, retry_on_rate_limit
from handlers.streaming_generators import (
    generate_bedrock_streaming_response,
    generate_claude_streaming_response,
)
from handlers.streaming_handler import make_backend_request
from proxy_helpers import Detector, Converters
from utils.logging_utils import get_server_logger, get_transport_logger
from utils.sdk_pool import get_bedrock_client, invalidate_bedrock_client
from utils.sdk_utils import extract_deployment_id

if TYPE_CHECKING:
    from config import ProxyConfig, ProxyGlobalContext, ServiceKey

logger = get_server_logger(__name__)
transport_logger = get_transport_logger(__name__)

messages_bp = Blueprint("messages", __name__)

# These will be set by register_blueprints() in proxy_server.py
_proxy_config: "ProxyConfig" = None  # type: ignore
_ctx: "ProxyGlobalContext" = None  # type: ignore

DEFAULT_CLAUDE_MODEL: str = "anthropic--claude-4.5-sonnet"
API_VERSION_BEDROCK_2023_05_31 = "bedrock-2023-05-31"
API_VERSION_2024_12_01_PREVIEW = "2024-12-01-preview"
API_VERSION_2023_05_15 = "2023-05-15"


def init_messages_blueprint(
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


@messages_bp.route("/v1/messages", methods=["POST"])
def proxy_claude_request():
    """Handles requests that are compatible with the Anthropic Claude Messages API using SAP AI SDK."""
    tid: str = str(uuid.uuid4())

    # Log raw request received from client
    request_body_str: str = request.get_data(as_text=True)
    logger.info(f"REQ: tid={tid}, body={request_body_str}")
    transport_logger.info(f"REQ: tid={tid}, url={request.url}, body={request_body_str}")

    # Validate API key using proxy config authentication
    is_valid, error_response = validate_api_key(
        _proxy_config.secret_authentication_tokens
    )
    if not is_valid:
        return error_response

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
        return create_invalid_request_error("Missing 'model' parameter")

    # Validate model availability
    try:
        selected_url, subaccount_name, resource_group, model = load_balance_url(
            request_model, _proxy_config
        )
    except ValueError as e:
        logger.error(f"Model validation failed: {e}", exc_info=True)
        return create_error_response(
            "not_found_error", f"Model '{request_model}' not available", 404
        )

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
            sub_account_config=_proxy_config.subaccounts[subaccount_name],
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
        logger.info("Request body for Bedrock (pretty):\\n%s", pretty_body_json)

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

                # Check for authentication errors and retry with fresh client
                if response_status in [401, 403]:
                    logger.warning(
                        f"Authentication error ({response_status}) from SDK for model '{model}', "
                        f"invalidating client and retrying..."
                    )
                    invalidate_bedrock_client(model)
                    # Get a fresh client (will force re-authentication)
                    bedrock_client = get_bedrock_client(
                        sub_account_config=_proxy_config.subaccounts[subaccount_name],
                        model_name=model,
                        deployment_id=extract_deployment_id(selected_url),
                    )
                    # Retry the request
                    response = invoke_bedrock_streaming(bedrock_client, body_json)
                    response_status = response.get("ResponseMetadata", {}).get(
                        "HTTPStatusCode"
                    )
                    response_body = response.get("body")

                # Check for malformed response first (missing status code)
                if response_status is None:
                    logger.error("Missing HTTPStatusCode in response metadata")
                    return create_api_error("Malformed response from backend API")

                # If status is not 200, return error before starting stream
                if response_status != 200:
                    logger.error(f"Non-200 status code from SDK: {response_status}")
                    return create_api_error(
                        f"Backend API returned status {response_status}",
                        response_status,
                    )

                # If we detect an error before streaming starts, return error response
                if response_body is None:
                    logger.error(
                        "Response body is None from SDK invoke_model_with_response_stream"
                    )
                    # At this point, response_status is 200, so we return 500 for error
                    return create_api_error("Empty response body from backend API")

            except Exception as e:
                # If error occurs before streaming, we can return proper error status
                logger.error(f"Error before streaming: {e}", exc_info=True)
                return create_api_error(str(e))

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

            # Check for authentication errors and retry with fresh client
            if response_status in [401, 403]:
                logger.warning(
                    f"Authentication error ({response_status}) from SDK for model '{model}', "
                    f"invalidating client and retrying..."
                )
                invalidate_bedrock_client(model)
                # Get a fresh client (will force re-authentication)
                bedrock_client = get_bedrock_client(
                    sub_account_config=_proxy_config.subaccounts[subaccount_name],
                    model_name=model,
                    deployment_id=extract_deployment_id(selected_url),
                )
                # Retry the request
                response = invoke_bedrock_non_streaming(bedrock_client, body_json)
                response_status = response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                response_body = response.get("body")

            # Check for malformed response (missing status code)
            if response_status is None:
                logger.error("Missing HTTPStatusCode in response metadata")
                return create_api_error("Malformed response from backend API")

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
                    return create_api_error(
                        "Empty response data from backend API", error_status
                    )
            else:
                logger.error("Response body is None from SDK invoke_model")
                error_status = response_status if response_status >= 400 else 500
                return create_api_error(
                    "Empty response body from backend API", error_status
                )

    except Exception as e:
        # Check if this is a rate limit error from retry exhaustion
        if isinstance(e, RetryError) and hasattr(e, "__cause__"):
            cause = e.__cause__
            # Use the same retry_on_rate_limit function to classify the error
            if retry_on_rate_limit(cause):
                logger.warning(f"Rate limit exceeded for Anthropic proxy request: {e}")
                return create_rate_limit_error()

        logger.error(
            f"Error handling Anthropic proxy request using SDK: {e}", exc_info=True
        )
        return create_api_error(str(e))


def proxy_claude_request_original():
    """Original implementation preserved as fallback."""
    import requests

    logger.info("Using original Claude request implementation")

    is_valid, error_response = validate_api_key(
        _proxy_config.secret_authentication_tokens
    )
    if not is_valid:
        return error_response

    payload = request.json
    model = payload.get("model")
    if not model:
        return create_invalid_request_error("Missing 'model' parameter")

    is_stream = payload.get("stream", False)
    logger.info(f"Claude API request for model: {model}, Streaming: {is_stream}")

    try:
        base_url, subaccount_name, resource_group, model = load_balance_url(
            model, _proxy_config
        )
        token_manager = _ctx.get_token_manager(subaccount_name)
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

        service_key: "ServiceKey | None" = _proxy_config.subaccounts[
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

            # Check for authentication errors and retry with fresh token
            if not result.success and result.status_code in [401, 403]:
                logger.warning(
                    f"Authentication error ({result.status_code}) for subaccount '{subaccount_name}', "
                    f"invalidating token and retrying..."
                )
                token_manager.invalidate_token()
                # Fetch new token and update headers
                subaccount_token = token_manager.get_token()
                headers["Authorization"] = f"Bearer {subaccount_token}"
                # Retry the request
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
        return create_invalid_request_error(str(err))
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
        return create_api_error("An unexpected error occurred.")
