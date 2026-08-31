from logging import Logger

import requests  # noqa: F401 - used by tests via proxy_server.requests.post
from botocore.exceptions import ClientError  # noqa: F401 - used in bedrock_handler

from saip.auth import RequestValidator  # noqa: F401 - re-exported for tests
from saip.auth.token_manager import TokenManager  # noqa: F401 - used by tests via proxy_server.TokenManager
from saip.cli import parse_arguments  # noqa: F401 - re-exported for tests
from saip.config import ProxyConfig, ProxyGlobalContext
from saip.handlers.model_handlers import (
    handle_claude_request as _handle_claude_request,
    handle_default_request as _handle_default_request,
    handle_gemini_request as _handle_gemini_request,
)
from saip.handlers.streaming_handler import (
    get_claude_stop_reason_from_gemini_chunk,  # noqa: F401 - re-exported for tests
    get_claude_stop_reason_from_openai_chunk,  # noqa: F401 - re-exported for tests
    parse_sse_response_to_claude_json as _parse_sse_response_to_claude_json,
)
from saip.load_balancer import (
    load_balance_url as _load_balance_url,
    resolve_model_name as _resolve_model_name,
)
from saip.utils.logging_utils import get_server_logger, get_transport_logger
from saip.utils.sdk_pool import get_bedrock_client  # noqa: F401 - re-exported for downstream use

# Initialize token logger (will be configured on first use)
logger: Logger = get_server_logger(__name__)
transport_logger: Logger = get_transport_logger(__name__)
token_usage_logger: Logger = get_server_logger("token_usage")

ctx: ProxyGlobalContext

API_VERSION_2023_05_15 = "2023-05-15"
API_VERSION_2024_12_01_PREVIEW = "2024-12-01-preview"
API_VERSION_BEDROCK_2023_05_31 = "bedrock-2023-05-31"

DEFAULT_CLAUDE_MODEL: str = "anthropic--claude-4.6-sonnet"
DEFAULT_GEMINI_MODEL: str = "gemini-2.5-pro"
DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
DEFAULT_GPT_MODEL = "gpt-4.1"

# Retry configuration - now unified in utils/retry.py

"""SAP API Reference are documented at https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/example-payloads-for-inferencing-third-party-models"""

# Global configuration
proxy_config: ProxyConfig = ProxyConfig()


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


def resolve_model_name(model_name):
    """Resolve model name with backward-compatible wrapper."""
    return _resolve_model_name(model_name, proxy_config)


def load_balance_url(model):
    """Load balance URL with backward-compatible wrapper.

    This wrapper uses the global proxy_config.
    For new code, import from saip.load_balancer and pass proxy_config explicitly.
    """
    return _load_balance_url(model, proxy_config)


def parse_sse_response_to_claude_json(response_text):
    """Parse SSE response to Claude JSON - backward-compatible wrapper."""
    return _parse_sse_response_to_claude_json(response_text)


def handle_claude_request(payload, model="3.5-sonnet"):
    """Handle Claude model request with multi-subAccount support.

    This is a backward-compatible wrapper that uses the global proxy_config.
    For new code, import from saip.handlers.model_handlers and pass proxy_config explicitly.
    """
    return _handle_claude_request(payload, model, proxy_config)


def handle_gemini_request(payload, model="gemini-2.5-pro"):
    """Handle Gemini model request with multi-subAccount support.

    This is a backward-compatible wrapper that uses the global proxy_config.
    For new code, import from saip.handlers.model_handlers and pass proxy_config explicitly.
    """
    return _handle_gemini_request(payload, model, proxy_config)


def handle_default_request(payload, model=DEFAULT_GPT_MODEL):
    """Handle default (non-Claude, non-Gemini) model request with multi-subAccount support.

    This is a backward-compatible wrapper that uses the global proxy_config.
    For new code, import from saip.handlers.model_handlers and pass proxy_config explicitly.
    """
    return _handle_default_request(payload, model, proxy_config)


# All endpoints have been migrated to FastAPI routers (routers/).


def main() -> None:
    """Deprecated entry point (delegates to FastAPI)."""
    logger.warning(
        "proxy_server.py entry point is deprecated; delegating to FastAPI app"
    )
    from saip.main import main as fastapi_main

    fastapi_main()


if __name__ == "__main__":
    main()
