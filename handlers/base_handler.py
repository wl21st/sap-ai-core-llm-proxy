"""Default model handler implementation."""

from __future__ import annotations

from dataclasses import dataclass

from converters.mappings import API_VERSION_2023_05_15, API_VERSION_2024_12_01_PREVIEW
from load_balancer import load_balance_url
from utils.logging_utils import get_server_logger

logger = get_server_logger(__name__)


@dataclass
class DefaultHandler:
    """Fallback handler for OpenAI-compatible models."""

    def handle_request(self, request: dict, config, ctx):
        payload = request
        model = payload.get("model")
        selected_url, subaccount_name, _, model = load_balance_url(model, config)

        if any(m in model for m in ["o3", "o4-mini", "o3-mini", "gpt-5"]):
            api_version = API_VERSION_2024_12_01_PREVIEW
            modified_payload = payload.copy()
            if "temperature" in modified_payload:
                logger.info("Removing 'temperature' parameter for o3-mini model.")
                del modified_payload["temperature"]
        else:
            api_version = API_VERSION_2023_05_15
            modified_payload = payload

        endpoint_url = (
            f"{selected_url.rstrip('/')}/chat/completions?api-version={api_version}"
        )

        return endpoint_url, modified_payload, subaccount_name

    def handle_streaming(self, request: dict, config, ctx):
        return self.handle_request(request, config, ctx)

    def get_converter(self):
        return None
