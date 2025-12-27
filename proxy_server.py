import argparse
import ast
import json
import random
import subprocess
import sys
import time
import uuid
from logging import Logger

import requests
from botocore.exceptions import ClientError
from flask import Flask, Response, jsonify, request, stream_with_context
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper
# SAP AI SDK imports
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from auth import RequestValidator, TokenManager
# Import from new modular structure
from config import ProxyConfig, load_proxy_config
from proxy_helpers import Converters, Detector
from utils.error_handlers import handle_http_429_error
from utils.logging_utils import get_server_logger, get_transport_logger, init_logging
from utils.sdk_utils import extract_deployment_id

# Initialize token logger (will be configured on first use)
logger: Logger = get_server_logger(__name__)
transport_logger: Logger = get_transport_logger(__name__)
token_usage_logger: Logger = get_server_logger("token_usage")

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


# Retry decorator for SAP AI SDK calls that may hit rate limits
def retry_on_rate_limit(exception):
    """Check if exception is a rate limit error that should be retried."""
    # Check for ClientError with 429 status code first (more reliable)
    if isinstance(exception, ClientError):
        error_code = exception.response.get("Error", {}).get("Code", "")
        http_status = exception.response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode"
        )
        if error_code == "429" or http_status == 429:
            return True

    # Fallback to string matching for other exception types
    error_message = str(exception).lower()
    return (
        "too many tokens" in error_message
        or "rate limit" in error_message
        or "throttling" in error_message
        or "too many requests" in error_message
        or "exceeding the allowed request" in error_message
        or "rate limited by ai core" in error_message
    )


bedrock_retry = retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(
        multiplier=RETRY_MULTIPLIER, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT
    ),
    retry=retry_on_rate_limit,
    before_sleep=lambda retry_state: logger.warning(
        f"Rate limit hit, retrying in {retry_state.next_action.sleep if retry_state.next_action else 'unknown'} seconds "
        f"(attempt {retry_state.attempt_number}/{RETRY_MAX_ATTEMPTS}): {str(retry_state.outcome.exception()) if retry_state.outcome else 'unknown error'}"
    ),
)


# Helper functions for SDK invocation with retry logic
@bedrock_retry
def invoke_bedrock_streaming(bedrock_client, body_json: str):
    """
    Invoke Bedrock streaming API with retry logic for rate limits.

    Note: This only retries the initial connection/request. Once streaming starts,
    errors during stream consumption cannot be retried as the stream is already open.
    """
    return bedrock_client.invoke_model_with_response_stream(body=body_json)


@bedrock_retry
def invoke_bedrock_non_streaming(bedrock_client, body_json: str):
    """Invoke Bedrock non-streaming API with retry logic for rate limits."""
    return bedrock_client.invoke_model(body=body_json)


# Helper functions for response validation


def read_response_body_stream(response_body) -> str:
    """
    Read response body stream and return as string.

    Args:
        response_body: The streaming response body from AWS SDK

    Returns:
        String containing the full response data
    """
    chunk_data = ""
    for event in response_body:
        if isinstance(event, bytes):
            chunk_data += event.decode("utf-8")
        else:
            chunk_data += str(event)
    return chunk_data


# Global configuration
proxy_config: ProxyConfig = ProxyConfig()

app = Flask(__name__)


@app.route("/v1/embeddings", methods=["POST"])
def handle_embedding_request():
    logger.info("Received request to /v1/embeddings")
    tid = str(uuid.uuid4())

    # Log raw request received from client
    transport_logger.info(
        f"EMBED_REQ[{tid}] url={request.url}, body={request.get_data(as_text=True)}"
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
        endpoint_url, modified_payload, subaccount_name = handle_embedding_service_call(
            input_text, model, encoding_format
        )
        # Create a global token manager for sub accounts
        token_manager = TokenManager(proxy_config.subaccounts[subaccount_name])
        subaccount_token = token_manager.get_token()
        subaccount = proxy_config.subaccounts[subaccount_name]
        resource_group = subaccount.resource_group
        service_key = subaccount.service_key
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Resource-Group": resource_group,
            "AI-Tenant-Id": service_key.identity_zone_id,
        }

        # Log request being sent to LLM service - no formatting
        transport_logger.info(
            f"EMBED_REQ_LLM[{tid}] url={endpoint_url}, body={modified_payload}"
        )

        response = requests.post(endpoint_url, headers=headers, json=modified_payload)

        # Log raw response from LLM service - no formatting
        transport_logger.info(
            f"EMBED_RSP_LLM: tid={tid}, status={response.status_code}, headers={dict(response.headers)}, body={response.text}"
        )

        response.raise_for_status()
        return response.json(), 200
        # return jsonify(format_embedding_response(response.json(), model)), 200
    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error in embedding request({model}): {http_err}", exc_info=True
        )

        if http_err.response is not None:
            response = http_err.response
            status_code = response.status_code

            # Handle HTTP 429 (Too Many Requests) specifically
            if status_code == 429:
                return handle_http_429_error(http_err, f"embedding request for {model}")

            logger.error(
                f"EMBED_ERR: tid={tid}, status={status_code}, headers={dict(response.headers)}, body={response.text}",
                exc_info=True,
            )
            transport_logger.error(
                f"EMBED_ERR: tid={tid}, status={status_code}, headers={dict(response.headers)}, body={response.text}"
            )

            try:
                error_json = http_err.response.json()
                logger.error(
                    f"EMBED_ERR: tid={tid}, response={json.dumps(error_json, indent=2)}",
                    exc_info=True,
                )
                return jsonify(error_json), status_code
            except json.JSONDecodeError:
                logger.error(
                    f"EMBED_ERR: tid={tid}, response={response.text}", exc_info=True
                )
                return jsonify({"error": response.text}), status_code
        else:
            logger.error(
                f"EMBED_ERR: tid={tid}, reason=no_response, error={str(http_err)}",
                exc_info=True,
            )
            return jsonify({"error": str(http_err)}), 500
    except Exception as e:
        logger.error(
            f"EMBED_ERR: tid={tid}, reason=no_response, error={str(e)}", exc_info=True
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


def get_version_info():
    """Get version and git hash information.

    This function works in multiple scenarios:
    1. PyInstaller build: Reads from _version.txt bundled in the executable
    2. Development mode: Reads from pyproject.toml and git

    Returns:
        tuple: (version: str, git_hash: str)
    """
    # First, try to read from _version.txt (for PyInstaller builds)
    try:
        import os

        # Check if we're running in PyInstaller bundle
        if getattr(sys, "frozen", False):
            # Running in PyInstaller bundle
            bundle_dir = sys._MEIPASS
            version_file = os.path.join(bundle_dir, "_version.txt")
        else:
            # Running in normal Python
            version_file = "_version.txt"

        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                lines = f.read().strip().split("\n")
                version = lines[0] if len(lines) > 0 else "unknown"
                git_hash = lines[1] if len(lines) > 1 else "unknown"
                return version, git_hash
    except Exception:
        pass

    # Fallback: Read from pyproject.toml and git (development mode)
    version = "unknown"
    git_hash = "unknown"

    # Try to get version from pyproject.toml
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None

    if tomllib:
        try:
            with open("pyproject.toml", "rb") as f:
                data = tomllib.load(f)
                version = data.get("project", {}).get("version", "unknown")
        except Exception:
            pass

    # Try to get git hash
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        git_hash = result.stdout.strip()
    except Exception:
        pass

    return version, git_hash


def get_version():
    """Get version string.

    Returns:
        str: Version string or 'unknown' if not found
    """
    version, _ = get_version_info()
    return version


def get_git_hash():
    """Get current git commit hash (short version).

    Returns:
        str: Short git commit hash or 'unknown' if not available
    """
    _, git_hash = get_version_info()
    return git_hash


def get_version_string():
    """Get full version string with git hash.

    Returns:
        str: Version string in format 'version (git: hash)'
    """
    version, git_hash = get_version_info()
    return f"{version} (git: {git_hash})"


def parse_arguments():
    version_string = get_version_string()
    parser = argparse.ArgumentParser(
        description=f"Proxy server for AI models - {version_string}",
        epilog=f"Version: {version_string}",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version_string}",
        help="Show version information and exit",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to the configuration file",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


def get_claude_stop_reason_from_gemini_chunk(gemini_chunk):
    """Extracts and maps the stop reason from a final Gemini chunk."""
    finish_reason = gemini_chunk.get("candidates", [{}])[0].get("finishReason")
    if finish_reason:
        stop_reason_map = {
            "STOP": "end_turn",
            "MAX_TOKENS": "max_tokens",
            "SAFETY": "stop_sequence",
            "RECITATION": "stop_sequence",
            "OTHER": "stop_sequence",
        }
        return stop_reason_map.get(finish_reason, "stop_sequence")
    return None


def get_claude_stop_reason_from_openai_chunk(openai_chunk):
    """Extracts and maps the stop reason from a final OpenAI chunk."""
    finish_reason = openai_chunk.get("choices", [{}])[0].get("finish_reason")
    if finish_reason:
        stop_reason_map = {
            "stop": "end_turn",
            "length": "max_tokens",
            "content_filter": "stop_sequence",
            "tool_calls": "tool_use",
        }
        return stop_reason_map.get(finish_reason, "stop_sequence")
    return None


def load_balance_url(selected_model_name: str) -> tuple[str, str, str, str]:
    """
    Load balance requests for a model across all subAccounts that have it deployed.

    Args:
        selected_model_name: Name of the model to load balance

    Returns:
        Tuple of (selected_url, subaccount_name, resource_group, final_model_name)

    Raises:
        ValueError: If no subAccounts have the requested model
    """
    # Initialize counters dictionary if it doesn't exist
    if not hasattr(load_balance_url, "counters"):
        load_balance_url.counters = {}

    # Get list of subAccounts that have this model
    if (
        selected_model_name not in proxy_config.model_to_subaccounts
        or not proxy_config.model_to_subaccounts[selected_model_name]
    ):
        # Check if it's a Claude or Gemini model and try fallback
        if Detector.is_claude_model(selected_model_name):
            logger.info(
                f"Claude model '{selected_model_name}' not found, trying fallback models"
            )
            # Try common Claude model fallbacks
            fallback_models = ["anthropic--claude-4.5-sonnet"]
            for fallback in fallback_models:
                if (
                    fallback in proxy_config.model_to_subaccounts
                    and proxy_config.model_to_subaccounts[fallback]
                ):
                    logger.info(
                        f"Using fallback Claude model '{fallback}' for '{selected_model_name}'"
                    )
                    selected_model_name = fallback
                    break
            else:
                logger.error("No Claude models available in any subAccount")
                raise ValueError(
                    f"Claude model '{selected_model_name}' and fallbacks not available in any subAccount"
                )
        elif Detector.is_gemini_model(selected_model_name):
            logger.info(
                f"Gemini model '{selected_model_name}' not found, trying fallback models"
            )
            # Try common Gemini model fallbacks
            fallback_models = ["gemini-2.5-pro"]
            for fallback in fallback_models:
                if (
                    fallback in proxy_config.model_to_subaccounts
                    and proxy_config.model_to_subaccounts[fallback]
                ):
                    logger.info(
                        f"Using fallback Gemini model '{fallback}' for '{selected_model_name}'"
                    )
                    selected_model_name = fallback
                    break
            else:
                logger.error("No Gemini models available in any subAccount")
                raise ValueError(
                    f"Gemini model '{selected_model_name}' and fallbacks not available in any subAccount"
                )
        else:
            # For other models, try common fallbacks
            logger.warning(
                f"Model '{selected_model_name}' not found, trying fallback models"
            )
            fallback_models = [DEFAULT_GPT_MODEL]
            for fallback in fallback_models:
                if (
                    fallback in proxy_config.model_to_subaccounts
                    and proxy_config.model_to_subaccounts[fallback]
                ):
                    logger.info(
                        f"Using fallback model '{fallback}' for '{selected_model_name}'"
                    )
                    selected_model_name = fallback
                    break
            else:
                logger.error(
                    f"No subAccounts with model '{selected_model_name}' or fallbacks found"
                )
                raise ValueError(
                    f"Model '{selected_model_name}' and fallbacks not available in any subAccount"
                )

    subaccount_names = proxy_config.model_to_subaccounts[selected_model_name]

    # Create counter for this model if it doesn't exist
    if selected_model_name not in load_balance_url.counters:
        load_balance_url.counters[selected_model_name] = 0

    # Select subAccount using round-robin
    subaccount_index = load_balance_url.counters[selected_model_name] % len(
        subaccount_names
    )
    selected_subaccount: str = subaccount_names[subaccount_index]

    # Increment counter for next request
    load_balance_url.counters[selected_model_name] += 1

    # Get the model URL list from the selected subAccount
    subaccount = proxy_config.subaccounts[selected_subaccount]
    url_list = subaccount.model_to_deployment_urls.get(selected_model_name, [])

    if not url_list:
        logger.error(
            f"Model '{selected_model_name}' listed for subAccount '{selected_subaccount}' but no URLs found"
        )
        raise ValueError(
            f"Configuration error: No URLs for model '{selected_model_name}' in subAccount '{selected_subaccount}'"
        )

    # Select URL using round-robin within the subAccount
    url_counter_key = f"{selected_subaccount}:{selected_model_name}"
    if url_counter_key not in load_balance_url.counters:
        load_balance_url.counters[url_counter_key] = 0

    url_index = load_balance_url.counters[url_counter_key] % len(url_list)
    selected_url: str = url_list[url_index]

    # Increment URL counter for next request
    load_balance_url.counters[url_counter_key] += 1

    # Get resource group for the selected subAccount
    selected_resource_group: str = subaccount.resource_group

    logger.info(
        f"Selected subAccount '{selected_subaccount}' and URL '{selected_url}' for model '{selected_model_name}'"
    )
    return (
        selected_url,
        selected_subaccount,
        selected_resource_group,
        selected_model_name,
    )


def handle_claude_request(payload, model="3.5-sonnet"):
    """Handle Claude model request with multi-subAccount support.

    Args:
        payload: Request payload from client
        model: The model name to use

    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)
    """
    stream = payload.get("stream", True)
    logger.info(f"handle_claude_request: model={model} stream={stream}")

    # Get the selected URL, subaccount and resource group using our load balancer
    try:
        selected_url, subaccount_name, _, model = load_balance_url(model)
    except ValueError as e:
        logger.error(
            f"Failed to load balance URL for model '{model}': {e}", exc_info=True
        )
        raise ValueError(f"No valid Claude model found for '{model}' in any subAccount")

    # Determine the endpoint path based on model and streaming settings
    if stream:
        # Check if the model is Claude 3.7 or 4 for streaming endpoint
        if Detector.is_claude_37_or_4(model):
            endpoint_path = "/converse-stream"
        else:
            endpoint_path = "/invoke-with-response-stream"
    else:
        # Check if the model is Claude 3.7 or 4
        if Detector.is_claude_37_or_4(model):
            endpoint_path = "/converse"
        else:
            endpoint_path = "/invoke"

    endpoint_url = f"{selected_url.rstrip('/')}{endpoint_path}"

    # Convert the payload to the right format
    if Detector.is_claude_37_or_4(model):
        modified_payload = Converters.convert_openai_to_claude37(payload)
    else:
        modified_payload = Converters.convert_openai_to_claude(payload)

    logger.info(
        f"handle_claude_request: {endpoint_url} (subAccount: {subaccount_name})"
    )
    return endpoint_url, modified_payload, subaccount_name


def handle_gemini_request(payload, model="gemini-2.5-pro"):
    """Handle Gemini model request with multi-subAccount support.

    Args:
        payload: Request payload from client
        model: The model name to use

    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)
    """
    stream = payload.get("stream", True)  # Default to True if 'stream' is not provided
    logger.info(f"handle_gemini_request: model={model} stream={stream}")

    # Get the selected URL, subaccount and resource group using our load balancer
    try:
        selected_url, subaccount_name, _, model = load_balance_url(model)
    except ValueError as e:
        logger.error(
            f"Failed to load balance URL for model '{model}': {e}", exc_info=True
        )
        raise ValueError(f"No valid Gemini model found for '{model}' in any subAccount")

    # Extract the model name for the endpoint (e.g., "gemini-2.5-pro" from the model)
    # The endpoint format is: /models/{model}:generateContent
    model_endpoint_name = model
    if ":" in model:
        model_endpoint_name = model.split(":")[0]

    # Determine the endpoint path based on streaming settings
    if stream:
        endpoint_path = f"/models/{model_endpoint_name}:streamGenerateContent"
    else:
        endpoint_path = f"/models/{model_endpoint_name}:generateContent"

    endpoint_url = f"{selected_url.rstrip('/')}{endpoint_path}"

    # Convert the payload to Gemini format
    modified_payload = Converters.convert_openai_to_gemini(payload)

    logger.info(
        f"handle_gemini_request: {endpoint_url} (subAccount: {subaccount_name})"
    )
    return endpoint_url, modified_payload, subaccount_name


def handle_default_request(payload, model=DEFAULT_GPT_MODEL):
    """Handle default (non-Claude, non-Gemini) model request with multi-subAccount support.

    Args:
        payload: Request payload from client
        model: The model name to use

    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)
    """
    # Get the selected URL, subaccount and resource group using our load balancer
    selected_url, subaccount_name, _, model = load_balance_url(model)

    # Determine API version based on model
    if any(m in model for m in ["o3", "o4-mini", "o3-mini", "gpt-5"]):
        api_version = API_VERSION_2024_12_01_PREVIEW
        # Remove unsupported parameters for o3-mini
        modified_payload = payload.copy()
        if "temperature" in modified_payload:
            logger.info("Removing 'temperature' parameter for o3-mini model.")
            del modified_payload["temperature"]
        # Add checks for other potentially unsupported parameters if needed
    else:
        api_version = API_VERSION_2023_05_15
        modified_payload = payload

    endpoint_url = (
        f"{selected_url.rstrip('/')}/chat/completions?api-version={api_version}"
    )

    logger.info(
        f"handle_default_request: {endpoint_url} (subAccount: {subaccount_name})"
    )
    return endpoint_url, modified_payload, subaccount_name


@app.route("/v1/models", methods=["GET", "OPTIONS"])
def list_models():
    """Lists all available models across all subAccounts."""
    logger.info("Received request to /v1/models")
    logger.info(f"Request headers: {request.headers}")
    # logger.info(f"Request payload: {request.get_json()}")

    # if not verify_request_token(request):
    #     logger.info("Unauthorized request to list models.")
    #     return jsonify({"error": "Unauthorized"}), 401

    # Collect all available models from all subAccounts
    models = []
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
        f"CHAT_REQ: tid={tid}, url={request.url}, body={request.get_data(as_text=True)}"
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

    # Check if model is available in any subAccount
    if effective_model not in proxy_config.model_to_subaccounts:
        error_message: str = f"Model {effective_model} is not supported."
        if effective_model != original_model:
            error_message = f"Models '{original_model}' and '{effective_model}'(fallback) are NOT defined in any subAccount"

        return jsonify({"error": error_message}), 404

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
        # TODO: Put TokenManager to module level instead of creating a new one for each request
        subaccount = proxy_config.subaccounts[subaccount_name]
        subaccount_token = TokenManager(subaccount).get_token()

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
    logger.info("Received request to /v1/messages")
    tid = str(uuid.uuid4())

    # Log raw request received from client
    transport_logger.info(f"MSG_CLIENT_REQ[{tid}] URL={request.url}")
    transport_logger.info(
        f"MSG_CLIENT_REQ[{tid}] BODY={request.get_data(as_text=True)}"
    )

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
    request_json = request.get_json(cache=False)

    # Handle missing model by hardcoding to anthropic--claude-4.5-sonnet
    request_model = request_json.get("model")
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
    stream = request_json.get("stream", True)

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
        conversation = request_json.get("messages", [])
        logger.debug(f"Original conversation: {conversation}")

        thinking_cfg_preview = request_json.get("thinking")
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
        body = request_json.copy()

        # Log the original request body for debugging
        logger.info("Original request body keys: %s", list(body.keys()))

        # Remove model and stream from body as they're handled separately
        body.pop("model", None)
        body.pop("stream", None)

        # Add required anthropic_version for Bedrock
        body["anthropic_version"] = API_VERSION_BEDROCK_2023_05_31

        # Remove unsupported fields for Bedrock
        unsupported_fields = ["context_management", "metadata"]
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
        transport_logger.info(f"MSG_BEDROCK_REQ[{tid}] MODEL={model}")
        transport_logger.info(f"MSG_BEDROCK_REQ[{tid}] BODY={pretty_body_json}")

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
            def stream_generate():
                try:
                    for event in response_body:
                        chunk = json.loads(event["chunk"]["bytes"])
                        logger.debug(f"Streaming chunk: {chunk}")

                        # Log raw chunk from Bedrock
                        transport_logger.info(
                            f"MSG_BEDROCK_RSP_CHUNK[{tid}] {json.dumps(chunk)[:200]}"
                        )

                        chunk_type = chunk.get("type")

                        # Handle different chunk types according to Claude streaming format
                        if chunk_type == "message_start":
                            response_line = f"event: message_start\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            transport_logger.info(
                                f"MSG_CLIENT_RSP_CHUNK[{tid}] {response_line[:200]}"
                            )
                            yield response_line
                        elif chunk_type == "content_block_start":
                            response_line = f"event: content_block_start\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            transport_logger.info(
                                f"MSG_CLIENT_RSP_CHUNK[{tid}] {response_line[:200]}"
                            )
                            yield response_line
                        elif chunk_type == "content_block_delta":
                            response_line = f"event: content_block_delta\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            transport_logger.info(
                                f"MSG_CLIENT_RSP_CHUNK[{tid}] {response_line[:200]}"
                            )
                            yield response_line
                        elif chunk_type == "content_block_stop":
                            response_line = f"event: content_block_stop\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            transport_logger.info(
                                f"MSG_CLIENT_RSP_CHUNK[{tid}] {response_line[:200]}"
                            )
                            yield response_line
                        elif chunk_type == "message_delta":
                            response_line = f"event: message_delta\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            transport_logger.info(
                                f"MSG_CLIENT_RSP_CHUNK[{tid}] {response_line[:200]}"
                            )
                            yield response_line
                        elif chunk_type == "message_stop":
                            response_line = f"event: message_stop\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            transport_logger.info(
                                f"MSG_CLIENT_RSP_CHUNK[{tid}] {response_line[:200]}"
                            )
                            yield response_line
                            transport_logger.info(
                                f"MSG_STREAM_COMPLETE[{tid}] Stream finished successfully"
                            )
                            yield "data: [DONE]\n\n"
                            break
                        elif chunk_type == "error":
                            # Handle error chunks in the stream
                            response_line = f"event: error\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            transport_logger.info(
                                f"MSG_CLIENT_RSP_ERROR[{tid}] {response_line[:200]}"
                            )
                            yield response_line
                            break

                except Exception as e:
                    # Errors during streaming can only be sent as SSE events
                    logger.error(f"Error during streaming: {e}", exc_info=True)
                    error_chunk = {
                        "type": "error",
                        "error": {"type": "api_error", "message": str(e)},
                    }
                    yield f"event: error\ndata: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"

            return Response(stream_generate(), mimetype="text/event-stream"), 200

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
                        f"MSG_BEDROCK_RSP[{tid}] STATUS={response_status}"
                    )
                    transport_logger.info(
                        f"MSG_BEDROCK_RSP[{tid}] BODY={json.dumps(final_response)}"
                    )

                    # Log response being sent to client
                    transport_logger.info(
                        f"MSG_CLIENT_RSP[{tid}] STATUS={response_status}"
                    )
                    transport_logger.info(
                        f"MSG_CLIENT_RSP[{tid}] BODY={json.dumps(final_response)}"
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
        token_manager = TokenManager(proxy_config.subaccounts[subaccount_name])
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

        service_key = proxy_config.subaccounts[subaccount_name].service_key
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
            backend_response = requests.post(
                endpoint_url, headers=headers, json=backend_payload, timeout=600
            )
            backend_response.raise_for_status()
            backend_json = backend_response.json()

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

            return jsonify(final_response), backend_response.status_code
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


def parse_sse_response_to_claude_json(response_text):
    """
    Parse SSE response text and reconstruct Claude JSON response.

    Args:
        response_text: The SSE response text

    Returns:
        dict: Claude JSON response format
    """
    import ast

    content = ""
    usage = {}
    stop_reason = "end_turn"

    lines = response_text.strip().split("\n")
    for line in lines:
        if line.startswith("data: "):
            data_str = line[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                # Handle both JSON and Python dict literal formats
                if data_str.startswith("{"):
                    data = json.loads(data_str)
                else:
                    data = ast.literal_eval(data_str)

                if "contentBlockDelta" in data:
                    delta_text = data["contentBlockDelta"]["delta"].get("text", "")
                    content += delta_text
                elif "metadata" in data:
                    usage = data["metadata"].get("usage", {})
                elif "messageStop" in data:
                    stop_reason = data["messageStop"].get("stopReason", "end_turn")

            except (json.JSONDecodeError, ValueError, SyntaxError) as e:
                logger.warning(f"Failed to parse SSE data line: {data_str}, error: {e}")
                continue

    # Build Claude response format
    response_data = {
        "id": f"msg_{random.randint(10000, 99999)}",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": "claude-3-5-sonnet-20241022",  # Default, will be overridden
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
        },
    }

    return response_data


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
    try:
        # Log request being sent to LLM service
        transport_logger.info(
            f"CHAT_REQ_LLM: tid={tid}, url={url}, body={json.dumps(payload)}"
        )

        # Make request to backend API
        response = requests.post(url, headers=headers, json=payload, timeout=600)

        # Log raw response from LLM service
        transport_logger.info(
            f"CHAT_RSP_LLM: tid={tid}, status={response.status_code}, headers={dict(response.headers)}, body={response.text}"
        )

        response.raise_for_status()
        logger.info(f"CHAT: OK, tid={tid}, model={model}")

        # Validate response has content before parsing
        if not response.content:
            logger.error(f"CHAT: EMPTY_RESPONSE, tid={tid}, model={model}")

            return jsonify({"error": "Empty response from backend API"}), 500

        # Process response based on model type
        try:
            # For Claude models, check if response is SSE format (backend may send SSE even for non-streaming)
            if Detector.is_claude_model(model) and response.text.strip().startswith(
                "data: "
            ):
                logger.info(
                    "Claude model response is in SSE format, parsing as streaming response for non-streaming request"
                )
                response_data = parse_sse_response_to_claude_json(response.text)
            else:
                response_data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(
                f"CHAT: JSON_PARSE_ERR, tid={tid}, response={response.text}, headers={dict(response.headers)}, err={str(e)}",
                exc_info=True,
            )
            return jsonify(
                {
                    "error": "Invalid JSON response from backend API",
                    "details": str(e),
                    "response_text": response.text,
                }
            ), 500

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
            f"CHAT_RSP: tid={tid}, status=200, body={json.dumps(final_response)}"
        )

        return jsonify(final_response), 200

    except requests.exceptions.HTTPError as http_err:
        if http_err.response is not None:
            response = http_err.response
            status_code = response.status_code

            # Handle HTTP 429 (Too Many Requests) specifically
            if status_code == 429:
                return handle_http_429_error(
                    http_err, f"non-streaming request for {model}"
                )

            logger.error(
                f"CHAT: HTTP_ERR, tid={tid}, status={status_code}, headers={dict(response.headers)}, response={response.text}",
                exc_info=True,
            )
            try:
                error_data = http_err.response.json()
                return jsonify(error_data), http_err.response.status_code
            except json.JSONDecodeError:
                return jsonify({"error": http_err.response.text}), status_code
        else:
            logger.error(
                f"CHAT: HTTP_ERR, tid={tid}, err={str(http_err)}", exc_info=True
            )
            return jsonify({"error": str(http_err)}), 500

    except Exception as err:
        logger.error(f"CHAT: UNKNOWN_ERR, tid={tid}, err={str(err)}", exc_info=True)
        return jsonify({"error": str(err)}), 500


def generate_streaming_response(
    url, headers, payload, model: str, subaccount_name: str, tid: str
):
    """Generate streaming response from backend API.

    Args:
        url: Backend API endpoint URL
        headers: Request headers
        payload: Request payload
        model: Model name
        subaccount_name: Name of the selected subAccount
        tid: Trace UUID for logging correlation

    Yields:
        SSE formatted response chunks
    """
    # Log the raw request body and payload being forwarded
    logger.info(f"CHAT_REQ_ST_LLM: tid={tid}, url={url}], body={json.dumps(payload)}")
    # Log request being sent to LLM service
    transport_logger.info(
        f"CHAT_REQ_ST_LLM: tid={tid}, url={url}], body={json.dumps(payload)}"
    )

    buffer = ""
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    claude_metadata = {}  # For Claude 3.7 metadata
    chunk = None  # Initialize chunk variable to avoid reference errors

    # Make streaming request to backend
    with requests.post(
        url, headers=headers, json=payload, stream=True, timeout=600
    ) as response:
        try:
            response.raise_for_status()

            # --- Claude 3.7/4 Streaming Logic ---
            if Detector.is_claude_model(model) and Detector.is_claude_37_or_4(model):
                logger.info(
                    f"Using Claude 3.7/4 streaming for subAccount '{subaccount_name}'"
                )
                for line_bytes in response.iter_lines():
                    if line_bytes:
                        line = line_bytes.decode("utf-8")
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            # logger.info(f"Raw data chunk from Claude API: {line_content}")
                            try:
                                line_content = ast.literal_eval(line_content)
                                line_content = json.dumps(line_content)
                                claude_dict_chunk = json.loads(line_content)

                                # Check if this is a metadata chunk by looking for 'metadata' key directly
                                if "metadata" in claude_dict_chunk:
                                    claude_metadata = claude_dict_chunk.get(
                                        "metadata", {}
                                    )
                                    logger.info(f"CHAT_RSP_ST_META: {claude_metadata}")
                                    # Extract token counts immediately
                                    if isinstance(claude_metadata.get("usage"), dict):
                                        total_tokens = claude_metadata["usage"].get(
                                            "totalTokens", 0
                                        )
                                        prompt_tokens = claude_metadata["usage"].get(
                                            "inputTokens", 0
                                        )
                                        completion_tokens = claude_metadata[
                                            "usage"
                                        ].get("outputTokens", 0)
                                        logger.info(
                                            f"Extracted token usage from metadata: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                                        )
                                    # Don't process this chunk further, just continue to next
                                    continue

                                # Convert chunk to OpenAI format
                                openai_sse_chunk_str = (
                                    Converters.convert_claude37_chunk_to_openai(
                                        claude_dict_chunk, model
                                    )
                                )
                                if openai_sse_chunk_str:
                                    # Log client chunk sent
                                    logger.info(
                                        f"CHAT_RSP_ST_CHUNK: tid={tid}, {openai_sse_chunk_str[:200]}"
                                    )
                                    transport_logger.info(
                                        f"CHAT_RSP_ST_CHUNK: tid={tid}, {openai_sse_chunk_str}"
                                    )
                                    yield openai_sse_chunk_str
                            except Exception as e:
                                logger.error(
                                    f"Error processing Claude 3.7 chunk from '{subaccount_name}': {e}",
                                    exc_info=True,
                                )
                                error_payload = {
                                    "id": f"chatcmpl-error-{random.randint(10000, 99999)}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "content": "[PROXY ERROR: Failed to process upstream data]"
                                            },
                                            "finish_reason": "stop",
                                        }
                                    ],
                                }
                                yield f"{json.dumps(error_payload)}\n\n"

                # Send final chunk with usage information before [DONE]
                if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                    final_usage_chunk = {
                        "id": f"chatcmpl-claude37-{random.randint(10000, 99999)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                    }
                    final_usage_chunk_str = f"data: {json.dumps(final_usage_chunk)}\n\n"
                    logger.info(
                        f"Sending final usage chunk with SSE format: {final_usage_chunk_str[:200]}..."
                    )
                    yield final_usage_chunk_str
                    logger.info(
                        f"Sent final usage chunk: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                    )

                    # Log token usage
                    user_id = request.headers.get("Authorization", "unknown")
                    if user_id and len(user_id) > 20:
                        user_id = f"{user_id[:20]}..."
                    ip_address = request.remote_addr or request.headers.get(
                        "X-Forwarded-For", "unknown_ip"
                    )
                    token_usage_logger.info(
                        f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                        f"PromptTokens: {prompt_tokens}, CompletionTokens: {completion_tokens}, TotalTokens: {total_tokens} (Streaming)"
                    )

            # --- Gemini Streaming Logic ---
            elif Detector.is_gemini_model(model):
                logger.info(
                    f"Using Gemini streaming for subAccount '{subaccount_name}'"
                )
                for line_bytes in response.iter_lines():
                    if line_bytes:
                        line = line_bytes.decode("utf-8")
                        logger.info(f"Gemini raw line received: {line}")

                        # Process Gemini streaming lines
                        line_content = ""
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            logger.info(f"Gemini data line content: {line_content}")
                        elif line.strip():
                            # Handle lines without "" prefix
                            line_content = line.strip()
                            logger.info(
                                f"Gemini line content (no prefix): {line_content}"
                            )

                        if line_content and line_content != "[DONE]":
                            try:
                                gemini_chunk = json.loads(line_content)
                                logger.info(
                                    f"Gemini parsed chunk: {json.dumps(gemini_chunk, indent=2)}"
                                )

                                # Convert chunk to OpenAI format
                                openai_sse_chunk_str = (
                                    Converters.convert_gemini_chunk_to_openai(
                                        gemini_chunk, model
                                    )
                                )
                                if openai_sse_chunk_str:
                                    logger.info(
                                        f"Gemini converted to OpenAI chunk: {openai_sse_chunk_str}"
                                    )
                                    yield openai_sse_chunk_str
                                else:
                                    logger.info("Gemini chunk conversion returned None")

                                # Extract token usage from usageMetadata if available
                                if "usageMetadata" in gemini_chunk:
                                    usage_metadata = gemini_chunk["usageMetadata"]
                                    total_tokens = usage_metadata.get(
                                        "totalTokenCount", 0
                                    )
                                    prompt_tokens = usage_metadata.get(
                                        "promptTokenCount", 0
                                    )
                                    completion_tokens = usage_metadata.get(
                                        "candidatesTokenCount", 0
                                    )
                                    logger.info(
                                        f"Gemini token usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                                    )

                            except json.JSONDecodeError as e:
                                logger.error(
                                    f"Error parsing Gemini chunk from '{subaccount_name}': {e}",
                                    exc_info=True,
                                )
                                logger.error(
                                    f"Problematic line content: {line_content}"
                                )
                                continue
                            except Exception as e:
                                logger.error(
                                    f"Error processing Gemini chunk from '{subaccount_name}': {e}",
                                    exc_info=True,
                                )
                                logger.error(
                                    f"Problematic chunk: {gemini_chunk if 'gemini_chunk' in locals() else 'Failed to parse'}"
                                )
                                error_payload = {
                                    "id": f"chatcmpl-error-{random.randint(10000, 99999)}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "content": "[PROXY ERROR: Failed to process upstream data]"
                                            },
                                            "finish_reason": "stop",
                                        }
                                    ],
                                }
                                yield f"{json.dumps(error_payload)}\n\n"

                # Send final chunk with usage information before [DONE] for Gemini
                if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                    final_usage_chunk = {
                        "id": f"chatcmpl-gemini-{random.randint(10000, 99999)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                    }
                    final_usage_chunk_str = f"{json.dumps(final_usage_chunk)}\n\n"
                    logger.info(
                        f"Sending final Gemini usage chunk with SSE format: {final_usage_chunk_str[:200]}..."
                    )
                    yield final_usage_chunk_str
                    logger.info(
                        f"Sent final Gemini usage chunk: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                    )

                    # Log token usage
                    user_id = request.headers.get("Authorization", "unknown")
                    if user_id and len(user_id) > 20:
                        user_id = f"{user_id[:20]}..."
                    ip_address = request.remote_addr or request.headers.get(
                        "X-Forwarded-For", "unknown_ip"
                    )
                    token_usage_logger.info(
                        f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                        f"PromptTokens: {prompt_tokens}, CompletionTokens: {completion_tokens}, TotalTokens: {total_tokens} (Streaming)"
                    )

            # --- Other Models (including older Claude) ---
            else:
                for chunk in response.iter_content(chunk_size=128):
                    if chunk:
                        if Detector.is_claude_model(model):  # Older Claude
                            buffer += chunk.decode("utf-8")
                            while "data: " in buffer:
                                try:
                                    start = buffer.index("data: ") + len("data: ")
                                    end = buffer.index("\n\n", start)
                                    json_chunk_str = buffer[start:end].strip()
                                    buffer = buffer[end + 2 :]

                                    # Convert Claude chunk to OpenAI format
                                    openai_sse_chunk_str = (
                                        Converters.convert_claude_chunk_to_openai(
                                            json_chunk_str, model
                                        )
                                    )
                                    yield openai_sse_chunk_str.encode("utf-8")

                                    # Parse token usage if available
                                    try:
                                        claude_data = json.loads(json_chunk_str)
                                        if "usage" in claude_data:
                                            prompt_tokens = claude_data["usage"].get(
                                                "input_tokens", 0
                                            )
                                            completion_tokens = claude_data[
                                                "usage"
                                            ].get("output_tokens", 0)
                                            total_tokens = (
                                                prompt_tokens + completion_tokens
                                            )
                                    except json.JSONDecodeError:
                                        pass
                                except ValueError:
                                    break  # Not enough data in buffer
                                except Exception as e:
                                    logger.error(
                                        f"Error processing claude chunk: {e}",
                                        exc_info=True,
                                    )
                                    break
                        else:  # OpenAI-like models
                            yield chunk
                            try:
                                # Try to extract token counts from final chunk
                                if chunk:
                                    chunk_text = chunk.decode("utf-8")
                                    if '"finish_reason":' in chunk_text:
                                        for line in chunk_text.strip().split("\n"):
                                            if (
                                                line.startswith("data: ")
                                                and line[6:].strip() != "[DONE]"
                                            ):
                                                try:
                                                    data = json.loads(line[6:])
                                                    if "usage" in data:
                                                        total_tokens = data[
                                                            "usage"
                                                        ].get("total_tokens", 0)
                                                        prompt_tokens = data[
                                                            "usage"
                                                        ].get("prompt_tokens", 0)
                                                        completion_tokens = data[
                                                            "usage"
                                                        ].get("completion_tokens", 0)
                                                except json.JSONDecodeError:
                                                    pass
                            except Exception:
                                pass

            # Log token usage at the end of the stream (only for non-Claude 3.7/4 models)
            # Claude 3.7/4 models already log their token usage after sending the final usage chunk
            if not (
                Detector.is_claude_model(model) and Detector.is_claude_37_or_4(model)
            ):
                user_id = request.headers.get("Authorization", "unknown")
                if user_id and len(user_id) > 20:
                    user_id = f"{user_id[:20]}..."
                ip_address = request.remote_addr or request.headers.get(
                    "X-Forwarded-For", "unknown_ip"
                )

                # Log with subAccount information
                token_usage_logger.info(
                    f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                    f"PromptTokens: {prompt_tokens if 'prompt_tokens' in locals() else 0}, "
                    f"CompletionTokens: {completion_tokens if 'completion_tokens' in locals() else 0}, "
                    f"TotalTokens: {total_tokens} (Streaming)"
                )

            # Standard stream end
            transport_logger.info(f"CHAT_STREAM_COMPLETE[{tid}] Streaming completed")
            yield "data: [DONE]\n\n"

        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP Error in streaming response:({model}): {http_err}", exc_info=True
            )

            error_content: str = ""

            if http_err.response is not None:
                response = http_err.response
                status_code = response.status_code
                error_content = response.text

                # Handle HTTP 429 (Too Many Requests) specifically
                if status_code == 429:
                    return handle_http_429_error(
                        http_err, f"streaming request for {model}"
                    )

                logger.error(f"Error response status: {response.status_code}")
                logger.error(f"Error response headers: {dict(response.headers)}")
                logger.error(f"Error response body: {response.text}")
                try:
                    logger.error(f"Error response body: {error_content}")

                    # Try to parse as JSON for better formatting
                    try:
                        error_content = json.dumps(response.json(), indent=2)
                        logger.error(f"Error response JSON: {error_content}")
                    except json.JSONDecodeError:
                        pass
                except Exception as e:
                    logger.error(
                        f"Could not read error response content: {e}", exc_info=True
                    )
            else:
                status_code = 500
                error_content = str(http_err)

            error_payload = {
                "id": f"error-{random.randint(10000, 99999)}",
                "object": "error",
                "created": int(time.time()),
                "model": model,
                "error": {
                    "message": error_content,
                    "type": "http_error",
                    "code": status_code,
                    "subaccount": subaccount_name,
                },
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as http_err:
            logger.error(
                f"Error in streaming response from '{subaccount_name}': {http_err}",
                exc_info=True,
            )
            error_payload = {
                "id": f"error-{random.randint(10000, 99999)}",
                "object": "error",
                "created": int(time.time()),
                "model": model,
                "error": {
                    "message": str(http_err),
                    "type": "proxy_error",
                    "code": 500,
                    "subaccount": subaccount_name,
                },
            }
            # Use strings directly without referencing chunk to avoid errors
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"


def generate_claude_streaming_response(url, headers, payload, model, subaccount_name):
    """
    Generates a streaming response in the Anthropic Claude Messages API format.
    If the backend is a Claude model, it passes the stream through.
    If the backend is Gemini or OpenAI, it converts their SSE stream to Claude's format.
    """
    logger.info(
        f"Starting Claude streaming response for model '{model}' using subAccount '{subaccount_name}'"
    )
    logger.debug(
        f"Forwarding payload to API (Claude streaming): {json.dumps(payload, indent=2)}"
    )
    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request headers: {headers}")

    # If the backend is already a Claude model, we need to convert the response format.
    if Detector.is_claude_model(model):
        logger.info(
            f"Backend is Claude model, converting response format for '{model}'"
        )
        try:
            with requests.post(
                url, headers=headers, json=payload, stream=True, timeout=600
            ) as response:
                response.raise_for_status()
                logger.debug(f"Claude backend response status: {response.status_code}")

                # Send message_start event
                message_start_data = {
                    "type": "message_start",
                    "message": {
                        "id": f"msg_{random.randint(10000, 99999)}",
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": model,
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                }
                message_start_event = (
                    f"event: message_start\ndata: {json.dumps(message_start_data)}\n\n"
                )
                yield message_start_event.encode("utf-8")

                # Send content_block_start event
                content_block_start_data = {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                }
                content_block_start_event = f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
                yield content_block_start_event.encode("utf-8")

                chunk_count = 0
                stop_reason = None

                for line in response.iter_lines():
                    chunk_count += 1
                    if not line:
                        continue

                    line_str = line.decode("utf-8", errors="ignore").strip()
                    logger.debug(f"Claude backend chunk {chunk_count}: {line_str}")

                    if line_str.startswith("data: "):
                        data_content = line_str[6:].strip()  # Remove 'data: ' prefix

                        # Handle different data formats
                        if data_content == "[DONE]":
                            break

                        try:
                            # Try to parse as JSON first
                            try:
                                parsed_data = json.loads(data_content)
                            except json.JSONDecodeError:
                                # If JSON parsing fails, try to evaluate as Python dict
                                # This handles the case where single quotes are used instead of double quotes
                                parsed_data = ast.literal_eval(data_content)

                            # Convert Claude backend format to standard Claude API format
                            if "contentBlockDelta" in parsed_data:
                                # Extract text from the delta and format it the same way as OpenAI conversion
                                text_content = parsed_data["contentBlockDelta"][
                                    "delta"
                                ].get("text", "")
                                if text_content:
                                    delta_data = {
                                        "type": "content_block_delta",
                                        "index": 0,
                                        "delta": {
                                            "type": "text_delta",
                                            "text": text_content,
                                        },
                                    }
                                    delta_event = f"event: content_block_delta\ndata: {json.dumps(delta_data)}\n\n"
                                    yield delta_event.encode("utf-8")

                            elif "contentBlockStop" in parsed_data:
                                content_block_stop_data = {
                                    "type": "content_block_stop",
                                    "index": parsed_data["contentBlockStop"].get(
                                        "contentBlockIndex", 0
                                    ),
                                }
                                content_block_stop_event = f"event: content_block_stop\ndata: {json.dumps(content_block_stop_data)}\n\n"
                                yield content_block_stop_event.encode("utf-8")

                            elif "messageStop" in parsed_data:
                                stop_reason = parsed_data["messageStop"].get(
                                    "stopReason", "end_turn"
                                )

                            elif "metadata" in parsed_data:
                                # Extract token usage information
                                usage_info = parsed_data.get("metadata", {}).get(
                                    "usage", {}
                                )
                                message_delta_data = {
                                    "type": "message_delta",
                                    "delta": {
                                        "stop_reason": stop_reason or "end_turn",
                                        "stop_sequence": None,
                                    },
                                    "usage": {
                                        "output_tokens": usage_info.get(
                                            "outputTokens", 0
                                        )
                                    },
                                }
                                message_delta_event = f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
                                yield message_delta_event.encode("utf-8")

                                message_stop_event = f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
                                yield message_stop_event.encode("utf-8")

                        except (json.JSONDecodeError, ValueError, SyntaxError) as e:
                            logger.warning(
                                f"Could not parse Claude backend data: {data_content}, error: {e}"
                            )
                            continue

                logger.info(
                    f"Claude backend conversion completed with {chunk_count} chunks"
                )
        except Exception as e:
            logger.error(
                f"Error in Claude backend conversion for '{model}': {e}", exc_info=True
            )
            raise
        return

    # For other models, we need to convert the stream to Claude's event format.
    logger.info(f"Converting non-Claude model '{model}' stream to Claude format")

    # 1. Send message_start event
    message_start_data = {
        "type": "message_start",
        "message": {
            "id": f"msg_{random.randint(10000, 99999)}",
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }
    message_start_event = (
        f"event: message_start\ndata: {json.dumps(message_start_data)}\n\n"
    )
    logger.debug(f"Sending message_start event: {message_start_event}")
    yield message_start_event.encode("utf-8")

    # 2. Send content_block_start event
    content_block_start_data = {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    }
    content_block_start_event = (
        f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
    )
    logger.debug(f"Sending content_block_start event: {content_block_start_event}")
    yield content_block_start_event.encode("utf-8")

    stop_reason = None
    chunk_count = 0
    delta_count = 0

    try:
        with requests.post(
            url, headers=headers, json=payload, stream=True, timeout=600
        ) as response:
            response.raise_for_status()
            logger.debug(f"Backend response status: {response.status_code}")
            logger.debug(f"Backend response headers: {dict(response.headers)}")

            # 3. Iterate and yield content_block_delta events
            for line in response.iter_lines():
                chunk_count += 1
                logger.debug(f"Processing backend chunk {chunk_count}: {line}")

                if not line or not line.strip().startswith(b"data:"):
                    logger.debug(f"Skipping non-data line {chunk_count}: {line}")
                    continue

                line_str = line.decode("utf-8", errors="ignore")[5:].strip()
                logger.debug(f"Extracted line content: {line_str}")

                if line_str == "[DONE]":
                    logger.info(f"Received [DONE] signal at chunk {chunk_count}")
                    break

                try:
                    backend_chunk = json.loads(line_str)
                    logger.debug(
                        f"Parsed backend chunk: {json.dumps(backend_chunk, indent=2)}"
                    )

                    claude_delta = None
                    if Detector.is_gemini_model(model):
                        logger.debug("Converting Gemini chunk to Claude delta")
                        claude_delta = Converters.convert_gemini_chunk_to_claude_delta(
                            backend_chunk
                        )
                        if not stop_reason:
                            stop_reason = get_claude_stop_reason_from_gemini_chunk(
                                backend_chunk
                            )
                            if stop_reason:
                                logger.debug(
                                    f"Extracted stop reason from Gemini: {stop_reason}"
                                )
                    else:  # Assume OpenAI-compatible
                        logger.debug("Converting OpenAI chunk to Claude delta")
                        claude_delta = Converters.convert_openai_chunk_to_claude_delta(
                            backend_chunk
                        )
                        if not stop_reason:
                            stop_reason = get_claude_stop_reason_from_openai_chunk(
                                backend_chunk
                            )
                            if stop_reason:
                                logger.debug(
                                    f"Extracted stop reason from OpenAI: {stop_reason}"
                                )

                    if claude_delta:
                        delta_count += 1
                        delta_event = f"event: content_block_delta\ndata: {json.dumps(claude_delta)}\n\n"
                        logger.debug(
                            f"Sending content_block_delta {delta_count}: {delta_event}"
                        )
                        yield delta_event.encode("utf-8")
                    else:
                        logger.debug(f"No delta extracted from chunk {chunk_count}")

                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Could not decode JSON from stream chunk {chunk_count}: {line_str}, error: {e}"
                    )
                    continue
                except Exception as e:
                    logger.error(
                        f"Error processing chunk {chunk_count}: {e}", exc_info=True
                    )
                    continue

            logger.info(
                f"Processed {chunk_count} chunks, generated {delta_count} deltas"
            )

    except requests.exceptions.HTTPError as e:
        logger.error(
            f"HTTP error in Claude streaming conversion({model}): {e}",
            exc_info=True,
        )
        if hasattr(e, "response") and e.response:
            logger.error(f"Error response status: {e.response.status_code}")
            logger.error(f"Error response body: {e.response.text}")
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error in Claude streaming conversion for '{model}': {e}",
            exc_info=True,
        )
        raise

    # 4. Send stop events
    logger.debug(f"Sending stop events with stop_reason: {stop_reason}")

    content_block_stop_event = f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    logger.debug(f"Sending content_block_stop event: {content_block_stop_event}")
    yield content_block_stop_event.encode("utf-8")

    message_delta_data = {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason or "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 0},  # Token usage is not available in most streams
    }
    message_delta_event = (
        f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
    )
    logger.debug(f"Sending message_delta event: {message_delta_event}")
    yield message_delta_event.encode("utf-8")

    message_stop_event = (
        f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
    )
    logger.debug(f"Sending message_stop event: {message_stop_event}")
    yield message_stop_event.encode("utf-8")

    logger.info(
        f"Claude streaming response completed for model '{model}' with {delta_count} content deltas"
    )


def main() -> None:
    """Main entry point for the SAP AI Core LLM Proxy Server."""
    args = parse_arguments()

    # Setup logging using the new modular function
    init_logging(debug=args.debug)

    # Log version information at startup
    version_info = get_version_string()
    logger.info(f"SAP AI Core LLM Proxy Server - Version: {version_info}")

    logger.info(f"Loading configuration from: {args.config}")

    # Load the proxy config
    global proxy_config
    proxy_config = load_proxy_config(args.config)

    # Get server configuration
    host = proxy_config.host
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
