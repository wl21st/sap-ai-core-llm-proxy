"""
Model request handlers for SAP AI Core LLM Proxy.

This module contains handlers for routing requests to different model backends:
- Claude (Anthropic via Bedrock)
- Gemini (Google)
- Default (OpenAI-compatible, e.g., GPT models)
"""

from load_balancer import load_balance_url
from proxy_helpers import Converters, Detector
from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)

# API version constants
API_VERSION_2023_05_15 = "2023-05-15"
API_VERSION_2024_12_01_PREVIEW = "2024-12-01-preview"

# Default model constants
DEFAULT_GPT_MODEL = "gpt-4.1"


def handle_claude_request(payload, model, proxy_config):
    """Handle Claude model request with multi-subAccount support.

    Args:
        payload: Request payload from client
        model: The model name to use
        proxy_config: The proxy configuration object

    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)

    Raises:
        ValueError: If no valid Claude model is found
    """
    stream = payload.get("stream", True)
    logger.info(f"handle_claude_request: model={model} stream={stream}")

    # Get the selected URL, subaccount and resource group using our load balancer
    try:
        selected_url, subaccount_name, _, model = load_balance_url(model, proxy_config)
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


def handle_gemini_request(payload, model, proxy_config):
    """Handle Gemini model request with multi-subAccount support.

    Args:
        payload: Request payload from client
        model: The model name to use
        proxy_config: The proxy configuration object

    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)

    Raises:
        ValueError: If no valid Gemini model is found
    """
    stream = payload.get("stream", True)  # Default to True if 'stream' is not provided
    logger.info(f"handle_gemini_request: model={model} stream={stream}")

    # Get the selected URL, subaccount and resource group using our load balancer
    try:
        selected_url, subaccount_name, _, model = load_balance_url(model, proxy_config)
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


def handle_default_request(payload, model, proxy_config):
    """Handle default (non-Claude, non-Gemini) model request with multi-subAccount support.

    Args:
        payload: Request payload from client
        model: The model name to use
        proxy_config: The proxy configuration object

    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)
    """
    # Get the selected URL, subaccount and resource group using our load balancer
    selected_url, subaccount_name, _, model = load_balance_url(model, proxy_config)

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
