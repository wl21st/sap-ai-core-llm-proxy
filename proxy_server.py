import argparse
import ast
import json
import logging
import random
import threading
import time
from typing import Dict, Any

import requests
from flask import Flask, request, jsonify, Response, stream_with_context
# SAP AI SDK imports
from gen_ai_hub.proxy.native.amazon.clients import Session

from auth import TokenManager, RequestValidator
# Import from new modular structure
from config import ServiceKey, SubAccountConfig, ProxyConfig, load_config
from proxy_helpers import Detector, Converters
from utils import setup_logging, get_token_logger, handle_http_429_error

# Global configuration
proxy_config = ProxyConfig()

app = Flask(__name__)

# ------------------------
# SAP AI SDK session/client cache for performance
# ------------------------
# Creating a new SDK Session()/client per request is expensive. Reuse a process-wide
# Session and cache clients per model in a thread-safe manner.
_sdk_session = None
_sdk_session_lock = threading.Lock()
_bedrock_clients: Dict[str, Any] = {}
_bedrock_clients_lock = threading.Lock()

def get_sapaicore_sdk_session() -> Session:
    """Lazily initialize and return a global SAP AI Core SDK Session."""
    global _sdk_session
    if _sdk_session is None:
        with _sdk_session_lock:
            if _sdk_session is None:
                logging.info("Initializing global SAP AI SDK Session")
                _sdk_session = Session()
    return _sdk_session

def get_sapaicore_sdk_client(model_name: str):
    """Get or create a cached SAP AI Core (Bedrock) client for the given model."""
    client = _bedrock_clients.get(model_name)
    if client is not None:
        return client
    with _bedrock_clients_lock:
        client = _bedrock_clients.get(model_name)
        if client is None:
            logging.info(f"Creating SAP AI SDK client for model '{model_name}'")
            client = get_sapaicore_sdk_session().client(model_name=model_name)
            _bedrock_clients[model_name] = client
    return client

# handle_http_429_error is now imported from utils.error_handlers

@app.route('/v1/embeddings', methods=['POST'])
def handle_embedding_request():
    logging.info("Received request to /v1/embeddings")
    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    if not validator.validate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    payload = request.json
    input_text = payload.get("input")
    model = payload.get("model", "text-embedding-3-large")
    encoding_format = payload.get("encoding_format")

    if not input_text:
        return jsonify({"error": "Input text is required"}), 400

    try:
        endpoint_url, modified_payload, subaccount_name = handle_embedding_service_call(input_text, model, encoding_format)
        token_manager = TokenManager(proxy_config.subaccounts[subaccount_name])
        subaccount_token = token_manager.get_token()
        subaccount = proxy_config.subaccounts[subaccount_name]
        resource_group = subaccount.resource_group
        service_key = subaccount.service_key
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Resource-Group": resource_group,
            "AI-Tenant-Id": service_key.identityzoneid
        }
        response = requests.post(endpoint_url, headers=headers, json=modified_payload)
        response.raise_for_status()
        return response.json(), 200
        # return jsonify(format_embedding_response(response.json(), model)), 200
    except requests.exceptions.HTTPError as http_err:
        # Handle HTTP 429 (Too Many Requests) specifically
        if http_err.response is not None and http_err.response.status_code == 429:
            return handle_http_429_error(http_err, "embedding request")
        else:
            # Handle other HTTP errors
            logging.error(f"HTTP Error handling embedding request: {http_err}")
            if http_err.response is not None:
                logging.error(f"HTTP Status Code: {http_err.response.status_code}")
                logging.error(f"Response Body: {http_err.response.text}")
            return jsonify({"error": str(http_err)}), http_err.response.status_code if http_err.response else 500
    except Exception as e:
        logging.error(f"Error handling embedding request: {e}")
        return jsonify({"error": str(e)}), 500

def handle_embedding_service_call(input_text, model, encoding_format):
    # Logic to prepare the request to SAP AI Core
    selected_url, subaccount_name, _, model = load_balance_url(model)
    
    # Construct the URL based on the official SAP AI Core documentation
    # This is critical or it will return 404
    # TODO: Follow up on what is the required
    api_version = "2023-05-15"
    endpoint_url = f"{selected_url.rstrip('/')}/embeddings?api-version={api_version}"

    # The payload for the embeddings endpoint only requires the input.
    modified_payload = {"input": input_text}
        
    return endpoint_url, modified_payload, subaccount_name

def format_embedding_response(response, model):
    # Logic to convert the response to OpenAI format
    embedding_data = response.get("embedding", [])
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "embedding": embedding_data,
                "index": 0
            }
        ],
        "model": model,
        "usage": {
            "prompt_tokens": len(embedding_data),
            "total_tokens": len(embedding_data)
        }
    }

# Initialize token logger (will be configured on first use)
token_logger = get_token_logger()

# load_config is now imported from config.loader

def parse_arguments():
    parser = argparse.ArgumentParser(description="Proxy server for AI models")
    parser.add_argument("--config", type=str, default="config.json", help="Path to the configuration file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


# Configure logging if not already configured elsewhere
# logging.basicConfig(level=logging.DEBUG)


def get_claude_stop_reason_from_gemini_chunk(gemini_chunk):
    """Extracts and maps the stop reason from a final Gemini chunk."""
    finish_reason = gemini_chunk.get("candidates", [{}])[0].get("finishReason")
    if finish_reason:
        stop_reason_map = {
            "STOP": "end_turn",
            "MAX_TOKENS": "max_tokens",
            "SAFETY": "stop_sequence",
            "RECITATION": "stop_sequence",
            "OTHER": "stop_sequence"
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


def load_balance_url(model_name: str) -> tuple:
    """
    Load balance requests for a model across all subAccounts that have it deployed.
    
    Args:
        model_name: Name of the model to load balance
        
    Returns:
        Tuple of (selected_url, subaccount_name, resource_group, final_model_name)
        
    Raises:
        ValueError: If no subAccounts have the requested model
    """
    # Initialize counters dictionary if it doesn't exist
    if not hasattr(load_balance_url, "counters"):
        load_balance_url.counters = {}
    
    # Get list of subAccounts that have this model
    if model_name not in proxy_config.model_to_subaccounts or not proxy_config.model_to_subaccounts[model_name]:
        # Check if it's a Claude or Gemini model and try fallback
        if Detector.is_claude_model(model_name):
            logging.info(f"Claude model '{model_name}' not found, trying fallback models")
            # Try common Claude model fallbacks
            #fallback_models = ["anthropic--claude-4-sonnet"]
            fallback_models = ["anthropic--claude-4.5-sonnet"]
            for fallback in fallback_models:
                if fallback in proxy_config.model_to_subaccounts and proxy_config.model_to_subaccounts[fallback]:
                    logging.info(f"Using fallback Claude model '{fallback}' for '{model_name}'")
                    model_name = fallback
                    break
            else:
                logging.error(f"No Claude models available in any subAccount")
                raise ValueError(f"Claude model '{model_name}' and fallbacks not available in any subAccount")
        elif Detector.is_gemini_model(model_name):
            logging.info(f"Gemini model '{model_name}' not found, trying fallback models")
            # Try common Gemini model fallbacks
            fallback_models = ["gemini-2.5-pro"]
            for fallback in fallback_models:
                if fallback in proxy_config.model_to_subaccounts and proxy_config.model_to_subaccounts[fallback]:
                    logging.info(f"Using fallback Gemini model '{fallback}' for '{model_name}'")
                    model_name = fallback
                    break
            else:
                logging.error(f"No Gemini models available in any subAccount")
                raise ValueError(f"Gemini model '{model_name}' and fallbacks not available in any subAccount")
        else:
            # For other models, try common fallbacks
            logging.warning(f"Model '{model_name}' not found, trying fallback models")
            fallback_models = ["gpt-5"]
            for fallback in fallback_models:
                if fallback in proxy_config.model_to_subaccounts and proxy_config.model_to_subaccounts[fallback]:
                    logging.info(f"Using fallback model '{fallback}' for '{model_name}'")
                    model_name = fallback
                    break
            else:
                logging.error(f"No subAccounts with model '{model_name}' or fallbacks found")
                raise ValueError(f"Model '{model_name}' and fallbacks not available in any subAccount")
    
    subaccount_names = proxy_config.model_to_subaccounts[model_name]
    
    # Create counter for this model if it doesn't exist
    if model_name not in load_balance_url.counters:
        load_balance_url.counters[model_name] = 0
    
    # Select subAccount using round-robin
    subaccount_index = load_balance_url.counters[model_name] % len(subaccount_names)
    selected_subaccount = subaccount_names[subaccount_index]
    
    # Increment counter for next request
    load_balance_url.counters[model_name] += 1
    
    # Get the model URL list from the selected subAccount
    subaccount = proxy_config.subaccounts[selected_subaccount]
    url_list = subaccount.normalized_models.get(model_name, [])
    
    if not url_list:
        logging.error(f"Model '{model_name}' listed for subAccount '{selected_subaccount}' but no URLs found")
        raise ValueError(f"Configuration error: No URLs for model '{model_name}' in subAccount '{selected_subaccount}'")
    
    # Select URL using round-robin within the subAccount
    url_counter_key = f"{selected_subaccount}:{model_name}"
    if url_counter_key not in load_balance_url.counters:
        load_balance_url.counters[url_counter_key] = 0
    
    url_index = load_balance_url.counters[url_counter_key] % len(url_list)
    selected_url = url_list[url_index]
    
    # Increment URL counter for next request
    load_balance_url.counters[url_counter_key] += 1
    
    # Get resource group for the selected subAccount
    resource_group = subaccount.resource_group
    
    logging.info(f"Selected subAccount '{selected_subaccount}' and URL '{selected_url}' for model '{model_name}'")
    return selected_url, selected_subaccount, resource_group, model_name

def handle_claude_request(payload, model="3.5-sonnet"):
    """Handle Claude model request with multi-subAccount support.
    
    Args:
        payload: Request payload from client
        model: The model name to use
        
    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)
    """
    stream = payload.get("stream", True)  
    logging.info(f"handle_claude_request: model={model} stream={stream}")
    
    # Get the selected URL, subaccount and resource group using our load balancer
    try:
        selected_url, subaccount_name, _, model = load_balance_url(model)
    except ValueError as e:
        logging.error(f"Failed to load balance URL for model '{model}': {e}")
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
    
    logging.info(f"handle_claude_request: {endpoint_url} (subAccount: {subaccount_name})")
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
    logging.info(f"handle_gemini_request: model={model} stream={stream}")
    
    # Get the selected URL, subaccount and resource group using our load balancer
    try:
        selected_url, subaccount_name, _, model = load_balance_url(model)
    except ValueError as e:
        logging.error(f"Failed to load balance URL for model '{model}': {e}")
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
    
    logging.info(f"handle_gemini_request: {endpoint_url} (subAccount: {subaccount_name})")
    return endpoint_url, modified_payload, subaccount_name

def handle_default_request(payload, model="gpt-4o"):
    """Handle default (non-Claude, non-Gemini) model request with multi-subAccount support.
    
    Args:
        payload: Request payload from client
        model: The model name to use
        
    Returns:
        Tuple of (endpoint_url, modified_payload, subaccount_name)
    """
    # Get the selected URL, subaccount and resource group using our load balancer
    try:
        selected_url, subaccount_name, _, model = load_balance_url(model)
    except ValueError as e:
        logging.error(f"Failed to load balance URL for model '{model}': {e}")
        # Try with default model if specified model not found
        try:
            fallback_model = "gpt-4o"  # Default fallback
            logging.info(f"Falling back to '{fallback_model}' model")
            selected_url, subaccount_name, _, model = load_balance_url(fallback_model)
        except ValueError:
            raise ValueError(f"No valid model found for '{model}' or fallback in any subAccount")
    
    # Determine API version based on model
    if any(m in model for m in ["o3", "o4-mini", "o3-mini"]):
        api_version = "2024-12-01-preview"
        # Remove unsupported parameters for o3-mini
        modified_payload = payload.copy()
        if 'temperature' in modified_payload:
            logging.info(f"Removing 'temperature' parameter for o3-mini model.")
            del modified_payload['temperature']
        # Add checks for other potentially unsupported parameters if needed
    else:
        api_version = "2023-05-15"
        modified_payload = payload
    
    endpoint_url = f"{selected_url.rstrip('/')}/chat/completions?api-version={api_version}"
    
    logging.info(f"handle_default_request: {endpoint_url} (subAccount: {subaccount_name})")
    return endpoint_url, modified_payload, subaccount_name

@app.route('/v1/chat/completions', methods=['OPTIONS'])
def proxy_openai_stream2():
    logging.info("OPTIONS:Received request to /v1/chat/completions")
    logging.info(f"Request headers: {request.headers}")
    logging.info(f"Request payload as string: {request.data.decode('utf-8')}")
    return jsonify({
        "id": "gen-1747041021-KLZff2aBrJPmV6L1bZf1",
        "provider": "OpenAI",
        "model": "gpt-4o",
        "object": "chat.completion",
        "created": 1747041021,
        "choices": [
            {
                "logprobs": None,
                "finish_reason": "stop",
                "native_finish_reason": "stop",
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hi.",
                    "refusal": None,
                    "reasoning": None
                }
            }
        ],
        "system_fingerprint": "fp_f5bdcc3276",
        "usage": {
            "prompt_tokens": 26,
            "completion_tokens": 3,
            "total_tokens": 29,
            "prompt_tokens_details": {
                "cached_tokens": 0
            },
            "completion_tokens_details": {
                "reasoning_tokens": 0
            }
        }
    }), 204

@app.route('/v1/models', methods=['GET', 'OPTIONS'])
def list_models():
    """Lists all available models across all subAccounts."""
    logging.info("Received request to /v1/models")
    logging.info(f"Request headers: {request.headers}")
    # logging.info(f"Request payload: {request.get_json()}")
    
    # if not verify_request_token(request):
    #     logging.info("Unauthorized request to list models.")
    #     return jsonify({"error": "Unauthorized"}), 401
    
    # Collect all available models from all subAccounts
    models = []
    timestamp = int(time.time())
    
    for model_name in proxy_config.model_to_subaccounts.keys():
        models.append({
            "id": model_name,
            "object": "model",
            "created": timestamp,
            "owned_by": "sap-ai-core"
        })
    
    return jsonify({"object": "list", "data": models}), 200

@app.route('/api/event_logging/batch', methods=['POST', 'OPTIONS'])
def handle_event_logging():
    """Dummy endpoint for Claude Code event logging to prevent 404 errors."""
    logging.info("Received request to /api/event_logging/batch")
    logging.debug(f"Request headers: {request.headers}")
    logging.debug(f"Request body: {request.get_json(silent=True)}")
    
    # Return success response for event logging
    return jsonify({
        "status": "success",
        "message": "Events logged successfully"
    }), 200

content_type="Application/json"
@app.route('/v1/chat/completions', methods=['POST'])
def proxy_openai_stream():
    """Main handler for chat completions endpoint with multi-subAccount support."""
    logging.info("Received request to /v1/chat/completions")
    logging.debug(f"Request headers: {request.headers}")
    logging.debug(f"Request body:\n{json.dumps(request.get_json(), indent=4)}")
    
    # Verify client authentication token
    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    if not validator.validate(request):
        logging.info("Unauthorized request received. Token verification failed.")
        return jsonify({"error": "Unauthorized"}), 401

    # Extract model from the request payload
    payload = request.json
    model = payload.get("model")
    if not model:
        logging.warning("No model specified in request, using default model")
        model = "gpt-4o"  # Default model
    
    # Check if model is available in any subAccount
    if model not in proxy_config.model_to_subaccounts:
        logging.warning(f"Model '{model}' not found in any subAccount, falling back to default")
        model = "gpt-4o"  # Fallback model
        if model not in proxy_config.model_to_subaccounts:
            return jsonify({"error": f"Model '{model}' not available in any subAccount."}), 404
    
    # Check streaming mode
    is_stream = payload.get("stream", False)
    logging.info(f"Model: {model}, Streaming: {is_stream}")
    
    try:
        # Handle request based on model type
        if Detector.is_claude_model(model):
            endpoint_url, modified_payload, subaccount_name = handle_claude_request(payload, model)
        elif Detector.is_gemini_model(model):
            endpoint_url, modified_payload, subaccount_name = handle_gemini_request(payload, model)
        else:
            endpoint_url, modified_payload, subaccount_name = handle_default_request(payload, model)
        
        # Get token for the selected subAccount
        token_manager = TokenManager(proxy_config.subaccounts[subaccount_name])
        subaccount_token = token_manager.get_token()
        
        # Get resource group for the selected subAccount
        resource_group = proxy_config.subaccounts[subaccount_name].resource_group
        
        # Get service key for tenant ID
        service_key = proxy_config.subaccounts[subaccount_name].service_key
        
        # Prepare headers for the backend request
        headers = {
            "AI-Resource-Group": resource_group,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Tenant-Id": service_key.identityzoneid
        }
        
        logging.info(f"Forwarding request to {endpoint_url} with subAccount '{subaccount_name}'")
        
        # Handle non-streaming requests
        if not is_stream:
            return handle_non_streaming_request(endpoint_url, headers, modified_payload, model, subaccount_name)
        
        # Handle streaming requests
        return Response(
            stream_with_context(generate_streaming_response(
                endpoint_url, headers, modified_payload, model, subaccount_name
            )),
            content_type='text/event-stream'
        )
    
    except ValueError as err:
        logging.error(f"Value error during request handling: {err}")
        return jsonify({"error": str(err)}), 400
    
    except Exception as err:
        logging.error(f"Unexpected error during request handling: {err}", exc_info=True)
        return jsonify({"error": str(err)}), 500


@app.route('/v1/messages', methods=['POST'])
def proxy_claude_request():
    """Handles requests that are compatible with the Anthropic Claude Messages API using SAP AI SDK."""
    logging.info("Received request to /v1/messages")
    logging.debug(f"Request headers: {request.headers}")
    logging.debug(f"Request body:\n{json.dumps(request.get_json(), indent=4)}")

    # Validate API key using proxy config authentication
    api_key = request.headers.get("X-Api-Key", "")
    if not api_key:
        api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    if not validator.validate(request):
        return jsonify({
            "type": "error",
            "error": { "type": "authentication_error", "message": "Invalid API Key provided." }
        }), 401

    # Get request body and extract model
    request_json = request.get_json(cache=False)
    request_model = request_json.get("model")
    logging.info(f"request_model is: {request_model}")
    # Hardcode to claude-3-5-haiku-20241022 if no model specified
    request_model = "anthropic--claude-4.5-sonnet"
    logging.info(f"hardcode request_model to: {request_model}")
    
    if not request_model:
        return jsonify({
            "type": "error", 
            "error": {"type": "invalid_request_error", "message": "Missing 'model' parameter"}
        }), 400

    # Validate model availability
    try:
        selected_url, subaccount_name, resource_group, model = load_balance_url(request_model)
    except ValueError as e:
        logging.error(f"Model validation failed: {e}")
        model = request_model
        # return jsonify({
        #     "type": "error",
        #     "error": {"type": "invalid_request_error", "message": f"Model '{request_model}' not available"}
        # }), 400

    # Check if this is an Anthropic model that should use the SDK
    if not Detector.is_claude_model(model):
        logging.warning(f"Model '{model}' is not a Claude model, falling back to original implementation")
        # Fall back to original implementation for non-Claude models
        return proxy_claude_request_original()

    logging.info(f"Request from Claude API for model: {model}")
    
    # Extract streaming flag
    stream = request_json.get("stream", False)
    
    try:
        # Use cached SAP AI SDK client for the model
        logging.info(f"Obtaining SAP AI SDK client for model: {model}")
        bedrock = get_sapaicore_sdk_client(model)
        logging.info("SAP AI SDK client ready (cached)")
        
        # Get the conversation messages
        conversation = request_json.get("messages", [])
        logging.debug(f"Original conversation: {conversation}")

        thinking_cfg_preview = request_json.get("thinking")
        logging.info(
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
                    if item.get("type") == "text" and (not item.get("text") or item.get("text") == ""):
                        # Mark empty text items for removal
                        items_to_remove.append(i)
                    elif (item.get("type") == "image" and 
                          item.get("source", {}).get("type") == "base64"):
                        # Compress image data if available (would need ImageCompressor utility)
                        image_data = item.get("source", {}).get("data")
                        if image_data:
                            # Note: ImageCompressor would need to be imported/implemented
                            # For now, keeping original data
                            logging.debug("Image data found in message content")
                
                # Remove empty text items (in reverse order to maintain indices)
                for i in reversed(items_to_remove):
                    content.pop(i)

        # Prepare the request body for Bedrock
        body = request_json.copy()
        
        # Log the original request body for debugging
        logging.info("Original request body keys: %s", list(body.keys()))
        
        # Remove model and stream from body as they're handled separately
        body.pop("model", None)
        body.pop("stream", None)
        
        # Add required anthropic_version for Bedrock
        body["anthropic_version"] = "bedrock-2023-05-31"

        # Remove unsupported fields for Bedrock
        unsupported_fields = ["context_management", "metadata"]
        for field in unsupported_fields:
            if field in body:
                logging.info("Removing unsupported top-level field '%s' from request body", field)
                body.pop(field, None)
        
        # Check for context_management in thinking config
        thinking_cfg = body.get("thinking")
        if isinstance(thinking_cfg, dict):
            if "context_management" in thinking_cfg:
                logging.info("Removing 'context_management' from thinking config")
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
                logging.warning(f"Invalid max_tokens value '{raw_max_tokens}' in request; resetting to None")
                max_tokens_value = None

        if isinstance(thinking_cfg, dict):
            budget_tokens = thinking_cfg.get("budget_tokens")
            if isinstance(budget_tokens, int):
                required_min_tokens = budget_tokens + 1
                if max_tokens_value is None or max_tokens_value <= budget_tokens:
                    body["max_tokens"] = required_min_tokens
                    logging.info(
                        "Adjusted max_tokens to %s to satisfy thinking.budget_tokens=%s",
                        required_min_tokens,
                        budget_tokens,
                    )
                else:
                    logging.debug(
                        "max_tokens=%s already greater than thinking.budget_tokens=%s",
                        max_tokens_value,
                        budget_tokens,
                    )
            else:
                logging.debug("No integer thinking.budget_tokens found in request")
        elif thinking_cfg is not None:
            logging.debug("Ignoring non-dict thinking config in request body")

        if body.get("max_tokens") is not None:
            logging.info(
                "Final max_tokens for model %s request: %s",
                model,
                body["max_tokens"],
            )
        else:
            logging.info("No max_tokens specified after adjustment for model %s", model)
        
        # Log final body keys before sending to Bedrock
        logging.info("Final request body keys before Bedrock: %s", list(body.keys()))
        if "thinking" in body:
            logging.info("Thinking config keys: %s", list(body["thinking"].keys()) if isinstance(body["thinking"], dict) else type(body["thinking"]))
        
        # Convert body to JSON string for Bedrock API
        body_json = json.dumps(body)
        
        # Pretty-print the body JSON for easier debugging
        try:
            pretty_body_json = json.dumps(json.loads(body_json), indent=2, ensure_ascii=False)
        except Exception:
            pretty_body_json = body_json
        logging.info("Request body for Bedrock (pretty):\n%s", pretty_body_json)

        if stream:
            # Handle streaming response
            def stream_generate():
                try:
                    response = bedrock.invoke_model_with_response_stream(body=body_json)
                    response_body = response.get("body")
                    
                    if response_body is not None:
                        for event in response_body:
                            chunk = json.loads(event["chunk"]["bytes"])
                            logging.debug(f"Streaming chunk: {chunk}")
                            
                            chunk_type = chunk.get("type")
                            
                            # Handle different chunk types according to Claude streaming format
                            if chunk_type == "message_start":
                                yield f"event: message_start\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            elif chunk_type == "content_block_start":
                                yield f"event: content_block_start\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            elif chunk_type == "content_block_delta":
                                yield f"event: content_block_delta\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            elif chunk_type == "content_block_stop":
                                yield f"event: content_block_stop\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            elif chunk_type == "message_delta":
                                yield f"event: message_delta\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                            elif chunk_type == "message_stop":
                                yield f"event: message_stop\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                                yield "data: [DONE]\n\n"
                                break
                                
                except Exception as e:
                    logging.error(f"Error in streaming response: {e}", exc_info=True)
                    error_chunk = {
                        "type": "error",
                        "error": {"type": "api_error", "message": str(e)}
                    }
                    yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"

            return Response(stream_generate(), mimetype="text/event-stream"), 200
            
        else:
            # Handle non-streaming response
            response = bedrock.invoke_model(body=body_json)
            response_body = response.get("body")
            
            if response_body is not None:
                # Read the response body
                chunk_data = ''
                for event in response_body:
                    if isinstance(event, bytes):
                        chunk_data += event.decode("utf-8")
                    else:
                        chunk_data += str(event)
                
                if chunk_data:
                    final_response = json.loads(chunk_data)
                    logging.debug(f"Non-streaming response: {final_response}")
                    return jsonify(final_response), 200
                else:
                    return jsonify({}), 200
            else:
                return jsonify({}), 200

    except Exception as e:
        logging.error(f"Error handling Anthropic proxy request using SDK: {e}", exc_info=True)
        error_dict = {
            "type": "error",
            "error": {
                "type": "api_error", 
                "message": str(e)
            }
        }
        return jsonify(error_dict), 500


def proxy_claude_request_original():
    """Original implementation preserved as fallback."""
    logging.info("Using original Claude request implementation")
    
    validator = RequestValidator(proxy_config.secret_authentication_tokens)
    if not validator.validate(request):
        return jsonify({
            "type": "error",
            "error": { "type": "authentication_error", "message": "Invalid API Key provided." }
        }), 401

    payload = request.json
    model = payload.get("model")
    if not model:
        return jsonify({"type": "error", "error": {"type": "invalid_request_error", "message": "Missing 'model' parameter"}}), 400

    is_stream = payload.get("stream", False)
    logging.info(f"Claude API request for model: {model}, Streaming: {is_stream}")

    try:
        base_url, subaccount_name, resource_group, model = load_balance_url(model)
        token_manager = TokenManager(proxy_config.subaccounts[subaccount_name])
        subaccount_token = token_manager.get_token()

        # Convert incoming Claude payload to the format expected by the backend model
        if Detector.is_gemini_model(model):
            backend_payload = Converters.convert_claude_request_to_gemini(payload)
            endpoint_path = f"/models/{model}:streamGenerateContent" if is_stream else f"/models/{model}:generateContent"
        elif Detector.is_claude_model(model):
            backend_payload = Converters.convert_claude_request_for_bedrock(payload)
            if is_stream:
                endpoint_path = "/converse-stream" if Detector.is_claude_37_or_4(model) else "/invoke-with-response-stream"
            else:
                endpoint_path = "/converse" if Detector.is_claude_37_or_4(model) else "/invoke"
        else:  # Assume OpenAI-compatible
            backend_payload = Detector.convert_claude_request_to_openai(payload)
            api_version = "2024-12-01-preview" if any(m in model for m in ["o3", "o4-mini", "o3-mini"]) else "2023-05-15"
            endpoint_path = f"/chat/completions?api-version={api_version}"

        endpoint_url = f"{base_url.rstrip('/')}{endpoint_path}"

        service_key = proxy_config.subaccounts[subaccount_name].service_key
        headers = {
            "AI-Resource-Group": resource_group,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {subaccount_token}",
            "AI-Tenant-Id": service_key.identityzoneid
        }

        # Handle anthropic-specific headers
        for h in ['anthropic-version', 'anthropic-beta']:
            if h in request.headers:
                headers[h] = request.headers[h]
        
        # Add default anthropic-beta header for Claude streaming if not already present
        if Detector.is_claude_model(model) and is_stream:
            existing_beta = request.headers.get('anthropic-beta', '')
            if 'fine-grained-tool-streaming-2025-05-14' not in existing_beta:
                if existing_beta:
                    # Append to existing anthropic-beta header
                    headers['anthropic-beta'] = f"{existing_beta},fine-grained-tool-streaming-2025-05-14"
                else:
                    # Set new anthropic-beta header
                    headers['anthropic-beta'] = 'fine-grained-tool-streaming-2025-05-14'

        logging.info(f"Forwarding converted request to {endpoint_url} for subAccount '{subaccount_name}'")

        if not is_stream:
            backend_response = requests.post(endpoint_url, headers=headers, json=backend_payload, timeout=600)
            backend_response.raise_for_status()
            backend_json = backend_response.json()

            if Detector.is_gemini_model(model):
                final_response = Converters.convert_gemini_response_to_claude(backend_json, model)
            elif Detector.is_claude_model(model):
                final_response = backend_json
            else:
                final_response = Converters.convert_openai_response_to_claude(backend_json)

            
            # Log the response for debug purposes
            logging.info(f"Final response to client: {json.dumps(final_response, indent=2)}")


            return jsonify(final_response), backend_response.status_code
        else:
            return Response(
                stream_with_context(generate_claude_streaming_response(
                    endpoint_url, headers, backend_payload, model, subaccount_name
                )),
                content_type='text/event-stream'
            )

    except ValueError as err:
        logging.error(f"Value error during Claude request handling: {err}")
        return jsonify({"type": "error", "error": {"type": "invalid_request_error", "message": str(err)}}), 400
    except requests.exceptions.HTTPError as err:
        logging.error(f"HTTP error in Claude request: {err}")
        try:
            return jsonify(err.response.json()), err.response.status_code
        except:
            return jsonify({"error": str(err)}), err.response.status_code if err.response else 500
    except Exception as err:
        logging.error(f"Unexpected error during Claude request handling: {err}", exc_info=True)
        return jsonify({"type": "error", "error": {"type": "api_error", "message": "An unexpected error occurred."}}), 500


def handle_non_streaming_request(url, headers, payload, model, subaccount_name):
    """Handle non-streaming request to backend API.
    
    Args:
        url: Backend API endpoint URL
        headers: Request headers
        payload: Request payload
        model: Model name
        subaccount_name: Name of the selected subAccount
    
    Returns:
        Flask response with the API result
    """
    try:
        # Log the raw request body and payload being forwarded
        logging.info(f"Raw request received (non-streaming): {json.dumps(request.json, indent=2)}")
        logging.info(f"Forwarding payload to API (non-streaming): {json.dumps(payload, indent=2)}")
        
        # Make request to backend API
        response = requests.post(url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        logging.info(f"Non-streaming request succeeded for model '{model}' using subAccount '{subaccount_name}'")
        
        # Process response based on model type
        try:
            response_data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Failed to parse JSON response from backend API: {e}")
            logging.error(f"Response text: {response.text}")
            logging.error(f"Response headers: {dict(response.headers)}")
            return jsonify({
                "error": "Invalid JSON response from backend API",
                "details": str(e),
                "response_text": response.text
            }), 500
        
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
        ip_address = request.remote_addr or request.headers.get("X-Forwarded-For", "unknown_ip")
        token_logger.info(f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                          f"PromptTokens: {prompt_tokens}, CompletionTokens: {completion_tokens}, TotalTokens: {total_tokens}")
        
        return jsonify(final_response), 200
    
    except requests.exceptions.HTTPError as err:
        logging.error(f"HTTP error in non-streaming request: {err}")
        if err.response:
            logging.error(f"Error response status: {err.response.status_code}")
            logging.error(f"Error response headers: {dict(err.response.headers)}")
            logging.error(f"Error response body: {err.response.text}")
            try:
                error_data = err.response.json()
                logging.error(f"Error response JSON: {json.dumps(error_data, indent=2)}")
                return jsonify(error_data), err.response.status_code
            except json.JSONDecodeError:
                return jsonify({"error": err.response.text}), err.response.status_code
        return jsonify({"error": str(err)}), 500
    
    except Exception as err:
        logging.error(f"Error in non-streaming request: {err}", exc_info=True)
        return jsonify({"error": str(err)}), 500


def generate_streaming_response(url, headers, payload, model, subaccount_name):
    """Generate streaming response from backend API.
    
    Args:
        url: Backend API endpoint URL
        headers: Request headers
        payload: Request payload
        model: Model name
        subaccount_name: Name of the selected subAccount
    
    Yields:
        SSE formatted response chunks
    """
    # Log the raw request body and payload being forwarded
    logging.info(f"Raw request received (streaming): {json.dumps(request.json, indent=2)}")
    logging.info(f"Forwarding payload to API (streaming): {json.dumps(payload, indent=2)}")
    
    buffer = ""
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    claude_metadata = {}  # For Claude 3.7 metadata
    chunk = None  # Initialize chunk variable to avoid reference errors
    
    # Make streaming request to backend
    with requests.post(url, headers=headers, json=payload, stream=True, timeout=600) as response:
        try:
            response.raise_for_status()
            
            # --- Claude 3.7/4 Streaming Logic ---
            if Detector.is_claude_model(model) and Detector.is_claude_37_or_4(model):
                logging.info(f"Using Claude 3.7/4 streaming for subAccount '{subaccount_name}'")
                for line_bytes in response.iter_lines():
                    if line_bytes:
                        line = line_bytes.decode('utf-8')
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            # logging.info(f"Raw data chunk from Claude API: {line_content}")
                            try:
                                line_content = ast.literal_eval(line_content)
                                line_content = json.dumps(line_content)
                                claude_dict_chunk = json.loads(line_content)

                                # Check if this is a metadata chunk by looking for 'metadata' key directly
                                if "metadata" in claude_dict_chunk:
                                    claude_metadata = claude_dict_chunk.get("metadata", {})
                                    logging.info(f"Found metadata chunk from '{subaccount_name}': {claude_metadata}")
                                    # Extract token counts immediately
                                    if isinstance(claude_metadata.get("usage"), dict):
                                        total_tokens = claude_metadata["usage"].get("totalTokens", 0)
                                        prompt_tokens = claude_metadata["usage"].get("inputTokens", 0)
                                        completion_tokens = claude_metadata["usage"].get("outputTokens", 0)
                                        logging.info(f"Extracted token usage from metadata: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                                    # Don't process this chunk further, just continue to next
                                    continue
                                
                                # Convert chunk to OpenAI format
                                openai_sse_chunk_str = Converters.convert_claude37_chunk_to_openai(claude_dict_chunk, model)
                                if openai_sse_chunk_str:
                                    yield openai_sse_chunk_str
                            except Exception as e:
                                logging.error(f"Error processing Claude 3.7 chunk from '{subaccount_name}': {e}", exc_info=True)
                                error_payload = {
                                    "id": f"chatcmpl-error-{random.randint(10000, 99999)}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": f"[PROXY ERROR: Failed to process upstream data]"},
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"{json.dumps(error_payload)}\n\n"
                
                # Send final chunk with usage information before [DONE]
                if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                    final_usage_chunk = {
                        "id": f"chatcmpl-claude37-{random.randint(10000, 99999)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": None
                        }],
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens
                        }
                    }
                    final_usage_chunk_str = f"data: {json.dumps(final_usage_chunk)}\n\n"
                    logging.info(f"Sending final usage chunk with SSE format: {final_usage_chunk_str[:200]}...")
                    yield final_usage_chunk_str
                    logging.info(f"Sent final usage chunk: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                    
                    # Log token usage
                    user_id = request.headers.get("Authorization", "unknown")
                    if user_id and len(user_id) > 20:
                        user_id = f"{user_id[:20]}..."
                    ip_address = request.remote_addr or request.headers.get("X-Forwarded-For", "unknown_ip")
                    token_logger.info(f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                                     f"PromptTokens: {prompt_tokens}, CompletionTokens: {completion_tokens}, TotalTokens: {total_tokens} (Streaming)")
            
            # --- Gemini Streaming Logic ---
            elif Detector.is_gemini_model(model):
                logging.info(f"Using Gemini streaming for subAccount '{subaccount_name}'")
                for line_bytes in response.iter_lines():
                    if line_bytes:
                        line = line_bytes.decode('utf-8')
                        logging.info(f"Gemini raw line received: {line}")
                        
                        # Process Gemini streaming lines
                        line_content = ""
                        if line.startswith("data: "):
                            line_content = line.replace("data: ", "").strip()
                            logging.info(f"Gemini data line content: {line_content}")
                        elif line.strip():
                            # Handle lines without "" prefix
                            line_content = line.strip()
                            logging.info(f"Gemini line content (no prefix): {line_content}")
                        
                        if line_content and line_content != "[DONE]":
                            try:
                                gemini_chunk = json.loads(line_content)
                                logging.info(f"Gemini parsed chunk: {json.dumps(gemini_chunk, indent=2)}")
                                
                                # Convert chunk to OpenAI format
                                openai_sse_chunk_str = Converters.convert_gemini_chunk_to_openai(gemini_chunk, model)
                                if openai_sse_chunk_str:
                                    logging.info(f"Gemini converted to OpenAI chunk: {openai_sse_chunk_str}")
                                    yield openai_sse_chunk_str
                                else:
                                    logging.info(f"Gemini chunk conversion returned None")
                                
                                # Extract token usage from usageMetadata if available
                                if "usageMetadata" in gemini_chunk:
                                    usage_metadata = gemini_chunk["usageMetadata"]
                                    total_tokens = usage_metadata.get("totalTokenCount", 0)
                                    prompt_tokens = usage_metadata.get("promptTokenCount", 0)
                                    completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
                                    logging.info(f"Gemini token usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                                    
                            except json.JSONDecodeError as e:
                                logging.error(f"Error parsing Gemini chunk from '{subaccount_name}': {e}")
                                logging.error(f"Problematic line content: {line_content}")
                                continue
                            except Exception as e:
                                logging.error(f"Error processing Gemini chunk from '{subaccount_name}': {e}", exc_info=True)
                                logging.error(f"Problematic chunk: {gemini_chunk if 'gemini_chunk' in locals() else 'Failed to parse'}")
                                error_payload = {
                                    "id": f"chatcmpl-error-{random.randint(10000, 99999)}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": f"[PROXY ERROR: Failed to process upstream data]"},
                                        "finish_reason": "stop"
                                    }]
                                }
                                yield f"{json.dumps(error_payload)}\n\n"

                # Send final chunk with usage information before [DONE] for Gemini
                if total_tokens > 0 or prompt_tokens > 0 or completion_tokens > 0:
                    final_usage_chunk = {
                        "id": f"chatcmpl-gemini-{random.randint(10000, 99999)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": None
                        }],
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens
                        }
                    }
                    final_usage_chunk_str = f"{json.dumps(final_usage_chunk)}\n\n"
                    logging.info(f"Sending final Gemini usage chunk with SSE format: {final_usage_chunk_str[:200]}...")
                    yield final_usage_chunk_str
                    logging.info(f"Sent final Gemini usage chunk: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                    
                    # Log token usage
                    user_id = request.headers.get("Authorization", "unknown")
                    if user_id and len(user_id) > 20:
                        user_id = f"{user_id[:20]}..."
                    ip_address = request.remote_addr or request.headers.get("X-Forwarded-For", "unknown_ip")
                    token_logger.info(f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                                     f"PromptTokens: {prompt_tokens}, CompletionTokens: {completion_tokens}, TotalTokens: {total_tokens} (Streaming)")
            
            # --- Other Models (including older Claude) ---
            else:
                for chunk in response.iter_content(chunk_size=128):
                    if chunk:
                        if Detector.is_claude_model(model):  # Older Claude
                            buffer += chunk.decode('utf-8')
                            while "data: " in buffer:
                                try:
                                    start = buffer.index("data: ") + len("data: ")
                                    end = buffer.index("\n\n", start)
                                    json_chunk_str = buffer[start:end].strip()
                                    buffer = buffer[end + 2:]
                                    
                                    # Convert Claude chunk to OpenAI format
                                    openai_sse_chunk_str = Converters.convert_claude_chunk_to_openai(json_chunk_str, model)
                                    yield openai_sse_chunk_str.encode('utf-8')
                                    
                                    # Parse token usage if available
                                    try:
                                        claude_data = json.loads(json_chunk_str)
                                        if "usage" in claude_data:
                                            prompt_tokens = claude_data["usage"].get("input_tokens", 0)
                                            completion_tokens = claude_data["usage"].get("output_tokens", 0)
                                            total_tokens = prompt_tokens + completion_tokens
                                    except json.JSONDecodeError:
                                        pass
                                except ValueError:
                                    break  # Not enough data in buffer
                                except Exception as e:
                                    logging.error(f"Error processing claude chunk: {e}", exc_info=True)
                                    break
                        else:  # OpenAI-like models
                            yield chunk
                            try:
                                # Try to extract token counts from final chunk
                                if chunk:
                                    chunk_text = chunk.decode('utf-8')
                                    if '"finish_reason":' in chunk_text:
                                        for line in chunk_text.strip().split('\n'):
                                            if line.startswith("data: ") and line[6:].strip() != "[DONE]":
                                                try:
                                                    data = json.loads(line[6:])
                                                    if "usage" in data:
                                                        total_tokens = data["usage"].get("total_tokens", 0)
                                                        prompt_tokens = data["usage"].get("prompt_tokens", 0)
                                                        completion_tokens = data["usage"].get("completion_tokens", 0)
                                                except json.JSONDecodeError:
                                                    pass
                            except Exception:
                                pass
            
            # Log token usage at the end of the stream (only for non-Claude 3.7/4 models)
            # Claude 3.7/4 models already log their token usage after sending the final usage chunk
            if not (Detector.is_claude_model(model) and Detector.is_claude_37_or_4(model)):
                user_id = request.headers.get("Authorization", "unknown")
                if user_id and len(user_id) > 20:
                    user_id = f"{user_id[:20]}..."
                ip_address = request.remote_addr or request.headers.get("X-Forwarded-For", "unknown_ip")
                
                # Log with subAccount information
                token_logger.info(f"User: {user_id}, IP: {ip_address}, Model: {model}, SubAccount: {subaccount_name}, "
                                 f"PromptTokens: {prompt_tokens if 'prompt_tokens' in locals() else 0}, "
                                 f"CompletionTokens: {completion_tokens if 'completion_tokens' in locals() else 0}, "
                                 f"TotalTokens: {total_tokens} (Streaming)")
            
            # Standard stream end
            yield "data: [DONE]\n\n"
            
        except requests.exceptions.HTTPError as err:
            logging.error(f"HTTP Error in streaming response from '{subaccount_name}': {err}")
            if hasattr(err, 'response') and err.response is not None:
                logging.error(f"Error response status: {err.response.status_code}")
                logging.error(f"Error response headers: {dict(err.response.headers)}")
                try:
                    error_content = err.response.text
                    logging.error(f"Error response body: {error_content}")
                    # Try to parse as JSON for better formatting
                    try:
                        error_json = err.response.json()
                        logging.error(f"Error response JSON: {json.dumps(error_json, indent=2)}")
                    except json.JSONDecodeError:
                        pass
                except Exception as e:
                    logging.error(f"Could not read error response content: {e}")
            
            error_payload = {
                "id": f"error-{random.randint(10000, 99999)}",
                "object": "error",
                "created": int(time.time()),
                "model": model,
                "error": {
                    "message": str(err),
                    "type": "http_error",
                    "code": err.response.status_code if hasattr(err, 'response') and err.response else 500,
                    "subaccount": subaccount_name
                }
            }
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as err:
            logging.error(f"Error in streaming response from '{subaccount_name}': {err}", exc_info=True)
            error_payload = {
                "id": f"error-{random.randint(10000, 99999)}",
                "object": "error",
                "created": int(time.time()),
                "model": model,
                "error": {
                    "message": str(err),
                    "type": "proxy_error",
                    "code": 500,
                    "subaccount": subaccount_name
                }
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
    logging.info(f"Starting Claude streaming response for model '{model}' using subAccount '{subaccount_name}'")
    logging.debug(f"Forwarding payload to API (Claude streaming): {json.dumps(payload, indent=2)}")
    logging.debug(f"Request URL: {url}")
    logging.debug(f"Request headers: {headers}")

    # If the backend is already a Claude model, we need to convert the response format.
    if Detector.is_claude_model(model):
        logging.info(f"Backend is Claude model, converting response format for '{model}'")
        try:
            with requests.post(url, headers=headers, json=payload, stream=True, timeout=600) as response:
                response.raise_for_status()
                logging.debug(f"Claude backend response status: {response.status_code}")
                
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
                        "usage": {"input_tokens": 0, "output_tokens": 0}
                    }
                }
                message_start_event = f"event: message_start\ndata: {json.dumps(message_start_data)}\n\n"
                yield message_start_event.encode('utf-8')

                # Send content_block_start event
                content_block_start_data = {
                    "type": "content_block_start", 
                    "index": 0, 
                    "content_block": {"type": "text", "text": ""}
                }
                content_block_start_event = f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
                yield content_block_start_event.encode('utf-8')
                
                chunk_count = 0
                stop_reason = None
                
                for line in response.iter_lines():
                    chunk_count += 1
                    if not line:
                        continue
                        
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    logging.debug(f"Claude backend chunk {chunk_count}: {line_str}")
                    
                    if line_str.startswith('data: '):
                        data_content = line_str[6:].strip()  # Remove 'data: ' prefix
                        
                        # Handle different data formats
                        if data_content == '[DONE]':
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
                            if 'contentBlockDelta' in parsed_data:
                                # Extract text from the delta and format it the same way as OpenAI conversion
                                text_content = parsed_data['contentBlockDelta']['delta'].get('text', '')
                                if text_content:
                                    delta_data = {
                                        "type": "content_block_delta",
                                        "index": 0,
                                        "delta": {"type": "text_delta", "text": text_content}
                                    }
                                    delta_event = f"event: content_block_delta\ndata: {json.dumps(delta_data)}\n\n"
                                    yield delta_event.encode('utf-8')
                                
                            elif 'contentBlockStop' in parsed_data:
                                content_block_stop_data = {
                                    "type": "content_block_stop",
                                    "index": parsed_data['contentBlockStop'].get('contentBlockIndex', 0)
                                }
                                content_block_stop_event = f"event: content_block_stop\ndata: {json.dumps(content_block_stop_data)}\n\n"
                                yield content_block_stop_event.encode('utf-8')
                                
                            elif 'messageStop' in parsed_data:
                                stop_reason = parsed_data['messageStop'].get('stopReason', 'end_turn')
                                
                            elif 'metadata' in parsed_data:
                                # Extract token usage information
                                usage_info = parsed_data.get('metadata', {}).get('usage', {})
                                message_delta_data = {
                                    "type": "message_delta",
                                    "delta": {"stop_reason": stop_reason or "end_turn", "stop_sequence": None},
                                    "usage": {"output_tokens": usage_info.get('outputTokens', 0)}
                                }
                                message_delta_event = f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
                                yield message_delta_event.encode('utf-8')
                                
                                message_stop_event = f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
                                yield message_stop_event.encode('utf-8')
                                
                        except (json.JSONDecodeError, ValueError, SyntaxError) as e:
                            logging.warning(f"Could not parse Claude backend data: {data_content}, error: {e}")
                            continue
                
                logging.info(f"Claude backend conversion completed with {chunk_count} chunks")
        except Exception as e:
            logging.error(f"Error in Claude backend conversion for '{model}': {e}", exc_info=True)
            raise
        return

    # For other models, we need to convert the stream to Claude's event format.
    logging.info(f"Converting non-Claude model '{model}' stream to Claude format")
    
    # 1. Send message_start event
    message_start_data = {
        "type": "message_start",
        "message": {
            "id": f"msg_{random.randint(10000, 99999)}", "type": "message", "role": "assistant",
            "content": [], "model": model, "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0}
        }
    }
    message_start_event = f"event: message_start\ndata: {json.dumps(message_start_data)}\n\n"
    logging.debug(f"Sending message_start event: {message_start_event}")
    yield message_start_event.encode('utf-8')

    # 2. Send content_block_start event
    content_block_start_data = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
    content_block_start_event = f"event: content_block_start\ndata: {json.dumps(content_block_start_data)}\n\n"
    logging.debug(f"Sending content_block_start event: {content_block_start_event}")
    yield content_block_start_event.encode('utf-8')

    stop_reason = None
    chunk_count = 0
    delta_count = 0

    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=600) as response:
            response.raise_for_status()
            logging.debug(f"Backend response status: {response.status_code}")
            logging.debug(f"Backend response headers: {dict(response.headers)}")

            # 3. Iterate and yield content_block_delta events
            for line in response.iter_lines():
                chunk_count += 1
                logging.debug(f"Processing backend chunk {chunk_count}: {line}")
                
                if not line or not line.strip().startswith(b'data:'):
                    logging.debug(f"Skipping non-data line {chunk_count}: {line}")
                    continue

                line_str = line.decode('utf-8', errors='ignore')[5:].strip()
                logging.debug(f"Extracted line content: {line_str}")
                
                if line_str == "[DONE]":
                    logging.info(f"Received [DONE] signal at chunk {chunk_count}")
                    break

                try:
                    backend_chunk = json.loads(line_str)
                    logging.debug(f"Parsed backend chunk: {json.dumps(backend_chunk, indent=2)}")

                    claude_delta = None
                    if Detector.is_gemini_model(model):
                        logging.debug(f"Converting Gemini chunk to Claude delta")
                        claude_delta = Converters.convert_gemini_chunk_to_claude_delta(backend_chunk)
                        if not stop_reason: 
                            stop_reason = get_claude_stop_reason_from_gemini_chunk(backend_chunk)
                            if stop_reason:
                                logging.debug(f"Extracted stop reason from Gemini: {stop_reason}")
                    else:  # Assume OpenAI-compatible
                        logging.debug(f"Converting OpenAI chunk to Claude delta")
                        claude_delta = Converters.convert_openai_chunk_to_claude_delta(backend_chunk)
                        if not stop_reason: 
                            stop_reason = get_claude_stop_reason_from_openai_chunk(backend_chunk)
                            if stop_reason:
                                logging.debug(f"Extracted stop reason from OpenAI: {stop_reason}")

                    if claude_delta:
                        delta_count += 1
                        delta_event = f"event: content_block_delta\ndata: {json.dumps(claude_delta)}\n\n"
                        logging.debug(f"Sending content_block_delta {delta_count}: {delta_event}")
                        yield delta_event.encode('utf-8')
                    else:
                        logging.debug(f"No delta extracted from chunk {chunk_count}")

                except json.JSONDecodeError as e:
                    logging.warning(f"Could not decode JSON from stream chunk {chunk_count}: {line_str}, error: {e}")
                    continue
                except Exception as e:
                    logging.error(f"Error processing chunk {chunk_count}: {e}", exc_info=True)
                    continue

            logging.info(f"Processed {chunk_count} chunks, generated {delta_count} deltas")

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error in Claude streaming conversion for '{model}': {e}", exc_info=True)
        if hasattr(e, 'response') and e.response:
            logging.error(f"Error response status: {e.response.status_code}")
            logging.error(f"Error response body: {e.response.text}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error in Claude streaming conversion for '{model}': {e}", exc_info=True)
        raise

    # 4. Send stop events
    logging.debug(f"Sending stop events with stop_reason: {stop_reason}")
    
    content_block_stop_event = f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    logging.debug(f"Sending content_block_stop event: {content_block_stop_event}")
    yield content_block_stop_event.encode('utf-8')

    message_delta_data = {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason or "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 0}  # Token usage is not available in most streams
    }
    message_delta_event = f"event: message_delta\ndata: {json.dumps(message_delta_data)}\n\n"
    logging.debug(f"Sending message_delta event: {message_delta_event}")
    yield message_delta_event.encode('utf-8')

    message_stop_event = f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"
    logging.debug(f"Sending message_stop event: {message_stop_event}")
    yield message_stop_event.encode('utf-8')
    
    logging.info(f"Claude streaming response completed for model '{model}' with {delta_count} content deltas")


if __name__ == '__main__':
    args = parse_arguments()
    
    # Setup logging using the new modular function
    setup_logging(debug=args.debug)
    
    logging.info(f"Loading configuration from: {args.config}")
    config = load_config(args.config)
    
    # Check if this is the new format with subAccounts
    if isinstance(config, ProxyConfig):
        proxy_config = config
        # Initialize all subaccounts and build model mappings
        proxy_config.initialize()
        
        # Get server configuration
        host = proxy_config.host
        port = proxy_config.port
        
        logging.info(f"Loaded multi-subAccount configuration with {len(proxy_config.subaccounts)} subAccounts")
        logging.info(f"Available subAccounts: {', '.join(proxy_config.subaccounts.keys())}")
        logging.info(f"Available models: {', '.join(proxy_config.model_to_subaccounts.keys())}")
    else:
        # Legacy configuration support
        logging.warning("Using legacy configuration format (single subAccount)")
        
        # Initialize global variables for backward compatibility
        service_key_json = config['service_key_json']
        model_deployment_urls = config['deployment_models']
        secret_authentication_tokens = config['secret_authentication_tokens']
        resource_group = config['resource_group']
        
        # Normalize model_deployment_urls keys
        normalized_model_deployment_urls = {
            key.replace("anthropic--", ""): value for key, value in model_deployment_urls.items()
        }

        # Load service key
        service_key = load_config(service_key_json)

        host = config.get('host', '127.0.0.1')  # Use host from config, default to 127.0.0.1 if not specified
        port = config.get('port', 3001)  # Use port from config, default to 3001 if not specified

        # Initialize the proxy_config for compatibility with new code
        proxy_config.secret_authentication_tokens = secret_authentication_tokens
        proxy_config.host = host
        proxy_config.port = port
        
        # Create a default subAccount
        default_subaccount = SubAccountConfig(
            name="default",
            resource_group=resource_group,
            service_key_json=service_key_json,
            deployment_models=model_deployment_urls
        )
        
        # Add service key
        default_subaccount.service_key = ServiceKey(
            clientid=service_key.get('clientid', ''),
            clientsecret=service_key.get('clientsecret', ''),
            url=service_key.get('url', ''),
            identityzoneid=service_key.get('identityzoneid', '')
        )
        
        # Normalize model names
        default_subaccount.normalized_models = normalized_model_deployment_urls
        
        # Add to proxy_config
        proxy_config.subaccounts["default"] = default_subaccount
        
        # Build model mappings
        proxy_config.build_model_mapping()

    logging.info(f"Starting proxy server on host {host} and port {port}...")
    logging.info(f"API Host: http://{host}:{port}/v1")
    logging.info(f"Available endpoints:")
    logging.info(f"  - OpenAI Compatible API: http://{host}:{port}/v1/chat/completions")
    logging.info(f"  - Anthropic Claude API: http://{host}:{port}/v1/messages")
    logging.info(f"  - Models Listing: http://{host}:{port}/v1/models")
    logging.info(f"  - Embeddings API: http://{host}:{port}/v1/embeddings")
    app.run(host=host, port=port, debug=args.debug)
